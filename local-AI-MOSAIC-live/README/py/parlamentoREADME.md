# parlamento.py

> 🗨️ PARLAMENTO — hablar con un EMPLEADO (tecla [P], propuesta Gustavo 5-jul).

## Qué hace

🗨️ PARLAMENTO — hablar con un EMPLEADO (tecla [P], propuesta Gustavo 5-jul).
🗨️   El chat es DUEÑO DE SU PROPIO PROMPT (arreglo #3 de Opus 21:15): llama a
🗨️   la flota DIRECTO — system = identidad del rol por su RANGO (persona en 1ª
🗨️   persona + su prompt + SUS lecturas recortadas + seguridad + idioma), user
🗨️   = el mensaje de Gustavo. NO pasa por la máscara efímera de mosaic.py (el
🗨️   doble envoltorio que vació el pleno) → nace sano aunque el pleno siga con
🗨️   su #1. Red del <think>: si tras recortarlo queda vacío pero el modelo
🗨️   habló, se queda lo posterior al </think> (jamás vacío si hubo tokens).
🗨️   Palabra, JAMÁS manos: el chat NO ejecuta tools ni escalaciones (un chat no
🗨️   es un turno — sin cadencia ni sellos). Si el empleado necesita algo, que
🗨️   lo pida en SU turno. Cada intercambio se REGISTRA (user:/assistant:, el
🗨️   formato de la agenda) y es REANUDABLE.
🗨️ Uso:  echo "hola Lola" | ./parlamento.py --rol diseno [--sesion FICHERO]
🗨️       ./parlamento.py --system --rol diseno    (muestra el system que inyectaría)

## Piezas clave

- `_arg`
- `_host`
- `_puerto`
- `_rol_yaml`
- `_think_red`
- `cargar_historial`
- `construir_system`
- `hablar`
- `main`
- `registrar`

---
_Auto-documentado desde la cabecera de `parlamento.py`. Parte de MOSAIC._
