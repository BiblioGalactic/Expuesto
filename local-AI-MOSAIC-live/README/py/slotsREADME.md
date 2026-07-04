# slots.py

> SLOTS — arquitectura DINÁMICA de servidores. Desbloquea N slots (no 3 fijos):

## Qué hace

SLOTS — arquitectura DINÁMICA de servidores. Desbloquea N slots (no 3 fijos):
muchos PEQUEÑOS en masa, pocos GRANDES en serie, o MIXTO — lo que quepa.
Elige por Elo+tamaño y RESPETA el presupuesto de GPU (esto ES el guard anti-OOM).

Uso:   ./slots.py PERFIL [--dir DIR]
  PERFIL: masa | calidad | mixto | auto
Salida (stdout): "ruta:puerto ruta:puerto ..."  -> para MODELOS_EXTRA de lanzar_cluster.sh
Ajustes (env): MODELOS_DIR, PRESUPUESTO_GB (MacBook≈36, mini≈11), OVERHEAD_GB, BASE_PORT.

## Piezas clave

- `elo_de`
- `empacar`
- `inventario`
- `main`
- `tam_gb`

---
_Auto-documentado desde la cabecera de `slots.py`. Parte de MOSAIC._
