#!/usr/bin/env python3
"""
SLOTS — arquitectura DINÁMICA de servidores. Desbloquea N slots (no 3 fijos):
muchos PEQUEÑOS en masa, pocos GRANDES en serie, o MIXTO — lo que quepa.
Elige por Elo+tamaño y RESPETA el presupuesto de GPU (esto ES el guard anti-OOM).

Uso:   ./slots.py PERFIL [--dir DIR]
  PERFIL: masa | calidad | mixto | auto
Salida (stdout): "ruta:puerto ruta:puerto ..."  -> para MODELOS_EXTRA de lanzar_cluster.sh
Ajustes (env): MODELOS_DIR, PRESUPUESTO_GB (MacBook≈36, mini≈11), OVERHEAD_GB, BASE_PORT.
"""
import os
import sys
import json
import glob
from pathlib import Path

DIR = os.getenv("MODELOS_DIR", os.path.expanduser("~/modelo/modelos_grandes"))
GB = float(os.getenv("PRESUPUESTO_GB", "36"))       # GPU usable (MacBook ~36, mini ~11)
OVERHEAD = float(os.getenv("OVERHEAD_GB", "1.6"))   # KV-cache + compute por servidor
BASE = int(os.getenv("BASE_PORT", "8092"))          # primer puerto libre tras los fijos 8090/8091
SMALL = float(os.getenv("SMALL_MAX_GB", "5.5"))     # frontera "pequeño"
MED = float(os.getenv("MED_MAX_GB", "14"))          # frontera "mediano"
ELO = Path(os.getenv("ELO_PATH", "data/elo.json"))


def tam_gb(p):
    try:
        return os.path.getsize(p) / (1024 ** 3)
    except OSError:
        return 0.0


def elo_de(fichero, elos):
    """Empareja el nombre del fichero con un nombre del Elo (todos los tokens del Elo en el fichero)."""
    n = fichero.lower()
    best = 1500.0
    for k, v in elos.items():
        toks = [t for t in k.lower().replace("-", " ").replace(".", " ").split() if len(t) > 2]
        if toks and all(t in n for t in toks):
            best = max(best, float(v.get("elo", 1500)))
    return best


def inventario(elos):
    out = []
    for p in glob.glob(os.path.join(DIR, "**", "*.gguf"), recursive=True):
        b = os.path.basename(p)
        if "vocab" in b.lower():
            continue
        g = tam_gb(p)
        if g < 0.1:           # 0 bytes / roto -> fuera
            continue
        out.append((p, round(g, 1), elo_de(b, elos)))
    return out


def empacar(pool, gb):
    """Greedy dentro del presupuesto (= guard anti-OOM): añade mientras quepa."""
    elegidos, usado, puerto = [], 0.0, BASE
    for p, g, e in pool:
        if usado + g + OVERHEAD <= gb:
            elegidos.append((p, puerto, g, e))
            usado += g + OVERHEAD
            puerto += 1
    return elegidos, usado


def main():
    perfil = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "auto"
    try:
        elos = json.loads(ELO.read_text()) if ELO.exists() else {}
    except Exception:
        elos = {}
    cands = inventario(elos)
    if not cands:
        sys.stderr.write(f"[slots] no hay modelos en {DIR}\n")
        return

    if perfil == "masa":            # muchos pequeños -> muchos slots paralelos
        pool = sorted([c for c in cands if c[1] <= SMALL], key=lambda x: -x[2])
    elif perfil == "calidad":       # los de más Elo que quepan (grandes en serie)
        pool = sorted(cands, key=lambda x: (-x[2], -x[1]))
    elif perfil == "mixto":         # 2 medianos + 2 pequeños (por Elo)
        med = sorted([c for c in cands if SMALL < c[1] <= MED], key=lambda x: -x[2])[:2]
        sml = sorted([c for c in cands if c[1] <= SMALL], key=lambda x: -x[2])[:2]
        pool = med + sml
    else:                            # auto: por Elo, lo que quepa
        pool = sorted(cands, key=lambda x: -x[2])

    elegidos, usado = empacar(pool, GB)
    print(" ".join(f"{p}:{pt}" for p, pt, _, _ in elegidos))   # <- para MODELOS_EXTRA
    sys.stderr.write(f"[slots] perfil={perfil}  presupuesto={GB:.0f}GB  ->  "
                     f"{len(elegidos)} servidores, {usado:.1f}GB usados\n")
    for p, pt, g, e in elegidos:
        sys.stderr.write(f"   :{pt}  {g:>4}GB  Elo {e:>4.0f}  {os.path.basename(p)}\n")


if __name__ == "__main__":
    main()
