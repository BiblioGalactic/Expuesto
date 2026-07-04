# vigia.sh

> 🩺 VIGÍA — watchdog de salud del MacBook

## Qué hace

🩺 VIGÍA — watchdog de salud del MacBook
🩺 Vigila la carga; si lleva demasiado tiempo A TOPE, levanta data/pausa.flag
🩺 y el bucle continuo PAUSA la ingesta hasta que se enfría.
🩺 Stats LOCALES (córrelo en el MacBook) o por SSH (VIGIA_SSH=user@ip; p.ej.
🩺 desde el mini cuando tengas las llaves). Veredicto en lenguaje natural vía el 8B.
🩺 Uso:  ./vigia.sh          (bucle; Ctrl+C para parar)

## Piezas clave

- `leer_pct`
- `log`
- `veredicto`

---
_Auto-documentado desde la cabecera de `vigia.sh`. Parte de MOSAIC._
