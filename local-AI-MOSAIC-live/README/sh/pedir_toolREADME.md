# pedir_tool.sh

> 🧰 PEDIR_TOOL — el CLI humano del dispatcher (v2 · manifiesto Opus 13:36).

## Qué hace

🧰 PEDIR_TOOL — el CLI humano del dispatcher (v2 · manifiesto Opus 13:36).
🧰   TODA la lógica de permisos/escalado/contrato vive en herramientas.py
🧰   (una sola fuente); esto solo construye el payload cómodo y enseña bonito.
🧰   Prioridad del ticket: LA FIJA EL AGENTE (--prioridad 1-5; default = nivel del tool).
🧰 Uso:  ./pedir_tool.sh <rol> <tool> [args…] [--prioridad N] [--ticket TCK-…]
🧰   args por tool: leer_registro RUTA · rag/buscar CONSULTA · web URL ·
🧰                  ocr RUTA · depositar "TEXTO"
🧰   crudo: ./pedir_tool.sh <rol> <tool> --json '{"campo":…}'

## Piezas clave

- `err`
- `log`

---
_Auto-documentado desde la cabecera de `pedir_tool.sh`. Parte de MOSAIC._
