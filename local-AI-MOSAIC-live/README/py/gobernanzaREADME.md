# gobernanza.py

> GOBERNANZA — la puerta por la que una capacidad PROPUESTA (del oráculo o de defensa) entra

## Qué hace

GOBERNANZA — la puerta por la que una capacidad PROPUESTA (del oráculo o de defensa) entra
(o no) en la biblioteca viva, SIN diluir. Tres filtros encadenados:
  #66 NOVEDAD      : ¿aporta algo nuevo? distancia al catálogo (semántica con MiniLM; léxica si no hay).
  #65 VERIFICACIÓN : ¿es una capacidad válida, general, no trivial? juez de curación (cuarentena).
  #67 STAGING      : lo que pasa va a un área de pruebas; 'promover' lo sube a capabilities/.

Uso:
  ./gobernanza.py revisar [--fuente data/seguridad_propuestas.yaml]   # propuestas -> staging / rechazo
  ./gobernanza.py promover                                            # staging -> capabilities/ (vivo)
  ./gobernanza.py estado
  ... --offline   # salta el juez (no bloquea), para probar el flujo

## Piezas clave

- `_append`
- `_dump`
- `_load`
- `estado`
- `juez_curacion`
- `live_patterns`
- `main`
- `promover`
- `revisar`

---
_Auto-documentado desde la cabecera de `gobernanza.py`. Parte de MOSAIC._
