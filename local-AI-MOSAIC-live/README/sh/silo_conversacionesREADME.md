# silo_conversaciones.sh

> 🔭 SILO CONVERSACIONES — MOSAIC observa tu historial de chats de la MÁS ANTIGUA

## Qué hace

🔭 SILO CONVERSACIONES — MOSAIC observa tu historial de chats de la MÁS ANTIGUA
🔭 hacia HOY (evolución cronológica), depositando una nota en el calendario por cada
🔭 conversación (vía mosaic_observador.py). Reanudable (memoria unificada, ámbito
🔭 'conversaciones'). Cada chat es enorme (tamaño Gutenberg) → de UNA en una.
🔭 Relleno de BAJA PRIORIDAD: el modo 'idle' digiere solo cuando NO hay tareas y el
🔭 server sigue vivo, y CEDE el paso en cuanto llega trabajo real.
🔭 Uso:
🔭   ./silo_conversaciones.sh [N]    procesa N (def. 1) de la más antigua sin observar
🔭   ./silo_conversaciones.sh idle   bucle ocioso preemptable (máx CONV_IDLE_MIN min)

## Piezas clave

- `cola_size`
- `log`
- `modo_idle`
- `por_antiguedad`
- `procesar_n`
- `vivo`

---
_Auto-documentado desde la cabecera de `silo_conversaciones.sh`. Parte de MOSAIC._
