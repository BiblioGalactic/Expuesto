# R-Shell

Cliente SSH de escritorio hecho con Tauri, React y Rust.

## Por que existe

Este repo no nacio como un producto limpio. Nacio porque me canse de saltar entre una terminal, un cliente SFTP, un panel de metricas y scripts sueltos para levantar servicios del workspace. Preferi un shell de escritorio unico, aunque fuera mas pesado, a mantener cuatro herramientas medias.

La base visual salio de un spike de Figma/Tauri. No la reescribi desde cero porque ya servia para trabajar. Esa decision ahorro semanas, pero deja una cicatriz visible: hay zonas que se sienten producto y otras que todavia huelen a prototipo.

## Estado que puedo sostener con datos

- `pnpm test`: 114 tests en verde, 7 `skip`.
- `cargo test`: 1 test verde, 5 ignorados por depender de SSH real.
- `pnpm build`: genera un bundle principal de unos 1.7 MB minificado.
- El updater esta desactivado a proposito hasta tener un canal de releases propio y verificable.

Los 7 tests saltados no son humo. Son integraciones SSH reales que requieren runtime Tauri y credenciales de fixture. Preferi dejarlos opt-in antes que mantener una suite roja por defecto.

## Que hace bien hoy

- Gestionar conexiones SSH guardadas.
- Abrir terminales persistentes.
- Mostrar metricas remotas.
- Servir de shell para flujos de trabajo del workspace.

## Lo que todavia no vendo como perfecto

- El frontend sigue teniendo piezas heredadas del spike inicial.
- El build web ya funciona, pero el bundle es mas grande de lo que me gustaria.
- Algunas integraciones avanzadas siguen dependiendo de entorno real para dar confianza de verdad.
- El canal de updates no esta listo; por eso esta apagado y no maquillado.

## Estructura util

```text
positronic-brain/
├── src/              # UI React, estado, terminales, conexiones, metricas
├── src-tauri/        # Backend Rust y comandos Tauri
├── docs/             # Notas de integracion y especificaciones operativas
└── tests/            # E2E y soporte de verificacion
```

## Arranque

```bash
pnpm install
pnpm tauri dev
```

Si solo quieres ver el frontend:

```bash
pnpm dev
```

## Tests

Frontend:

```bash
pnpm test
```

Rust:

```bash
cd src-tauri
cargo test
```

Integracion SSH real:

```bash
TAURI_INTEGRATION_TESTS=1 \
TAURI_TEST_HOST=... \
TAURI_TEST_USERNAME=... \
TAURI_TEST_PASSWORD=... \
pnpm test
```

## Decisiones con coste visible

- Elegi Tauri en vez de Electron porque para este caso me importaba mas tener un runtime de escritorio razonable que un ecosistema mas comodo.
- Mantengo las integraciones SSH como pruebas opt-in porque una suite siempre roja degrada el mantenimiento mas que una suite honesta con dependencias declaradas.
- Desactive el updater. Prefiero perder comodidad antes que distribuir una app que apunte a un canal de releases que no controlo.

## Si vienes a tocarlo

No intentes "embellecer" el repo sin mirar comportamiento. Aqui lo importante no es que el README suene moderno; es que la app siga abriendo terminales, guardando perfiles y no rompa el flujo de escritorio del workspace.
