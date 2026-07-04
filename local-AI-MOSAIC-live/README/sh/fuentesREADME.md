# fuentes.sh

> FUENTES — coordinación de la ingesta: PULL con PRESUPUESTO por fuente.

## Qué hace

FUENTES — coordinación de la ingesta: PULL con PRESUPUESTO por fuente.
Modelo acordado: la COCINA pide; nada se produce sin hambre.
  · cada fuente es una función que recibe N (máx a añadir este ciclo)
  · se reparten los huecos libres de la cola por PRIORIDAD (escaso primero)
  · presupuesto/fuente = rate-limit (#63); MAX_COLA = backpressure dura
Así es IMPOSIBLE el autómata desbocado: ni más de lo que cabe, ni más del presupuesto.
Añadir una fuente = una función con el contrato fn(N) + una línea en REGISTRO (#62).
Uso:  ./fuentes.sh pull

## Piezas clave

- `cola_size`
- `fuente_cuarentena`
- `fuente_fabrica`
- `fuente_oraculo`
- `fuente_silo`
- `log`
- `pull`

---
_Auto-documentado desde la cabecera de `fuentes.sh`. Parte de MOSAIC._
