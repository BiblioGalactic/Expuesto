# banco_central.py

> 🏦 BANCO CENTRAL — la CASA DE MONEDA respaldada por cómputo (estudio Opus

## Qué hace

🏦 BANCO CENTRAL — la CASA DE MONEDA respaldada por cómputo (estudio Opus
🏦   19:40 · pieza final de la ronda bursátil 5-jul). N3 DETERMINISTA:
🏦   cero LLM, cero red — MIDE la capacidad de la flota (servidores.conf ×
🏦   slots × throughput observado × horas) y la ACUÑA en el libro. No
🏦   imprime: no se emite más de lo que la flota computa (ancla anti-fiat:
🏦   el techo es la RAM de dos Macs, no una promesa).
🏦   El libro: data/tesoreria.jsonl — APPEND-ONLY con HASH ENCADENADO
🏦   (cada línea sella la anterior: alterar una rompe la cadena — nadie
🏦   cocina las cuentas; `verificar` es la fiscalización de Diógenes).
🏦   LÍNEAS ROJAS (cableadas): el banco PROPONE, jamás mueve solo (aplicar
🏦   una asignación = Acción + doble sello) · sin crédito · sin interés ·
🏦   🔔 LA CAMPANA: sin primera Acción SELLADA el banco NO acuña (el debut
🏦   abre el mercado — override a conciencia: MOSAIC_BANCO=1).
🏦 Uso:  ./banco_central.py acunar      (mide y ACUÑA el periodo → libro)
🏦       ./banco_central.py resumen     (activo vs pasivo del último periodo)
🏦       ./banco_central.py verificar   (la cadena de hashes, línea a línea)

## Piezas clave

- `_asentar`
- `_campana`
- `_err`
- `_flota`
- `_politica`
- `_ultimo_hash`
- `acunar`
- `main`
- `resumen`
- `verificar`

---
_Auto-documentado desde la cabecera de `banco_central.py`. Parte de MOSAIC._
