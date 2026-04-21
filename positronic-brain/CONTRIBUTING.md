# Contributing to R-Shell

## Contexto real

Este repo se usa como shell de trabajo del workspace `Expuesto`. No lo trato como demo de UI ni como sandbox para "vibe coding" sin consecuencias. Si cambias algo aqui, lo normal es que afecte sesiones SSH, persistencia de layout, SFTP, metricas o integracion con servicios externos.

## Antes de abrir una PR

Necesito que la descripcion explique por que tomaste la decision, no solo que cambiaste.

Un buen cambio suele incluir:

- el problema que te encontraste,
- por que elegiste esa solucion y no otra,
- que parte probaste de verdad,
- que deuda dejas abierta si no cerraste todo.

## Checks minimos

Frontend:

```bash
pnpm test
```

Rust:

```bash
cd src-tauri
cargo test
```

Si tu cambio toca integracion SSH real, dilo con claridad. La suite normal deja integraciones en `skip` porque necesitan runtime Tauri y credenciales reales.

## Criterio de calidad

- No acepto commits que solo "mejoran el texto" mientras ocultan limites operativos.
- Si tocas interfaz, prioriza comportamiento y legibilidad de mantenimiento antes que decoracion.
- Si tocas Rust/Tauri, explica riesgos de concurrencia, red o estado persistente.
- Si el cambio deja una cicatriz rara pero util, documentala. No hace falta limpiar todo para que parezca perfecto.

## Bugs y mejoras

Al abrir un issue o una PR, incluye:

- pasos para reproducir,
- comportamiento esperado y real,
- entorno,
- si el fallo ocurre en web, en Tauri o solo con SSH real.

## Commits

No me importa un formalismo excesivo; si me importa que el mensaje deje claro el coste de la decision. Un `fix:` vago vale menos que una frase que diga que se desactivo, que se degrado o que se aislo y por que.
