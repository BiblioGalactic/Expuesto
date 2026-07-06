# discriminar.py

> ✂️ DISCRIMINAR — elige un LOTE diverso del BANCO (cola) para FASE 2, en vez de

## Qué hace

✂️ DISCRIMINAR — elige un LOTE diverso del BANCO (cola) para FASE 2, en vez de
✂️ volcarlo entero. HÍBRIDO:
✂️   · cupos por FUENTE (round-robin) → variedad de origen
✂️   · dentro de cada fuente, DIVERSIDAD por embedding (farthest-point) = tu
✂️     Levenshtein "único + común" del teorema (MiniLM del dedup → léxica de respaldo)
✂️   · ENVEJECIMIENTO: una fracción del lote son SIEMPRE los más antiguos (nadie
✂️     se queda atrás en el banco)
✂️ Marca los elegidos como 'procesando' (estado=1) e imprime sus preguntas (1/línea),
✂️ igual que 'volcar'. Recupera primero lo que quedó a medias (estado 1 → 0).
✂️ Uso:  python3 discriminar.py DB [L]

## Piezas clave

- `_gramas`
- `dist`
- `diversos`
- `volcar`

---
_Auto-documentado desde la cabecera de `discriminar.py`. Parte de MOSAIC._
