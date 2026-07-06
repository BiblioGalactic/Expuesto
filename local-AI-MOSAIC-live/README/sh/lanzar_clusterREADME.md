# lanzar_cluster.sh

> 🚀 LANZAR_CLUSTER v3 — el botón único de la flota, AHORA CON CABEZA (3-jul-2026,

## Qué hace

🚀 LANZAR_CLUSTER v3 — el botón único de la flota, AHORA CON CABEZA (3-jul-2026,
🚀 tras congelar el MacBook: mea culpa de Fable — v2 lanzaba TODO sin mirar la RAM).
🚀 Lo que cambia en v3 (la gestión inteligente que faltaba):
🚀   1) PRESUPUESTO por máquina ANTES de tocar nada: suma los GGUF fijos + overhead
🚀      y si no caben (MacBook ~40 usables de 48 · mini ~12 de 16) SE NIEGA a arrancar.
🚀   2) Solo lanza los 'fijo' del conf; los 'demanda' son de lentes.sh (por turnos,
🚀      con su propia guardia) — el roster completo JAMÁS convive entero.
🚀   3) Arranque SECUENCIAL: un servidor no se lanza hasta que el anterior INFIERE
🚀      (la carga es el pico de RAM; nada de picos simultáneos).
🚀   4) RAM libre medida antes de CADA lanzamiento (vm_stat/meminfo) + margen.
🚀   5) Supervisión con CORTAFUEGOS: revive solo si hay RAM; 2 muertes en 10 min
🚀      → deja de revivirlo y AVISA (se acabó la espiral OOM→revivir→OOM).
🚀   Ctrl+C = apagado CRUZADO Y ORDENADO: mini → verificar → MacBook (como mandó Gustavo).
🚀 Uso: ./lanzar_cluster.sh [subir|bajar|estado|plan]   (sin args = arrancar+supervisar)

## Piezas clave

- `bajar`
- `esperar_uno`
- `estado`
- `flota_viva`
- `gb_de`
- `gb_de_mini`
- `gb_libres`
- `gb_libres_mini`
- `host_de`
- `lanzar_uno`
- `leer_conf`
- `liberar_flota`
- `limpiar_zombies`
- `listo`
- `log`
- `plan`
- `reclamar_flota`
- `resolver_local`
- `resolver_mini`
- `subir`
- `supervisar`
- `verificar_muerto`
- `warn`

---
_Auto-documentado desde la cabecera de `lanzar_cluster.sh`. Parte de MOSAIC._
