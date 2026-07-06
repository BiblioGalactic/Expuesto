# valorar_empresa.py

> 💹 VALORAR_EMPRESA — el ticker DERIVADO de una empresa (ronda bursátil 5-jul:

## Qué hace

💹 VALORAR_EMPRESA — el ticker DERIVADO de una empresa (ronda bursátil 5-jul:
💹   propuesta Sombra 17:53 + requisitos Opus 17:20 + recon Fable 17:57).
💹   N3 DETERMINISTA: cero LLM, cero red — lee ficheros que YA existen
💹   (actas · capabilities · acciones · escalaciones · turnos · herramientas)
💹   y PESA con data/formula_valor.yaml (fórmula ABIERTA, auditable con cat).
💹   Líneas rojas (grabadas): valor derivado y reproducible · sin actas =
💹   «sin cotizar», jamás un cero inventado · el ranking PROPONE, nadie
💹   ejecuta por cotización (palabra, jamás manos).
💹 Uso:  ./valorar_empresa.py                    (la sede → data/ticker.json)
💹       ./valorar_empresa.py --base RUTA        (otra empresa)
💹       ./valorar_empresa.py --grupo            (sede + ~/Empresas/* → data/ranking.json)
💹       ./valorar_empresa.py --json             (además, el resultado por stdout)

## Piezas clave

- `_actas`
- `_biblioteca`
- `_leer_formula`
- `_madurez`
- `_rotar_historia`
- `main`
- `valorar`

---
_Auto-documentado desde la cabecera de `valorar_empresa.py`. Parte de MOSAIC._
