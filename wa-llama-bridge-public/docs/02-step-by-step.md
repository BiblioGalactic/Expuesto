# Paso a paso

## 1) Instalar bridge

```bash
cd wa-llama-bridge-public
npm install
cp .env.example .env
```

## 2) Configurar modelo principal

Edita `scripts/run_llama_main.sh`:

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

## 3) Configurar `.env`

Minimo obligatorio:

- `LLM_BASE_URL`
- `LLM_MODEL`
- `WA_PAIRING_PHONE`
- `ALLOW_FROM`
- `SYSTEM_PROMPT_FILE` o `SYSTEM_PROMPT`

## 4) Vincular WhatsApp

Modo codigo recomendado:

```env
WA_USE_PAIRING_CODE=true
WA_SHOW_QR=false
```

Arranca bridge:

```bash
bash scripts/run_bridge.sh
```

## 5) Activar chat

En el chat de WhatsApp donde quieras usar IA:

```text
/on
```

Comprobar:

```text
/status
```

## 6) Fallback opcional

Arranca fallback:

```bash
bash scripts/run_llama_fallback.sh
```

Activa en `.env`:

```env
LLM_FALLBACK_BASE_URL=http://127.0.0.1:8081/v1
LLM_FALLBACK_MODEL=/absolute/path/to/fallback-model.gguf
```

## 7) Multimodal local opcional

### STT local (audio)

1. Instala `ffmpeg`:

```bash
brew install ffmpeg
```

2. Configura `LOCAL_STT_*` y activa:

```env
LOCAL_STT_ENABLED=true
```

### OCR local

Configura `LOCAL_OCR_*` y activa:

```env
LOCAL_OCR_ENABLED=true
```

### VLM + YOLO + analisis auto de imagen

Activa:

```env
LOCAL_VLM_ENABLED=true
LOCAL_YOLO_ENABLED=true
AUTO_IMAGE_ANALYZE_ENABLED=true
```

### Imagen local (`/img`)

Activa:

```env
LOCAL_IMAGE_ENABLED=true
```

Firma: Eto Demerzel (Gustavo Silva Da Costa)
