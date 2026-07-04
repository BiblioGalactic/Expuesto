#!/usr/bin/env python3
# ✂️ =====================================================================
# ✂️ DISCRIMINAR — elige un LOTE diverso del BANCO (cola) para FASE 2, en vez de
# ✂️ volcarlo entero. HÍBRIDO:
# ✂️   · cupos por FUENTE (round-robin) → variedad de origen
# ✂️   · dentro de cada fuente, DIVERSIDAD por embedding (farthest-point) = tu
# ✂️     Levenshtein "único + común" del teorema (MiniLM del dedup → léxica de respaldo)
# ✂️   · ENVEJECIMIENTO: una fracción del lote son SIEMPRE los más antiguos (nadie
# ✂️     se queda atrás en el banco)
# ✂️ Marca los elegidos como 'procesando' (estado=1) e imprime sus preguntas (1/línea),
# ✂️ igual que 'volcar'. Recupera primero lo que quedó a medias (estado 1 → 0).
# ✂️ Uso:  python3 discriminar.py DB [L]
# ✂️ =====================================================================
import os
import sys
import sqlite3
from collections import OrderedDict

DB = sys.argv[1]
L = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.getenv("LOTE_DISPATCH", "23") or 23)
AGING_FRAC = float(os.getenv("DISPATCH_AGING", "0.3") or 0.3)   # 30% del lote = los más antiguos, garantizados
EMB_MODEL = os.getenv("EMB_MODEL", os.path.expanduser("~/modelo/modelos_grandes/semantico/"
                      "models--sentence-transformers--all-MiniLM-L6-v2/snapshots"))

con = sqlite3.connect(DB)
con.execute("PRAGMA busy_timeout=10000")
con.execute("UPDATE cola SET estado=0 WHERE estado=1")   # recupera lo dejado a medias
con.commit()
rows = con.execute("SELECT id, COALESCE(fuente,'?'), COALESCE(pregunta,''), COALESCE(ts,'') "
                   "FROM cola WHERE estado=0 ORDER BY id").fetchall()
if not rows:
    raise SystemExit(0)


def volcar(ids):
    if not ids:
        return
    con.execute("UPDATE cola SET estado=1, ts_proc=datetime('now') WHERE id IN (%s)"
                % ",".join("?" * len(ids)), ids)
    con.commit()
    texto = {r[0]: r[2] for r in rows}
    for i in ids:
        print((texto.get(i) or "").replace("\n", " ").replace("\r", " "))


# si caben todas, es un volcado normal (no hay nada que discriminar)
if len(rows) <= L:
    volcar([r[0] for r in rows])
    raise SystemExit(0)

# --- vectores: MiniLM (semántica) o respaldo léxico (3-gramas de caracteres) ---
V = None
try:
    import glob
    import numpy as np
    from sentence_transformers import SentenceTransformer
    cand = EMB_MODEL
    for c in [EMB_MODEL] + sorted(glob.glob(os.path.join(EMB_MODEL, "*"))):
        if os.path.isdir(c):
            cand = c
            break
    V = np.asarray(SentenceTransformer(cand).encode([r[2] for r in rows], normalize_embeddings=True))
except Exception:
    V = None


def _gramas(s):
    s = s or ""
    return {s[i:i + 3] for i in range(max(len(s) - 2, 1))}


_cache = {}


def dist(i, j):
    if V is not None:
        return 1.0 - float(V[i].dot(V[j]))
    a = _cache.get(i) or _cache.setdefault(i, _gramas(rows[i][2]))
    b = _cache.get(j) or _cache.setdefault(j, _gramas(rows[j][2]))
    u = len(a | b)
    return 1.0 - (len(a & b) / u if u else 0.0)


def diversos(gis):
    """orden farthest-point de índices globales gis (semilla = el más antiguo)."""
    if not gis:
        return []
    sel = [gis[0]]
    restantes = set(gis[1:])
    while restantes:
        best, bd = None, -1.0
        for g in restantes:
            d = min(dist(g, s) for s in sel)
            if d > bd:
                bd, best = d, g
        sel.append(best)
        restantes.discard(best)
    return sel


orden = list(range(len(rows)))                    # ya vienen por id asc (viejo→nuevo)
AG = min(len(rows), max(1, round(L * AGING_FRAC)))
viejos = [rows[i][0] for i in orden[:AG]]         # los más antiguos, garantizados
resto = orden[AG:]
R = L - len(viejos)

# reparto por fuente (round-robin) + diversidad dentro de cada fuente
porf = OrderedDict()
for gi in resto:
    porf.setdefault(rows[gi][1], []).append(gi)
orden_div = {f: diversos(gis) for f, gis in porf.items()}
punteros = {f: 0 for f in porf}
elegidos = []
while len(elegidos) < R and porf:
    avance = False
    for f in list(porf.keys()):
        if len(elegidos) >= R:
            break
        p = punteros[f]
        if p < len(orden_div[f]):
            elegidos.append(rows[orden_div[f][p]][0])
            punteros[f] += 1
            avance = True
    if not avance:
        break

volcar(viejos + elegidos)
sys.stderr.write("✂️ discriminar: modo=%s · lote=%d (viejos=%d + diversos=%d) de %d en banco · fuentes=%d\n"
                 % ("minilm" if V is not None else "lexica",
                    len(viejos) + len(elegidos), len(viejos), len(elegidos), len(rows), len(porf)))
