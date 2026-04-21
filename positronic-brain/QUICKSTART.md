# Quick Start - R-Shell

Este repo ya no esta en fase "mira que bonita la UI". La parte visual abre y responde, pero el valor real aparece cuando lo conectas a maquinas SSH de verdad y al runtime Tauri.

## Lo minimo que necesitas

- Node.js y `pnpm`
- Rust estable
- dependencias de Tauri para tu sistema

## Primer arranque

```bash
pnpm install
pnpm tauri dev
```

Si solo quieres revisar el frontend:

```bash
pnpm dev
```

## Que esta verificado ahora mismo

- El frontend compila.
- `pnpm test` deja 114 tests verdes y 7 `skip`.
- `cargo test` pasa en la parte Rust que no depende de SSH real.

## Que sigue dependiendo de entorno real

- conexiones SSH,
- autenticacion por password o clave,
- lectura de metricas remotas,
- algunas pruebas de integracion.

No oculto eso porque es justo donde mas tiempo se pierde cuando uno entra nuevo al repo: la UI parece terminada mucho antes de que el flujo operativo lo este.

## Variables para integracion SSH

Si quieres ejecutar la parte de pruebas que de verdad toca SSH:

```bash
export TAURI_INTEGRATION_TESTS=1
export TAURI_TEST_HOST=tu-host
export TAURI_TEST_USERNAME=tu-usuario
export TAURI_TEST_PASSWORD=tu-password
pnpm test
```

## Dos notas honestas

- El updater esta apagado a proposito. No hay canal de releases fiable para esta build.
- Si vienes de una app tipo terminal "ligera", aqui vas a encontrar mas interfaz de la que esperas. Fue una decision consciente: priorice centralizar el trabajo sobre minimizar superficie.
