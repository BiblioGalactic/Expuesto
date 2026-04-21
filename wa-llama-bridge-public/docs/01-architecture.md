# Arquitectura

## Por que la arquitectura es tan corta

Este bridge no intenta ser un framework. Lo diseñe para que el recorrido de un mensaje fuese lo bastante corto como para depurarlo sin adivinar:

1. WhatsApp entrega el mensaje a Baileys.
2. `bridge.js` decide si entra texto, audio o imagen.
3. Si hay media, la transforma con la capa local o remota que este activada.
4. Construye el prompt con sistema, historial corto y entrada procesada.
5. Llama al modelo principal.
6. Si el principal falla, intenta fallback.
7. Responde por WhatsApp en chunks.

## Estado persistente

- `data/auth/`: sesion de WhatsApp Web.
- `data/history.json`: memoria corta por chat.
- `data/chat-enabled.json`: lista de chats activados.

La memoria es corta porque queria algo inspeccionable a mano. El coste es evidente: aqui no hay semantica larga ni RAG. Si un chat necesita eso, este no es el modulo.

## Politica de activacion

- por defecto: chat apagado,
- `/on`: habilita el chat actual,
- `/off`: lo vuelve a apagar.

No lo hice para "parecer seguro". Lo hice porque una sesion vinculada en WhatsApp merece una barrera explicita antes de responder sola.

## Relacion con OpenClaw

OpenClaw queda fuera del camino principal. Si lo meto en medio, gano orquestacion pero pierdo claridad operacional. Para este repo prefiero poder seguir un mensaje extremo a extremo sin tres capas mas de abstraccion.
