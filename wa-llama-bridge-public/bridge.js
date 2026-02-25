#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { setTimeout as sleep } from "node:timers/promises";
import dotenv from "dotenv";
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  jidNormalizedUser,
  useMultiFileAuthState
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import pino from "pino";
import qrcode from "qrcode-terminal";

dotenv.config();

const STARTED_AT_MS = Date.now();
const ROOT_DIR = process.cwd();
const DATA_DIR = path.join(ROOT_DIR, "data");
const AUTH_DIR = path.join(DATA_DIR, "auth");
const HISTORY_FILE = path.join(DATA_DIR, "history.json");

const YES = new Set(["1", "true", "yes", "on"]);

function envString(name, fallback = "") {
  const value = process.env[name];
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

function envBool(name, fallback = false) {
  const raw = process.env[name];
  if (typeof raw !== "string") return fallback;
  return YES.has(raw.trim().toLowerCase());
}

function envInt(name, fallback, min = Number.MIN_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER) {
  const raw = process.env[name];
  if (typeof raw !== "string") return fallback;
  const parsed = Number.parseInt(raw.trim(), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

function envFloat(name, fallback, min = -Infinity, max = Infinity) {
  const raw = process.env[name];
  if (typeof raw !== "string") return fallback;
  const parsed = Number.parseFloat(raw.trim());
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

function normalizePhone(value) {
  return String(value ?? "").replace(/[^\d]/g, "");
}

function normalizeJid(jid) {
  if (!jid) return "";
  try {
    return jidNormalizedUser(jid);
  } catch {
    return String(jid);
  }
}

function jidToPhone(jid) {
  const normalized = normalizeJid(jid);
  const userPart = normalized.split("@")[0] ?? "";
  const withoutDevice = userPart.split(":")[0] ?? userPart;
  return normalizePhone(withoutDevice);
}

function parseAllowFrom(raw) {
  if (!raw) return [];
  return raw
    .split(",")
    .map((v) => normalizePhone(v))
    .filter(Boolean);
}

function isAllowedByList(senderDigits, allowFromDigits) {
  if (allowFromDigits.length === 0) return true;
  if (!senderDigits) return false;
  return allowFromDigits.some((allowed) => {
    if (!allowed) return false;
    return senderDigits === allowed || senderDigits.endsWith(allowed) || allowed.endsWith(senderDigits);
  });
}

function buildChatCompletionsUrl(baseUrl) {
  const cleaned = String(baseUrl ?? "").trim().replace(/\/+$/, "");
  if (!cleaned) return "";
  if (cleaned.endsWith("/v1")) return `${cleaned}/chat/completions`;
  return `${cleaned}/v1/chat/completions`;
}

function extractAssistantText(payload) {
  const choice = payload?.choices?.[0];
  if (!choice || typeof choice !== "object") return "";

  const messageContent = choice?.message?.content;
  if (typeof messageContent === "string") return messageContent.trim();

  if (Array.isArray(messageContent)) {
    const joined = messageContent
      .map((part) => {
        if (!part || typeof part !== "object") return "";
        if (typeof part.text === "string") return part.text;
        if (part.type === "text" && typeof part?.content === "string") return part.content;
        return "";
      })
      .filter(Boolean)
      .join("\n")
      .trim();
    if (joined) return joined;
  }

  if (typeof choice?.text === "string") return choice.text.trim();
  return "";
}

function splitText(text, maxChars) {
  const clean = String(text ?? "").trim();
  if (!clean) return [];
  if (clean.length <= maxChars) return [clean];

  const chunks = [];
  let rest = clean;
  while (rest.length > maxChars) {
    let cut = rest.lastIndexOf("\n", maxChars);
    if (cut < Math.floor(maxChars * 0.4)) cut = rest.lastIndexOf(" ", maxChars);
    if (cut < Math.floor(maxChars * 0.4)) cut = maxChars;
    const piece = rest.slice(0, cut).trim();
    if (piece) chunks.push(piece);
    rest = rest.slice(cut).trim();
  }
  if (rest) chunks.push(rest);
  return chunks;
}

function extractMessageText(message) {
  if (!message || typeof message !== "object") return "";

  const directCandidates = [
    message.conversation,
    message?.extendedTextMessage?.text,
    message?.imageMessage?.caption,
    message?.videoMessage?.caption,
    message?.documentMessage?.caption,
    message?.buttonsResponseMessage?.selectedDisplayText,
    message?.listResponseMessage?.title,
    message?.templateButtonReplyMessage?.selectedDisplayText
  ];
  for (const candidate of directCandidates) {
    if (typeof candidate === "string" && candidate.trim()) return candidate.trim();
  }

  const nestedCandidates = [
    message?.ephemeralMessage?.message,
    message?.viewOnceMessage?.message,
    message?.viewOnceMessageV2?.message,
    message?.viewOnceMessageV2Extension?.message,
    message?.documentWithCaptionMessage?.message,
    message?.editedMessage?.message
  ];
  for (const nested of nestedCandidates) {
    const extracted = extractMessageText(nested);
    if (extracted) return extracted;
  }

  for (const value of Object.values(message)) {
    if (!value || typeof value !== "object") continue;
    if (value?.message) {
      const extracted = extractMessageText(value.message);
      if (extracted) return extracted;
    }
  }

  return "";
}

function messageTimestampToMs(rawTs) {
  if (rawTs == null) return null;
  if (typeof rawTs === "number") return rawTs > 10_000_000_000 ? rawTs : rawTs * 1000;
  if (typeof rawTs === "bigint") return Number(rawTs) * 1000;
  if (typeof rawTs === "object" && typeof rawTs.low === "number") return rawTs.low * 1000;
  return null;
}

const CONFIG = {
  llmBaseUrl: envString("LLM_BASE_URL", "http://127.0.0.1:8080/v1"),
  llmModel: envString("LLM_MODEL"),
  llmApiKey: envString("LLM_API_KEY"),
  fallbackBaseUrl: envString("LLM_FALLBACK_BASE_URL"),
  fallbackModel: envString("LLM_FALLBACK_MODEL"),
  fallbackApiKey: envString("LLM_FALLBACK_API_KEY"),
  systemPromptFile: envString("SYSTEM_PROMPT_FILE"),
  systemPrompt: envString(
    "SYSTEM_PROMPT",
    "Eres mi asistente personal en WhatsApp. Responde breve, clara y util, salvo que te pidan detalle."
  ),
  temperature: envFloat("TEMPERATURE", 0.8, 0, 2),
  maxTokens: envInt("MAX_TOKENS", 500, 1, 8192),
  requestTimeoutMs: envInt("REQUEST_TIMEOUT_MS", 120000, 5000, 600000),
  historyTurns: envInt("HISTORY_TURNS", 8, 0, 64),
  maxHistoryChars: envInt("MAX_HISTORY_CHARS", 12000, 1000, 200000),
  selfChatOnly: envBool("SELF_CHAT_ONLY", true),
  allowGroups: envBool("ALLOW_GROUPS", false),
  allowFromDigits: parseAllowFrom(envString("ALLOW_FROM")),
  ignoreOldMessages: envBool("IGNORE_OLD_MESSAGES", true),
  usePairingCode: envBool("WA_USE_PAIRING_CODE", true),
  pairingPhone: normalizePhone(envString("WA_PAIRING_PHONE")),
  showQr: envBool("WA_SHOW_QR", false),
  replyChunkChars: envInt("WA_REPLY_CHUNK_CHARS", 1400, 400, 5000),
  logLevel: envString("LOG_LEVEL", "info")
};

if (!CONFIG.llmModel) {
  console.error("[wa-bridge] Missing LLM_MODEL in .env");
  process.exit(1);
}

const LLM_ENDPOINTS = [
  {
    name: "primary",
    baseUrl: CONFIG.llmBaseUrl,
    model: CONFIG.llmModel,
    apiKey: CONFIG.llmApiKey
  }
];

if (CONFIG.fallbackBaseUrl && CONFIG.fallbackModel) {
  LLM_ENDPOINTS.push({
    name: "fallback",
    baseUrl: CONFIG.fallbackBaseUrl,
    model: CONFIG.fallbackModel,
    apiKey: CONFIG.fallbackApiKey
  });
}

let selfJid = "";
let shuttingDown = false;
let reconnectTimer = null;
let activeSocket = null;

const log = pino({ level: CONFIG.logLevel });

const sentByBridge = new Map();
const laneByChat = new Map();
const historyByChat = Object.create(null);
let saveTimer = null;

async function loadSystemPromptFromFileIfNeeded() {
  if (!CONFIG.systemPromptFile) return;
  const promptPath = path.isAbsolute(CONFIG.systemPromptFile)
    ? CONFIG.systemPromptFile
    : path.resolve(ROOT_DIR, CONFIG.systemPromptFile);

  try {
    const raw = await fs.readFile(promptPath, "utf8");
    const promptText = raw.trim();
    if (!promptText) {
      log.warn({ promptPath }, "system prompt file is empty; using SYSTEM_PROMPT fallback");
      return;
    }
    CONFIG.systemPrompt = promptText;
    CONFIG.systemPromptFile = promptPath;
    log.info({ promptPath, chars: promptText.length }, "system prompt loaded from file");
  } catch (error) {
    log.error(
      { promptPath, err: String(error) },
      "failed to load system prompt file; using SYSTEM_PROMPT fallback"
    );
  }
}

async function ensureDataDirs() {
  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.mkdir(AUTH_DIR, { recursive: true });
}

async function loadHistory() {
  try {
    const raw = await fs.readFile(HISTORY_FILE, "utf8");
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return;
    for (const [jid, entries] of Object.entries(parsed)) {
      if (!Array.isArray(entries)) continue;
      historyByChat[jid] = entries
        .filter((entry) => entry && typeof entry === "object")
        .map((entry) => ({
          role: entry.role === "assistant" ? "assistant" : "user",
          content: String(entry.content ?? "").trim()
        }))
        .filter((entry) => entry.content.length > 0);
    }
  } catch (error) {
    if (error?.code !== "ENOENT") {
      log.warn({ err: String(error) }, "history file could not be loaded");
    }
  }
}

function scheduleHistorySave() {
  if (saveTimer) return;
  saveTimer = setTimeout(async () => {
    saveTimer = null;
    try {
      await fs.writeFile(HISTORY_FILE, JSON.stringify(historyByChat, null, 2), "utf8");
    } catch (error) {
      log.error({ err: String(error) }, "failed to write history");
    }
  }, 200);
}

async function flushHistorySaveNow() {
  if (saveTimer) {
    clearTimeout(saveTimer);
    saveTimer = null;
  }
  try {
    await fs.writeFile(HISTORY_FILE, JSON.stringify(historyByChat, null, 2), "utf8");
  } catch (error) {
    log.error({ err: String(error) }, "failed to flush history");
  }
}

function getHistory(jid) {
  return historyByChat[jid] ?? [];
}

function trimHistoryEntries(entries) {
  const maxEntries = CONFIG.historyTurns > 0 ? CONFIG.historyTurns * 2 : 0;
  const byTurns = maxEntries > 0 ? entries.slice(-maxEntries) : [];
  if (byTurns.length === 0) return byTurns;

  let used = 0;
  const result = [];
  for (let i = byTurns.length - 1; i >= 0; i -= 1) {
    const entry = byTurns[i];
    const chars = entry.content.length;
    if (result.length > 0 && used + chars > CONFIG.maxHistoryChars) break;
    used += chars;
    result.unshift(entry);
  }
  return result;
}

function appendHistory(jid, role, content) {
  const text = String(content ?? "").trim();
  if (!text) return;
  const current = getHistory(jid);
  current.push({ role, content: text });
  historyByChat[jid] = trimHistoryEntries(current);
  scheduleHistorySave();
}

function resetHistory(jid) {
  delete historyByChat[jid];
  scheduleHistorySave();
}

function rememberSentId(id) {
  if (!id) return;
  sentByBridge.set(id, Date.now());
}

function cleanupSentIds() {
  const now = Date.now();
  for (const [id, ts] of sentByBridge.entries()) {
    if (now - ts > 2 * 60 * 60 * 1000) sentByBridge.delete(id);
  }
}

function queueForChat(chatKey, task) {
  const previous = laneByChat.get(chatKey) ?? Promise.resolve();
  const current = previous
    .then(task, task)
    .catch((error) => {
      log.error({ err: String(error), chatKey }, "lane task failed");
    })
    .finally(() => {
      if (laneByChat.get(chatKey) === current) laneByChat.delete(chatKey);
    });
  laneByChat.set(chatKey, current);
  return current;
}

async function callLlmEndpoint(endpoint, messages) {
  const url = buildChatCompletionsUrl(endpoint.baseUrl);
  if (!url) throw new Error(`invalid base URL for ${endpoint.name}`);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CONFIG.requestTimeoutMs);

  try {
    const headers = { "content-type": "application/json" };
    if (endpoint.apiKey) headers.authorization = `Bearer ${endpoint.apiKey}`;

    const body = {
      model: endpoint.model,
      messages,
      temperature: CONFIG.temperature,
      max_tokens: CONFIG.maxTokens,
      stream: false
    };

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: controller.signal
    });

    const rawText = await response.text();
    if (!response.ok) {
      throw new Error(`${endpoint.name} HTTP ${response.status}: ${rawText.slice(0, 240)}`);
    }

    let payload;
    try {
      payload = JSON.parse(rawText);
    } catch {
      throw new Error(`${endpoint.name} invalid JSON response`);
    }

    const text = extractAssistantText(payload);
    if (!text) throw new Error(`${endpoint.name} returned empty answer`);
    return text;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function callLlmWithFallback(messages) {
  const errors = [];
  for (const endpoint of LLM_ENDPOINTS) {
    try {
      const text = await callLlmEndpoint(endpoint, messages);
      return { text, endpoint };
    } catch (error) {
      errors.push(`${endpoint.name}: ${error?.message ?? String(error)}`);
    }
  }
  throw new Error(`All models failed (${LLM_ENDPOINTS.length}): ${errors.join(" | ")}`);
}

async function sendReply(sock, jid, text, quoted) {
  const chunks = splitText(text, CONFIG.replyChunkChars);
  if (chunks.length === 0) return;

  for (let i = 0; i < chunks.length; i += 1) {
    const chunk = chunks[i];
    const options = i === 0 && quoted ? { quoted } : {};
    const sent = await sock.sendMessage(jid, { text: chunk }, options);
    rememberSentId(sent?.key?.id);
    if (i < chunks.length - 1) await sleep(200);
  }
}

function startTypingLoop(sock, jid) {
  let closed = false;

  const tick = async () => {
    if (closed) return;
    try {
      await sock.presenceSubscribe(jid);
      await sock.sendPresenceUpdate("composing", jid);
    } catch {}
  };

  void tick();
  const timer = setInterval(() => {
    void tick();
  }, 7000);

  return async () => {
    if (closed) return;
    closed = true;
    clearInterval(timer);
    try {
      await sock.sendPresenceUpdate("paused", jid);
    } catch {}
  };
}

function getDisconnectCode(error) {
  if (!error) return null;
  if (typeof error?.output?.statusCode === "number") return error.output.statusCode;
  try {
    const boom = new Boom(error);
    return boom?.output?.statusCode ?? null;
  } catch {
    return null;
  }
}

function isAllowedSender(senderJid) {
  const senderDigits = jidToPhone(senderJid);
  return isAllowedByList(senderDigits, CONFIG.allowFromDigits);
}

async function handleCommand(sock, chatJid, normalizedChatJid, text, quoted) {
  const cmd = text.trim().toLowerCase();

  if (cmd === "/help") {
    await sendReply(
      sock,
      chatJid,
      [
        "Comandos:",
        "/help - ayuda",
        "/reset o /new - limpiar memoria de este chat",
        "/model - modelo activo y fallback",
        "/status - estado rapido"
      ].join("\n"),
      quoted
    );
    return true;
  }

  if (cmd === "/reset" || cmd === "/new") {
    resetHistory(normalizedChatJid);
    await sendReply(sock, chatJid, "Memoria del chat reiniciada.", quoted);
    return true;
  }

  if (cmd === "/model") {
    const lines = [
      `Primary: ${CONFIG.llmModel} @ ${CONFIG.llmBaseUrl}`,
      CONFIG.fallbackModel && CONFIG.fallbackBaseUrl
        ? `Fallback: ${CONFIG.fallbackModel} @ ${CONFIG.fallbackBaseUrl}`
        : "Fallback: (off)"
    ];
    await sendReply(sock, chatJid, lines.join("\n"), quoted);
    return true;
  }

  if (cmd === "/status") {
    const lane = laneByChat.get(normalizedChatJid) ? "busy" : "idle";
    const historyCount = getHistory(normalizedChatJid).length;
    await sendReply(
      sock,
      chatJid,
      `Status: ${lane}\nHistory entries: ${historyCount}\nSelf chat only: ${CONFIG.selfChatOnly}`,
      quoted
    );
    return true;
  }

  return false;
}

async function processIncomingMessage(sock, msg) {
  if (!msg || !msg.key || !msg.message) return;
  cleanupSentIds();

  const chatJid = msg.key.remoteJid ?? "";
  if (!chatJid) return;
  if (chatJid === "status@broadcast") return;

  const normalizedChatJid = normalizeJid(chatJid);
  const isGroup = normalizedChatJid.endsWith("@g.us");
  if (isGroup && !CONFIG.allowGroups) return;

  if (CONFIG.selfChatOnly && selfJid && normalizedChatJid !== selfJid) return;

  if (msg.key.id && sentByBridge.has(msg.key.id)) return;

  const senderJid = msg.key.participant || chatJid;
  if (!isAllowedSender(senderJid)) return;

  const msgTs = messageTimestampToMs(msg.messageTimestamp);
  if (CONFIG.ignoreOldMessages && msgTs && msgTs < STARTED_AT_MS - 60_000) return;

  const text = extractMessageText(msg.message).trim();
  if (!text) return;

  log.info(
    {
      from: senderJid,
      chat: normalizedChatJid,
      length: text.length
    },
    "inbound message"
  );

  await queueForChat(normalizedChatJid, async () => {
    if (await handleCommand(sock, chatJid, normalizedChatJid, text, msg)) return;

    const stopTyping = startTypingLoop(sock, chatJid);
    try {
      const historyEntries = trimHistoryEntries(getHistory(normalizedChatJid));
      const messages = [];
      if (CONFIG.systemPrompt) messages.push({ role: "system", content: CONFIG.systemPrompt });
      for (const entry of historyEntries) {
        messages.push({ role: entry.role, content: entry.content });
      }
      messages.push({ role: "user", content: text });

      const completion = await callLlmWithFallback(messages);
      const answer = completion.text.trim() || "No tengo respuesta ahora.";

      appendHistory(normalizedChatJid, "user", text);
      appendHistory(normalizedChatJid, "assistant", answer);

      await sendReply(sock, chatJid, answer, msg);
      log.info({ endpoint: completion.endpoint.name }, "reply sent");
    } catch (error) {
      const message = error?.message ?? String(error);
      log.error({ err: message }, "reply failed");
      await sendReply(sock, chatJid, `[bridge] Error: ${message}`, msg);
    } finally {
      await stopTyping();
    }
  });
}

async function startBridgeSocket() {
  await ensureDataDirs();
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const versionInfo = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }));

  const sock = makeWASocket({
    auth: state,
    version: versionInfo.version,
    logger: log,
    printQRInTerminal: false,
    syncFullHistory: false,
    markOnlineOnConnect: false,
    browser: ["WA-Llama-Bridge", "Desktop", "1.0.0"]
  });

  activeSocket = sock;
  sock.ev.on("creds.update", saveCreds);

  let pairingRequested = false;

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr && CONFIG.showQr && !CONFIG.usePairingCode) {
      console.log("\n[wa-bridge] Scan this QR in WhatsApp > Linked Devices:\n");
      qrcode.generate(qr, { small: true });
      console.log("");
    }

    if (
      !pairingRequested &&
      CONFIG.usePairingCode &&
      CONFIG.pairingPhone &&
      state?.creds?.registered !== true
    ) {
      pairingRequested = true;
      try {
        const code = await sock.requestPairingCode(CONFIG.pairingPhone);
        console.log(`\n[wa-bridge] Pairing code: ${code}`);
        console.log(
          "[wa-bridge] In WhatsApp: Linked Devices -> Link a device -> Link with phone number -> enter code.\n"
        );
      } catch (error) {
        log.error({ err: String(error) }, "failed to request pairing code");
      }
    }

    if (connection === "open") {
      const rawSelf = sock.user?.id ?? "";
      selfJid = normalizeJid(rawSelf);
      log.info({ selfJid, selfChatOnly: CONFIG.selfChatOnly }, "whatsapp connected");
      return;
    }

    if (connection === "close") {
      const code = getDisconnectCode(lastDisconnect?.error);
      const loggedOut = code === DisconnectReason.loggedOut;
      log.warn({ code, loggedOut }, "whatsapp connection closed");

      if (loggedOut) {
        log.error("logged out: delete data/auth and login again");
        return;
      }

      if (!shuttingDown && !reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          void startBridgeSocket();
        }, 2000);
      }
    }
  });

  sock.ev.on("messages.upsert", ({ messages, type }) => {
    if (type !== "notify") return;
    for (const msg of messages) {
      void processIncomingMessage(sock, msg);
    }
  });
}

async function shutdown(exitCode = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  try {
    await flushHistorySaveNow();
  } catch {}
  try {
    activeSocket?.end?.();
  } catch {}
  process.exit(exitCode);
}

process.on("SIGINT", () => {
  void shutdown(130);
});
process.on("SIGTERM", () => {
  void shutdown(0);
});

async function main() {
  console.log("[wa-bridge] starting");
  console.log(`[wa-bridge] primary model: ${CONFIG.llmModel}`);
  if (CONFIG.fallbackModel && CONFIG.fallbackBaseUrl) {
    console.log(`[wa-bridge] fallback model: ${CONFIG.fallbackModel}`);
  }
  console.log(
    `[wa-bridge] mode: selfChatOnly=${CONFIG.selfChatOnly}, allowGroups=${CONFIG.allowGroups}, usePairingCode=${CONFIG.usePairingCode}`
  );

  await ensureDataDirs();
  await loadSystemPromptFromFileIfNeeded();
  console.log(
    `[wa-bridge] prompt source: ${
      CONFIG.systemPromptFile ? `file ${CONFIG.systemPromptFile}` : "SYSTEM_PROMPT (.env)"
    }`
  );
  await loadHistory();
  await startBridgeSocket();
}

main().catch((error) => {
  console.error(`[wa-bridge] fatal: ${error?.stack ?? String(error)}`);
  process.exit(1);
});
