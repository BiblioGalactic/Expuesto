# Paso a paso

Esta es la ruta corta que yo seguiria en una maquina nueva. Si intentas activar todo a la vez, lo normal es perder tiempo en capas que todavia no sabes si necesitas.

## 1) Levanta primero el modelo

```bash
cd wa-llama-bridge-public
npm install
cp .env.example .env
bash scripts/run_llama_main.sh
```

Comprueba antes de seguir:

```bash
curl http://127.0.0.1:8080/v1/models
```

Si esto falla, no abras WhatsApp todavia. Primero arregla el modelo.

## 2) Configura `.env` con lo minimo

No toques veinte flags de una vez. Para arrancar necesito:

- `LLM_BASE_URL`
- `LLM_MODEL`
- `WA_PAIRING_PHONE`
- `ALLOW_FROM`
- `SYSTEM_PROMPT_FILE` o `SYSTEM_PROMPT`

## 3) Vincula WhatsApp

El modo por codigo me dio menos guerra que el QR:

```env
WA_USE_PAIRING_CODE=true
WA_SHOW_QR=false
```

Luego:

```bash
bash scripts/run_bridge.sh
```

## 4) Activa solo el chat que vayas a usar

En WhatsApp:

```text
/on
/status
```

El gate por chat esta ahi a proposito. No lo quites para "ir mas rapido".

## 5) Añade fallback solo si el camino principal ya va bien

```bash
bash scripts/run_llama_fallback.sh
```

Y luego en `.env`:

```env
LLM_FALLBACK_BASE_URL=http://127.0.0.1:8081/v1
LLM_FALLBACK_MODEL=/ruta/absoluta/al/fallback.gguf
```

## 6) Activa multimodal por capas

Orden recomendado:

1. STT local
2. OCR local
3. VLM / YOLO
4. imagen local con `/img`

Cada capa nueva suma dependencias y puntos de fallo. Si una no te hace falta, dejala apagada.
