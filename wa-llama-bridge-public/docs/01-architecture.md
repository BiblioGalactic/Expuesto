# Arquitectura del puente

## Flujo principal

1. El usuario envía mensaje en WhatsApp.
2. `bridge.js` recibe el mensaje vía WebSocket de WhatsApp Web (Baileys).
3. El bridge construye contexto:
   - `system prompt` (archivo o variable)
   - historial corto por chat
   - mensaje del usuario
4. El bridge llama a `POST /v1/chat/completions` de `llama-server`.
5. La respuesta vuelve a WhatsApp.

## Componentes

- WhatsApp (móvil + dispositivo vinculado)
- Bridge Node.js (`bridge.js`)
- llama.cpp (`llama-server`)
- Fallback opcional (otro llama-server)

## Dónde vive el estado

- `data/auth/`:
  - Credenciales de sesión de WhatsApp Web.
  - Si hay `401 loggedOut`, borrar esta carpeta y volver a vincular.
- `data/history.json`:
  - Memoria por chat (lista corta de turnos user/assistant).
  - Controlada por:
    - `HISTORY_TURNS`
    - `MAX_HISTORY_CHARS`

## Prompt del sistema

Orden de prioridad:

1. `SYSTEM_PROMPT_FILE` (si existe y carga bien)
2. `SYSTEM_PROMPT` del `.env`

Esto permite separar “personalidad” del código.

## Relación con OpenClaw

- Este puente funciona solo, sin gateway.
- OpenClaw queda opcional para:
  - otros canales
  - automatizaciones
  - herramientas extra

Si usas ambos, evita respuestas duplicadas en el mismo chat.
