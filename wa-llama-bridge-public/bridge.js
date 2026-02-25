#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { setTimeout as sleep } from "node:timers/promises";
import dotenv from "dotenv";
import makeWASocket, {
  DisconnectReason,
  downloadMediaMessage,
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
const TMP_DIR = path.join(DATA_DIR, "tmp");
const HISTORY_FILE = path.join(DATA_DIR, "history.json");
const CHAT_SWITCH_FILE = path.join(DATA_DIR, "chat-enabled.json");

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

function parseStringList(raw) {
  if (!raw) return [];
  return raw
    .split(",")
    .map((v) => String(v).trim())
    .filter(Boolean);
}

function resolveMaybePath(rawPath) {
  const value = String(rawPath ?? "").trim();
  if (!value) return "";
  if (path.isAbsolute(value)) return value;
  return path.resolve(ROOT_DIR, value);
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

function buildAudioTranscriptionsUrl(baseUrl) {
  const cleaned = String(baseUrl ?? "").trim().replace(/\/+$/, "");
  if (!cleaned) return "";
  if (cleaned.endsWith("/v1")) return `${cleaned}/audio/transcriptions`;
  return `${cleaned}/v1/audio/transcriptions`;
}

function buildUrlFromInput(rawUrl) {
  try {
    const parsed = new URL(String(rawUrl ?? "").trim());
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    return parsed;
  } catch {
    return null;
  }
}

function sanitizeHtmlToText(html) {
  const source = String(html ?? "");
  if (!source.trim()) return "";
  return source
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<\/(p|div|h1|h2|h3|h4|h5|h6|li|tr|section|article|header|footer)>/gi, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&#39;/gi, "'")
    .replace(/&quot;/gi, "\"")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function extractUrls(text) {
  const matches = String(text ?? "").match(/https?:\/\/[^\s<>"')]+/gi);
  return Array.isArray(matches) ? matches : [];
}

function normalizeMaybeLong(value) {
  if (value == null) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "bigint") return Number(value);
  if (typeof value === "string") {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }
  if (typeof value === "object" && typeof value.low === "number") return value.low;
  return null;
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

function extractCommandName(text) {
  const clean = String(text ?? "").trim();
  if (!clean.startsWith("/")) return "";
  const match = clean.match(/^\/([a-z0-9_-]+)/i);
  if (!match || !match[1]) return "";
  return `/${match[1].toLowerCase()}`;
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

function extractAudioMessage(message) {
  if (!message || typeof message !== "object") return null;
  if (message.audioMessage && typeof message.audioMessage === "object") return message.audioMessage;

  const nestedCandidates = [
    message?.ephemeralMessage?.message,
    message?.viewOnceMessage?.message,
    message?.viewOnceMessageV2?.message,
    message?.viewOnceMessageV2Extension?.message,
    message?.documentWithCaptionMessage?.message,
    message?.editedMessage?.message
  ];
  for (const nested of nestedCandidates) {
    const extracted = extractAudioMessage(nested);
    if (extracted) return extracted;
  }

  for (const value of Object.values(message)) {
    if (!value || typeof value !== "object") continue;
    if (value?.message) {
      const extracted = extractAudioMessage(value.message);
      if (extracted) return extracted;
    }
    const extracted = extractAudioMessage(value);
    if (extracted) return extracted;
  }

  return null;
}

function extractImageMessage(message) {
  if (!message || typeof message !== "object") return null;
  if (message.imageMessage && typeof message.imageMessage === "object") return message.imageMessage;

  const nestedCandidates = [
    message?.ephemeralMessage?.message,
    message?.viewOnceMessage?.message,
    message?.viewOnceMessageV2?.message,
    message?.viewOnceMessageV2Extension?.message,
    message?.documentWithCaptionMessage?.message,
    message?.editedMessage?.message
  ];
  for (const nested of nestedCandidates) {
    const extracted = extractImageMessage(nested);
    if (extracted) return extracted;
  }

  for (const value of Object.values(message)) {
    if (!value || typeof value !== "object") continue;
    if (value?.message) {
      const extracted = extractImageMessage(value.message);
      if (extracted) return extracted;
    }
    const extracted = extractImageMessage(value);
    if (extracted) return extracted;
  }

  return null;
}

async function writeTempBuffer(buffer, extension) {
  const ext = String(extension || "bin").replace(/[^a-z0-9]/gi, "").toLowerCase() || "bin";
  const filename = `${Date.now()}-${randomUUID()}.${ext}`;
  const fullPath = path.join(TMP_DIR, filename);
  await fs.writeFile(fullPath, buffer);
  return fullPath;
}

function runLocalPythonTool(pythonPath, scriptPath, payload, timeoutMs = 180000) {
  function parseToolPayload(rawStdout) {
    const raw = String(rawStdout ?? "").trim();
    if (!raw) return null;

    try {
      return JSON.parse(raw);
    } catch {}

    const lines = raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    for (let i = lines.length - 1; i >= 0; i -= 1) {
      const line = lines[i];
      try {
        return JSON.parse(line);
      } catch {}
    }

    const braceIndex = raw.lastIndexOf("{");
    if (braceIndex >= 0) {
      const candidate = raw.slice(braceIndex);
      try {
        return JSON.parse(candidate);
      } catch {}
    }

    return null;
  }

  return new Promise((resolve, reject) => {
    if (!pythonPath || !scriptPath) {
      reject(new Error("missing python/script path"));
      return;
    }

    const child = spawn(pythonPath, [scriptPath], {
      cwd: ROOT_DIR,
      stdio: ["pipe", "pipe", "pipe"]
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill("SIGKILL");
      reject(new Error(`local tool timeout (${Math.round(timeoutMs / 1000)}s)`));
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });

    child.on("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(error);
    });

    child.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);

      const parsed = parseToolPayload(stdout);

      if (code !== 0) {
        const errText = parsed?.error || stderr.trim() || stdout.trim() || `exit code ${code}`;
        reject(new Error(errText));
        return;
      }

      if (!parsed || parsed.ok !== true) {
        const errText = parsed?.error || stderr.trim() || "local tool returned invalid payload";
        reject(new Error(errText));
        return;
      }

      resolve(parsed);
    });

    try {
      child.stdin.write(`${JSON.stringify(payload)}\n`);
      child.stdin.end();
    } catch (error) {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        reject(error);
      }
    }
  });
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
  logLevel: envString("LOG_LEVEL", "info"),
  webScrapeEnabled: envBool("WEB_SCRAPE_ENABLED", true),
  webScrapeAutoUrl: envBool("WEB_SCRAPE_AUTO_URL", false),
  webScrapeMaxChars: envInt("WEB_SCRAPE_MAX_CHARS", 14000, 1000, 200000),
  webScrapeTimeoutMs: envInt("WEB_SCRAPE_TIMEOUT_MS", 20000, 2000, 180000),
  webScrapeAllowDomains: parseStringList(envString("WEB_SCRAPE_ALLOW_DOMAINS")).map((v) =>
    v.toLowerCase()
  ),
  webScrapeUserAgent: envString(
    "WEB_SCRAPE_USER_AGENT",
    "wa-llama-bridge/0.2 (+https://github.com/openai/codex)"
  ),
  audioTranscribeEnabled: envBool("AUDIO_TRANSCRIBE_ENABLED", true),
  audioTranscribeBaseUrl: envString("AUDIO_TRANSCRIBE_BASE_URL"),
  audioTranscribeModel: envString("AUDIO_TRANSCRIBE_MODEL", "whisper-1"),
  audioTranscribeApiKey: envString("AUDIO_TRANSCRIBE_API_KEY"),
  audioTranscribeLanguage: envString("AUDIO_TRANSCRIBE_LANGUAGE", "es"),
  audioTranscribePrompt: envString("AUDIO_TRANSCRIBE_PROMPT"),
  audioTranscribeMaxMb: envFloat("AUDIO_TRANSCRIBE_MAX_MB", 20, 1, 500),
  localSttEnabled: envBool("LOCAL_STT_ENABLED", true),
  localSttPython: resolveMaybePath(
    envString("LOCAL_STT_PYTHON", "python3")
  ),
  localSttScript: resolveMaybePath(envString("LOCAL_STT_SCRIPT", "./tools/stt_local.py")),
  localSttModelDir: resolveMaybePath(
    envString("LOCAL_STT_MODEL_DIR", "")
  ),
  localSttTask: envString("LOCAL_STT_TASK", "transcribe"),
  localSttForceCpu: envBool("LOCAL_STT_FORCE_CPU", true),
  localSttChunkLengthS: envInt("LOCAL_STT_CHUNK_LENGTH_S", 30, 0, 120),
  localOcrEnabled: envBool("LOCAL_OCR_ENABLED", true),
  localOcrPython: resolveMaybePath(
    envString("LOCAL_OCR_PYTHON", "python3")
  ),
  localOcrScript: resolveMaybePath(envString("LOCAL_OCR_SCRIPT", "./tools/ocr_local.py")),
  localOcrModelDir: resolveMaybePath(
    envString("LOCAL_OCR_MODEL_DIR")
  ),
  localOcrDetModelName: envString("LOCAL_OCR_DET_MODEL_NAME", "PP-OCRv4_server_det"),
  localOcrRecModelName: envString("LOCAL_OCR_REC_MODEL_NAME", "PP-OCRv4_server_rec"),
  localOcrClsModelName: envString("LOCAL_OCR_CLS_MODEL_NAME"),
  localOcrDetModelDir: resolveMaybePath(
    envString("LOCAL_OCR_DET_MODEL_DIR", "")
  ),
  localOcrRecModelDir: resolveMaybePath(
    envString("LOCAL_OCR_REC_MODEL_DIR", "")
  ),
  localOcrClsModelDir: resolveMaybePath(envString("LOCAL_OCR_CLS_MODEL_DIR")),
  localOcrUseTextlineOrientation: envBool("LOCAL_OCR_USE_TEXTLINE_ORIENTATION", false),
  localOcrLang: envString("LOCAL_OCR_LANG", "es"),
  autoImageAnalyzeEnabled: envBool("AUTO_IMAGE_ANALYZE_ENABLED", false),
  autoImageAnalyzeRequireOcr: envBool("AUTO_IMAGE_ANALYZE_REQUIRE_OCR", false),
  autoImageAnalyzeMaxOcrChars: envInt("AUTO_IMAGE_ANALYZE_MAX_OCR_CHARS", 4000, 200, 50000),
  autoImageAnalyzeMaxVlmChars: envInt("AUTO_IMAGE_ANALYZE_MAX_VLM_CHARS", 2500, 200, 50000),
  autoImageAnalyzeMaxYoloItems: envInt("AUTO_IMAGE_ANALYZE_MAX_YOLO_ITEMS", 10, 1, 200),
  localVlmEnabled: envBool("LOCAL_VLM_ENABLED", false),
  localVlmPython: resolveMaybePath(
    envString("LOCAL_VLM_PYTHON", "python3")
  ),
  localVlmScript: resolveMaybePath(envString("LOCAL_VLM_SCRIPT", "./tools/vlm_local.py")),
  localVlmModelDir: resolveMaybePath(
    envString(
      "LOCAL_VLM_MODEL_DIR",
      ""
    )
  ),
  localVlmPrompt: envString(
    "LOCAL_VLM_PROMPT",
    "Describe brevemente la imagen en español: escena, personas/objetos, acción, contexto y tono."
  ),
  localVlmMaxNewTokens: envInt("LOCAL_VLM_MAX_NEW_TOKENS", 220, 32, 2048),
  localVlmForceCpu: envBool("LOCAL_VLM_FORCE_CPU", false),
  localVlmTimeoutMs: envInt("LOCAL_VLM_TIMEOUT_MS", 600000, 10000, 3600000),
  localYoloEnabled: envBool("LOCAL_YOLO_ENABLED", false),
  localYoloPython: resolveMaybePath(
    envString("LOCAL_YOLO_PYTHON", "python3")
  ),
  localYoloScript: resolveMaybePath(envString("LOCAL_YOLO_SCRIPT", "./tools/yolo_local.py")),
  localYoloModelPath: resolveMaybePath(
    envString(
      "LOCAL_YOLO_MODEL_PATH",
      ""
    )
  ),
  localYoloConf: envFloat("LOCAL_YOLO_CONF", 0.25, 0, 1),
  localYoloIou: envFloat("LOCAL_YOLO_IOU", 0.45, 0, 1),
  localYoloMaxDet: envInt("LOCAL_YOLO_MAX_DET", 30, 1, 300),
  localYoloTimeoutMs: envInt("LOCAL_YOLO_TIMEOUT_MS", 180000, 10000, 3600000),
  localImageEnabled: envBool("LOCAL_IMAGE_ENABLED", false),
  localImagePython: resolveMaybePath(
    envString("LOCAL_IMAGE_PYTHON", "python3")
  ),
  localImageScript: resolveMaybePath(envString("LOCAL_IMAGE_SCRIPT", "./tools/image_local.py")),
  localImageModelDir: resolveMaybePath(
    envString("LOCAL_IMAGE_MODEL_DIR", "")
  ),
  localImageCheckpoint: resolveMaybePath(envString("LOCAL_IMAGE_CHECKPOINT")),
  localImageSteps: envInt("LOCAL_IMAGE_STEPS", 28, 1, 200),
  localImageGuidance: envFloat("LOCAL_IMAGE_GUIDANCE", 6.5, 0, 40),
  localImageWidth: envInt("LOCAL_IMAGE_WIDTH", 1024, 256, 1536),
  localImageHeight: envInt("LOCAL_IMAGE_HEIGHT", 1024, 256, 1536)
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
const sentTextByBridge = new Map();
const laneByChat = new Map();
const historyByChat = Object.create(null);
const enabledChats = new Set();
let saveTimer = null;
let chatSwitchSaveTimer = null;

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
  await fs.mkdir(TMP_DIR, { recursive: true });
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

async function loadChatSwitches() {
  try {
    const raw = await fs.readFile(CHAT_SWITCH_FILE, "utf8");
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return;
    enabledChats.clear();
    for (const entry of parsed) {
      const jid = normalizeJid(entry);
      if (!jid) continue;
      enabledChats.add(jid);
    }
  } catch (error) {
    if (error?.code !== "ENOENT") {
      log.warn({ err: String(error) }, "chat switch file could not be loaded");
    }
  }
}

function scheduleChatSwitchSave() {
  if (chatSwitchSaveTimer) return;
  chatSwitchSaveTimer = setTimeout(async () => {
    chatSwitchSaveTimer = null;
    try {
      const payload = [...enabledChats].sort();
      await fs.writeFile(CHAT_SWITCH_FILE, JSON.stringify(payload, null, 2), "utf8");
    } catch (error) {
      log.error({ err: String(error) }, "failed to write chat switch file");
    }
  }, 200);
}

async function flushChatSwitchSaveNow() {
  if (chatSwitchSaveTimer) {
    clearTimeout(chatSwitchSaveTimer);
    chatSwitchSaveTimer = null;
  }
  try {
    const payload = [...enabledChats].sort();
    await fs.writeFile(CHAT_SWITCH_FILE, JSON.stringify(payload, null, 2), "utf8");
  } catch (error) {
    log.error({ err: String(error) }, "failed to flush chat switch file");
  }
}

function isChatEnabled(jid) {
  const normalized = normalizeJid(jid);
  if (!normalized) return false;
  return enabledChats.has(normalized);
}

function setChatEnabled(jid, enabled) {
  const normalized = normalizeJid(jid);
  if (!normalized) return false;
  const before = enabledChats.has(normalized);
  if (enabled) enabledChats.add(normalized);
  else enabledChats.delete(normalized);
  const after = enabledChats.has(normalized);
  if (before !== after) scheduleChatSwitchSave();
  return after;
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

function rememberSentText(chatJid, text) {
  const normalizedChatJid = normalizeJid(chatJid);
  const cleanText = String(text ?? "").trim();
  if (!normalizedChatJid || !cleanText) return;
  const key = `${normalizedChatJid}::${cleanText}`;
  sentTextByBridge.set(key, Date.now());
}

function cleanupSentIds() {
  const now = Date.now();
  for (const [id, ts] of sentByBridge.entries()) {
    if (now - ts > 2 * 60 * 60 * 1000) sentByBridge.delete(id);
  }
  for (const [key, ts] of sentTextByBridge.entries()) {
    if (now - ts > 10 * 60 * 1000) sentTextByBridge.delete(key);
  }
}

function wasRecentlySentText(chatJid, text) {
  const normalizedChatJid = normalizeJid(chatJid);
  const cleanText = String(text ?? "").trim();
  if (!normalizedChatJid || !cleanText) return false;
  const key = `${normalizedChatJid}::${cleanText}`;
  const ts = sentTextByBridge.get(key);
  if (!ts) return false;
  return Date.now() - ts <= 5 * 60 * 1000;
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

function buildConversationMessages(normalizedChatJid, userContent) {
  const historyEntries = trimHistoryEntries(getHistory(normalizedChatJid));
  const messages = [];
  if (CONFIG.systemPrompt) messages.push({ role: "system", content: CONFIG.systemPrompt });
  for (const entry of historyEntries) {
    messages.push({ role: entry.role, content: entry.content });
  }
  messages.push({ role: "user", content: userContent });
  return messages;
}

function isWebDomainAllowed(urlObj) {
  if (!CONFIG.webScrapeAllowDomains || CONFIG.webScrapeAllowDomains.length === 0) return true;
  const host = String(urlObj.hostname ?? "").toLowerCase();
  return CONFIG.webScrapeAllowDomains.some((allowed) => {
    const normalized = String(allowed ?? "").trim().toLowerCase();
    if (!normalized) return false;
    return host === normalized || host.endsWith(`.${normalized}`);
  });
}

async function fetchWebContent(urlRaw) {
  if (!CONFIG.webScrapeEnabled) throw new Error("web scraping is disabled by config");

  const urlObj = buildUrlFromInput(urlRaw);
  if (!urlObj) throw new Error("invalid URL (only http/https)");
  if (!isWebDomainAllowed(urlObj)) {
    throw new Error(`domain not allowed: ${urlObj.hostname}`);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CONFIG.webScrapeTimeoutMs);
  try {
    const response = await fetch(urlObj.toString(), {
      method: "GET",
      headers: {
        "user-agent": CONFIG.webScrapeUserAgent,
        accept: "text/html, text/plain;q=0.9, */*;q=0.1"
      },
      signal: controller.signal,
      redirect: "follow"
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const contentType = String(response.headers.get("content-type") ?? "").toLowerCase();
    const raw = await response.text();
    const text = contentType.includes("html") ? sanitizeHtmlToText(raw) : String(raw ?? "").trim();
    if (!text) throw new Error("empty content extracted");
    return text.slice(0, CONFIG.webScrapeMaxChars);
  } finally {
    clearTimeout(timeoutId);
  }
}

async function runWebQuestion(normalizedChatJid, url, question) {
  const content = await fetchWebContent(url);
  const task = question?.trim()
    ? question.trim()
    : "Resume este contenido en español en 8-12 puntos prácticos.";
  const userContent = [
    `URL: ${url}`,
    "Contenido extraído de la web:",
    content,
    `Tarea: ${task}`
  ].join("\n\n");
  const completion = await callLlmWithFallback(buildConversationMessages(normalizedChatJid, userContent));
  return {
    answer: completion.text.trim() || "No tengo respuesta ahora.",
    endpoint: completion.endpoint,
    extractedChars: content.length
  };
}

function audioMimeToExtension(mimeType) {
  const normalized = String(mimeType ?? "").toLowerCase();
  if (normalized.includes("ogg")) return "ogg";
  if (normalized.includes("mpeg") || normalized.includes("mp3")) return "mp3";
  if (normalized.includes("wav")) return "wav";
  if (normalized.includes("mp4")) return "m4a";
  if (normalized.includes("aac")) return "aac";
  return "ogg";
}

function imageMimeToExtension(mimeType) {
  const normalized = String(mimeType ?? "").toLowerCase();
  if (normalized.includes("png")) return "png";
  if (normalized.includes("webp")) return "webp";
  if (normalized.includes("bmp")) return "bmp";
  return "jpg";
}

async function transcribeAudioLocal(buffer, mimeType = "audio/ogg") {
  if (!CONFIG.localSttEnabled) throw new Error("local STT disabled");

  const ext = audioMimeToExtension(mimeType);
  const inputPath = await writeTempBuffer(buffer, ext);
  try {
    const payload = {
      audio_path: inputPath,
      model_dir: CONFIG.localSttModelDir,
      language: CONFIG.audioTranscribeLanguage || "",
      prompt: CONFIG.audioTranscribePrompt || "",
      task: CONFIG.localSttTask || "transcribe",
      force_cpu: CONFIG.localSttForceCpu,
      chunk_length_s: CONFIG.localSttChunkLengthS
    };
    const out = await runLocalPythonTool(
      CONFIG.localSttPython,
      CONFIG.localSttScript,
      payload,
      Math.max(CONFIG.requestTimeoutMs, 300000)
    );
    const transcript = String(out?.text ?? "").trim();
    if (!transcript) throw new Error("local STT empty transcript");
    return transcript;
  } finally {
    await fs.rm(inputPath, { force: true }).catch(() => {});
  }
}

async function transcribeAudioBuffer(buffer, mimeType = "audio/ogg") {
  const canUseApi = CONFIG.audioTranscribeEnabled;

  if (!canUseApi) {
    return transcribeAudioLocal(buffer, mimeType);
  }

  const baseUrl = CONFIG.audioTranscribeBaseUrl || CONFIG.llmBaseUrl;
  const url = buildAudioTranscriptionsUrl(baseUrl);
  if (!url) {
    return transcribeAudioLocal(buffer, mimeType);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CONFIG.requestTimeoutMs);

  try {
    try {
      const headers = {};
      const apiKey = CONFIG.audioTranscribeApiKey || CONFIG.llmApiKey;
      if (apiKey) headers.authorization = `Bearer ${apiKey}`;

      const extension = audioMimeToExtension(mimeType);
      const form = new FormData();
      form.append("model", CONFIG.audioTranscribeModel);
      if (CONFIG.audioTranscribeLanguage) form.append("language", CONFIG.audioTranscribeLanguage);
      if (CONFIG.audioTranscribePrompt) form.append("prompt", CONFIG.audioTranscribePrompt);
      form.append("file", new Blob([buffer], { type: mimeType || "audio/ogg" }), `voice.${extension}`);

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: form,
        signal: controller.signal
      });

      const rawText = await response.text();
      if (!response.ok) {
        throw new Error(`STT HTTP ${response.status}: ${rawText.slice(0, 220)}`);
      }

      let payload;
      try {
        payload = JSON.parse(rawText);
      } catch {
        throw new Error("STT returned invalid JSON");
      }

      const transcript = String(payload?.text ?? "").trim();
      if (!transcript) throw new Error("STT returned empty transcript");
      return transcript;
    } catch (apiError) {
      if (!CONFIG.localSttEnabled) throw apiError;
      log.warn({ err: String(apiError) }, "STT API failed, trying local STT");
      return transcribeAudioLocal(buffer, mimeType);
    }
  } finally {
    clearTimeout(timeoutId);
  }
}

async function runLocalOcrOnBuffer(buffer, mimeType = "image/jpeg") {
  if (!CONFIG.localOcrEnabled) throw new Error("local OCR disabled");
  const ext = imageMimeToExtension(mimeType);
  const inputPath = await writeTempBuffer(buffer, ext);
  try {
    const payload = {
      image_path: inputPath,
      model_dir: CONFIG.localOcrModelDir,
      det_model_name: CONFIG.localOcrDetModelName,
      rec_model_name: CONFIG.localOcrRecModelName,
      cls_model_name: CONFIG.localOcrClsModelName,
      det_model_dir: CONFIG.localOcrDetModelDir,
      rec_model_dir: CONFIG.localOcrRecModelDir,
      cls_model_dir: CONFIG.localOcrClsModelDir,
      use_textline_orientation: CONFIG.localOcrUseTextlineOrientation,
      lang: CONFIG.localOcrLang
    };
    const out = await runLocalPythonTool(
      CONFIG.localOcrPython,
      CONFIG.localOcrScript,
      payload,
      Math.max(CONFIG.requestTimeoutMs, 180000)
    );
    const text = String(out?.text ?? "").trim();
    if (!text) throw new Error("OCR returned empty text");
    return {
      text,
      lines: Array.isArray(out?.lines) ? out.lines : []
    };
  } finally {
    await fs.rm(inputPath, { force: true }).catch(() => {});
  }
}

async function runLocalVlmOnBuffer(buffer, mimeType = "image/jpeg") {
  if (!CONFIG.localVlmEnabled) throw new Error("local VLM disabled");
  const ext = imageMimeToExtension(mimeType);
  const inputPath = await writeTempBuffer(buffer, ext);
  try {
    const payload = {
      image_path: inputPath,
      model_dir: CONFIG.localVlmModelDir,
      prompt: CONFIG.localVlmPrompt,
      max_new_tokens: CONFIG.localVlmMaxNewTokens,
      force_cpu: CONFIG.localVlmForceCpu
    };
    const out = await runLocalPythonTool(
      CONFIG.localVlmPython,
      CONFIG.localVlmScript,
      payload,
      Math.max(CONFIG.localVlmTimeoutMs, CONFIG.requestTimeoutMs)
    );
    const text = String(out?.text ?? "").trim();
    if (!text) throw new Error("VLM returned empty text");
    return {
      text,
      meta: out?.meta || {}
    };
  } finally {
    await fs.rm(inputPath, { force: true }).catch(() => {});
  }
}

async function runLocalYoloOnBuffer(buffer, mimeType = "image/jpeg") {
  if (!CONFIG.localYoloEnabled) throw new Error("local YOLO disabled");
  const ext = imageMimeToExtension(mimeType);
  const inputPath = await writeTempBuffer(buffer, ext);
  try {
    const payload = {
      image_path: inputPath,
      model_path: CONFIG.localYoloModelPath,
      conf: CONFIG.localYoloConf,
      iou: CONFIG.localYoloIou,
      max_det: CONFIG.localYoloMaxDet
    };
    const out = await runLocalPythonTool(
      CONFIG.localYoloPython,
      CONFIG.localYoloScript,
      payload,
      Math.max(CONFIG.localYoloTimeoutMs, CONFIG.requestTimeoutMs)
    );
    return {
      detections: Array.isArray(out?.detections) ? out.detections : [],
      summary: out?.summary && typeof out.summary === "object" ? out.summary : {},
      meta: out?.meta || {}
    };
  } finally {
    await fs.rm(inputPath, { force: true }).catch(() => {});
  }
}

function summarizeYoloDetections(detections = [], maxItems = 10) {
  if (!Array.isArray(detections) || detections.length === 0) return "";
  const grouped = new Map();
  for (const det of detections) {
    const label = String(det?.label || det?.class_name || det?.class || "").trim() || "objeto";
    const conf = Number(det?.confidence ?? det?.conf ?? 0);
    const prev = grouped.get(label) || { count: 0, confSum: 0 };
    prev.count += 1;
    prev.confSum += Number.isFinite(conf) ? conf : 0;
    grouped.set(label, prev);
  }
  const rows = [...grouped.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, Math.max(1, maxItems))
    .map(([label, stats]) => {
      const avgConf = stats.count > 0 ? stats.confSum / stats.count : 0;
      return `${label} x${stats.count} (conf~${avgConf.toFixed(2)})`;
    });
  return rows.join(", ");
}

async function generateImageLocal(prompt) {
  if (!CONFIG.localImageEnabled) throw new Error("local image generation disabled");
  const outputPath = path.join(TMP_DIR, `${Date.now()}-${randomUUID()}.png`);
  const payload = {
    prompt: String(prompt ?? "").trim(),
    output_path: outputPath,
    model_dir: CONFIG.localImageModelDir,
    checkpoint: CONFIG.localImageCheckpoint || "",
    steps: CONFIG.localImageSteps,
    guidance: CONFIG.localImageGuidance,
    width: CONFIG.localImageWidth,
    height: CONFIG.localImageHeight
  };
  const out = await runLocalPythonTool(
    CONFIG.localImagePython,
    CONFIG.localImageScript,
    payload,
    Math.max(CONFIG.requestTimeoutMs, 300000)
  );
  const imagePath = String(out?.image_path || outputPath);
  const imageBuffer = await fs.readFile(imagePath);
  await fs.rm(imagePath, { force: true }).catch(() => {});
  return {
    imageBuffer,
    meta: out?.meta || {}
  };
}

async function resolveInboundText(sock, msg) {
  const plainText = extractMessageText(msg.message).trim();
  const image = extractImageMessage(msg?.message);
  const isCommandText = plainText.startsWith("/");
  if (plainText && (!image || isCommandText)) return { text: plainText, source: "text" };

  const audio = extractAudioMessage(msg.message);
  if (audio) {
    if (!CONFIG.audioTranscribeEnabled && !CONFIG.localSttEnabled) {
      return { text: "", source: "audio-disabled" };
    }

    const maxBytes = Math.floor(CONFIG.audioTranscribeMaxMb * 1024 * 1024);
    const declaredBytes = normalizeMaybeLong(audio?.fileLength);
    if (declaredBytes && declaredBytes > maxBytes) {
      throw new Error(
        `audio too large (${Math.round(declaredBytes / 1024 / 1024)} MB > ${CONFIG.audioTranscribeMaxMb} MB)`
      );
    }

    const buffer = await downloadMediaMessage(
      msg,
      "buffer",
      {},
      {
        logger: log,
        reuploadRequest: sock.updateMediaMessage
      }
    );

    const actualBytes = Buffer.isBuffer(buffer) ? buffer.length : 0;
    if (!actualBytes) throw new Error("audio download returned empty buffer");
    if (actualBytes > maxBytes) {
      throw new Error(
        `audio too large (${Math.round(actualBytes / 1024 / 1024)} MB > ${CONFIG.audioTranscribeMaxMb} MB)`
      );
    }

    const mimeType = String(audio?.mimetype || "audio/ogg");
    const transcript = await transcribeAudioBuffer(buffer, mimeType);
    return { text: transcript, source: "audio" };
  }

  if (image && CONFIG.autoImageAnalyzeEnabled) {
    let media = null;
    try {
      media = await downloadInboundImageBuffer(sock, msg);
    } catch (error) {
      const downloadError = `fallo al descargar imagen: ${error?.message ?? String(error)}`;
      log.warn({ err: downloadError }, "auto image download failed");
      if (plainText) return { text: plainText, source: "text" };
      return { text: "", source: "image-download-error" };
    }
    if (!media?.buffer) {
      if (plainText) return { text: plainText, source: "text" };
      return { text: "", source: "image-empty" };
    }

    let ocrText = "";
    let ocrError = "";
    let vlmText = "";
    let vlmError = "";
    let yoloDetections = [];
    let yoloSummary = "";
    let yoloError = "";

    const jobs = [];
    if (CONFIG.localOcrEnabled) {
      jobs.push(
        runLocalOcrOnBuffer(media.buffer, media.mimeType)
          .then((ocr) => {
            ocrText = String(ocr?.text || "").trim();
          })
          .catch((error) => {
            ocrError = error?.message ?? String(error);
            log.warn({ err: ocrError }, "auto image OCR failed");
          })
      );
    } else {
      ocrError = "OCR local desactivado";
    }

    if (CONFIG.localVlmEnabled) {
      jobs.push(
        runLocalVlmOnBuffer(media.buffer, media.mimeType)
          .then((vlm) => {
            vlmText = String(vlm?.text || "").trim();
          })
          .catch((error) => {
            vlmError = error?.message ?? String(error);
            log.warn({ err: vlmError }, "auto image VLM failed");
          })
      );
    } else {
      vlmError = "VLM local desactivado";
    }

    if (CONFIG.localYoloEnabled) {
      jobs.push(
        runLocalYoloOnBuffer(media.buffer, media.mimeType)
          .then((yolo) => {
            yoloDetections = Array.isArray(yolo?.detections) ? yolo.detections : [];
            yoloSummary = summarizeYoloDetections(yoloDetections, CONFIG.autoImageAnalyzeMaxYoloItems);
          })
          .catch((error) => {
            yoloError = error?.message ?? String(error);
            log.warn({ err: yoloError }, "auto image YOLO failed");
          })
      );
    } else {
      yoloError = "YOLO local desactivado";
    }

    if (jobs.length > 0) {
      await Promise.all(jobs);
    }

    if (!plainText && !ocrText && !vlmText && yoloDetections.length === 0 && CONFIG.autoImageAnalyzeRequireOcr) {
      return { text: "", source: "image-no-ocr" };
    }

    const prompt = buildAutoImagePrompt({
      plainText,
      ocrText,
      ocrError,
      vlmText,
      vlmError,
      yoloSummary,
      yoloDetections,
      yoloError,
      imageMeta: media.imageMeta || image
    });
    return { text: prompt, source: "image" };
  }

  if (plainText) return { text: plainText, source: "text" };
  return { text: "", source: "none" };
}

async function downloadInboundImageBuffer(sock, msg) {
  const image = extractImageMessage(msg?.message);
  if (!image) return null;

  const buffer = await downloadMediaMessage(
    msg,
    "buffer",
    {},
    {
      logger: log,
      reuploadRequest: sock.updateMediaMessage
    }
  );

  if (!Buffer.isBuffer(buffer) || buffer.length === 0) return null;
  return {
    buffer,
    mimeType: String(image?.mimetype || "image/jpeg"),
    imageMeta: image
  };
}

function buildAutoImagePrompt({
  plainText,
  ocrText,
  ocrError,
  vlmText,
  vlmError,
  yoloSummary,
  yoloDetections,
  yoloError,
  imageMeta
}) {
  const caption = String(plainText || "").trim();
  const ocr = String(ocrText || "").trim();
  const vlm = String(vlmText || "").trim();
  const yolo = String(yoloSummary || "").trim();
  const width = Number(imageMeta?.width || 0);
  const height = Number(imageMeta?.height || 0);
  const mime = String(imageMeta?.mimetype || "image/jpeg");
  const yoloCount = Array.isArray(yoloDetections) ? yoloDetections.length : 0;

  const lines = [
    "Usuario envio una imagen por WhatsApp.",
    `Metadatos: tipo=${mime}${width > 0 && height > 0 ? `, tamaño=${width}x${height}` : ""}.`,
    caption ? `Caption del usuario: ${caption}` : "Caption del usuario: (sin caption)"
  ];

  if (ocr) {
    lines.push(`Texto OCR detectado:\n${ocr.slice(0, CONFIG.autoImageAnalyzeMaxOcrChars)}`);
  } else if (ocrError) {
    lines.push(`OCR no disponible: ${ocrError}`);
  } else {
    lines.push("Texto OCR detectado: (sin texto)");
  }

  if (vlm) {
    lines.push(`Descripcion VLM:\n${vlm.slice(0, CONFIG.autoImageAnalyzeMaxVlmChars)}`);
  } else if (vlmError) {
    lines.push(`VLM no disponible: ${vlmError}`);
  } else {
    lines.push("Descripcion VLM: (sin salida)");
  }

  if (yolo) {
    lines.push(`Objetos YOLO (top): ${yolo}`);
  } else if (yoloError) {
    lines.push(`YOLO no disponible: ${yoloError}`);
  } else if (yoloCount > 0) {
    lines.push(`Objetos YOLO: ${yoloCount} detecciones`);
  } else {
    lines.push("Objetos YOLO: (sin detecciones)");
  }

  lines.push(
    "Tarea: responde breve en español con lo que intuyes que hay en la imagen usando caption+OCR+VLM+YOLO+metadatos. " +
      "Prioriza evidencia visual (VLM+YOLO), luego OCR y caption. " +
      "Si no hay evidencia suficiente, dilo con claridad y pide más contexto."
  );

  return lines.join("\n\n");
}

async function sendReply(sock, jid, text, quoted) {
  const chunks = splitText(text, CONFIG.replyChunkChars);
  if (chunks.length === 0) return;

  for (let i = 0; i < chunks.length; i += 1) {
    const chunk = chunks[i];
    const options = i === 0 && quoted ? { quoted } : {};
    const sent = await sock.sendMessage(jid, { text: chunk }, options);
    rememberSentId(sent?.key?.id);
    rememberSentText(jid, chunk);
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

async function handleCommand(sock, chatJid, normalizedChatJid, text, quoted, rawMsg) {
  const trimmed = text.trim();
  const cmd = trimmed.toLowerCase();
  const chatEnabled = isChatEnabled(normalizedChatJid);

  if (cmd === "/on") {
    const wasEnabled = chatEnabled;
    setChatEnabled(normalizedChatJid, true);
    await sendReply(
      sock,
      chatJid,
      wasEnabled
        ? "Este chat ya estaba activado."
        : "✅ Chat activado. A partir de ahora procesare tus mensajes aqui hasta que uses /off.",
      quoted
    );
    return true;
  }

  if (cmd === "/off") {
    const wasEnabled = chatEnabled;
    setChatEnabled(normalizedChatJid, false);
    await sendReply(
      sock,
      chatJid,
      wasEnabled
        ? "⏸️ Chat desactivado. Para reactivar usa /on."
        : "Este chat ya estaba desactivado. Usa /on para activarlo.",
      quoted
    );
    return true;
  }

  if (cmd === "/help") {
    await sendReply(
      sock,
      chatJid,
      [
        "Comandos:",
        "/on - activar asistente en este chat",
        "/off - desactivar asistente en este chat",
        "/help - ayuda",
        "/reset o /new - limpiar memoria de este chat",
        "/model - modelo activo y fallback",
        "/status - estado rapido",
        "/web <url> [pregunta] - raspa la web y responde con contexto",
        "/ocr [pregunta] - OCR de imagen (enviar como caption o en reply)",
        "/img <prompt> - genera imagen con SD local",
        "(auto) al recibir imagen: OCR + VLM + YOLO + LLM (según configuración)"
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
      [
        `Status: ${lane}`,
        `History entries: ${historyCount}`,
        `Chat active: ${chatEnabled}`,
        `Self chat only: ${CONFIG.selfChatOnly}`,
        `Web: ${CONFIG.webScrapeEnabled}`,
        `Audio STT API: ${CONFIG.audioTranscribeEnabled}`,
        `Audio STT local: ${CONFIG.localSttEnabled}`,
        `OCR local: ${CONFIG.localOcrEnabled}`,
        `Auto image analyze: ${CONFIG.autoImageAnalyzeEnabled}`,
        `VLM local: ${CONFIG.localVlmEnabled}`,
        `YOLO local: ${CONFIG.localYoloEnabled}`,
        `Image local: ${CONFIG.localImageEnabled}`
      ].join("\n"),
      quoted
    );
    return true;
  }

  if (!chatEnabled) {
    if (trimmed.startsWith("/")) {
      await sendReply(
        sock,
        chatJid,
        "Este chat esta desactivado. Usa /on para activarlo.",
        quoted
      );
      return true;
    }
    return false;
  }

  if (cmd.startsWith("/web ") || cmd.startsWith("/scrape ")) {
    const payload = trimmed.replace(/^\/(web|scrape)\s+/i, "").trim();
    if (!payload) {
      await sendReply(sock, chatJid, "Uso: /web <url> [pregunta]", quoted);
      return true;
    }

    const firstSpace = payload.search(/\s/);
    const url = firstSpace === -1 ? payload : payload.slice(0, firstSpace).trim();
    const question = firstSpace === -1 ? "" : payload.slice(firstSpace + 1).trim();
    const urlObj = buildUrlFromInput(url);
    if (!urlObj) {
      await sendReply(sock, chatJid, "URL inválida. Usa http:// o https://", quoted);
      return true;
    }

    try {
      const result = await runWebQuestion(normalizedChatJid, urlObj.toString(), question);
      const answer = result.answer;
      appendHistory(normalizedChatJid, "user", trimmed);
      appendHistory(normalizedChatJid, "assistant", answer);
      await sendReply(sock, chatJid, answer, quoted);
      log.info(
        { endpoint: result.endpoint?.name, extractedChars: result.extractedChars, url: urlObj.hostname },
        "web command reply sent"
      );
    } catch (error) {
      const message = error?.message ?? String(error);
      await sendReply(sock, chatJid, `[bridge] Web error: ${message}`, quoted);
    }
    return true;
  }

  if (cmd === "/ocr" || cmd.startsWith("/ocr ")) {
    if (!CONFIG.localOcrEnabled) {
      await sendReply(sock, chatJid, "[bridge] OCR local desactivado (LOCAL_OCR_ENABLED=false).", quoted);
      return true;
    }

    const question = trimmed.replace(/^\/ocr\b/i, "").trim();
    let media = null;
    try {
      media = await downloadInboundImageBuffer(sock, rawMsg);
    } catch (error) {
      await sendReply(sock, chatJid, `[bridge] OCR error descargando imagen: ${error?.message ?? String(error)}`, quoted);
      return true;
    }

    if (!media?.buffer) {
      await sendReply(
        sock,
        chatJid,
        "Para OCR: envia `/ocr` como caption de una imagen, o en el mismo mensaje con imagen.",
        quoted
      );
      return true;
    }

    try {
      const ocr = await runLocalOcrOnBuffer(media.buffer, media.mimeType);
      let answer = `OCR extraido:\n\n${ocr.text}`;

      if (question) {
        const userContent = [
          "Texto OCR extraído:",
          ocr.text,
          `Tarea: ${question}`
        ].join("\n\n");
        const completion = await callLlmWithFallback(buildConversationMessages(normalizedChatJid, userContent));
        answer = completion.text.trim() || "No tengo respuesta ahora.";
        appendHistory(normalizedChatJid, "user", `/ocr ${question}\n[OCR]\n${ocr.text}`);
        appendHistory(normalizedChatJid, "assistant", answer);
      }

      await sendReply(sock, chatJid, answer, quoted);
    } catch (error) {
      await sendReply(sock, chatJid, `[bridge] OCR error: ${error?.message ?? String(error)}`, quoted);
    }
    return true;
  }

  if (cmd === "/img" || cmd.startsWith("/img ")) {
    if (!CONFIG.localImageEnabled) {
      await sendReply(sock, chatJid, "[bridge] Imagen local desactivada (LOCAL_IMAGE_ENABLED=false).", quoted);
      return true;
    }

    const prompt = trimmed.replace(/^\/img\b/i, "").trim();
    if (!prompt) {
      await sendReply(sock, chatJid, "Uso: /img <prompt>", quoted);
      return true;
    }

    try {
      const generated = await generateImageLocal(prompt);
      const meta = generated?.meta ?? {};
      const caption = [
        "Imagen generada.",
        `Prompt: ${prompt}`,
        meta?.width && meta?.height ? `Size: ${meta.width}x${meta.height}` : null,
        meta?.steps ? `Steps: ${meta.steps}` : null
      ]
        .filter(Boolean)
        .join("\n");

      const sent = await sock.sendMessage(
        chatJid,
        { image: generated.imageBuffer, caption },
        quoted ? { quoted } : {}
      );
      rememberSentId(sent?.key?.id);
      rememberSentText(chatJid, caption);
      appendHistory(normalizedChatJid, "user", `/img ${prompt}`);
      appendHistory(normalizedChatJid, "assistant", caption);
    } catch (error) {
      await sendReply(sock, chatJid, `[bridge] IMG error: ${error?.message ?? String(error)}`, quoted);
    }
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

  const chatEnabled = isChatEnabled(normalizedChatJid);
  const rawText = extractMessageText(msg.message).trim();
  const rawCmd = extractCommandName(rawText);
  if (!chatEnabled && !rawCmd) return;

  let inbound;
  try {
    inbound = await resolveInboundText(sock, msg);
  } catch (error) {
    const message = error?.message ?? String(error);
    log.error({ err: message }, "failed to process inbound media");
    await sendReply(sock, chatJid, `[bridge] Error procesando audio: ${message}`, msg);
    return;
  }

  const text = String(inbound?.text ?? "").trim();
  if (!text) return;

  if (wasRecentlySentText(normalizedChatJid, text)) {
    log.info({ chat: normalizedChatJid, length: text.length }, "ignoring mirrored bridge text");
    return;
  }

  log.info(
    {
      from: senderJid,
      chat: normalizedChatJid,
      length: text.length,
      source: inbound?.source ?? "text"
    },
    "inbound message"
  );

  await queueForChat(normalizedChatJid, async () => {
    if (await handleCommand(sock, chatJid, normalizedChatJid, text, msg, msg)) return;

    const stopTyping = startTypingLoop(sock, chatJid);
    try {
      let userContent = text;
      if (CONFIG.webScrapeEnabled && CONFIG.webScrapeAutoUrl) {
        const urls = extractUrls(text);
        if (urls.length > 0) {
          try {
            const webText = await fetchWebContent(urls[0]);
            userContent = [text, `[Contexto web extraído de ${urls[0]}]`, webText].join("\n\n");
          } catch (error) {
            log.warn({ err: String(error), url: urls[0] }, "auto web context failed");
          }
        }
      }

      const messages = buildConversationMessages(normalizedChatJid, userContent);

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
    await flushChatSwitchSaveNow();
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
  console.log(
    `[wa-bridge] features: webScrape=${CONFIG.webScrapeEnabled} (autoUrl=${CONFIG.webScrapeAutoUrl}), audioTranscribeApi=${CONFIG.audioTranscribeEnabled}, audioTranscribeLocal=${CONFIG.localSttEnabled}, ocrLocal=${CONFIG.localOcrEnabled}, autoImageAnalyze=${CONFIG.autoImageAnalyzeEnabled}, vlmLocal=${CONFIG.localVlmEnabled}, yoloLocal=${CONFIG.localYoloEnabled}, imageLocal=${CONFIG.localImageEnabled}`
  );

  await ensureDataDirs();
  await loadSystemPromptFromFileIfNeeded();
  console.log(
    `[wa-bridge] prompt source: ${
      CONFIG.systemPromptFile ? `file ${CONFIG.systemPromptFile}` : "SYSTEM_PROMPT (.env)"
    }`
  );
  await loadHistory();
  await loadChatSwitches();
  console.log(
    `[wa-bridge] chat activation: default=off, enabledChats=${enabledChats.size}`
  );
  await startBridgeSocket();
}

main().catch((error) => {
  console.error(`[wa-bridge] fatal: ${error?.stack ?? String(error)}`);
  process.exit(1);
});
