# flota.sh

> 🚚 FLOTA — reparte los modelos entre  MacBook (48GB) · MacMini (16GB) · SSD (archivo maestro)

## Qué hace

🚚 FLOTA — reparte los modelos entre  MacBook (48GB) · MacMini (16GB) · SSD (archivo maestro)
🚚 · Archiva los OBSOLETOS del MacBook a la SSD con VERIFICACIÓN antes de borrar
🚚 · Descarga/coloca el set de trabajo de cada máquina (Mini ≥3: 2+emergencia · MacBook 4-6)
🚚 · Comprueba: sin pérdidas, sin duplicados
🚚 REGLA DE ORO: NADA se borra del MacBook sin una copia CONFIRMADA (tamaño exacto) en la SSD.
🚚 La SSD está enchufada al MacMini → todo va por ssh+rsync (ojo al ESPACIO en "Extreme SSD").
🚚 Uso:  ./flota.sh reportar
🚚       ./flota.sh archivar            # DRY-RUN (enseña; no toca nada)
🚚       ./flota.sh archivar --aplicar  # ejecuta (rsync→verifica→borra original)
🚚       ./flota.sh descargar [--aplicar]
🚚       ./flota.sh verificar

## Piezas clave

- `archivar`
- `cleanup`
- `descargar`
- `die`
- `hHR`
- `log`
- `reportar`
- `tam_local`
- `tam_remoto`
- `validar`
- `verificar`
- `warn`

---
_Auto-documentado desde la cabecera de `flota.sh`. Parte de MOSAIC._
