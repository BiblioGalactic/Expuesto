# debrief.sh

> 🧭 DEBRIEF — el mapa del ciclo en ~20 líneas (diseño de la MESA, 4-jul-2026).

## Qué hace

🧭 DEBRIEF — el mapa del ciclo en ~20 líneas (diseño de la MESA, 4-jul-2026).
🧭   · ESPEJO del acta (regla de MOSAIC: se LEE data/actas/acta_*.json, jamás se recalcula)
🧭   · cada fila con su ANCLA grep-able (regla de Opus/Fable: función, no línea)
🧭   · semáforo de colores (petición de Gustavo: verde=bien · ámbar=ojo · rojo=roto)
🧭   · delta vs acta anterior (Opus/el Nuevo) · flags vivos (Fable) · bucle acta→gobernador
🧭     y procedencia del banco (MOSAIC) · guarda copia PLANA en data/debrief_ultimo.md
🧭 Uso:  dentro del ciclo lo llama ciclo.sh (DEBRIEF=0 lo apaga) ·
🧭       en frío: ./debrief.sh  (reimprime el panel del ÚLTIMO acta, sin marcas de fase)

## Piezas clave

- `ejecutar`
- `estado_fase`
- `fila`
- `marca`
- `validar`

---
_Auto-documentado desde la cabecera de `debrief.sh`. Parte de MOSAIC._
