# silo.sh

> SILO — depósito de archivos locales → cola, por LOTES y por EXTENSIÓN.

## Qué hace

SILO — depósito de archivos locales → cola, por LOTES y por EXTENSIÓN.
Tiras CUALQUIER archivo a silo/. Cuando hay ≥ LOTE, activa ese lote; el
resto espera. Cada archivo se discrimina por extensión y se convierte a
texto (pdf/audio/img→texto), se envuelve como TAREA y entra a la cola
(fuente=silo). Originales → silo/.hechos (nunca se borran).
Uso:  ./silo.sh           (procesa lo que haya por lotes)
      ./silo.sh estado    (cuántos archivos esperando)

## Piezas clave

- `contar`
- `convertir`
- `dedup_lote`
- `ejecutar`
- `log`
- `procesar_uno`
- `validar`
- `warn`

---
_Auto-documentado desde la cabecera de `silo.sh`. Parte de MOSAIC._
