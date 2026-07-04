# fnc.py

> FNC — Composición Funcional Neopolilingüe como ARMA de FIRMEZA para MOSAIC.

## Qué hace

FNC — Composición Funcional Neopolilingüe como ARMA de FIRMEZA para MOSAIC.
Convierte una REGLA/PROHIBICIÓN en claro → versión FNC (EN estructura ·
DE técnico · ES intención · [JA imperativo opcional]) con un modelo FUERTE,
y la VALIDA con tu propio validate_prompt.py (portero de calidad, 0-100).
GATED: solo firma si MOSAIC_FNC=1 y la salida pasa el validador. Si no,
devuelve el texto EN CLARO (degradación elegante: NUNCA rompe el pipeline).
Cache: las reglas FIJAS se firman UNA vez (data/fnc_cache.json).
Uso:  echo "regla" | fnc.py firmar      ·      echo "texto" | fnc.py validar

## Piezas clave

- `_cache_load`
- `_cache_save`
- `_ja_imperativo`
- `_key`
- `_llm`
- `_meta_prompt`
- `_validador`
- `firmar`
- `validar`

---
_Auto-documentado desde la cabecera de `fnc.py`. Parte de MOSAIC._
