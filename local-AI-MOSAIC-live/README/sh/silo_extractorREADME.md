# silo_extractor.sh

> SILO EXTRACTOR — convierte un archivo NO apto para IA en TEXTO plano.

## Qué hace

SILO EXTRACTOR — convierte un archivo NO apto para IA en TEXTO plano.
Lo ÚTIL (transcripción, OCR, texto) → silo/ (.txt, para ingerir).
Los SUBPRODUCTOS (vídeo, audio extraído, intermedios) → silo/extraciones/
(se GUARDAN, nunca se ingieren ni se borran).
Usa las MISMAS herramientas que tus scripts (ffmpeg, whisper, tesseract,
pdftotext) pero NO interactivo. Tus scripts fueron la referencia.
Uso:  ./silo_extractor.sh ARCHIVO   ·   return 0 = sacó texto · 1 = falló · 2 = no aplica

## Piezas clave

- `extraer`
- `log`
- `transcribir`

---
_Auto-documentado desde la cabecera de `silo_extractor.sh`. Parte de MOSAIC._
