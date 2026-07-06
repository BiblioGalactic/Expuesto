# desplegar_recolector_mini.sh

> 🛰️ DESPLEGAR RECOLECTOR → MINI   ·   F6 (los 6 pasos de Opus)

## Qué hace

🛰️ DESPLEGAR RECOLECTOR → MINI   ·   F6 (los 6 pasos de Opus)
🛰️ El crawler de GitHub corre en el MINI (ocioso en FASE 1), juzga los repos
🛰️ con SU pequeño (no el 24B), deduplica LÉXICO (sin torch) y llena una
🛰️ despensa (~/oraculo). El MacBook la RECOGE sin esperar (fire-and-forget).
🛰️ Handoff por rsync: mini:~/oraculo/{hallazgos,lotes} → MacBook (cuarentena.sh clona).
🛰️ DRY-RUN por defecto.  Aplica con:  ./desplegar_recolector_mini.sh --aplicar

## Piezas clave

- `cleanup`
- `ejecutar`
- `err`
- `log`
- `mini`
- `ok`
- `push`
- `validar`
- `warn`

---
_Auto-documentado desde la cabecera de `desplegar_recolector_mini.sh`. Parte de MOSAIC._
