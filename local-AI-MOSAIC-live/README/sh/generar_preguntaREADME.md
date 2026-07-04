# generar_pregunta.sh

> MOSAIC — generador de preguntas (3 modelos) -> ingesta automática

## Qué hace

MOSAIC — generador de preguntas (3 modelos) -> ingesta automática
Tres fuentes generan preguntas aleatorias y cada una se pasa a mosaic:
  1) mythomax-13b  (local, llama-cli)
  2) Mistral-24B   (proxy 8080 -> directo 8090 si el proxy está caído)
  3) Unholy-13B    (proxy 8081 -> directo 8091 si el proxy está caído)
Hace cd, abre/cierra el entorno py, asegura el cluster y avisa cuando
algo se va a SEGUNDO PLANO.  Uso:  ./generar_pregunta.sh [RONDAS]  (def. 1)

## Piezas clave

- `activar_venv`
- `asegurar_cluster`
- `aviso`
- `cleanup`
- `cluster_vivo`
- `err`
- `generar_http`
- `generar_local`
- `generar_modelo`
- `limpiar`
- `log`
- `procesar`
- `validar`

---
_Auto-documentado desde la cabecera de `generar_pregunta.sh`. Parte de MOSAIC._
