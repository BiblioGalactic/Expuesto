# gobernador.py

> 🧭 GOBERNADOR — FASE 6 · auto-afinar el LANZAMIENTO sobre valores ACOTADOS.

## Qué hace

🧭 GOBERNADOR — FASE 6 · auto-afinar el LANZAMIENTO sobre valores ACOTADOS.
🧭 Lee las últimas actas (FASE 7, data/actas/*.json) y escribe el perfil:
🧭   data/perfil_lanzamiento.json  (mandos → ciclo.sh los exporta al arrancar)
🧭   data/perfil_lanzamiento.md    (el PORQUÉ de cada decisión — auditable)
🧭 Reglas DETERMINISTAS con histéresis: 1 paso por mando y por ejecución,
🧭 siempre dentro de [min,max] duros. Con <3 actas NO decide (perfil neutro).
🧭 ⚠️  Decide por CRAG / huecos / A-B — JAMÁS por la nota (saturada).
🧭 ⚠️  FNC lleva CANDADO: el gobernador no puede encenderlo (falta evidencia).
🧭 Uso:  python3 gobernador.py [--n 5]     (n = actas a digerir)
🧭 = realización del #0: "normas de lanzamiento que emergen".

## Piezas clave

- `acotar`
- `decidir`
- `escribir`
- `leer_actas`
- `main`
- `media`
- `perfil_previo`

---
_Auto-documentado desde la cabecera de `gobernador.py`. Parte de MOSAIC._
