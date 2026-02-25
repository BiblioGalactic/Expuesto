# UPDATES 2026-02-25 - V3.1 Parches Tecnicos

Fecha: 25 de febrero de 2026
Objetivo: cerrar tres pendientes tecnicos marcados en la V3.

## Parches aplicados

1. Goldbach timeout / limite de iteraciones
- Archivo: `volumen_memoria/memory_system/launch_MemorySystem.sh`
- Se añadieron:
  - `GOLDBACH_MAX_ITERATIONS` (default 200000)
  - `GOLDBACH_MAX_MS` (default 1500ms)
- Comportamiento: si se exceden limites, el paso Goldbach se omite de forma segura y registra log.

2. Lock anti-concurrencia en multi-agent
- Archivo: `Prime_Radiant/openclaw-Modifier/modifier/scripts/start_multi_agent.sh`
- Se añadió lock de arranque:
  - Primario: `flock` sobre `~/.openclaw/multi-agent.lock`
  - Fallback: lock por directorio (`mkdir`) si `flock` no existe
- Se libera lock en `cleanup()`.

3. Typo GLADIA + compatibilidad
- Archivo: `light-sculpture/docker-entrypoint.sh`
- Cambio visible:
  - `classificationpic.sh` (nombre mostrado correcto)
- Compatibilidad:
  - Se añade alias para que `classificationpic.sh` siga ejecutando `clasificationpic.sh` real.

## Validacion

- `bash -n` OK en los tres scripts.

## Firma

Eto Demerzel (Gustavo Silva Da Costa)
