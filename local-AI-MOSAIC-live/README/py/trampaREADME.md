# trampa.py

> TRAMPA — red-team de ROBUSTEZ (lado ofensivo de la rama seguridad, #44).

## Qué hace

TRAMPA — red-team de ROBUSTEZ (lado ofensivo de la rama seguridad, #44).
Bucle: ATACANTE (modelo sin censura) inventa un intento de MANIPULACIÓN de una categoría →
DEFENSOR (MOSAIC, con sus capacidades de seguridad actuales) intenta RESISTIR →
ÁRBITRO juzga si resistió o cayó; si cayó, destila la lección defensiva → PROPUESTA de
capacidad de 'seguridad' (a data/seguridad_propuestas.yaml → gobernanza decide si entra).
Lleva un score de resistencia POR categoría (dónde MOSAIC es fuerte/débil).

Objetivo DEFENSIVO: medir y reforzar la resistencia a la manipulación. NO fabrica daño:
las "trampas" son casos de prueba de inyección/autoridad-falsa/urgencia/etc., y lo que se
guarda es la DEFENSA. Stdlib (urllib). Roles desde roles/trampa.yaml.

Uso:
  ./trampa.py                 # una trampa por categoría
  ./trampa.py --cat inyeccion # solo esa categoría
  ./trampa.py --n 3           # 3 por categoría
  ... --offline               # sin red (mock, prueba el flujo)

## Piezas clave

- `_dignidad`
- `_escribir_atomico`
- `_json`
- `_proponer`
- `_puntuar`
- `_slug`
- `_trazar`
- `cargar_roles`
- `defensas_actuales`
- `juzgar`
- `llm`
- `main`
- `probar`

---
_Auto-documentado desde la cabecera de `trampa.py`. Parte de MOSAIC._
