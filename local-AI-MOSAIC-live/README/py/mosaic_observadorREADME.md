# mosaic_observador.py

> 🔭 MOSAIC OBSERVADOR — lee UNA conversación y deposita UNA nota meta.json en el

## Qué hace

🔭 MOSAIC OBSERVADOR — lee UNA conversación y deposita UNA nota meta.json en el
🔭 formato EXACTO del calendario_mental: taxonomía de 5 niveles + calidad/confianza
🔭 + embedding MiniLM-384 (el MISMO que usa el dedup de MOSAIC) — y el ORO NUEVO:
🔭 'observacion' = qué CAPACIDAD/insight emerge para MOSAIC al leer esa conversación.
🔭 Normaliza la taxonomía LIMPIO (sin el bug ia→inteligencia-artificial del clasificador).
🔭 Degrada con elegancia: sin cluster/MiniLM produce una nota bien formada igualmente.
🔭 Uso:  python3 mosaic_observador.py CHAT.txt [carpeta_notas]

## Piezas clave

- `_json_de`
- `_llm`
- `_slug`
- `clasificar`
- `embed`
- `fecha_carta`
- `fecha_de`
- `main`
- `observar`

---
_Auto-documentado desde la cabecera de `mosaic_observador.py`. Parte de MOSAIC._
