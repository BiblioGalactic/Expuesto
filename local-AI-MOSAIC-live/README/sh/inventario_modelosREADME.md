# inventario_modelos.sh

> INVENTARIO DE MODELOS — escanea QUÉ modelos de IA hay y los clasifica por

## Qué hace

INVENTARIO DE MODELOS — escanea QUÉ modelos de IA hay y los clasifica por
capacidad (LLM · visión · imagen · OCR · detección · ASR · separación ·
TTS · hablantes · embeddings). Sirve para decidir qué mover a la SSD (#45)
y qué capacidades enchufar (#76+). Corre igual en el MacBook y en el mini.
Incluye cachés (~/.cache, ~/Library) y SSD externas (/Volumes/*).
Uso:  bash inventario_modelos.sh [raíces extra...]
      ssh MINI 'bash -s' < inventario_modelos.sh      (escanea el mini + su SSD)

## Piezas clave

- `clasifica`
- `cleanup`

---
_Auto-documentado desde la cabecera de `inventario_modelos.sh`. Parte de MOSAIC._
