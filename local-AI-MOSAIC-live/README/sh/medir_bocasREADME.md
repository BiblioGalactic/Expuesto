# medir_bocas.sh

> 📏 MEDIR_BOCAS — tokens/s REALES con N bocas concurrentes (el dato que

## Qué hace

📏 MEDIR_BOCAS — tokens/s REALES con N bocas concurrentes (el dato que
📏 exige Opus ANTES de paralelizar la FASE 2: ¿satura la GPU o hay margen?)
📏
📏 Uso:  ./medir_bocas.sh URL1 [URL2] [URL3] [URL4]
📏   FASE A: cada boca SOLA (línea base) · FASE B: TODAS A LA VEZ → veredicto.
📏 Ejemplos (con la flota arriba y OCIOSA — no en mitad de un ciclo):
📏   ./medir_bocas.sh http://127.0.0.1:8092/v1
📏   ./medir_bocas.sh http://127.0.0.1:8092/v1 http://127.0.0.1:8091/v1
📏   ./medir_bocas.sh http://localhost:8090/v1 http://localhost:8093/v1

## Piezas clave

- `cleanup`
- `ejecutar`
- `log`
- `pedir`
- `validar`
- `warn`

---
_Auto-documentado desde la cabecera de `medir_bocas.sh`. Parte de MOSAIC._
