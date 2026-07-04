#!/usr/bin/env python3
# 🔁 =====================================================================
# 🔁 RECUPERAR — el paso RIEMANN del teorema de memoria, aplicado a la ingesta.
# 🔁 Cuando las fuentes vivas ceden por vacío, en vez de fabricar HUMO se rescata
# 🔁 de la MEMORIA de huecos los que PEOR salieron (más baja calidad) y se re-proponen
# 🔁 como PRÁCTICA real. Rota con un cursor para no repetir siempre los mismos.
# 🔁 Imprime cada 'request' en una línea (el shell los re-encola). "Recuperar de la
# 🔁 copia antes que inventar."
# 🔁 Uso:  RECUP_MAX=N python3 recuperar.py     (imprime hasta N peticiones)
# 🔁 =====================================================================
import json
import os
import sys

BASE = os.getenv("MOSAIC_DIR", os.path.expanduser("~/Mosaic_privado"))
HUECOS = os.getenv("HUECOS_JSON", os.path.join(BASE, "data", "huecos.consolidado.json"))
CURSOR = os.getenv("RECUP_CURSOR", os.path.join(BASE, "data", "recuperacion.cursor"))
N = int(os.getenv("RECUP_MAX", "0") or 0)
UMBRAL = float(os.getenv("RECUP_UMBRAL_CALIDAD", "0.6"))   # solo los que costaron (calidad < esto)


def salir():
    raise SystemExit(0)


if N <= 0:
    salir()
try:
    huecos = json.load(open(HUECOS, encoding="utf-8"))
except Exception:
    salir()
if not isinstance(huecos, list):
    salir()

# candidatos: los que tienen texto y baja calidad (merecen práctica); peor calidad primero
cand = [h for h in huecos
        if isinstance(h, dict) and str(h.get("request", "")).strip()
        and float(h.get("quality", 1) or 1) < UMBRAL]
cand.sort(key=lambda h: float(h.get("quality", 1) or 1))
if not cand:
    salir()

# cursor rotatorio: no repetir siempre los mismos; barre de peor a mejor a lo largo de los ciclos
try:
    cur = int(open(CURSOR).read().strip())
except Exception:
    cur = 0
cur %= len(cand)
k = min(N, len(cand))
sel = [cand[(cur + i) % len(cand)] for i in range(k)]
for h in sel:
    print(str(h["request"]).replace("\n", " ").replace("\r", " ").strip())

try:
    with open(CURSOR, "w", encoding="utf-8") as fh:
        fh.write(str((cur + k) % len(cand)))
except Exception:
    pass
