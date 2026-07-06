#!/usr/bin/env python3
# 🧰 rag (nivel 2 · lectura): consulta la BIBLIOTECA DE CAPACIDADES con las tripas
#    PROPIAS de mosaic (HybridRetriever + build_embedder — degrada a léxico si no hay
#    torch, como manda la doctrina). Devuelve el top-k de la máscara para una intención.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _contrato import ok, fail, payload, base

P = payload()
q = str(P.get("q", "")).strip()
if not q:
    fail("rag: sin consulta")
k = max(1, min(int(P.get("k", 5)), 10))
sys.path.insert(0, base())
os.chdir(base())
try:
    from mosaic import HybridRetriever, build_embedder, load_capabilities
    caps = load_capabilities(os.getenv("MOSAIC_CAPS_DIR", ""))
    r = HybridRetriever(caps, build_embedder())
    hits = r.retrieve(q, k_final=k)
    modo = "hibrido"
except Exception as e:                                   # léxico puro: mejor honesto que mudo
    try:
        from mosaic import load_capabilities
        caps = load_capabilities(os.getenv("MOSAIC_CAPS_DIR", ""))
        terms = set(q.lower().split())
        def puntua(c):
            texto = f"{c.id} {' '.join(c.domain_expertise)} {' '.join(c.tags)} {c.behavioral_pattern}".lower()
            return sum(1 for t in terms if t in texto)
        hits = sorted(caps, key=puntua, reverse=True)[:k]
        modo = f"lexico-degradado ({type(e).__name__})"
    except Exception as e2:
        fail(f"rag: ni con la biblioteca pude: {e2}")
ok({"q": q, "modo": modo,
    "capacidades": [{"id": c.id, "role": c.role, "score": round(float(c.performance_score), 3),
                     "extracto": c.behavioral_pattern[:220]} for c in hits]})
