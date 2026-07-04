# lock.sh

> 🔒 lock.sh — lock PORTABLE (mkdir atómico, con caducidad). Evita que dos

## Qué hace

🔒 lock.sh — lock PORTABLE (mkdir atómico, con caducidad). Evita que dos
   orquestadores/consolidar se pisen (lost-update del state.json, doble cluster).
   Uso:   source lock.sh ; tomar_lock orquestador || exit 1 ; trap soltar_locks EXIT

## Piezas clave

- `soltar_locks`
- `tomar_lock`

---
_Auto-documentado desde la cabecera de `lock.sh`. Parte de MOSAIC._
