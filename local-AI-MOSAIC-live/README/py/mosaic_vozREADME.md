# mosaic_voz.py

> 🤖 VOZ — el parte de guardia de MOSAIC en la mesa (idea de Gustavo,

## Qué hace

🤖 VOZ — el parte de guardia de MOSAIC en la mesa (idea de Gustavo,
🤖 arnés de Opus, construcción de Fable — carta del 2-jul-2026).
🤖 En FASE 0, MOSAIC deja en info/CARTAS.md un TELEGRAMA factual:
🤖 determinista, parseado de sus datos reales (perfil + última acta),
🤖 SIN modelo, SIN adornos — "el sistema dando su parte", no un diario.
🤖 Guardia anti-inundación: solo escribe si su parte CAMBIÓ desde el
🤖 último (huella en data/.voz_ultimo). Auditable por Opus contra las fuentes.
🤖 Uso:  python3 mosaic_voz.py [--forzar]

## Piezas clave

- `leer_json`
- `main`
- `ultima_acta`

---
_Auto-documentado desde la cabecera de `mosaic_voz.py`. Parte de MOSAIC._
