# silo_libros.sh

> SILO LIBROS — flujo continuo desde tu corpus Gutenberg (27 GB · 69k libros).

## Qué hace

SILO LIBROS — flujo continuo desde tu corpus Gutenberg (27 GB · 69k libros).
Si el silo se queda sin trabajo, toma N libros NO vistos, les quita el
boilerplate LEGAL de Gutenberg (marcadores *** START/END ***) y deja un
FRAGMENTO crudo en silo/ (libro_<lang>_<id>.txt).
El cuerpo queda SUCIO a propósito (saltos duros, notas, restos): es el
gimnasio para que MOSAIC haga EMERGER una capacidad de REFINADO/INGESTA.
No es conocimiento; es entrenar el ACTO de limpiar texto difícil.
Genera fragmentos (no toca tu corpus) + memoria UNIFICADA → sin agotar.
Uso:  ./silo_libros.sh [N]    (def. 3)

## Piezas clave

- `despelleja`
- `log`
- `titulo`

---
_Auto-documentado desde la cabecera de `silo_libros.sh`. Parte de MOSAIC._
