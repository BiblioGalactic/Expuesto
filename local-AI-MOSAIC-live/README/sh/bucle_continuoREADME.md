# bucle_continuo.sh

> 🔁 BUCLE CONTINUO v2 — ciclos COMPLETOS encadenados hasta TERMINAR el trabajo.

## Qué hace

🔁 BUCLE CONTINUO v2 — ciclos COMPLETOS encadenados hasta TERMINAR el trabajo.
🔁
🔁 ⚠️  ADVERTENCIA: esto puede correr HORAS o DÍAS (procesamiento continuo).
🔁 ⚠️  Pide CONFIRMACIÓN antes de arrancar (o pásale --si para saltarla).
🔁 ⚠️  Ctrl+C es seguro en cualquier momento (ciclo.sh suelta sus locks).
🔁
🔁 v2 (2-jul-2026, encargo de Gustavo): la v1 era de la época en que SOLO existía
🔁 la fábrica de preguntas (régimen humo). Ahora DELEGA TODO en ciclo.sh —
🔁 cascada anti-humo, banco, pipeline 2 máquinas, tribunal, FASE 7 acta y
🔁 FASE 6 gobernador — y se detiene SOLO cuando no queda trabajo real:
🔁   trabajo = cola pendiente (banco) + archivos en silo + cuarentena.
🔁 (La v1 queda en trash/backups/bucle_continuo.sh.*.bak)
🔁
🔁 Uso:  ./bucle_continuo.sh [CICLOS_MAX] [--si]
🔁         CICLOS_MAX  tope de ciclos (0 o vacío = sin tope, hasta agotar trabajo)
🔁         --si        salta la confirmación (para lanzamientos desatendidos)

## Piezas clave

- `cleanup`
- `confirmar`
- `contar_trabajo`
- `ejecutar`
- `log`
- `validar`

---
_Auto-documentado desde la cabecera de `bucle_continuo.sh`. Parte de MOSAIC._
