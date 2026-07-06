# perpetuo.sh

> ♾️ PERPETUO v1 — plenos "cada X" sin fin (spec Opus 15:41 · estudio Fable 15:46

## Qué hace

♾️ PERPETUO v1 — plenos "cada X" sin fin (spec Opus 15:41 · estudio Fable 15:46
♾️   · orden Gustavo 5-jul). Un bucle while+sleep que dispara pleno.sh: la
♾️   CADENCIA por rol decide quién habla (quien habló, calla) y el LOCK del
♾️   orquestador evita el solape (pleno.sh cede el paso si hay ciclo en marcha
♾️   y reintenta en la vuelta siguiente — el punto seguro manda).
♾️
♾️ ⚠️  PRERREQUISITO DURO (Opus 15:41): NO encenderlo hasta que un pleno se lea
♾️ ⚠️  LIMPIO tras el fix del eco — si no, es una máquina de ruido perpetuo.
♾️ ⚠️  Este script NACE APAGADO: pide confirmación (SI) salvo --si.
♾️
♾️   Freno de mano LIMPIO (sin Ctrl+C): touch data/senales/PARAR_PERPETUO
♾️     → para tras el pleno en curso y consume la señal (trazado en el log).
♾️   Respeta data/pausa.flag del vigía (MacBook a tope → espera, no dispara).
♾️   PID guard: data/.perpetuo.pid — UNO a la vez (poll-primero, lección zombi).
♾️ Uso:  ./perpetuo.sh [--si]
♾️   env: PLENO_CADA_MIN (60) · PERPETUO_MAX (0 = sin tope de plenos) ·
♾️        PERPETUO_PORTAVOZ=0 (pleno sin portavoz)

## Piezas clave

- `cleanup`
- `confirmar`
- `ejecutar`
- `err`
- `log`
- `validar`

---
_Auto-documentado desde la cabecera de `perpetuo.sh`. Parte de MOSAIC._
