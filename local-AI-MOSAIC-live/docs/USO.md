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

Re-skin: las 12 teclas se agruparon en **8 hubs** (cada botón rutea a la pantalla que ya existía).

| Tecla | Qué hace |
|---|---|
| `M` **Mesa** | El epistolar: cartas · debrief del ciclo · **Reportar** (`reportar.sh`, escritor único con cerrojo) · **Archivar** (`archivado.sh`, plan visible antes) · ciclo en vivo |
| `E` **Empresa** | La plantilla: organigrama de 3 niveles, alta/edición de empleados (escribe `roles/turnos/*.yaml`), niveles de acceso 1-5, **Persona** (fichas `ficha.sh`) y la **Bolsa** (el ticker) |
| `L` **Motor** | **Lanzar** (ciclo/aprender con flags · la MÁSCARA sobre el modelo que elijas) · **Flota** (subir/bajar el clúster, claim de una empresa a la vez) · **Perpetuo** |
| `P` **Parlamento** | Hablar con un empleado por su **rango** (chat directo; el buzón exterior queda fuera del contexto) |
| `A` **Agenda** | La agenda dual: **privada** (tu vida) / **empresarial** (tu gente) |
| `S` **Compartir** | Exportar un pack de máscara (revelado en Finder / borrador de Mail) o importar uno ajeno por la **aduana** |
| `V` · `Q` | Ciclo EN VIVO (expandible) · Cierre inteligente (por defecto solo sale; el trabajo vivo se reanuda al reabrir) |
| ocultas | `C` cartas · `D` debrief · `R` reportar · `T` tickets (escalaciones, solo lectura) · `F` flota |

## La orquesta de agentes (arranque rápido)

```bash
./turno_rol.sh seguridad --dry     # el prompt que hablaría esa silla (sin postear)
./turno_rol.sh central             # un N3: parte-de-estado SIN modelo (flota abajo vale)
./pleno.sh                         # toda la orquesta habla, de una orden
./ficha.sh --todos                 # las fichas de identidad (derivadas, cero store nuevo)
./bautizar.sh                      # nombres humanos para quien no tenga (idempotente)

# permisos graduados: pedir una tool por encima de tu nivel crea un TICKET que escala
./pedir_tool.sh ingesta buscar "tema"          # nivel 2: ejecuta si su acceso llega
./pedir_tool.sh gobierno depositar "nota"      # nivel 3 > su acceso → 🎫 ESC-…
./escalado.sh listar                           # la cola, por prioridad
./escalado.sh conceder ESC-20260705-01         # conceder EJECUTA (nivel 5 → sello humano)
```

Los agentes deciden sus escalaciones EN SU TURNO; el humano siempre es el final de la
cadena. Todo deja rastro: `data/escalaciones.json`, historial por ticket, archivo TTL.

## La empresa: parlamento, agenda, economía y perpetuo

```bash
# HABLAR con un empleado por su rango (desde la consola: [P] Parlamento)
#   llamada directa a la flota — su identidad de rol como system, sin doble envoltorio.
#   Charla reanudable, guardada en data/conversaciones_empresa/ y visible en la agenda.

# LA BOLSA — el ticker DERIVADO de la empresa (N3 determinista: cero LLM, cero red)
./valorar_empresa.py                 # la sede → data/ticker.json
./valorar_empresa.py --grupo         # rankea sede + ~/Empresas/* → data/ranking.json
#   valor = CRAG × [capacidades + resueltos] + madurez (sillas debutadas, acciones selladas,
#   tools conectadas), pesado por data/formula_valor.yaml (fórmula ABIERTA, auditable con cat).
#   Línea roja: sin actas = "sin cotizar" — jamás un cero inventado; el ranking PROPONE, no ejecuta.

# EL BANCO CENTRAL — moneda respaldada por cómputo (mide la flota y acuña; libro con hash encadenado)
./banco_central.py acunar            # mide y acuña el periodo → data/tesoreria.jsonl
./banco_central.py verificar         # fiscaliza la cadena de hashes, línea a línea
#   Ancla anti-fiat: no se emite más de lo que la flota computa. El banco PROPONE, jamás mueve
#   solo (asignar = Acción + doble sello). No acuña hasta la primera Acción sellada (el debut).

# EL PERPETUO — plenos "cada X" sin fin (nace APAGADO; pide confirmación)
./perpetuo.sh                        # freno de mano: touch data/senales/PARAR_PERPETUO
```

Multi-empresa: `./crear_empresa.sh <Nombre>` (dry-run) → `--aplicar` funda una instancia nueva
(N bases sobre UN motor, máscara vacía; se opera con `MOSAIC_BASE=~/Empresas/<Nombre>`).

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
