# documentar.sh

> DOCUMENTAR — genera un README por cada script (.sh/.py) a partir de su

## Qué hace

DOCUMENTAR — genera un README por cada script (.sh/.py) a partir de su
CABECERA (propósito + uso) y sus funciones/defs. Los deposita en
README/<ext>/<nombre>README.md → subcarpetas por extensión (sh, py) para
que NO colisionen cuando coincide el nombre y cambia la extensión.
Re-ejecutable: regenera la doc cuando cambian los scripts.
Uso:  ./documentar.sh

## Piezas clave

- `cabecera`
- `docstring`
- `funciones`
- `log`

---
_Auto-documentado desde la cabecera de `documentar.sh`. Parte de MOSAIC._
