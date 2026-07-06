# archivado.sh

> 🗄️ ARCHIVADO — rota CARTAS.md cuando pesa (RONDA 4 · diseño Opus).

## Qué hace

🗄️ ARCHIVADO — rota CARTAS.md cuando pesa (RONDA 4 · diseño Opus).
🗄️   Lo VIEJO (~70%, cortado en FRONTERA de cabecera '## ', jamás a media
🗄️   carta) → info/historico/CARTAS_YYYY-MM.md. Reabre un CARTAS ligero con
🗄️   RESUMEN EJECUTIVO determinista (índice de lo archivado + estado del sistema).
🗄️   CARTAS = fuente ÚNICA (Gustavo). MISMO cerrojo que reportar.sh (sin carreras).
🗄️   Corte por LÍNEAS (no bytes): inmune al multibyte de los emojis.
🗄️ Criterios (con --aplicar aplica si se cumple ALGUNO; --forzar salta el gate):
🗄️   tamaño > CARTAS_MAX_KB (450) · el día 1 del mes · manual.
🗄️ Uso:  ./archivado.sh            (DRY-RUN: enseña el plan)
🗄️       ./archivado.sh --aplicar  [--forzar]

## Piezas clave

- `cleanup`
- `ejecutar`
- `err`
- `frontera`
- `log`
- `toca_archivar`
- `validar`

---
_Auto-documentado desde la cabecera de `archivado.sh`. Parte de MOSAIC._
