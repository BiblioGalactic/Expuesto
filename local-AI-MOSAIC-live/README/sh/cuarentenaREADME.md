# cuarentena.sh

> CUARENTENA — código EXTERNO no confiable (de GitHub) → defensa → cola.

## Qué hace

CUARENTENA — código EXTERNO no confiable (de GitHub) → defensa → cola.
Misma lógica de LOTES que el silo, PERO aquí cada item es código de
desconocidos: pasa por defensa.py (sandbox + 3 lentes + juez) ANTES de
confiar. Lo SEGURO entra a la cola (fuente=cuarentena); lo que huele a
TRAMPA/DUDOSO genera capacidad de seguridad (vía gobernanza) y NO entra.
Uso:  ./cuarentena.sh clonar     (trae los hallazgos KEEP del oráculo)
      ./cuarentena.sh procesar   (analiza por lotes lo que haya)
      ./cuarentena.sh estado

## Piezas clave

- `clonar`
- `contar`
- `ejecutar`
- `log`
- `procesar_uno`
- `validar`
- `warn`

---
_Auto-documentado desde la cabecera de `cuarentena.sh`. Parte de MOSAIC._
