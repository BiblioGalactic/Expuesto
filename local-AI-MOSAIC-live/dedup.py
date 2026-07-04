#!/usr/bin/env python3
# 🧬 =====================================================================
# 🧬 DEDUP — servicio COMÚN de similitud semántica (MiniLM → léxica de respaldo).
# 🧬 Extraído de gobernanza (#60) para que lo usen TODAS las fuentes y no se
# 🧬 reprocesen entradas equivalentes entre sí. Bajo consumo: carga el modelo
# 🧬 UNA vez por llamada (pensado para LOTES); índice persistente y acotado.
# 🧬 API:   from dedup import make_sim
# 🧬 CLI:   echo "texto" | dedup.py parecido --indice data/dedup_index.jsonl --umbral 0.82
# 🧬           -> exit 0 = ya hay algo parecido (DUP) · exit 1 = NUEVO (lo registra)
# 🧬         dedup.py nuevos --indice ... --umbral 0.82 f1.txt f2.txt ...
# 🧬           -> imprime "NUEVO<TAB>fichero" / "DUP<TAB>fichero" (UNA carga de modelo,
# 🧬              deduplica contra el índice Y dentro del propio lote)
# 🧬 =====================================================================
import os, sys, glob, json
from pathlib import Path

EMB_MODEL = os.getenv("EMB_MODEL", os.path.expanduser("~/modelo/modelos_grandes/semantico/"
                      "models--sentence-transformers--all-MiniLM-L6-v2/snapshots"))
INDEX_MAX = int(os.getenv("DEDUP_INDEX_MAX", "1000"))    # acota coste/RAM del índice


def make_sim(patterns):
    """(fn_similitud, modo). MiniLM (semántica) → léxica (difflib) de respaldo.
    Idéntico al que vivía en gobernanza; lo importa gobernanza (#60)."""
    try:
        cand = EMB_MODEL if os.path.isdir(EMB_MODEL) else next(iter(glob.glob(EMB_MODEL + "*")), "")
        if cand and os.path.isdir(cand):
            from sentence_transformers import SentenceTransformer
            import numpy as np
            m = SentenceTransformer(cand)
            base = m.encode(patterns) if patterns else []

            def sim(t):
                if len(base) == 0:
                    return 0.0
                e = m.encode([t])[0]
                return max(float(np.dot(e, b) / ((np.linalg.norm(e) * np.linalg.norm(b)) or 1)) for b in base)
            return sim, "semántica"
    except Exception:
        pass
    import difflib

    def sim(t):
        return max((difflib.SequenceMatcher(None, t, p).ratio() for p in patterns), default=0.0)
    return sim, "léxica"


# ---- embebedor que carga el modelo UNA vez (para lotes incrementales) ----
def _embedder():
    """Devuelve (enc, modo). enc(texto)->vector(np) en modo semántico, o el propio
    texto en modo léxico. Carga el modelo una sola vez."""
    try:
        cand = EMB_MODEL if os.path.isdir(EMB_MODEL) else next(iter(glob.glob(EMB_MODEL + "*")), "")
        if cand and os.path.isdir(cand):
            from sentence_transformers import SentenceTransformer
            m = SentenceTransformer(cand)
            return (lambda t: m.encode([t])[0]), "semántica"
    except Exception:
        pass
    return (lambda t: t), "léxica"


def _sim(a, b, modo):
    if modo == "semántica":
        import numpy as np
        return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1))
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def _cargar(idx):
    out = []
    p = Path(idx)
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    t = json.loads(ln).get("t", "")
                    if t:
                        out.append(t)
                except Exception:
                    pass
    return out[-INDEX_MAX:]


def _anadir(idx, texto):
    Path(idx).parent.mkdir(parents=True, exist_ok=True)
    with open(idx, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": texto[:500]}, ensure_ascii=False) + "\n")


def _arg(flag, defecto=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else defecto


def _ficheros(argv):   # ficheros = args que no son flags ni sus valores
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False; continue
        if a in ("--indice", "--umbral"):
            skip = True; continue
        if a.startswith("--"):
            continue
        out.append(a)
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    idx = _arg("--indice", "data/dedup_index.jsonl")
    umbral = float(_arg("--umbral", os.getenv("DEDUP_UMBRAL", "0.82")))
    base = _cargar(idx)
    if cmd == "parecido":                       # un texto por stdin
        texto = sys.stdin.read().strip()
        if not texto:
            sys.exit(1)
        enc, modo = _embedder()
        vistos = [enc(t) for t in base]
        e = enc(texto)
        if any(_sim(e, v, modo) >= umbral for v in vistos):
            sys.exit(0)                          # DUP
        _anadir(idx, texto)
        sys.exit(1)                              # NUEVO (registrado)
    if cmd == "nuevos":                          # lote de ficheros: UNA carga de modelo
        files = _ficheros(sys.argv[2:])
        if not files and not sys.stdin.isatty():
            files = [l.strip() for l in sys.stdin if l.strip()]
        enc, modo = _embedder()
        vistos = [enc(t) for t in base]          # índice persistente, codificado una vez
        for fp in files:
            try:
                texto = Path(fp).read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                print(f"DUP\t{fp}"); continue
            if not texto:
                print(f"DUP\t{fp}"); continue
            e = enc(texto)
            if vistos and any(_sim(e, v, modo) >= umbral for v in vistos):
                print(f"DUP\t{fp}")
            else:
                print(f"NUEVO\t{fp}")
                vistos.append(e)                 # también deduplica DENTRO del lote
                _anadir(idx, texto)
        sys.exit(0)
    print("uso: dedup.py parecido|nuevos --indice <jsonl> --umbral 0.82 [ficheros...]", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
