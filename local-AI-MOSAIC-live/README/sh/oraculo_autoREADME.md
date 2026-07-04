# oraculo_auto.sh

> ORACULO AUTO — automatiza el scraping: elige un tema, corre el crawler

## Qué hace

ORACULO AUTO — automatiza el scraping: elige un tema, corre el crawler
(descubre + juzga repos) y clona los KEEP a cuarentena. Sin comandos a mano.
El token sale del store central (apikey.sh github). Temas rotan desde un
fichero (oraculo_temas.txt) para no buscar siempre lo mismo.
Lo llama el ciclo en FASE 1 si ORACULO_AUTO=1. Falla en silencio si no hay token.

## Piezas clave

- `log`

---
_Auto-documentado desde la cabecera de `oraculo_auto.sh`. Parte de MOSAIC._
