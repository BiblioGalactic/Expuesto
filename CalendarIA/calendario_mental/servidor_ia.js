#!/usr/bin/env node
// 🖥️ ===================================================== 🖥️
// 🖥️   CALENDARIO MENTAL — servidor estático + chat IA local 🖥️
// 🖥️ ===================================================== 🖥️

import http from 'node:http';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = __dirname;

// ⚙️ ===== Configuración (todas personalizables por variables de entorno) =====
const MODELS_DIR = process.env.IA_MODELS_DIR || path.join(ROOT_DIR, 'modelos');
const MAIN_BINARY = process.env.IA_MAIN_BINARY || path.join(ROOT_DIR, 'llama.cpp', 'build', 'bin', 'llama-cli');
const PORT = process.env.PORT || 8787;

// ✅ Validaciones de arranque (avisan, no bloquean)
if (!fs.existsSync(MAIN_BINARY)) {
  console.error(`❌ No se encontró el binario de llama.cpp: ${MAIN_BINARY}`);
  console.error('   El chat fallará hasta que IA_MAIN_BINARY apunte a uno válido.');
}
if (!fs.existsSync(MODELS_DIR)) {
  console.error(`❌ No se encontró la carpeta de modelos: ${MODELS_DIR}`);
  console.error('   /api/models devolverá una lista vacía hasta que exista.');
}

// ... resto del código igual que antes, pero usando estas variables
// 🧠 Utilidades de indexación y guardado
function slugify(name) {
  return name
    .toLowerCase()
    .replace(/\.gguf$/, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function labelize(name) {
  return name.replace(/\.gguf$/i, '').replace(/[_\-.]+/g, ' ').trim();
}

async function findGguf(dir, results = []) {
  let entries;
  try {
    entries = await fsp.readdir(dir, { withFileTypes: true });
  } catch {
    return results;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await findGguf(full, results);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.gguf')) {
      results.push(full);
    }
  }
  return results;
}

function localAgentFile(slug) {
  return path.join(ROOT_DIR, `local_${slug}.json`);
}

async function readJsonSafe(file, fallback) {
  try {
    const txt = await fsp.readFile(file, 'utf8');
    return JSON.parse(txt);
  } catch {
    return fallback;
  }
}

async function writeJsonAtomic(file, data) {
  const tmp = `${file}.tmp`;
  await fsp.writeFile(tmp, JSON.stringify(data, null, 2));
  await fsp.rename(tmp, file);
}

// 🎯 Construcción del Prompt estrictamente adaptado al modelo Mistral Instruct
function buildPrompt(messages, newMessage) {
  let prompt = '<s>';
  for (const m of messages) {
    if (m.sender === 'human') {
      prompt += `[INST] ${m.text} [/INST]`;
    } else {
      prompt += `${m.text}</s>`;
    }
  }
  prompt += `[INST] Eres un asistente útil, experto y directo. Responde siempre en español de forma clara y sin rodeos.\n\n${newMessage} [/INST] `;
  return prompt;
}

// 🧠 Función llama-cli robusta
function runLlama(modelPath, prompt) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(modelPath)) {
      return reject(new Error(`No existe el modelo de IA en: ${modelPath}`));
    }

    const args = [
      '-m', modelPath,
      '-c', '4096',
      '-n', '800',
      '--temp', '0.8',
      '-t', '6',
      '--no-display-prompt',
      '-p', prompt
    ];

    console.log(`\n🤖 [IA] Procesando consulta (${prompt.length} caracteres)...`);

    const proc = spawn(MAIN_BINARY, args);
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.stderr.on('data', (d) => { stderr += d.toString(); });

    proc.on('error', (err) => {
      reject(new Error(`Fallo de sistema al lanzar llama-cli: ${err.message}`));
    });

    proc.on('close', async (code) => {
      let cleanOutput = stdout.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, '').trim();

      if (stderr.trim() && !stderr.includes('Metal') && !stderr.includes('ggml')) {
        const logFile = path.join(ROOT_DIR, 'llama_errors.log');
        await fsp.appendFile(logFile, `\n[${new Date().toISOString()}] STDERR:\n${stderr}\n`).catch(() => {});
      }

      if (code !== 0) {
        console.error(`❌ [IA] Crash detectado. Código de salida: ${code}`);
        reject(new Error(`llama-cli crasheó (código ${code}). Mira llama_errors.log para ver el motivo real.`));
      } else if (!cleanOutput) {
        console.error(`⚠️ [IA] STDOUT vacío. Revisa STDERR:\n`, stderr.trim().slice(-500));
        reject(new Error('La IA ejecutó correctamente pero no devolvió ninguna respuesta en texto.'));
      } else {
        resolve(cleanOutput);
      }
    });
  });
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => { data += chunk; });
    req.on('end', () => resolve(data || '{}'));
    req.on('error', reject);
  });
}

// 🔌 API REST
async function handleApi(req, res, pathname) {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');

  if (pathname === '/api/models' && req.method === 'GET') {
    const files = await findGguf(MODELS_DIR);
    const models = files.map((f) => ({
      path: f,
      slug: slugify(path.basename(f)),
      label: labelize(path.basename(f)),
    }));
    res.end(JSON.stringify(models));
    return;
  }

  if (pathname === '/api/local-agents' && req.method === 'GET') {
    const entries = await fsp.readdir(ROOT_DIR).catch(() => []);
    const agents = [];
    for (const entry of entries) {
      const m = entry.match(/^local_(.+)\.json$/);
      if (!m) continue;
      const data = await readJsonSafe(path.join(ROOT_DIR, entry), []);
      if (Array.isArray(data) && data.length > 0) {
        agents.push({ slug: m[1], file: entry, label: labelize(m[1]) });
      }
    }
    res.end(JSON.stringify(agents));
    return;
  }

  // 🚀 INICIAR CHAT (SOPORTA HISTORIAL CLONADO)
  if (pathname === '/api/chat/start' && req.method === 'POST') {
    const body = JSON.parse(await readBody(req));
    const slug = slugify(path.basename(body.model_path || ''));
    const file = localAgentFile(slug);
    const sessions = await readJsonSafe(file, []);
    
    const history = body.initial_history || [];
    const baseName = body.original_title ? `[Fork] ${body.original_title}` : `Sesión local — ${labelize(slug)}`;

    const session = {
      id: `local_${slug}_${Date.now()}`,
      created_at: new Date().toISOString(),
      name: `${baseName} — ${new Date().toLocaleString('es-ES')}`,
      chat_messages: history,
    };

    sessions.push(session);
    await writeJsonAtomic(file, sessions);
    console.log(`🟢 [${new Date().toLocaleTimeString('es-ES')}] Sesión iniciada: ${session.name}`);
    res.end(JSON.stringify({ session_id: session.id, slug }));
    return;
  }

  if (pathname === '/api/chat/message' && req.method === 'POST') {
    const body = JSON.parse(await readBody(req));
    const { model_path, session_id, message } = body;
    const slug = slugify(path.basename(model_path || ''));
    const file = localAgentFile(slug);
    
    const sessions = await readJsonSafe(file, []);
    const session = sessions.find((s) => s.id === session_id);
    
    if (!session) {
      res.statusCode = 404;
      res.end(JSON.stringify({ error: 'Sesión no encontrada en el JSON' }));
      return;
    }

    const prompt = buildPrompt(session.chat_messages, message);
    let respuesta;
    
    try {
      respuesta = await runLlama(model_path, prompt);
    } catch (e) {
      console.error(`❌ [${new Date().toLocaleTimeString('es-ES')}] Error interno IA:`, e.message);
      res.statusCode = 500;
      res.end(JSON.stringify({ error: String(e.message || e) }));
      return;
    }

    session.chat_messages.push({ sender: 'human', text: message, timestamp: new Date().toISOString() });
    session.chat_messages.push({ sender: 'assistant', text: respuesta, timestamp: new Date().toISOString() });
    
    await writeJsonAtomic(file, sessions);
    res.end(JSON.stringify({ response: respuesta }));
    return;
  }

  if (pathname === '/api/chat/end' && req.method === 'POST') {
    const body = JSON.parse(await readBody(req));
    const { model_path, session_id } = body;
    const slug = slugify(path.basename(model_path || ''));
    const file = localAgentFile(slug);
    const sessions = await readJsonSafe(file, []);
    const session = sessions.find((s) => s.id === session_id);
    if (session) {
      session.ended_at = new Date().toISOString();
      await writeJsonAtomic(file, sessions);
      console.log(`🔴 [${new Date().toLocaleTimeString('es-ES')}] Sesión cerrada: ${slug}`);
    }
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  res.statusCode = 404;
  res.end(JSON.stringify({ error: 'Endpoint API no encontrado' }));
}

// 📁 Servidor estático
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.m4a': 'audio/mp4',
};

async function serveStatic(req, res, pathname) {
  let filePath = path.join(ROOT_DIR, decodeURIComponent(pathname));
  if (pathname === '/') filePath = path.join(ROOT_DIR, 'calendario_mental.html');
  
  if (!filePath.startsWith(ROOT_DIR)) {
    res.statusCode = 403;
    res.end('Prohibido');
    return;
  }
  
  try {
    const stat = await fsp.stat(filePath);
    if (stat.isDirectory()) {
      res.statusCode = 404;
      res.end('No encontrado');
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream');
    fs.createReadStream(filePath).pipe(res);
  } catch {
    res.statusCode = 404;
    res.end('No encontrado');
  }
}

// 🚀 Levantar el Servidor
const server = http.createServer(async (req, res) => {
  const pathname = req.url.split('?')[0];
  try {
    if (pathname.startsWith('/api/')) {
      await handleApi(req, res, pathname);
    } else {
      await serveStatic(req, res, pathname);
    }
  } catch (e) {
    res.statusCode = 500;
    res.end(JSON.stringify({ error: String(e.message || e) }));
  }
});

server.listen(PORT, () => {
  console.log(`\n======================================================`);
  console.log(`🟢 Calendario Mental escuchando en http://127.0.0.1:${PORT}`);
  console.log(`📂 Sirviendo HTML y JSON desde: ${ROOT_DIR}`);
  console.log(`🤖 Binario IA: ${MAIN_BINARY}`);
  console.log(`======================================================\n`);
});
