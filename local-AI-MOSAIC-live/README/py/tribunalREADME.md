# tribunal.py

> TRIBUNAL — un juez ADVERSARIAL en vez de uno solo (la rama para mejorar el juez).

## Qué hace

TRIBUNAL — un juez ADVERSARIAL en vez de uno solo (la rama para mejorar el juez).

Por cada respuesta: FISCAL (ataca) · ABOGADO (defiende) · ACUSACIÓN PARTICULAR (la voz
del usuario) -> JUEZ dicta veredicto leyendo los alegatos -> SALA DE APELACIÓN verifica
que el juez no fue negligente Y puntúa a cada actor. Los ROLES ROTAN entre los modelos
del pool. Los prompts de rol son CAPACIDADES MOSAIC (roles/juicio.yaml): editarlas/curarlas
las mejora, y su desempeño (data/juicio_scores.json) las ESPECIALIZA con el uso.

Todo se imprime EN TERMINAL (nada en segundo plano). Stdlib only (urllib).

Uso:
  ./tribunal.py "petición" "respuesta"                 # un juicio
  ./tribunal.py --ab "petición" "resp A" "resp B"      # dos juicios -> comparación
  ./tribunal.py --especializar                         # agrega recompensas -> scores
  ./tribunal.py --offline ...                          # sin red (mock, prueba el flujo)

## Piezas clave

- `_alegato`
- `_escribir_atomico`
- `_json`
- `_registrar`
- `_reparto`
- `cargar_roles`
- `especializar`
- `juicio`
- `juicio_lote`
- `llm`
- `main`

---
_Auto-documentado desde la cabecera de `tribunal.py`. Parte de MOSAIC._
