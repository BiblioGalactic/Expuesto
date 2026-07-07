# identidad.py

> 🪪 IDENTIDAD v1 — el resolver ÚNICO de autodeclaración (D19 del PLAN_MESA, 6-jul).

## Qué hace

🪪 IDENTIDAD v1 — el resolver ÚNICO de autodeclaración (D19 del PLAN_MESA, 6-jul).
Contrato: JSON-SUBPROCESS (mi recomendación en D19 — frontera dura contra el dios-módulo).
⚠️ AÚN NO CABLEADO A NADIE: Opus decide D19; si prefiere import, el mismo fichero sirve
(las funciones son importables). La migración de los 10 parsers será INCREMENTAL, cliente
a cliente, jamás big-bang (doctrina de la carta de Sombra 18:39).

Declara cada entidad en 3 capas DERIVADAS (fractal agente→depto→empresa):
  🔒 nucleo   — rol, nivel, departamento, tipo_reporte, puertos, nivel_acceso (roles/turnos/*.yaml)
  🎨 persona  — nombre, alias, emoji, tono (capa PERSONA del yaml; jamás cambia límites)
  💰 economia — derivada del libro: acciones propuestas/selladas/vetadas/ejecutadas por su firma

Uso (contrato JSON por stdout, un objeto por línea de invocación):
  python3 identidad.py --agente auditor
  python3 identidad.py --lista               (todas las sillas, núcleo mínimo)
  python3 identidad.py --self-test           (compara contra lectura yaml directa)

## Piezas clave

- `_economia`
- `_yaml`
- `declarar`
- `lista`
- `self_test`

---
_Auto-documentado desde la cabecera de `identidad.py`. Parte de MOSAIC._
