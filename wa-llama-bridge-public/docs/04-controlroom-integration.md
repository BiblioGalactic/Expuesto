# Integracion con ControlRoom

Yo lo gestiono como proceso externo porque asi puedo reiniciar el bridge sin tocar la app de escritorio ni mezclar su ciclo de vida con el de otros servicios.

## Servicio minimo

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

## Stack que tiene sentido

- servicio 1: `llama-server` principal,
- servicio 2: `wa_bridge`,
- servicio 3: fallback o gateway opcional si de verdad lo necesitas.

## Cuidado con `pkill`

El ejemplo es practico, no perfecto. Si en la misma maquina hay otros procesos `node bridge.js` parecidos, conviene afinar mas el comando de parada. Lo importante aqui es la idea: tratar el bridge como proceso independiente, no como plugin oculto.
