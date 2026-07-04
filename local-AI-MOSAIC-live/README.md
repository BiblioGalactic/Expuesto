# 🧩 MOSAIC live — un RAG de capacidades que se auto-extiende

> **MOSAIC no recupera datos: recupera *habilidades*.** Detecta lo que no sabe hacer
> (un *hueco*), lo registra y **genera él mismo la capacidad que falta**. Local-first
> sobre [`llama.cpp`](https://github.com/ggml-org/llama.cpp), en dos máquinas domésticas
> coordinadas (una genera, otra juzga). Todo el pegamento es **bash + Python (stdlib)**,
> sin frameworks.

Este repo es el **sistema vivo**. El linaje completo está publicado aparte:
el [paper del paradigma MOSAIC](https://github.com/BiblioGalactic/Prime_Radiant/tree/main/local-AI-MOSAIC)
(oct-2025, por qué componer agentes desde capacidades recuperables) y el
[whitepaper de Symbiont](https://github.com/BiblioGalactic/Prime_Radiant/tree/main/local-AI-Symbiont)
(jun-2026, el organismo que se cultiva solo). Aquí está lo que pasó cuando aquello se
construyó de verdad y se dejó correr.

## Qué es de verdad

Un sistema que come **material real** (PDFs con OCR, audio por whisper, vídeo, fotos de
iPhone, Excel, libros, noticias, código de GitHub, conversaciones con IAs), detecta qué
no sabe hacer con él, y se escribe sus propias capacidades — instrucciones recuperables
que luego COMPONE sobre cualquier modelo local. La biblioteca resultante es una
**máscara de competencia portátil**: no son pesos, son prompts cultivados con juez
independiente; se ponen sobre el modelo que elijas.

No es un producto. Es un organismo doméstico con siete fases y un gobernador que lee
sus propias actas y decide cómo lanzarse la próxima vez.

## Cómo se construyó (el método también es el proyecto)

Lo construimos **un humano y dos IAs con roles fijos** — una audita, otra construye —
escribiéndonos **cartas** en un epistolar que es la fuente de verdad del proyecto: cada
decisión, cada bug, cada mea culpa queda escrito ANTES de tocar código. El propio
MOSAIC tiene silla en esa mesa: un modo de autodiagnóstico donde lee su estado y
propone — con permiso acotado a *palabra*, jamás manos. Las cartas son privadas; el
método viaja: propón primero, aplica después; backup antes de tocar; una mejora por
iteración; y quien aplica, apunta.

## Estado que puedo sostener con datos (4-jul-2026)

- **~360 capacidades auto-generadas** desde ~550 huecos históricos detectados en material real.
- **CRAG 0.41 → 0.53** en tandas recientes; la nota del juez saturó en 4/5 (por eso la
  señal real es el CRAG, y lo contamos tal cual).
- **A/B composición-vs-crudo:** primeras victorias reales de la máscara (de 0-0-5 a 2-1-2).
  Joven, pero ya discrimina.
- **Defensa de código ajeno** con 4 lentes (intención · código · adversarial · juez) +
  sandbox, **fail-closed**: lo que no se pudo observar no se aprueba.
- **Flota de especialistas**: 4 medianos (13-14B) en la máquina fuerte + juez pequeño (3B)
  y banco a demanda en la modesta. Sin gigantes: la velocidad real son 2 GPUs trabajando.
- **Consola TUI** (`monitor.py`): ver · saber · escribir · respirar · mandar · opinar ·
  compartir — el puente de mando completo en una terminal.

## Lo que todavía no vendo como perfecto

- El A/B es joven: victorias sí, racha estable aún no. La firma multilingüe (FNC) existe
  pero sigue apagada hasta tener medida honesta.
- El OCR de recibos escaneados flojea (retiene, no pierde — pero flojea).
- **macOS-first**: `textutil`/`sips` no existen en Linux; esos formatos se *retienen* en
  vez de procesarse (el diseño aguanta; el detalle en `docs/PORTABILIDAD.md`).
- Los números de arriba son de MI corpus y MI flota; tu kilometraje variará — y esa es
  la gracia: tu clon aprende de TUS huecos.

## Arquitectura en un vistazo

```
  ENTRADAS (tus archivos reales: PDF+OCR, audio→whisper, vídeo, imágenes,
  docs, Excel, iWork, libros, noticias, código de GitHub, conversaciones IA)
      │
      ▼
  🚰 CASCADA anti-humo (con cesión y suelo "nunca cero")          FASE 1
      libro → conversación → oráculo → cuarentena → noticias
      → recuperación (rescata huecos viejos) → fábrica (ÚLTIMO recurso)
      │            [puerta común: memoria de vistos + dedup semántico]
      ▼
  🏦 BANCO (cola SQLite atómica) ──► lote DISCRIMINADO (primo, diverso)   FASE 2
      │                    un MEDIANO ejecuta ‖ el pequeño JUZGA (2ª máquina)
      ▼
  ⚖️ TRIBUNAL adversarial (muestra; en 2º plano)                  FASE 3
  🌱 APRENDER: hueco → capacidad nueva + consolidar (juez+poda+A/B)  FASE 4
  📊 PANEL (tendencia; la señal real es el CRAG, no la nota)       FASE 5
  📜 ACTA del ciclo (el sistema destila su propio resultado)       FASE 6
  🧭 GOBERNADOR (lee las actas y auto-afina el PRÓXIMO lanzamiento) FASE 7
```

La pieza rara y valiosa: **FASE 6/7 = propiocepción**. El sistema se lee a sí mismo
(actas destiladas, no logs crudos) y decide, sobre valores acotados con histéresis,
cómo lanzarse la próxima vez — y deja escrito el porqué.

Diagramas grandes en `docs/` (flujo de datos completo, cascada de ingesta, rama de
seguridad, ciclo de vida del dato). Detalle por fase en `docs/ARQUITECTURA.md`.

## Requisitos

| Qué | Detalle |
|---|---|
| SO | macOS (bash 5) — portable a Linux con matices (ver `docs/PORTABILIDAD.md`) |
| Núcleo | `python3` (≥3.9, stdlib), `curl`, `git`, `ssh` (para la 2ª máquina) |
| LLMs | `llama.cpp` (`llama-server`) + tus `.gguf`: medianos (13-14B) en la fuerte, pequeños (1-4B) en la modesta |
| PDF/OCR | `pdftotext`, `pdftoppm` (poppler) · `tesseract` |
| Audio/vídeo | `openai-whisper` · `ffmpeg` |
| Opcional | venv con `sentence-transformers` (dedup semántico; sin él degrada a léxico) · `textual` (consola) |

Sin cluster arrancado, muchas piezas tienen modo `--offline`/mock para probar el flujo.

## Instalación y primer ciclo

```bash
git clone <este-repo> && cd local-AI-MOSAIC-live
./setup.sh                        # verifica binarios, crea estructura, .env, selftest
cp servidores.conf.example servidores.conf   # TU flota (máquinas, puertos, .gguf)
nano .env                         # TU red (IPs/hosts de tus dos máquinas)

# probar SIN modelos (mock):
./mosaic.sh --offline "escribe una función async en python con tests"
./tribunal.py --offline "¿capital de Francia?" "París"

# tira CUALQUIER archivo al silo y corre un ciclo completo:
cp ~/Documentos/cualquiera.pdf silo/
./mosaic.sh ciclo

# la consola (requiere: pip install textual):
./monitor.py
```

Guía de uso real (aprender de TU uso, el bucle continuo, los packs) en `docs/USO.md`.

## Compartir máscaras: los packs

La biblioteca cultivada se puede **exportar como pack** (`./empaquetar.sh <dominio>`):
curado + saneado (PII redactada, whitelist de campos, grafo de sinergias incluido).
Recibir uno ajeno pasa por **aduana**: `./importar.sh pack.mosaic --aplicar` lo analiza
con la misma defensa que el código de GitHub — solo entra con veredicto SEGURO, con
namespace de autor y prior humilde que se recalibra con tu uso. Hay un pack de ejemplo
en `packs/` para probar la aduana sin terceros.

## Qué NO encontrarás aquí

Las **capacidades auto-generadas** (`capabilities/`), los **roles** afinados (`roles/`)
y el corpus del autor no se publican: son la *inteligencia íntima* que cada MOSAIC
aprende por sí mismo. Tu clon empezará con la biblioteca vacía — y la llenará con TUS
huecos. **De eso va esto.**

## Licencia

[MIT](LICENSE) © 2026 Gustavo Silva Da Costa (Eto Demerzel)
