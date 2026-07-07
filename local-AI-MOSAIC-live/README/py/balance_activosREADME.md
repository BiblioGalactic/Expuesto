# balance_activos.py

> 💰 BALANCE_ACTIVOS v0 — el balance de la empresa, SOLO LECTURA (P-resto del plan 6-jul).

## Qué hace

💰 BALANCE_ACTIVOS v0 — el balance de la empresa, SOLO LECTURA (P-resto del plan 6-jul).
Implementa la fórmula de FableEnLaSombra 18:04 (D20 del PLAN_MESA) SIN tocar la bolsa:
NO escribe ranking, NO cotiza, NO persiste — imprime el balance y se va. Es el banco de
pruebas para que Opus FIRME (o corrija) la fórmula viéndola correr sobre datos reales;
cablearlo a valorar_empresa.py es un paso POSTERIOR, tras su lupa.

ACTIVOS (todo DERIVADO, jamás inventado — auditable con cat):
  · biblioteca  = Σ score × log(1+uso) de las capacidades VIVAS (state.json)
  · packs       = inventario importado/exportable (ficheros pack_* en capabilities/)
  · reputación  = acciones selladas(lista/ejecutada) − vetadas (data/acciones.json)
  · experiencia = actas registradas (data/actas/)
  MULTIPLICADOR = CRAG (data/estado_sistema.json — la señal honesta, la nota saturó)
  DEPRECIACIÓN  = archived (caps dormidas restan a razón de su score visible)

Uso:  python3 balance_activos.py [--json]      (sin flags: tabla legible)

## Piezas clave

- `balance`
- `carga`

---
_Auto-documentado desde la cabecera de `balance_activos.py`. Parte de MOSAIC._
