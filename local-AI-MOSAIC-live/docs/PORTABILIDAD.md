# 🧳 PORTABILIDAD — entornos, macOS vs Linux, y tu red

## Los entornos (venvs) — cuántos y para qué

| Entorno | Qué trae | Quién lo usa |
|---|---|---|
| venv **pesado** (opcional, preferido) | torch · sentence-transformers · textual | dedup semántico, observador, la consola |
| venv **ligero** (se crea solo) | numpy · pyyaml | todo lo demás — el núcleo es stdlib |
| venv **whisper** (opcional) | openai-whisper | transcripción de audio/vídeo |

El interruptor: `MOSAIC_USE_WIKIRAG_VENV` (default 1 = usa el pesado si existe).
**Arranca aunque solo haya el ligero**: sin torch, los embeddings degradan a *hashing*;
sin sentence-transformers, el dedup degrada a *léxico*. Nada se rompe — se degrada
con elegancia y te lo dice.

## Tu red (dos máquinas)

1. `cp .env.example .env` → apunta `MOSAIC_LLM_BASE_URL` (tu generadora) y
   `MOSAIC_JUDGE_URL`/`MINI_*` (tu juez) a TUS hosts.
2. `cp servidores.conf.example servidores.conf` → tu flota real: máquina, puerto, rol,
   fijo/demanda, ruta del `.gguf`, contexto, flags.
3. El lanzador de la flota es idempotente: comprueba el roster, levanta SOLO lo caído
   y espera a que infiera. Los scripts sondan antes de hablar (`curl <url>/models`).

Doctrina de flota que este repo asume: **especialistas pequeños-medianos** — el modelo
JUSTO por tarea (un 3B juzga en un parpadeo; un 14B ejecuta; nadie carga un gigante
que se come la RAM de todo lo demás). Dos GPUs modestas coordinadas ganan a una grande
saturada.

## macOS vs Linux

| Pieza | macOS | Linux |
|---|---|---|
| Docs Office/iWork | `textutil` | no existe → el archivo se **retiene** en `.pendiente` (alternativa: `pandoc`/`libreoffice --headless`) |
| HEIC (fotos iPhone) | `sips` | `heif-convert` (libheif) — o se retiene |
| Revelar/Mail en `[S]` | `open -R` / `open -a Mail` | no aplica (el pack queda en `packs/`, compártelo a mano) |
| `timeout` | `gtimeout` (coreutils) o built-in | `timeout` nativo — el código prueba ambos |
| `stat` | `stat -f` | `stat -c` — el código prueba ambos |
| `bash` | **3.2 de sistema** en `/bin/bash` (o 5 por Homebrew) | 4/5 nativo |

**Nota bash:** macOS trae bash **3.2** en `/bin/bash`. El código lo tiene en cuenta (evita
heredocs anidados dentro de sustituciones de proceso, que 3.2 rompe con «File name too long»);
si instalas bash 5 por Homebrew, mejor. Un clon Linux con bash 4/5 no ve el problema.

**Regla del diseño:** lo que no se puede procesar se *retiene*, no se pierde. Un clon
Linux funciona hoy con PDF/OCR, audio, texto, código y noticias; los formatos Apple
esperan en `.pendiente` a que les des una herramienta.

## Qué NO viaja nunca contigo

Los modelos (`.gguf`, GBs) van aparte — bájalos tú y decláralos en `servidores.conf`.
El corpus (`data/`, `silo/`, `capabilities/`) es de cada instancia. Este repo es el
motor: el organismo lo crías tú.
