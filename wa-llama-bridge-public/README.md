# WhatsApp + llama.cpp (Public Guide)

Template público para montar un puente directo:

`WhatsApp (cuenta personal)` -> `Bridge Node.js` -> `llama-server (llama.cpp)`

Sin orquestación de agente (sin “carga extra” de prompt de control).

## 1) Qué incluye

- `bridge.js`: escucha WhatsApp y responde usando `chat/completions`.
- `.env.example`: configuración completa.
- `watchdog.sh`: auto-reinicio del bridge si cae.
- `prompts/`: plantillas de prompt.
- `scripts/`: ejemplos para arrancar `llama-server` (principal/fallback) y gateway opcional.
- `docs/`: arquitectura, setup y troubleshooting.

## 2) Requisitos

- Node.js 20+
- `llama-server` funcionando (llama.cpp build)
- WhatsApp en móvil para vincular dispositivo

## 3) Instalación

```bash
cd wa-llama-bridge-public
npm install
cp .env.example .env
```

Edita `.env`:

- `LLM_BASE_URL` -> URL del `llama-server` (ej. `http://127.0.0.1:8080/v1`)
- `LLM_MODEL` -> ID exacto del modelo (sale en `/v1/models`)
- `WA_PAIRING_PHONE` y `ALLOW_FROM` -> tu número
- `SYSTEM_PROMPT_FILE` -> ruta de prompt (`./prompts/prompt_main.txt` por defecto)

## 4) Arranque recomendado

1. Arranca llama-server (ver `scripts/run_llama_main.sh`)
2. Verifica:

```bash
curl http://127.0.0.1:8080/v1/models
```

3. Arranca bridge:

```bash
node bridge.js
```

o watchdog:

```bash
bash watchdog.sh
```

## 5) Vincular WhatsApp

### Opción A: código de vinculación (recomendado)

En `.env`:

```env
WA_USE_PAIRING_CODE=true
WA_SHOW_QR=false
```

Al arrancar verás `Pairing code: ...`.

En WhatsApp móvil:
1. Dispositivos vinculados
2. Vincular un dispositivo
3. Vincular con número de teléfono
4. Introducir código

### Opción B: QR

```env
WA_USE_PAIRING_CODE=false
WA_SHOW_QR=true
```

## 6) Prompt y memoria

- Prompt activo:
  - Si `SYSTEM_PROMPT_FILE` existe: se carga ese archivo.
  - Si falla: usa `SYSTEM_PROMPT` del `.env`.
- Memoria por chat: `data/history.json`
- Sesión WhatsApp (credenciales): `data/auth/`

Comandos útiles en WhatsApp:
- `/help`
- `/reset` o `/new` (limpia memoria del chat)
- `/model`
- `/status`

## 7) Gateway OpenClaw (opcional)

Este bridge no necesita gateway para funcionar.

Si quieres correr ambos:
- Bridge = IA directa para WhatsApp
- Gateway = otras integraciones/canales

Evita duplicados en WhatsApp:
- o paras OpenClaw en WhatsApp
- o limitas OpenClaw para que no responda en ese chat

## 8) Seguridad mínima

- No publiques `data/auth/`, `.env`, tokens o números reales.
- Mantén `SELF_CHAT_ONLY=true` hasta probar todo bien.
- Usa `ALLOW_FROM` para evitar respuestas a terceros.

## 9) Siguiente paso recomendado

Lee:
- `docs/01-architecture.md`
- `docs/02-step-by-step.md`
- `docs/03-troubleshooting.md`
