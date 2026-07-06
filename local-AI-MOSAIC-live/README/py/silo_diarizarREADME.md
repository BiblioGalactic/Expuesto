# silo_diarizar.py

> SILO DIARIZAR (#77) — estima cuántos HABLANTES hay en un audio.

## Qué hace

SILO DIARIZAR (#77) — estima cuántos HABLANTES hay en un audio.
Usa resemblyzer (los mismos embeddings de tu compara_voces) + clustering
aglomerativo eligiendo k por silhouette. Imprime UN entero:
  0 = no disponible (faltan libs / audio) · 1+ = nº estimado de hablantes.
Degrada con elegancia: nunca lanza excepción al llamador.
Uso:  python3 silo_diarizar.py audio.wav        (DIAR_PY = python del entorno con resemblyzer)

## Piezas clave

- `contar`

---
_Auto-documentado desde la cabecera de `silo_diarizar.py`. Parte de MOSAIC._
