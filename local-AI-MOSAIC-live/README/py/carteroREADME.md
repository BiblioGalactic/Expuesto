# cartero.py

> 📤 EL CARTERO — router de correo de SALIDA (P3 del plan 6-jul · espejo del estafeta).

## Qué hace

📤 EL CARTERO — router de correo de SALIDA (P3 del plan 6-jul · espejo del estafeta).
📤   N3 DETERMINISTA: reglas, cero LLM. NACE EN MODO PLUMA: mueve ficheros DENTRO
📤   de data/ y JAMÁS envía nada fuera. El envío real es un GESTO DE GUSTAVO.
📤   El flujo:
📤     data/buzones/<rol>/salida/carta_*.txt   ← un rol deja aquí su carta
📤        cabeceras en las primeras líneas:  PARA: <rol|dirección>  ·  ASUNTO: <texto>
📤     → cartero.py --procesar:
📤        1) PARA = rol CONOCIDO (roles/turnos/*.yaml) → INTERNO: se entrega a
📤           data/buzones/<destino>/entrada/ etiquetada [PROCEDENCIA: INTERIOR — de
📤           <origen>] (pluma-con-registro dentro de buzones: D22). El anti-poisoning
📤           del turno NO se dispara (interior verificado ≠ buzón exterior).
📤        2) PARA = dirección EXTERNA (email/tel/lo-no-conocido) → JAMÁS SE ENVÍA:
📤           queda en data/salida_pendiente/ con su metadato, esperando el DOBLE
📤           SELLO + el gesto humano (mensaje_externo es nivel 5: SIEMPRE humano).
📤        3) FILTRO DE FUGAS: toda carta pasa por los patrones `gate` de
📤           saneado_patrones.conf (la fuente única) — si contiene un secreto/PII de
📤           la casa se RETIENE (data/salida_pendiente/retenidas/) y se avisa. Un
📤           agente jamás saca secretos por correo, ni por error.
📤     Todo movimiento queda en data/buzones/libro.jsonl (el mismo libro del estafeta).
📤   Kill-switch: CARTERO=0 (no procesa nada). Sin --procesar = DRY (enseña el plan).
📤   Lo que NO hace (a conciencia): enviar (SMTP/SMS/lo-que-sea), tocar fuera de
📤   data/, decidir por el humano. La conexión como tool (correo_interno, nivel 4)
📤   espera la ratificación de D22 por la mesa.
📤 Uso:  ./cartero.py             (dry: qué haría)
📤       ./cartero.py --procesar

## Piezas clave

- `anotar`
- `cabeceras`
- `log`
- `main`
- `patrones_fuga`
- `roles_conocidos`

---
_Auto-documentado desde la cabecera de `cartero.py`. Parte de MOSAIC._
