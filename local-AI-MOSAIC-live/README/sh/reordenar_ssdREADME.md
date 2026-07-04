# reordenar_ssd.sh

> REORDENAR SSD — consolida el zoo de modelos de la Extreme SSD en un árbol

## Qué hace

REORDENAR SSD — consolida el zoo de modelos de la Extreme SSD en un árbol
limpio por capacidad:  MODELOS/{llm,multimodal,audio,embed}.
MUEVE dentro de la MISMA SSD (instantáneo, 0 espacio extra). NO borra nada:
el cajón duplicado "modelos/" va a llm/_revisar/ para que TÚ decidas.
Por defecto DRY-RUN (solo enseña). Para hacerlo de verdad:  --aplicar
Uso (desde el MacBook, la SSD está en el mini):
  ssh MINI 'bash -s'              < reordenar_ssd.sh    # ver el plan
  ssh MINI 'bash -s -- --aplicar' < reordenar_ssd.sh    # ejecutarlo

## Piezas clave

- `crear`
- `log`
- `mover`
- `tam_mb`

---
_Auto-documentado desde la cabecera de `reordenar_ssd.sh`. Parte de MOSAIC._
