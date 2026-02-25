# WhatsApp -> llama.cpp Bridge (Public)

Template publico para montar una IA personal en WhatsApp con puente directo:

`WhatsApp` -> `bridge.js` -> `llama-server (OpenAI-compatible)`

Sin motor de agente de OpenClaw en medio.

## Capacidades incluidas

- Chat normal por WhatsApp con memoria corta por chat.
- Activacion por chat con `/on` y desactivacion con `/off`.
- Login por codigo de vinculacion o QR.
- Modelo principal + fallback opcional.
- `/web <url> [pregunta]` para extraer texto de web y responder con contexto.
- Audio a texto:
  - API STT compatible OpenAI, o
  - STT local (Whisper) via `tools/stt_local.py`.
- OCR local con `/ocr` en imagen via `tools/ocr_local.py`.
- Analisis automatico de imagen (OCR + VLM + YOLO + LLM).
- Generacion local de imagen con `/img <prompt>` via `tools/image_local.py`.

## Estructura

- `bridge.js`: runtime principal del puente.
- `.env.example`: configuracion completa (base + multimodal).
- `tools/`: utilidades Python locales (STT/OCR/VLM/YOLO/imagen).
- `scripts/`: arranque de llama principal/fallback, bridge y gateway opcional.
- `docs/`: guia completa paso a paso.

## Quickstart

```bash
cd wa-llama-bridge-public
npm install
cp .env.example .env
```

1. Edita `.env` con tus rutas y numero.
2. Arranca llama-server:

```bash
bash scripts/run_llama_main.sh
```

3. Comprueba API:

```bash
curl http://127.0.0.1:8080/v1/models
```

4. Arranca bridge:

```bash
bash scripts/run_bridge.sh
```

## Vincular WhatsApp

Modo recomendado (codigo):

```env
WA_USE_PAIRING_CODE=true
WA_SHOW_QR=false
```

En WhatsApp movil:

1. Dispositivos vinculados
2. Vincular un dispositivo
3. Vincular con numero de telefono
4. Introducir el codigo mostrado por bridge

## Comandos de chat

- `/on` activar chat actual
- `/off` desactivar chat actual
- `/help`
- `/reset` o `/new`
- `/model`
- `/status`
- `/web <url> [pregunta]`
- `/ocr [pregunta]` (como caption o reply a imagen)
- `/img <prompt>`

## Nota importante de activacion

Por seguridad, cada chat arranca desactivado. Debes enviar `/on` en ese chat para que el asistente responda.

## Seguridad para publicar

- No subir nunca `.env` real.
- No subir `data/auth/` ni `data/history.json`.
- No subir tokens, numeros reales ni rutas privadas.

## Firma

Autor: Eto Demerzel (Gustavo Silva Da Costa)
