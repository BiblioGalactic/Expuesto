#!/bin/bash
# 📊 =====================================================================
# 📊 DIGNIDAD — ¿están los modelos haciendo su trabajo? Tasa de "buenas" por
# 📊 modelo y rol (la juzga el mismo juez bueno/fallido de la ingesta).
# 📊 Sale de defensa.py + trampa.py. Marca banquillo a los que no cumplen.
# 📊 Uso:  ./dignidad.sh
# 📊 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
DIG="${DIGNIDAD_SCORES:-$BASE/data/dignidad_modelos.json}"
UMBRAL="${DIGNIDAD_UMBRAL:-0.5}"      # por debajo (con ≥3 muestras) = al banquillo
MIN_N="${DIGNIDAD_MIN_N:-3}"

[ -f "$DIG" ] || { echo "📊 Aún no hay dignidad. Corre ./defensa.py o ./trampa.py contra el cluster vivo."; exit 0; }

python3 - "$DIG" "$UMBRAL" "$MIN_N" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); umbral = float(sys.argv[2]); min_n = int(sys.argv[3])
rows = []
for k, v in d.items():
    p = k.split("|")
    rows.append((p[0], p[1] if len(p) > 1 else "?", v))
print("=" * 66)
print(f"{'MODELO':22} {'ROL':14} {'BUE':>4} {'FAL':>4} {'DIGNIDAD':>9}")
print("-" * 66)
for modelo, rol, v in sorted(rows, key=lambda x: -x[2].get("dignidad", 0)):
    b, f = v.get("buenas", 0), v.get("fallidas", 0); dg = v.get("dignidad", 0)
    flag = "  ⚠️ banquillo" if (dg < umbral and (b + f) >= min_n) else ""
    print(f"{modelo:22} {rol:14} {b:>4} {f:>4} {dg:>9.2f}{flag}")
print("=" * 66)
agg = {}
for modelo, rol, v in rows:
    a = agg.setdefault(modelo, {"b": 0, "f": 0}); a["b"] += v.get("buenas", 0); a["f"] += v.get("fallidas", 0)
print("Por modelo (todos sus roles):")
for m, a in sorted(agg.items(), key=lambda x: -(x[1]["b"] / max(1, x[1]["b"] + x[1]["f"]))):
    t = a["b"] + a["f"]
    print(f"  {m:22} dignidad {a['b'] / t if t else 0:.2f}  ({a['b']}/{t})")
PY
