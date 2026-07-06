# reportar.sh

> 📋 REPORTAR — EL escritor único y SEGURO del epistolar (RONDA 3 · diseño Opus).

## Qué hace

📋 REPORTAR — EL escritor único y SEGURO del epistolar (RONDA 3 · diseño Opus).
📋   Por aquí pasan TODOS: el modal [R] del monitor, los agentes y el humano.
📋   Mecánica: bloque COMPLETO en tmp → cerrojo (lock.sh, con RETRY) → append
📋   íntegro a info/CARTAS.md → soltar. El monitor ve el mtime y repinta solo.
📋   CARTAS = fuente ÚNICA (decisión de Gustavo, R3): sin actual.md aparte.
📋 Uso:  ./reportar.sh "Informe|Decisión|Incidente|Acción" "titulo" "cuerpo" ["tag1 tag2"] ["autor"]
📋   autor por defecto: $REPORTAR_AUTOR o Gustavo (el humano en la terminal).
📋   AUTOR contra lista CERRADA (P1 orquesta: sin identidades fantasma) — amplía
📋   con REPORTAR_AUTORES_EXTRA="Rol1 Rol2" al registrar un rol nuevo.
📋   Tipo "Acción" (P1): plantilla OBLIGATORIA (Motivación·Cambios·Riesgos·Ficheros·
📋   Reversibilidad) + id ACC-fecha-NN + auto-registro en data/acciones.json (el libro
📋   de sellos: un ✅ en el TEXTO vale CERO; sellar.sh es el único que sella).

## Piezas clave

- `cleanup`
- `ejecutar`
- `emoji_de`
- `err`
- `log`
- `registrar_accion`
- `validar`

---
_Auto-documentado desde la cabecera de `reportar.sh`. Parte de MOSAIC._
