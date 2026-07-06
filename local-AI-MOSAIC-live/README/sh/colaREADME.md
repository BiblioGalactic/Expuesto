# cola.sh

> 📥 COLA — buzón de preguntas en SQLite (productores encolan, 1 worker procesa).

## Qué hace

📥 COLA — buzón de preguntas en SQLite (productores encolan, 1 worker procesa).
📥   ./cola.sh add "pregunta" [fuente]   -> encola (tú, o la fábrica)
📥   ./cola.sh run [--once]              -> worker: saca y pasa a mosaic, 1 a 1
📥   ./cola.sh ver | size | hechas       -> estado de la cola
📥 Claim ATÓMICO (UPDATE..RETURNING + WAL): no se reparte dos veces aunque haya
📥 varios workers. Escala a cientos de miles sin el viejo problema de 'ls *.json'.
📥 Reanudable: lo que quedó 'procesando' tras un Ctrl+C vuelve a pendiente.

## Piezas clave

- `_cuenta`
- `add`
- `cluster_vivo`
- `confirmar`
- `db_init`
- `discriminar`
- `err`
- `esperar_si_pausa`
- `fuentes_stats`
- `hechas`
- `log`
- `run`
- `size`
- `ver`
- `volcar`

---
_Auto-documentado desde la cabecera de `cola.sh`. Parte de MOSAIC._
