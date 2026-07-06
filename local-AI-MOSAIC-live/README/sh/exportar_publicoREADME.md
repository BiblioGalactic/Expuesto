# exportar_publico.sh

> 🚢 EXPORTAR_PUBLICO — la versión publicable de MOSAIC, por LISTA BLANCA.

## Qué hace

🚢 EXPORTAR_PUBLICO — la versión publicable de MOSAIC, por LISTA BLANCA.
🚢   Regla de oro (auditoría 2-jul + manifiesto Opus 19:45): el repo público
🚢   nace como COPIA exportada — lo que no está en la lista, NO viaja.
🚢   Destino: ~/Expuesto/Expuesto/local-AI-MOSAIC-live (decisión Gustavo 4-jul).
🚢   TRANSFORM solo de RED y solo EN LA COPIA (IP casa→127.0.0.1 · host→localhost);
🚢   las rutas ya van limpias por la F1 (de-hardcodeo en el privado).
🚢   GREP-GATE final que ABORTA si en el destino queda email/usuario/IP/host/token.
🚢   Idempotente: re-exportar = re-sincronizar código y docs (no borra extras
🚢   del destino, p. ej. capturas de pantalla que añada Gustavo).
🚢 Uso:  ./exportar_publico.sh              (DRY-RUN: el plan, sin escribir)
🚢       ./exportar_publico.sh --aplicar

## Piezas clave

- `copiar`
- `err`
- `gate`
- `log`
- `validar`
- `verificar`

---
_Auto-documentado desde la cabecera de `exportar_publico.sh`. Parte de MOSAIC._
