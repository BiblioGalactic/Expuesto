# mosaic_extraer_conversaciones.py

> MOSAIC EXTRAER CONVERSACIONES (Paso B) — lee exports de IA y saca UNA conversación

## Qué hace

MOSAIC EXTRAER CONVERSACIONES (Paso B) — lee exports de IA y saca UNA conversación
por .txt con FECHA en el nombre, para que luego silo_conversaciones.sh las observe
de la MÁS ANTIGUA a hoy. Detecta el esquema como tu analize_json.py:
  · ChatGPT  → 'mapping' (árbol de mensajes por uuid; fecha = create_time)
  · Claude   → 'chat_messages' (lista sender/text; fecha = created_at)
  · Gemini   → 'messages' (role/content)
RAM acotada: procesa UN export a la vez (el JSON grande se libera al pasar al siguiente).
Uso:  python3 mosaic_extraer_conversaciones.py export1.json [export2.json ...]
      (destino: CONV_TXT_DIR, def. calendario_mental/conversaciones_txt)

## Piezas clave

- `_fecha`
- `_slug`
- `_txt_lista`
- `_txt_mapping`
- `conversaciones`
- `main`

---
_Auto-documentado desde la cabecera de `mosaic_extraer_conversaciones.py`. Parte de MOSAIC._
