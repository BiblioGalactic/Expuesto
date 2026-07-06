# escalado.sh

> 🎫 ESCALADO — el CLI humano del libro de ESCALACIONES (plan Opus 13:56:

## Qué hace

🎫 ESCALADO — el CLI humano del libro de ESCALACIONES (plan Opus 13:56:
🎫   modelo de mission-control adaptado — json, sin sqlite, sin web).
🎫   TODA la lógica vive en herramientas.py (--esc …): una sola fuente de
🎫   permisos en el sistema; esto solo enseña bonito y firma como «humano».
🎫   La escalera: denegado → ticket abierto → AUTO-DISPATCH por la cadena del
🎫   organigrama (lead → manager → N1 → humano). Los agentes resuelven EN SU
🎫   TURNO; aquí resuelve la mano de confianza (Gustavo = final de toda cadena).
🎫   conceder EJECUTA la tool (resuelto = concedido+ejecutado) · nivel 5 →
🎫   esperando_sello (el doble sello es el último peldaño) · TTL → caducado+archivo.
🎫 Uso:  ./escalado.sh listar [abierto|escalado|en_revision|resuelto|denegado|esperando_sello]
🎫       ./escalado.sh ver      <ESC-id>
🎫       ./escalado.sh conceder <ESC-id> ["nota"]
🎫       ./escalado.sh denegar  <ESC-id> ["porqué"]
🎫       ./escalado.sh escalar  <ESC-id> ["nota"]     (subirlo un peldaño a mano)
🎫       ./escalado.sh caducar                        (barrido TTL a mano)
🎫   (tickets TCK-… = libro LEGADO tickets_escalado.jsonl: solo canje --ticket)

## Piezas clave

- `ejecutar`
- `err`
- `log`
- `validar`

---
_Auto-documentado desde la cabecera de `escalado.sh`. Parte de MOSAIC._
