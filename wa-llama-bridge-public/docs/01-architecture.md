# Arquitectura

## Flujo principal

1. WhatsApp entrega mensaje al bridge (Baileys).
2. Bridge detecta tipo de entrada:
   - texto
   - audio
   - imagen
3. Si hay media:
   - audio -> STT API o STT local
   - imagen -> OCR / VLM / YOLO (segun flags)
4. Bridge construye prompt con:
   - system prompt
   - historial corto del chat
   - entrada procesada
5. Bridge llama al endpoint `chat/completions` del modelo principal.
6. Si falla principal, intenta fallback.
7. Bridge responde por WhatsApp en chunks.

## Estados persistentes

- `data/auth/`: sesion de WhatsApp Web.
- `data/history.json`: memoria corta por chat.
- `data/chat-enabled.json`: chats activados por `/on`.

## Politica de activacion

- Default: chat desactivado.
- `/on`: habilita ese chat.
- `/off`: deshabilita ese chat.

## Relacion con OpenClaw

Este bridge funciona solo.
OpenClaw queda opcional para otros canales o automatizaciones.

Firma: Eto Demerzel (Gustavo Silva Da Costa)
