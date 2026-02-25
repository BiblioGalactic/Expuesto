# UPDATES 2026-02-25 - WA LLAMA BRIDGE PUBLIC

Fecha: 25 de febrero de 2026
Alcance: actualizacion de entregables publicos en `Expuesto/Expuesto`.

## Modulo actualizado

- `wa-llama-bridge-public/`

## Cambios integrados

1. Version funcional completa de `bridge.js` con:
- chat por WhatsApp con memoria corta,
- activacion por chat (`/on`) y desactivacion (`/off`),
- soporte de fallback de modelo,
- scraping web (`/web`),
- OCR (`/ocr`),
- generacion local de imagen (`/img`),
- analisis automatico de imagen (OCR + VLM + YOLO + LLM),
- STT por API o STT local.

2. Publicacion saneada:
- eliminadas rutas privadas y numeros personales de defaults,
- `.env.example` publico y portable,
- package name ajustado a `wa-llama-bridge-public`.

3. Herramientas locales incluidas en `tools/`:
- `stt_local.py`
- `ocr_local.py`
- `vlm_local.py`
- `yolo_local.py`
- `image_local.py`

4. Scripts de operacion:
- `scripts/run_llama_main.sh` (ctx-size 32000, flags de rendimiento)
- `scripts/run_llama_fallback.sh`
- `scripts/run_bridge.sh`
- `scripts/install_ffmpeg_macos.sh`
- `watchdog.sh`

5. Documentacion nueva/actualizada:
- `README.md`
- `docs/01-architecture.md`
- `docs/02-step-by-step.md`
- `docs/03-troubleshooting.md`
- `docs/04-controlroom-integration.md`

## Validacion aplicada

- Sintaxis Node validada en `bridge.js`.
- Busqueda de secretos y rutas privadas: sin coincidencias en modulo publico.

## Firma

Eto Demerzel (Gustavo Silva Da Costa)
