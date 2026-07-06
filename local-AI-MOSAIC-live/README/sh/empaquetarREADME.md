# empaquetar.sh

> EMPAQUETAR — exporta una MÁSCARA de dominio como pack portable (VISIÓN Opus 4-jul 17:16).

## Qué hace

EMPAQUETAR — exporta una MÁSCARA de dominio como pack portable (VISIÓN Opus 4-jul 17:16).
  MOSAIC = motor abierto + máscara portátil + corpus privado. Esto exporta la
  MÁSCARA: capacidades del dominio + sinergias aprendidas (state.json), CURADA
  y SANEADA — whitelist de campos, PII redactada, archivadas fuera, referencias
  a ids de fuera del pack podadas. Exportar = CURAR + SANEAR, jamás volcar a pelo.
  JAMÁS exporta lo PRIVADO: historial, huecos, silo, CARTAS, trazas, tokens.
Pack = packs/<dominio>_vN.mosaic (tar.gz: manifest.json + capabilities.yaml + graph.json)
  Contrato: schema_version + degradación elegante (el importador ignora lo que
  no entiende) · agnóstico de flota (declara roles, no modelos) · ⚔️ el 24B jamás.
Uso:  ./empaquetar.sh <dominio>                    (DRY-RUN: plan + redacciones)
      ./empaquetar.sh <dominio> --aplicar [--autor NOMBRE]
  dominio = capabilities/<dominio>.yaml entero, y/o coincidencia exacta en
  domain_expertise/tags de cualquier capacidad viva (minúsculas).

## Piezas clave

- `cleanup`
- `ejecutar`
- `err`
- `log`
- `validar`

---
_Auto-documentado desde la cabecera de `empaquetar.sh`. Parte de MOSAIC._
