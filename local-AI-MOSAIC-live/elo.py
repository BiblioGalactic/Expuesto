#!/usr/bin/env python3
"""
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
"""
import json
import os
import sys
from pathlib import Path

ELO = Path(os.getenv("ELO_PATH", "data/elo.json"))
ROLES_LOG = Path(os.getenv("TRIBUNAL_ROLES_CONS", "data/tribunal_roles.consolidado.jsonl"))
K = float(os.getenv("ELO_K", "24"))   # factor K: cuánto se mueve el Elo por enfrentamiento

# Semilla (clasificación inicial; opinión que el uso corrige). GB aproximados para el plan.
SEED = {
    "Mistral-Small-24B": (2750, 19), "DeepSeek-R1-Qwen3-8B": (2650, 4.7),
    "Qwen2.5-Coder-14B": (2600, 8.4), "Qwen2.5-Coder-7B": (2500, 4.7),   # lentes de código (roster 3-jul)
    "Qwen3-14B": (2550, 8.4), "Qwen3.5-9B": (2550, 5.5), "Qwen3-8B": (2550, 4.7),
    # 🐣 arsenal de especialistas pequeños (doctrina 3-jul: el modelo justo para cada tarea)
    "Qwen2.5-Coder-3B": (2450, 1.9), "Phi-4-mini": (2450, 2.5),
    "Qwen2.5-3B": (2400, 1.9), "Qwen2.5-1.5B": (2300, 1.0),
    "Dolphin3-8B": (2450, 4.6), "Ministral-8B": (2400, 8.0), "OLMo-3-7B": (2300, 8.0),
    "Mistral-7B-v0.1": (1850, 5.0), "Unholy-13B": (1800, 13), "mythomax-13B": (1800, 7.4),
    "meditron-7B": (1600, 4.4),
}


def cargar():
    if ELO.exists():
        try:
            return json.loads(ELO.read_text())
        except Exception:
            pass
    return {}


def guardar(d):
    ELO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ELO.with_name(f"{ELO.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ELO)   # atómico


def _elo(d, m):
    return d.get(m, {}).get("elo", SEED.get(m, (1500, 0))[0])


def actualizar(ganador, perdedor, k=K):
    d = cargar()
    ra, rb = _elo(d, ganador), _elo(d, perdedor)
    ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))   # probabilidad esperada de que gane A
    for m, real, base in ((ganador, 1.0, ra), (perdedor, 0.0, rb)):
        exp = ea if m == ganador else (1.0 - ea)
        e = d.get(m, {})
        e["elo"] = round(base + k * (real - exp), 1)
        e["n"] = e.get("n", 0) + 1
        d[m] = e
    guardar(d)
    return _elo(d, ganador), _elo(d, perdedor)


def sembrar():
    d = cargar()
    add = 0
    for m, (v, gb) in SEED.items():
        if m not in d:
            d[m] = {"elo": float(v), "n": 0, "gb": gb}
            add += 1
    guardar(d)
    print(f"Sembrados {add} modelos nuevos ({len(d)} en total) -> {ELO}")


def ranking():
    d = cargar()
    if not d:
        print("Elo vacío. Usa: ./elo.py seed"); return
    print("  ELO   (n)   modelo")
    for m, e in sorted(d.items(), key=lambda x: -x[1].get("elo", 0)):
        print(f"  {e.get('elo', 0):6.0f} (n{e.get('n', 0):>3})  {m}")


def desde_tribunal():
    """Deriva enfrentamientos del registro consolidado del tribunal: en cada juicio, el
    actor mejor puntuado 'gana' al peor (pares por rol). Así el Elo aprende de los juicios."""
    if not ROLES_LOG.exists():
        print(f"No hay {ROLES_LOG} (consolida el tribunal primero)."); return
    # agrupa por timestamp (un juicio) las marcas de actores y enfrenta mejor vs peor
    from collections import defaultdict
    porjuicio = defaultdict(list)
    for ln in ROLES_LOG.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
            porjuicio[r.get("ts")].append((r.get("modelo"), float(r.get("score", 0.5))))
        except Exception:
            pass
    juegos = 0
    for ts, marcas in porjuicio.items():
        ms = [m for m in marcas if m[0]]
        if len(ms) < 2:
            continue
        ms.sort(key=lambda x: -x[1])
        if ms[0][1] > ms[-1][1] and ms[0][0] != ms[-1][0]:
            actualizar(ms[0][0], ms[-1][0]); juegos += 1
    print(f"Elo actualizado con {juegos} enfrentamientos del tribunal.")


def plan():
    """Sugerencia: quién se queda (alto Elo), quién rota, quién se archiva (bajo Elo o nicho)."""
    d = cargar()
    if not d:
        sembrar(); d = cargar()
    filas = sorted(d.items(), key=lambda x: -x[1].get("elo", 0))
    print("Sugerencia (Elo manda; ajústalo con el uso):")
    for m, e in filas:
        elo, gb = e.get("elo", 0), e.get("gb", SEED.get(m, (0, 0))[1])
        if elo >= 2500:
            destino = "MacBook (fijo: pesos pesados / ejecutor)"
        elif elo >= 2300:
            destino = "Mini o MacBook (rota: juez/ligeras)"
        elif "Unholy" in m or "mythomax" in m or "Dolphin" in m:
            destino = "MacBook (rama seguridad: atacantes sin censura)"
        elif elo >= 1900:
            destino = "rota / según hueco"
        else:
            destino = "→ SSD (archivo: nicho / desfasado)"
        print(f"  {elo:6.0f}  {gb:>4}GB  {m:24} -> {destino}")


def main():
    a = sys.argv[1:]
    if not a:
        ranking()
    elif a[0] == "seed":
        sembrar()
    elif a[0] == "win" and len(a) >= 3:
        na, nb = actualizar(a[1], a[2])
        print(f"{a[1]} {na:.0f}  ·  {a[2]} {nb:.0f}")
    elif a[0] == "tribunal":
        desde_tribunal()
    elif a[0] == "plan":
        plan()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
