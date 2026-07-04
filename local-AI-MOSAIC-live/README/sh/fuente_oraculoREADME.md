# fuente_oraculo.sh

> FUENTE ORÁCULO — adaptador: convierte los HALLAZGOS del oráculo de código

## Qué hace

FUENTE ORÁCULO — adaptador: convierte los HALLAZGOS del oráculo de código
(~/oraculo) en TAREAS de MOSAIC y las encola (fuente=oraculo). El oráculo
descubre repos; MOSAIC los usa para exponer huecos y crear capacidades.
NO reimplementa el crawler: lo puentea. Idempotente y reanudable (registro 'vistos').
Lee tanto hallazgos/ vivos como los lotes/*.tar.gz comprimidos.
Uso:  ./fuente_oraculo.sh            (una pasada; encola lo nuevo con nota suficiente)

## Piezas clave

- `ejecutar`
- `err`
- `log`
- `meta_de`
- `procesar`
- `validar`

---
_Auto-documentado desde la cabecera de `fuente_oraculo.sh`. Parte de MOSAIC._
