# elo.py

> ELO — ranking de modelos estilo ajedrez. La MONEDA que une el tribunal (#39) con la

## Qué hace

ELO — ranking de modelos estilo ajedrez. La MONEDA que une el tribunal (#39) con la
gestión de hardware: quién merece servidor, quién rota y quién se archiva.

Semilla desde la clasificación inicial; con el uso se vuelve REAL (cada enfrentamiento
mueve el Elo con la fórmula del ajedrez). Escritura atómica (Ctrl+C seguro).

Uso:
  ./elo.py                         # ranking actual
  ./elo.py seed                    # (re)siembra los que falten
  ./elo.py win  GANADOR PERDEDOR   # registra un enfrentamiento -> actualiza Elo
  ./elo.py tribunal                # deriva enfrentamientos del registro del tribunal
  ./elo.py plan                    # sugiere quién se queda / rota / se archiva

## Piezas clave

- `_elo`
- `actualizar`
- `cargar`
- `desde_tribunal`
- `guardar`
- `main`
- `plan`
- `ranking`
- `sembrar`

---
_Auto-documentado desde la cabecera de `elo.py`. Parte de MOSAIC._
