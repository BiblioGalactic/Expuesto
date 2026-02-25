# Setup paso a paso (producción casera)

## 0) Preparar

```bash
cd wa-llama-bridge-public
npm install
cp .env.example .env
```

## 1) Levantar modelo principal

Edita `scripts/run_llama_main.sh` con:
- `LLAMA_BIN`
- `MODEL_PATH`

Arranca:

```bash
bash scripts/run_llama_main.sh
```

Valida:

```bash
curl http://127.0.0.1:8080/v1/models
```

## 2) Configurar bridge

Edita `.env`:

- `LLM_BASE_URL=http://127.0.0.1:8080/v1`
- `LLM_MODEL=<id exacto que devuelve /v1/models>`
- `WA_PAIRING_PHONE=<tu numero sin espacios>`
- `ALLOW_FROM=<tu numero>`
- `SYSTEM_PROMPT_FILE=./prompts/prompt_main.txt`

Recomendado al principio:

```env
SELF_CHAT_ONLY=true
ALLOW_GROUPS=false
```

## 3) Vincular WhatsApp

### Modo código (recomendado)

```env
WA_USE_PAIRING_CODE=true
WA_SHOW_QR=false
```

Ejecuta:

```bash
node bridge.js
```

Usa el código en:
Dispositivos vinculados -> Vincular dispositivo -> Vincular con número.

### Modo QR (alternativa)

```env
WA_USE_PAIRING_CODE=false
WA_SHOW_QR=true
```

## 4) Fallback (opcional)

Levanta segundo modelo (otro puerto/máquina):

```bash
bash scripts/run_llama_fallback.sh
```

Y en `.env`:

```env
LLM_FALLBACK_BASE_URL=http://127.0.0.1:8081/v1
LLM_FALLBACK_MODEL=<id fallback>
```

## 5) Watchdog

```bash
bash watchdog.sh
```

## 6) Gateway OpenClaw (opcional)

Si además quieres OpenClaw para otras cosas:

```bash
bash scripts/run_openclaw_gateway_optional.sh
```

Nota: el bridge no depende de este paso.
