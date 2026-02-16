# ARCHITECTURE.md — Expuesto

## Visión General

Expuesto es un toolkit multilingüe de IA local construido sobre `llama.cpp` y modelos GGUF (Mistral 7B). El proyecto organiza scripts bash y Python en módulos independientes que comparten una infraestructura común (`lib/bash-common.sh`, `.expuesto/config.env`).

```
Expuesto/
├── .expuesto/config.env         ← Configuración centralizada
├── lib/bash-common.sh           ← Librería compartida (sanitización, logging, SHA256)
├── Prime_Radiant/               ← Motor central: daemons, RAG, agentes
├── Robotsdelamanecer/           ← 5 perfiles de personalidad IA
├── volumen_bucle/               ← Loop IA multilingüe (7 idiomas)
├── volumen_memoria/             ← Sistema de memoria dinámica
├── volumen_linguistic_composition/ ← Composición lingüística y perfiles
├── volumen_overhead/            ← Infraestructura Docker
├── light-sculpture/             ← Procesamiento multimedia (GLADIA)
├── the-caves-of-steel/          ← Documentación multilingüe
├── we/                          ← Módulos de datos narrativos
└── tests/                       ← ShellCheck + pytest + e2e
```

## Módulos Principales

### Prime_Radiant — Motor Central

Contiene los subsistemas más avanzados del proyecto:

**local-AIDaemon-agentic-rag-adaptative/** es el sistema principal con 5 versiones evolutivas (A1 → E5). Cada versión refina la arquitectura de agentes RAG adaptativos. E5 es la versión activa (A1–D4 deprecadas). Componentes compartidos: `agents/` (base_agent, planner, validator, executor, react_agent, rag_agent) y `core/` (queue_manager, shared_state, evaluator, memory, model_router, orchestrator).

Otros subsistemas: `local-AI-CRAG/` (Corrective RAG), `local-AI-MOSAIC/` (procesamiento multimodal), `local-AI-cluster/` (ejecución distribuida), `local-agentic-MCP/` (servidor MCP con 11 tools), `local-agentic-assistant/` (instalador avanzado de asistente local), `local-AI-MMAP-memory/` (RAM-IA con memory mapping en C), `local-IA-modular-memory/` (memoria modular), `local-AI-git-Commit/` (commits automáticos con IA), `local-cross-eval-synth/` (evaluación cruzada), `Marion-Stokes/` (RAG builders), `openclaw-Modifier/` (modificación de modelos).

### Robotsdelamanecer — Perfiles de Personalidad

5 robots con personalidades distintas, cada uno con su prompt y directorio de destino:

| Robot | Archivo | Descripción |
|-------|---------|-------------|
| HAL_10 | `HAL_10/HAL_10.sh` | Perfil analítico |
| Da1ta1 | `Da1ta1/Da1ta1.sh` | Perfil creativo |
| CC-33PPOO | `CC-33PPOO/CC-33PPOO.sh` | Perfil protocolar |
| VENDER | `VENDER/VENDER.sh` | Perfil comercial |
| R12D12 | `D12R12/R12D12.sh` | Perfil técnico |

Todos sourcean `lib/bash-common.sh`, usan config centralizada, tienen rotación de logs por conteo de archivos (`rotate_old_logs()`), cleanup con trap, y validación de entorno.

### volumen_bucle — Loop IA Multilingüe

Sistema de bucle conversacional en 7 idiomas, refactorizado a arquitectura DRY:

```
volumen_bucle/
├── lib/
│   ├── base.sh              ← Motor compartido (run_loop, rotación, validación)
│   └── strings/
│       ├── es.sh  en.sh  cat.sh  eus.sh  jp.sh  zh.sh  fr.sh
├── bucleia/bucleia.sh        ← Wrapper ES (7 líneas)
├── loopai/loopai.sh          ← Wrapper EN
├── rodaia/rodaia.sh          ← Wrapper CAT
├── birakaia/birakaia.sh      ← Wrapper EUS
├── ループAI/ループAI.sh        ← Wrapper JP
├── 循環AI/循环AI.sh           ← Wrapper ZH
├── autoconversacion.sh (×6)  ← Conversación automática por idioma
└── Auto-narrative/ (×8)      ← Autonarrativa por idioma
```

Cada wrapper define 4 variables (`LOOP_LANG`, `LOOP_PROMPT_SISTEMA`, `LOOP_PROMPT_FILE`, `LOOP_SESSIONS_DIR`) y sourcea `lib/base.sh`, que resuelve rutas, carga i18n, rota logs y ejecuta `run_loop()`.

### volumen_memoria — Memoria Dinámica

`memory_system/launch_MemorySystem.sh` gestiona la memoria de contexto del LLM usando heurísticas matemáticas (distancia de Levenshtein, conjeturas de Collatz/Goldbach, hipótesis de Riemann operativa). Expande o contrae el contexto dinámicamente.

### light-sculpture/GLADIA — Procesamiento Multimedia

12 scripts para procesamiento de audio/video: `media_trimmer`, `spectrograf`, `video_translator`, `youtube_downloader`, `audio_separator`, `musicanalisys`, `musicparametres`, `quickanalisys`, `split_audio_video`, `videoanalisys`, `multiplatform_downloader`, `jamendo_downloader`. Todos sin `sudo` directo (mensajes informativos al usuario).

### volumen_linguistic_composition — Composición Lingüística

Módulos de información (`INFORMATION/`), perfiles (`PERFIL/`), plantillas README (`README/`) y tablas de datos (`TABLA/`).

### volumen_overhead — Infraestructura

`Docker-origami/` — Configuraciones Docker para despliegue.

### the-caves-of-steel — Documentación

Hub de documentación multilingüe: guías de IA en catalán, inglés, español, euskera, francés, japonés y chino. Sin scripts ejecutables.

### we — Datos Narrativos

Módulos `0-90/`, `D-503/`, `I-330/` — datos y referencias narrativas.

## Infraestructura Compartida

### Configuración Centralizada (`.expuesto/config.env`)

Fuente única de verdad para rutas y parámetros. Define `LLAMA_CLI`, `MODELO`, `MODELS_DIR`, parámetros de llama-cli (`CTX_SIZE`, `THREADS`, `TEMP`, `N_PREDICT`), y configuración de logs (`LOG_MAX_LINES`, `LOG_ROTATE_COUNT`).

### Librería Común (`lib/bash-common.sh`)

Funciones reutilizables con guard de doble-source:

| Función | Propósito |
|---------|-----------|
| `sanitize_path()` | Rechaza caracteres peligrosos en rutas (`;|&><!"$\`(){}`) |
| `sanitize_integer()` | Valida enteros positivos |
| `require_file/executable/dir/command()` | Validación de dependencias |
| `rotate_log()` | Rotación por conteo de líneas |
| `verify_sha256()` | Verificación SHA256 dual (sha256sum/shasum) |
| `cleanup_generic()` | Limpieza con trap EXIT |
| `load_config()` | Carga config.env |
| `info/ok/warn/error/die/step()` | Logging con timestamps y colores |

### Pipeline CI/CD (`.github/workflows/ci.yml`)

Ejecuta en cada push/PR a main: ShellCheck lint → pytest → tests e2e → gate de validación.

## Diagrama de Dependencias

```
┌─────────────────────────────────────────────────┐
│                 .expuesto/config.env             │
└──────────────────────┬──────────────────────────┘
                       │ source
┌──────────────────────▼──────────────────────────┐
│              lib/bash-common.sh                  │
│  (sanitize, validate, rotate, verify, log)       │
└──┬───────┬───────┬───────┬───────┬──────────────┘
   │       │       │       │       │
   ▼       ▼       ▼       ▼       ▼
┌──────┐┌──────┐┌──────┐┌──────┐┌──────────────┐
│Robots││volumen││volumen││light-││Prime_Radiant │
│del   ││bucle ││memoria││sculpt││  RAM-IA      │
│amane ││      ││       ││ure   ││  AIDaemon E5 │
│cer   ││      ││       ││      ││  MCP/cluster │
└──────┘└──┬───┘└──────┘└──────┘└──────────────┘
           │
           ▼
┌──────────────────────┐
│ volumen_bucle/lib/   │
│  base.sh + strings/  │
│  (i18n motor)        │
└──────────────────────┘
```

## Stack Tecnológico

| Componente | Tecnología |
|------------|-----------|
| Runtime IA | llama.cpp (llama-cli) |
| Modelo | Mistral 7B Instruct v0.1 Q6_K (GGUF) |
| Shell | Bash 5 (#!/usr/bin/env bash) |
| Python | 3.x (agentes, RAG, evaluación) |
| Memory mapping | C compilado en runtime (RAM-IA) |
| CI/CD | GitHub Actions |
| Lint | ShellCheck |
| Tests | pytest + bash e2e |
| OS target | macOS (primario) + Linux |
