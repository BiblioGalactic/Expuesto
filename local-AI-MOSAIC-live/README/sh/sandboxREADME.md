# sandbox.sh

> SANDBOX — jaula para EJECUTAR código externo/no confiable sin riesgo.

## Qué hace

SANDBOX — jaula para EJECUTAR código externo/no confiable sin riesgo.
  macOS: sandbox-exec -> DENIEGA red + escritura solo dentro de la jaula.
  Siempre: jaula efímera, HOME/TMPDIR aislados, límites CPU/mem/procesos,
           timeout de pared y salida acotada. La jaula se destruye al salir.
  Uso:  ./sandbox.sh --script FICHERO     (copia y ejecuta con su intérprete)
        ./sandbox.sh -- CMD args...       (ejecuta un comando dentro)
Pieza de la rama defensa (#64): las lentes técnicas PRUEBAN aquí, contenidas.

## Piezas clave

- `cleanup`
- `con_timeout`
- `err`
- `interprete`
- `log`
- `main`
- `perfil_sb`
- `run_jaula`

---
_Auto-documentado desde la cabecera de `sandbox.sh`. Parte de MOSAIC._
