# apikey.sh

> 🔑 apikey.sh — buscador CENTRAL de claves. Toda API pide su clave aquí:

## Qué hace

🔑 apikey.sh — buscador CENTRAL de claves. Toda API pide su clave aquí:
🔑     KEY="$(~/Mosaic_privado/apikey.sh github)"
🔑 Lee info/apiskeys.txt (formato SERVICIO|clave). Tolerante: case-insensitive
🔑 y normaliza espacios/guiones (apikey.sh "alpha vantage" → ALPHA_VANTAGE).
🔑 La clave sale por STDOUT (para capturarla); los errores/listado por STDERR.

---
_Auto-documentado desde la cabecera de `apikey.sh`. Parte de MOSAIC._
