# Troubleshooting

## `All models failed` o `fetch failed`

Lo primero que compruebo no es el bridge, sino `llama-server`:

```bash
curl http://127.0.0.1:8080/v1/models
```

Si aqui no responde, el resto del flujo da igual.

## `failed to request pairing code` o logout 401

Cuando el login se corrompe, suelo perder menos tiempo borrando sesion que intentando salvarla:

```bash
rm -rf data/auth
```

Luego reinicio el bridge y vuelvo a vincular.

## No responde en un chat

Revisa en este orden:

1. enviaste `/on`,
2. `SELF_CHAT_ONLY` no te esta cerrando el paso,
3. `ALLOW_FROM` no te esta filtrando.

## `ffmpeg was not found`

```bash
brew install ffmpeg
which ffmpeg
```

## Audio local: `out of range integral type conversion attempted`

Este error me aparecio con audios raros o mal convertidos. El wrapper ya intenta un modo mas compatible, pero si persiste, vuelve a probar con un archivo mas corto antes de depurar toda la cadena.

## OCR: `No module named 'paddle'`

La capa OCR depende de su propio entorno Python:

```bash
python -m pip install paddlepaddle paddleocr
```

## OCR: `Unknown argument: show_log`

Suele ser desfase entre versiones de PaddleOCR. El wrapper intenta adaptarse, pero no todas las combinaciones de version responden igual.

## Imagen local no responde

Confirma que el flag este realmente activo:

```env
LOCAL_IMAGE_ENABLED=true
```

## Respuestas duplicadas

Si convive con otro bot o con OpenClaw, el problema casi nunca es el LLM. El problema es que dos procesos creen que les toca responder al mismo chat.
