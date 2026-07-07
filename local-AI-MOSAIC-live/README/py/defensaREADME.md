# defensa.py

> DEFENSA — analiza código/repos EXTERNOS con 3 LENTES repartidas por FUERZA del modelo:

## Qué hace

DEFENSA — analiza código/repos EXTERNOS con 3 LENTES repartidas por FUERZA del modelo:
  intención  -> Mythos (lee la trama: cebo, doble propósito, ingeniería social)
  código     -> Dolphin (pasada técnica: red, eval/exec, exfiltración, ofuscación)
  adversarial-> Unholy (red-team profundo; puede pedir PROBAR en sandbox)
Un JUEZ DE SEGURIDAD funde las tres -> veredicto TRAMPA/SEGURO/DUDOSO + riesgo, y destila
un 'patron_defensa' -> PROPUESTA de capacidad de 'seguridad' (a revisar, no entra sola).
Objetivo DEFENSIVO: reconocer y resistir, no fabricar. El código se prueba SIEMPRE en
sandbox.sh (#64). Stdlib only (urllib). Roles desde roles/defensa.yaml.

Uso:
  ./defensa.py --repo u/r --readme README.md --codigo code.py
  ./defensa.py --repo u/r --readme-text "..." --codigo-text "..."
  ./defensa.py ... --offline       # sin red (mock, prueba el flujo)
  ./defensa.py --mapa              # arranque en seco: mapa lente→modelo y sale (ACC-20260706-01)
Asignación lente→modelo: asignacion_lentes.conf (LA FUENTE ÚNICA, compartida con lentes.sh).

## Piezas clave

- `_arg`
- `_asig`
- `_ciega`
- `_conf_lentes`
- `_dignidad`
- `_en_sandbox`
- `_escribir_atomico`
- `_json`
- `_oxigeno`
- `_proponer_capacidad`
- `_registrar`
- `_slug`
- `_trazar`
- `analizar`
- `cargar_roles`
- `juzgar`
- `llm`
- `main`

---
_Auto-documentado desde la cabecera de `defensa.py`. Parte de MOSAIC._
