# ARCHITECTURE.md - Expuesto

## Que es de verdad

`Expuesto/` no es una aplicacion unica. Es el repo coordinador de un workspace con 9 repos hijos. Lo deje asi porque los modulos crecieron a velocidades distintas: el cliente de escritorio, el bridge de WhatsApp, los robots de prompt, los experimentos de memoria y los scripts multimedia no comparten el mismo ciclo de cambios. Si lo hubiera metido todo en un unico arbol "perfecto", hoy costaria mucho mas congelar una v1 sin romper otra cosa.

En este repo central solo mantuve lo que si necesito compartir:

- `.expuesto/config.env` para rutas y parametros comunes.
- `lib/bash-common.sh` para sanitizacion, logs, SHA256 y checks de entorno.
- `tests/` para vigilar que el workspace no se degrade por acumulacion de scripts rotos o placeholders.
- `positronic-brain/` y `wa-llama-bridge-public/`, que son los dos modulos con operacion mas directa desde aqui.

La verificacion que doy por valida hoy sale de este repo, no de una promesa:

- `tests/e2e/test_project_structure.sh`: 58 checks en verde.
- `tests/e2e/test_sanitization.sh`: 38 checks en verde.
- `tests/python/test_bash_common.py`: 19 tests en verde.

## Arbol de trabajo

```text
Expuesto/
├── .expuesto/config.env
├── lib/bash-common.sh
├── positronic-brain/
├── wa-llama-bridge-public/
├── dashboard/
└── tests/
```

Repos hermanos en el mismo workspace:

- `Prime_Radiant/`: donde deje los sistemas mas pesados de RAG, agentes, cluster y asistentes.
- `Robotsdelamanecer/`: coleccion de robots/personajes con lanzadores directos.
- `light-sculpture/`: scripts GLADIA para audio, video e imagen.
- `the-caves-of-steel/`: documentacion terminal-first sobre IA local.
- `volumen_bucle/`: bucles autonomos y wrappers por idioma.
- `volumen_linguistic_composition/`: composicion linguistica funcional y perfiles.
- `volumen_memoria/`: memoria por prompt y heuristicas.
- `volumen_overhead/`: empaquetado, snapshots y automatizacion de entorno.

## Por que existe la infraestructura comun

### `lib/bash-common.sh`

Lo escribi cuando empece a ver el mismo error repetido en demasiados scripts: rutas sin validar, enteros rotos, logs creciendo sin control y wrappers que explotaban distinto segun la maquina. Preferi pagar el coste de una libreria comun antes que seguir arreglando veinte copias del mismo bug.

Lo que centraliza aqui:

- sanitizacion de rutas e enteros,
- comprobacion de ficheros, binarios y comandos,
- rotacion de logs,
- verificacion SHA256,
- helpers de logging con timestamps,
- limpieza con `trap`.

### `.expuesto/config.env`

No quise convertirlo en una "fuente unica de verdad" para absolutamente todo, porque en un workspace tan heterogeneo eso acaba siendo mentira. Lo uso solo para lo que realmente comparten varios modulos: rutas base y parametros de ejecucion que no merece la pena reescribir una y otra vez.

## Que modulo vive donde

### `positronic-brain/`

Cliente Tauri/React para SSH, SFTP, metricas y ControlRoom. La decision aqui fue pragmatica: preferi un shell de escritorio pesado pero unico antes que cuatro utilidades inconexas. El coste se ve en el bundle del frontend y en que algunas piezas siguen teniendo ADN de spike de diseno.

### `wa-llama-bridge-public/`

Bridge directo entre WhatsApp y `llama-server`. Lo mantuve aparte porque el canal de chat tiene riesgos y ritmos distintos a la app de escritorio. Aqui prefiero un flujo corto y auditable a una orquestacion mas "bonita".

### Repos hermanos

No los movi dentro de `Expuesto/` porque ya funcionan mejor como fronteras de producto o de laboratorio separadas. La arquitectura real de este workspace depende de esa separacion. Fingir lo contrario en la documentacion solo serviria para confundir al siguiente mantenimiento.

## Deuda que dejo visible

- No todo el workspace es un producto final unico; varias piezas siguen siendo laboratorio controlado.
- `positronic-brain` esta operable, pero el updater esta desactivado hasta tener un canal de releases real.
- `wa-llama-bridge-public` sigue arrastrando vulnerabilidades aguas arriba en Baileys/libsignal; la deuda es de proveedor, no de texto de README.
- Hay decisiones historicas raras en nombres y carpetas. No las he "limpiado" todas porque en varios casos esa cicatriz explica mejor la evolucion que un renombrado cosmetico.

## Como leer este workspace

Si vienes a operar algo:

1. Empieza por `Expuesto/` para entender infraestructura comun y checks.
2. Entra despues al repo concreto que quieras tocar.
3. Trata `Prime_Radiant/` como laboratorio principal y no como unica verdad del workspace.

Si vienes a congelar una version:

1. Delimita primero que repo es producto y cual es laboratorio.
2. Pasa los tests del repo central.
3. Congela despues el modulo concreto con su propia deuda explicita.
