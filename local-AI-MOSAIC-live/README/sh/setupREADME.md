# setup.sh

> 🧰 SETUP — prepara un clon RECIÉN CLONADO de MOSAIC para su primer ciclo.

## Qué hace

🧰 SETUP — prepara un clon RECIÉN CLONADO de MOSAIC para su primer ciclo.
🧰   1) valida binarios (núcleo obligatorio · formatos opcionales)
🧰   2) crea la estructura de directorios (data/ silo/ trash/ …)
🧰   3) copia .env.example → .env si no existe (NUNCA pisa el tuyo)
🧰   4) selftest offline: sintaxis de todos los .sh y compilación de los .py
🧰 No instala nada por ti: te dice QUÉ falta y CÓMO conseguirlo.
🧰 Idempotente: puedes lanzarlo las veces que quieras.
🧰 Uso:  ./setup.sh

## Piezas clave

- `cleanup`
- `entorno`
- `estructura`
- `log`
- `mirar`
- `selftest`
- `validar`
- `warn`

---
_Auto-documentado desde la cabecera de `setup.sh`. Parte de MOSAIC._
