# generar_pregunta.sh

> MOSAIC — generador de preguntas (3 voces) -> ingesta automática

## Qué hace

MOSAIC — generador de preguntas (3 voces) -> ingesta automática
Tres fuentes generan preguntas aleatorias y cada una se pasa a mosaic:
  1) Phi-4-mini local (llama-cli, plantilla Phi a mano — 2.5G, decisión Gustavo 4-jul)
  2) Qwen3-14B server (PRINCIPAL 8092; proxy 8080 si existe) — ⚔️ 4-jul: EL 24B JAMÁS
  3) Unholy-13B       (proxy 8081 -> directo 8091 si el proxy está caído)
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
