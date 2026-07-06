# turno_rol.sh

> 🎭 TURNO_ROL — el motor GENÉRICO de sillas (P4 orquesta · molde de autodiagnosis).

## Qué hace

🎭 TURNO_ROL — el motor GENÉRICO de sillas (P4 orquesta · molde de autodiagnosis).
🎭   Un rol = un yaml en roles/turnos/<rol>.yaml (prompt · lecturas · puertos ·
🎭   firma · tipo de reporte). N roles = N yamls, UNA sola fuente de salvaguardas:
🎭     · permiso ACOTADO: leer lo listado → componer (mosaic.sh) → depositar UNA
🎭       carta (reportar.sh). Palabra, jamás manos. Cero rm/curl-de-datos/ssh/eval.
🎭     · pre-vuelo de analista (sonda → un `subir` idempotente → tope de espera).
🎭     · tope duro de contexto por lectura y total (jamás petar el modelo).
🎭     · captura base64 + no-postear-vacío + pie de transparencia con la receta.
🎭     · si el rol promete una Acción y no cumple la plantilla → cae a Informe
🎭       avisando (no se pierde la palabra, no se cuela una Acción coja).
🎭   Kill-switches: TURNOS=0 (todos) · TURNO_<ROL>=0 (uno).
🎭 Uso:  ./turno_rol.sh <rol>          (el turno: lee, compone y postea)
🎭       ./turno_rol.sh <rol> --dry    (enseña prompt y sonda; NO postea)

## Piezas clave

- `_host_de_url`
- `asegurar_analista`
- `cleanup`
- `ejecutar`
- `err`
- `generar_directo`
- `log`
- `nombre_de`
- `validar`
- `vivo`

---
_Auto-documentado desde la cabecera de `turno_rol.sh`. Parte de MOSAIC._
