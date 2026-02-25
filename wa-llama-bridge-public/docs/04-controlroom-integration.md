# Integracion con ControlRoom (Tauri)

Este bridge puede gestionarse como proceso externo desde tu ControlRoom.

## Ejemplo de servicio para ControlRoom

```json
{
  "id": "wa_bridge",
  "name": "WA Bridge",
  "cwd": "/absolute/path/to/wa-llama-bridge-public",
  "start": { "program": "node", "args": ["bridge.js"] },
  "stop": { "program": "pkill", "args": ["-f", "node bridge.js"] },
  "logSources": ["stdout", "stderr"]
}
```

## Sugerencia de stack

- Servicio 1: `llama-server` principal
- Servicio 2: `wa_bridge`
- Servicio 3 (opcional): gateway OpenClaw

Asi puedes controlar start/stop/restart y logs en una sola interfaz.

Firma: Eto Demerzel (Gustavo Silva Da Costa)
