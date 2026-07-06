# ciclo.sh

> CICLO — el ciclo COMPLETO en UNA sola orden, por TANDAS, todo en terminal.

## Qué hace

CICLO — el ciclo COMPLETO en UNA sola orden, por TANDAS, todo en terminal.
Sin segundo plano (lo que va al mini se ve con ./ver_mini.sh).
  FASE 1 FÁBRICA  : llena la cola de preguntas hasta un tope (backpressure)
  FASE 2 INGESTA  : vacía la cola por mosaic (respuesta A = composición)
  FASE 3 JUICIO   : tribunal adversarial sobre una muestra (captura desde ya)
  FASE 4 APRENDER : generar (huecos) + consolidar (juez + recompensa + poda + A/B)
  FASE 5 PANEL    : refresca META.md y muestra el veredicto de madurez
Uso:  ./ciclo.sh [N]     (N ciclos; 0 o vacío = hasta Ctrl+C)

## Piezas clave

- `asegurar_cluster`
- `asegurar_mini`
- `cleanup`
- `cola_size`
- `esperar_si_pausa`
- `fase`
- `items_cuarentena`
- `items_silo`
- `ko`
- `log`
- `vivo`

---
_Auto-documentado desde la cabecera de `ciclo.sh`. Parte de MOSAIC._
