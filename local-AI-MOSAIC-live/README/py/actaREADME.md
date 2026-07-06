# acta.py

> 📜 ACTA — FASE 7 · el acta del ciclo (propiocepción)

## Qué hace

📜 ACTA — FASE 7 · el acta del ciclo (propiocepción)
📜 Destila la última tanda (resultados/aprendizaje_*) + panel en UN acta:
📜   data/actas/acta_<ts_tanda>.json  (máquina → para la FASE 6)
📜   data/actas/acta_<ts_tanda>.md    (humano, media página)
📜 Sin modelos, sin red: parse determinista de lo ya destilado
📜 (registros.json / analisis.md / aprendizaje.md / ab.json / META.md).
📜 ⚠️  La NOTA solo se REGISTRA, jamás decide (señal real = CRAG).
📜 Uso:  python3 acta.py [--dir resultados/aprendizaje_X] [--forzar]

## Piezas clave

- `destilar_ab`
- `destilar_analisis`
- `destilar_capacidades`
- `destilar_registros`
- `escribir_md`
- `huecos_globales`
- `leer_banco`
- `leer_json`
- `leer_meseta`
- `leer_texto`
- `main`
- `ultima_tanda`

---
_Auto-documentado desde la cabecera de `acta.py`. Parte de MOSAIC._
