# bucle_continuo.sh

> 🔁 MOSAIC — bucle continuo y CAUTELOSO (ingesta <-> evolución)

## Qué hace

🔁 MOSAIC — bucle continuo y CAUTELOSO (ingesta <-> evolución)
🔁 Alterna fases SIN solaparlas (mismo cluster 24B = cuello de botella):
🔁   FASE 1 · INGESTA   -> generar_pregunta.sh (3 modelos -> mosaic)
🔁   FASE 2 · DIGERIR   -> mosaic.sh generar + consolidar (síncrono)
🔁 Apaga el auto-mantenimiento de fondo de mosaic para que NO colisione.
🔁 Uso:  ./bucle_continuo.sh [CICLOS]     (0 o vacío = infinito, Ctrl+C para parar)

## Piezas clave

- `asegurar_mini`
- `digerir`
- `err`
- `esperar_si_pausa`
- `log`
- `validar`

---
_Auto-documentado desde la cabecera de `bucle_continuo.sh`. Parte de MOSAIC._
