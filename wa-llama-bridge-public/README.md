# WhatsApp -> llama.cpp Bridge

Hice este bridge porque queria el camino mas corto posible entre un chat de WhatsApp y un modelo local. Probe capas mas grandes de orquestacion y, para este canal concreto, me estaban costando mas de lo que aportaban. Aqui la ruta es deliberadamente corta:

`WhatsApp -> Baileys -> bridge.js -> llama-server`

## Que problema resuelve

- responder desde WhatsApp sin depender de API externa de chat,
- mantener memoria corta por chat,
- permitir fallback de modelo sin reescribir el flujo,
- conectar OCR, STT o vision local solo cuando de verdad los necesito.

## Decision importante: los chats nacen apagados

Cada chat arranca desactivado y hay que enviar `/on` manualmente. Lo deje asi por una razon simple: el peor fallo de este bridge no es que no responda, sino que responda en el sitio equivocado.

## Lo que incluye

- chat basico con memoria corta,
- activacion y desactivacion por chat con `/on` y `/off`,
- login por codigo de vinculacion o QR,
- modelo principal con fallback opcional,
- `/web` para extraer contexto de una URL,
- STT, OCR, VLM, YOLO e imagen local como capas opcionales.

## Lo que no voy a fingir

- Esto no es memoria larga. `data/history.json` es corta y deliberadamente simple.
- Las capas multimodales dependen de Python local y son las primeras en romperse cuando el entorno deriva.
- `npm audit` sigue reportando 3 vulnerabilidades criticas aguas arriba en Baileys/libsignal/protobufjs. No lo tapo porque no es una deuda imaginaria.

## Estructura

- `bridge.js`: runtime principal.
- `tools/`: OCR, STT, VLM, YOLO e imagen local.
- `scripts/`: arranque de modelo principal, fallback y bridge.
- `docs/`: arquitectura, operacion y troubleshooting.
- `prompts/`: prompts del sistema y ejemplos de persona.

## Arranque minimo

```bash
cd wa-llama-bridge-public
npm install
cp .env.example .env
```

1. Ajusta `.env`.
2. Levanta `llama-server`.
3. Comprueba `http://127.0.0.1:8080/v1/models`.
4. Arranca el bridge.

## Comandos utiles

- `/on`
- `/off`
- `/status`
- `/reset`
- `/model`
- `/web <url> [pregunta]`
- `/ocr [pregunta]`
- `/img <prompt>`

## Si vienes a mantenerlo

No intentes meter aqui una plataforma completa. El valor del repo es precisamente que el flujo es corto y auditable. Cuando una funcionalidad nueva complique demasiado el camino principal, prefiero dejarla opcional o fuera.
