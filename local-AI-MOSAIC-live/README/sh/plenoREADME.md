# pleno.sh

> 🏛️ PLENO — la orquesta ENTERA habla, de una orden (orden de Gustavo 5-jul).

## Qué hace

🏛️ PLENO — la orquesta ENTERA habla, de una orden (orden de Gustavo 5-jul).
🏛️   Recorre roles/turnos/*.yaml y da el turno a cada silla por el MISMO motor
🏛️   (turno_rol.sh): salvaguardas, cadencia y kill-switches intactos — un rol
🏛️   callado por cadencia o switch NO es un fallo, es disciplina. Un rol que
🏛️   falla NO tumba el pleno: se apunta y se sigue. Resumen al final.
🏛️   El portavoz global (autodiagnosis.sh) cierra el pleno si está activo.
🏛️   SQUAD (debate noventero 5-jul, mockup de Gustavo): con args de roles, SOLO esas
🏛️   sillas entran en la sala — la CADENCIA sigue mandando (elegir no es forzar).
🏛️ Uso:  ./pleno.sh                       (todos los turnos + portavoz)
🏛️       ./pleno.sh --dry                 (qué diría cada silla; NO postea nada)
🏛️       ./pleno.sh --sin-portavoz
🏛️       ./pleno.sh seguridad auditor …   (SQUAD: solo esas sillas)

## Piezas clave

- `ejecutar`
- `err`
- `log`
- `validar`

---
_Auto-documentado desde la cabecera de `pleno.sh`. Parte de MOSAIC._
