# presupuesto_contexto.py

> 🧮 PRESUPUESTO_CONTEXTO — la calculadora determinista de la ventana (P1 · plan 6-jul).

## Qué hace

🧮 PRESUPUESTO_CONTEXTO — la calculadora determinista de la ventana (P1 · plan 6-jul).
Nace del estudio de Opus 03:55 + D10-D13/D23 del PLAN_MESA: no adivinar max_tokens,
PRESUPUESTARLO por modelo con margen de oxígeno, ANTES de enviar. Es la cura del
«salió vacío» (2500 prompt + 3000 salida > 4096 ctx → rechazo instantáneo).

La llaman: turno_rol.sh::generar_directo · mosaic.py::ClusterLLM.generate · parlamento.py.
Kill-switch del llamante: PRESUPUESTO=0 → cada uno vuelve a sus defaults de siempre.

El presupuesto (D10-D13 + D23):
  n_ctx_efectivo = ctx(servidores.conf) ÷ parallel(flags)          # la trampa del bug
  oxígeno        = max(18% × n_ctx_ef, 512)                        # D10 (env OXIGENO_PCT/PISO)
  usable         = n_ctx_ef − oxígeno
  salida         = techo por tipo (accion 800 · informe 1200 · chat 800 · corto 600)  # D12*
  pensar         = reserva por MODELO (regla 3 Opus 00:45): *Thinking* 2000 · *R1*/*DeepSeek* 800 · chat 0
  cabe_prompt    = usable − salida − pensar
  t_prompt       = /tokenize del PROPIO modelo (exacto) · fallback estimador conservador
  si no cabe     → recorte determinista: las LECTURAS ceden primero, la más vieja primero
                   (bloques `===== ruta =====` desde el primero); persona+tarea y ANCLA intocables.
  si ni así cabe → FALLAR ALTO (exit 3): jamás enviar basura.
  max_tokens     = salida + pensar  (lo generado incluye el <think> del razonador)

  (*) D12 decía auditoría 600; subo accion→800 para no truncar la plantilla de 5 secciones
      a mitad (una Acción coja degrada a Informe). Desviación DECLARADA — Opus ajusta si quiere.

CLI:
  python3 presupuesto_contexto.py --url http://IP:8092/v1 --modelo Qwen3-14B \
      --tipo accion --prompt-file p.txt [--trim-out p.rec] [--plano]
  --plano  → una línea parseable en bash 3.2: «maxtok=N tprompt=N cabe=0|1 recortado=0|1 fuente=X»
  (sin --plano → JSON completo). exit: 0 ok · 3 no-cabe-ni-recortando · 2 uso.

## Piezas clave

- `_catalogo`
- `_entrada_catalogo`
- `_flag_si`
- `cap_max_tokens`
- `ctx_efectivo`
- `es_razonador`
- `main`
- `modelo_de_puerto`
- `presupuesto`
- `recortar`
- `reserva_pensar`
- `tokens_de`

---
_Auto-documentado desde la cabecera de `presupuesto_contexto.py`. Parte de MOSAIC._
