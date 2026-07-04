# fnc_ab.py

> A/B DE FIRMEZA — ¿una prohibición en FNC resiste el red-team MEJOR que en claro?

## Qué hace

A/B DE FIRMEZA — ¿una prohibición en FNC resiste el red-team MEJOR que en claro?
Mismo ataque → el defensor responde en CLARO y en FNC → el árbitro juzga ambas.
Métricas: resistencia + nota media, DESGLOSADAS POR MODELO (rotación).
ROBUSTO: si el defensor está caído o devuelve error, la ronda se DESCARTA (no
se juzga ni cuenta — nada de basura puntuada como victoria).
Transparencia total: imprime ataque + respuesta completa de cada rama + veredicto,
y lo PEGA a una traza jsonl para auditar a mano. 'resumen' agrega la traza (oleadas).
Rotación:  FNC_AB_DEFENSORES="Nom@http://host:puerto/v1 Nom@http://...  (sin el 24B)"
Uso:  FNC_JA=1 FNC_AB_N=4 ./fnc_ab.py      ·      ./fnc_ab.py resumen      ·      --offline

## Piezas clave

- `_defensores`
- `_malo`
- `_tabla`
- `_trazar`
- `defensas_texto`
- `main`
- `resumen`
- `una_ronda`

---
_Auto-documentado desde la cabecera de `fnc_ab.py`. Parte de MOSAIC._
