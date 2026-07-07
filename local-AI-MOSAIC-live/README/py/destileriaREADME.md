# destileria.py

> ⚗️ DESTILERÍA v0 — SOLO EL CANDADO Y EL PLAN (P10 del plan 6-jul · FÁBRICA v2 F1).

## Qué hace

⚗️ DESTILERÍA v0 — SOLO EL CANDADO Y EL PLAN (P10 del plan 6-jul · FÁBRICA v2 F1).
La destilería convertirá material REAL (conversaciones/preguntas ya existentes) en
alimento de la fábrica — pero NO SE ENCIENDE sin dos firmas de la mesa:
  · D6 (orden de visiones) y sobre todo D9: el OPT-IN de privacidad de Gustavo.

ESTE fichero, a conciencia, solo sabe hacer TRES cosas:
  1) negarse en seco si no existe data/destileria_incluir.yaml (el opt-in: SOLO entra
     lo que Gustavo liste ahí; lo no listado NO existe para la destilería);
  2) --plan: contar QUÉ entraría (ficheros por carpeta incluida) sin leer contenido;
  3) --preparar: volcar el LOTE con PROCEDENCIA a data/destileria_lote.jsonl (staging
     propio — JAMÁS toca cola.db: esa integración va tras la lupa de Opus, D8).

Formato de data/destileria_incluir.yaml (lo escribe GUSTAVO, nadie más):
  incluir:
    - conversaciones/exportadas       # rutas RELATIVAS a la base, carpetas o ficheros
    - notas_clasificadas
  presupuesto_por_tanda: 10           # D3: la vigilia es ACOTADA (default 10 ítems)

Kill-switch: DESTILERIA=0. Sin flags = enseña el candado y el estado.

## Piezas clave

- `candado`
- `inventario`
- `log`
- `main`

---
_Auto-documentado desde la cabecera de `destileria.py`. Parte de MOSAIC._
