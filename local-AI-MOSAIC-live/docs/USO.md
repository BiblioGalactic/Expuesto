# 📖 USO — del primer `--offline` al bucle continuo

## Probar YA, sin cluster (mock)

```bash
./mosaic.sh --offline "escribe una función async en python con tests"
./mosaic.sh --selftest
./tribunal.py --offline "¿capital de Francia?" "París"
```

Verás el flujo entero (composición de capacidades, fiscal/abogado/juez) con modelos
simulados. Sirve para validar la instalación antes de tocar la flota.

## Aprender de tu USO REAL (lo recomendado)

Cada `./mosaic.sh "tarea"` registra la petición y su resultado en el historial. Cuando
quieras, consolidas: el juez (el modelo pequeño de la 2ª máquina) puntúa esos usos
reales — sin re-ejecutarlos — y el sistema aprende de ellos.

```bash
./mosaic.sh "lo que necesites de verdad"    # úsalo normal; se registra solo
./aprender.sh consolidar                     # aprende de TUS casos reales
```

`aprender.sh` a secas entrena con ejercicios inventados; `consolidar` aprende de lo
tuyo. Lo segundo es lo valioso.

## El ciclo completo (las 7 fases)

```bash
cp ~/Documentos/cualquiera.pdf silo/    # cualquier archivo: PDF, audio, foto, Excel…
./mosaic.sh ciclo                        # cascada → banco → ejecución‖juicio → tribunal
                                         # → aprender → panel → acta → gobernador
./bucle_continuo.sh                      # ciclos encadenados hasta agotar el trabajo
```

La flota se levanta sola al empezar y se acuesta sola al terminar
(`MOSAIC_BAJAR_AL_ACABAR=0` para dejarla viva). El gobernador ajusta los mandos del
siguiente ciclo leyendo las actas; `MOSAIC_GOBERNADOR=0` lo apaga.

## La consola (el puente de mando)

```bash
pip install textual && ./monitor.py
```

| Tecla | Qué hace |
|---|---|
| `D` / `C` / `V` | Debrief del último ciclo · cola del epistolar · ciclo EN VIVO (expandible) |
| `R` | Reportar: deposita una entrada formateada (escritor único, con cerrojo) |
| `A` | Archivar el epistolar cuando pesa (plan visible antes de aplicar) |
| `L` | **Lanzar**: un modo (ciclo/aprender/…) con flags, la MÁSCARA sobre el modelo que elijas, o el turno de MOSAIC (autodiagnóstico) |
| `S` | **Compartir**: exportar un pack de máscara (con revelado en Finder / borrador de Mail) o importar uno ajeno por la aduana |
| `Q` | Cierre inteligente: por defecto solo sale — el trabajo vivo sigue y se reanuda al reabrir |

## Los packs de máscara

```bash
./empaquetar.sh <dominio>              # dry-run: plan + redacciones de PII
./empaquetar.sh <dominio> --aplicar    # → packs/<dominio>_vN.mosaic
./importar.sh recibido.mosaic          # dry-run: manifest, válidas, colisiones
./importar.sh recibido.mosaic --aplicar   # ADUANA (defensa) → solo SEGURO entra
```

El import jamás pisa lo tuyo: fichero aparte, ids con namespace de autor, scores
capados a un prior humilde que se recalibra con tu uso. Prueba con el pack de ejemplo
de `packs/` sin depender de terceros.

## Flags útiles (todas con default sano)

`MOSAIC_WORKERS` (pool de bocas) · `MOSAIC_JUECES` · `CASCADA_BG` (ingesta en 2º plano) ·
`PIPELINE` (auto si hay juez remoto) · `DEBRIEF` · `MOSAIC_ESCALADA` · `MOSAIC_FNC`
(firma multilingüe, apagada por defecto) · `AUTODIAG` (el turno de MOSAIC). El resto,
documentado en `.env.example`.
