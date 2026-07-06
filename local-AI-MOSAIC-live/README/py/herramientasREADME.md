# herramientas.py

> 🧰 HERRAMIENTAS — el DISPATCHER de tools (manifiesto Opus 13:36 · patrón del

## Qué hace

🧰 HERRAMIENTAS — el DISPATCHER de tools (manifiesto Opus 13:36 · patrón del
🧰   dispatcher.js de wa-llama-bridge, reimplementado mosaic-nativo, cero JS).
🧰   (agente, tool, payload) →
🧰     · nivel_acceso (su yaml) ≥ nivel_requerido (data/herramientas.yaml) →
🧰       EJECUTA el cmd por el CONTRATO (JSON stdin → stdout {"ok":…}).
🧰     · si NO alcanza → EL ESCALADOR (plan Opus 13:56, modelo de mission-control
🧰       adaptado — json, sin sqlite, sin web): NO se deniega a secas — ticket ESC
🧰       en data/escalaciones.json (escritor único + lock) con PRIORIDAD QUE FIJA
🧰       EL AGENTE (baja|normal|alta|urgente; default normal) y CADENA derivada del
🧰       organigrama vivo (N2 de su depto → N1 → humano). AUTO-DISPATCH: sube al
🧰       primer rango capaz (nivel_acceso Y techo de su rango ≥ nivel_requerido).
🧰       Estados: abierto→escalado→en_revision→resuelto|denegado|esperando_sello
🧰       (nivel 5 → doble sello: la escalera termina en sellar.sh)|caducado (TTL,
🧰       se ARCHIVA en escalaciones_archivo.jsonl — no se pierde).
🧰       Conceder EJECUTA la tool con el payload del ticket (resuelto = concedido+ejecutado).
🧰     · techo F1 = solo LECTURA (nivel ≤ techo_f1): un 4-5 NI CON TICKET.
🧰       (el motor 4-5/esperando_sello queda CABLEADO — probado con techo alzado en jaula.)
🧰   Salida SIEMPRE contrato JSON (el que llama — turno_rol, pedir_tool, escalado.sh,
🧰   humano — parsea una sola forma). Exit: 0 ok · 1 error tool · 3 techo/ticket-mal · 4 denegado.
🧰 Uso:  echo '{"q":"..."}' | ./herramientas.py --agente ingesta --tool buscar
🧰        [--prioridad baja|normal|alta|urgente] [--ticket TCK-… legado]
🧰       ./herramientas.py --listar
🧰       ./herramientas.py --esc listar [--estado E] [--rango R] [--origen O]
🧰       ./herramientas.py --esc resolver --id ESC-… --como <rol|humano> \
🧰                          --decision conceder|denegar|escalar [--motivo "…"]
🧰       ./herramientas.py --esc visto --id ESC-… --como <rol>
🧰       ./herramientas.py --esc caducar     (el barrido TTL; abrir el libro ya barre)

## Piezas clave

- `_ahora`
- `_cadena_de`
- `_capacidad`
- `_ejecutar_tool`
- `_esc_barrer_ttl`
- `_esc_cli`
- `_esc_crear`
- `_esc_dispatch`
- `_esc_listar`
- `_esc_resolver`
- `_esc_visto`
- `_sillas`
- `_techos`
- `arg`
- `cargar_registro`
- `emit`
- `main`

---
_Auto-documentado desde la cabecera de `herramientas.py`. Parte de MOSAIC._
