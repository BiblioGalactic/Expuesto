# Troubleshooting

## `[bridge] Error: All models failed ... fetch failed`

Causa: `llama-server` no esta levantado o URL/modelo incorrectos.

Validar:

```bash
curl http://127.0.0.1:8080/v1/models
```

## `failed to request pairing code` o logout 401

1. Borra sesion local:

```bash
rm -rf data/auth
```

2. Reinicia bridge y vuelve a vincular.

## No responde en un chat

Revisa:

- Debes enviar `/on` en ese chat.
- `SELF_CHAT_ONLY` puede bloquear otros chats.
- `ALLOW_FROM` puede filtrar remitentes.

## Audio falla: `ffmpeg was not found`

Instala y verifica:

```bash
brew install ffmpeg
which ffmpeg
```

## Audio local falla: `out of range integral type conversion attempted`

El tool local ya reintenta con modo compatible; suele ocurrir en audios problematicos.
Actualiza bridge y vuelve a probar.

## OCR falla: `No module named 'paddle'`

Instala dependencias en el entorno Python de OCR:

```bash
python -m pip install paddlepaddle paddleocr
```

## OCR falla: `Unknown argument: show_log`

Ya corregido en esta version: el wrapper detecta parametros compatibles segun version.

## Imagen local desactivada

Activa:

```env
LOCAL_IMAGE_ENABLED=true
```

## Duplicados de respuesta

Si convive con OpenClaw, evita que ambos respondan en el mismo chat.

Firma: Eto Demerzel (Gustavo Silva Da Costa)
