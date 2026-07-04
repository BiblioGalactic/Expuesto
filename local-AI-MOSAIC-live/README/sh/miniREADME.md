# mini.sh

> MINI — control del "segundo cerebro" (Mac mini) DESDE el MacBook, por SSH.

## Qué hace

MINI — control del "segundo cerebro" (Mac mini) DESDE el MacBook, por SSH.
Lo lanzamos con nohup (sobrevive al cierre de sesión) -> Ctrl+C NO lo para:
hay que pararlo a propósito con 'parar' (mata el PID guardado + pkill de respaldo).
Uso:  ./mini.sh lanzar | parar | reiniciar | estado | ver

## Piezas clave

- `err`
- `estado`
- `lanzar`
- `log`
- `parar`
- `reiniciar`
- `ver`

---
_Auto-documentado desde la cabecera de `mini.sh`. Parte de MOSAIC._
