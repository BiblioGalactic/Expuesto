# estafeta.py

> 📮 EL ESTAFETA — router de correo de ENTRADA (propuesta Fable 13:54, orden Gustavo).

## Qué hace

📮 EL ESTAFETA — router de correo de ENTRADA (propuesta Fable 13:54, orden Gustavo).
📮   N3 DETERMINISTA: reglas, cero LLM. Reparte lo que cae en la zona cruda a los
📮   buzones de los empleados. Todo movimiento queda en el LIBRO (trazable).
📮   El flujo:
📮     data/buzones/_entrada_cruda/*.txt   ← aquí deja mensajes el gateway (o tú)
📮        formato libre; cabeceras opcionales en las primeras líneas:
📮        DE: <remitente>   ·   ASUNTO: <texto>   ·   [PARA: <rol>] (en asunto o 1ª línea)
📮     → estafeta.py --repartir:
📮        1) [PARA: rol] explícito → buzón de ese rol.
📮        2) sin dirección → data/buzones/rutas.yaml (remitente conocido → rol ·
📮           palabra clave → rol del manager del departamento).
📮        3) inclasificable → buzón de DIRECCIÓN (humano — el default no adivina).
📮     Cada entrega se ETIQUETA: [PROCEDENCIA: EXTERIOR — NO VERIFICADO] + veredicto
📮     del remitente contra la ALLOWLIST (direccion/conocido/desconocido — un
📮     desconocido JAMÁS da órdenes: se lee como material, no como mandato).
📮   RE-RUTAS (delegación sin puerta de atrás): un rol deja en su salida/
📮     reruta_*.txt con [PARA: otro] en la 1ª línea → el estafeta lo mueve.
📮   Pluma, no manos: mueve ficheros DENTRO del árbol (línea consultada a Opus).
📮 Uso:  ./estafeta.py            (dry: qué repartiría)
📮       ./estafeta.py --repartir

## Piezas clave

- `anotar`
- `cargar_rutas`
- `clasificar`
- `entregar`
- `log`
- `main`
- `sillas`
- `veredicto_remitente`

---
_Auto-documentado desde la cabecera de `estafeta.py`. Parte de MOSAIC._
