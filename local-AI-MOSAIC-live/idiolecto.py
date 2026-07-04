#!/usr/bin/env python3
# 🗣 =====================================================================
# 🗣 IDIOLECTO — destila el "habla propia" de ESTE MOSAIC desde su biblioteca de
# 🗣 capacidades y escribe un retrato legible en info/IDIOLECTO.md:
# 🗣   · LÉXICO   → de qué habla (dominios)      · GRAMÁTICA → cómo habla (roles)
# 🗣   · NEOLOGISMOS → cuánto se ha alejado de la lengua base (emergidas)
# 🗣   · MODISMOS  → sus formas más asentadas (por performance)
# 🗣 (Hilo A de la idea del idiolecto: FNC = gramática universal; esto = habla de uno.)
# 🗣 Uso:  python3 idiolecto.py
# 🗣 =====================================================================
import os, sys, glob
from collections import Counter
from datetime import datetime

CAPS = os.getenv("MOSAIC_CAPS_DIR", "capabilities")
OUT = os.getenv("IDIOLECTO_OUT", "info/IDIOLECTO.md")
MODELO = os.getenv("MOSAIC_LLM_MODEL", "24b")


def cargar():
    caps = []
    try:
        import yaml
    except Exception:
        print("falta pyyaml (pip install pyyaml)", file=sys.stderr); return caps
    for f in sorted(glob.glob(os.path.join(CAPS, "*.yaml"))):
        try:
            d = yaml.safe_load(open(f, encoding="utf-8")) or {}
        except Exception:
            continue
        lista = d.get("capabilities") if isinstance(d, dict) else (d if isinstance(d, list) else [])
        for c in (lista or []):
            if isinstance(c, dict) and c.get("id"):
                caps.append(c)
    return caps


def emergida(c):
    tags = c.get("tags") or []
    return ("auto" in tags) or str(c.get("id", "")).endswith("-auto") or bool(c.get("fuente"))


def score(c):
    try:
        return float(c.get("performance_score", 0) or 0)
    except Exception:
        return 0.0


def main():
    caps = cargar()
    n = len(caps)
    if not n:
        print("sin capacidades", file=sys.stderr); sys.exit(1)
    roles = Counter(c.get("role", "?") for c in caps)
    doms = Counter()
    for c in caps:
        for d in (c.get("domain_expertise") or []):
            s = str(d).strip().lower()
            if s:
                doms[s] += 1
    emerg = sum(1 for c in caps if emergida(c))
    modismos = sorted(caps, key=lambda c: (score(c), len(c.get("domain_expertise") or [])), reverse=True)[:8]

    rol_top = roles.most_common()
    rol_str = " · ".join(f"{r} {100 * v // n}%" for r, v in rol_top[:4])
    dom_top4 = ", ".join(d for d, _ in doms.most_common(4))
    caracter = "procedimental (habla en procedimientos)" if roles.get("methodology", 0) > n / 2 else \
               "mixta (procedimientos + identidades + reglas)"

    L = []
    L.append(f"# 🗣 Idiolecto de este MOSAIC ({MODELO})")
    L.append("")
    L.append("> El *habla propia* que ha desarrollado esta instancia. FNC es la gramática universal;")
    L.append(f"> esto es lo que habla **tu** MOSAIC. Destilado el {datetime.now().strftime('%Y-%m-%d %H:%M')}.")
    L.append("")
    L.append("## Retrato")
    L.append(f"Este MOSAIC habla sobre todo de **{dom_top4}**. Su gramática es {caracter}: "
             f"{rol_str}. De sus **{n}** capacidades, **{emerg} ({100 * emerg // n}%) son propias** "
             f"(emergidas de los huecos que ha ido encontrando), así que ya habla su idiolecto mucho "
             f"más que la lengua base. Es, en una frase, el habla de alguien que piensa "
             f"**{'en código y datos' if any(d in doms for d in ('python','pandas','data_analysis')) else 'en su dominio'}**.")
    L.append("")
    L.append("## 📚 Léxico — de qué habla (dominios más frecuentes)")
    L.append("")
    for d, v in doms.most_common(15):
        L.append(f"- `{d}` ×{v}")
    L.append("")
    L.append("## 🔤 Gramática — cómo habla (reparto de roles)")
    L.append("")
    for r, v in rol_top:
        L.append(f"- **{r}** — {v} ({100 * v // n}%)")
    L.append("")
    L.append("## 🌱 Neologismos — cuánto se ha alejado de la lengua base")
    L.append("")
    L.append(f"- Emergidas (propias): **{emerg} / {n}** = **{100 * emerg // n}%**")
    L.append(f"- Heredadas de la base: {n - emerg}")
    L.append(f"- Léxico total: {len(doms)} dominios distintos")
    L.append("")
    L.append("## 💬 Modismos — sus formas más asentadas (top performance)")
    L.append("")
    L.append("_Las capacidades en las que más se apoya: sus \"maneras canónicas de decir algo\"._")
    L.append("")
    for c in modismos:
        dd = ", ".join((c.get("domain_expertise") or [])[:3])
        L.append(f"- **`{c.get('id')}`** · {c.get('role','?')} · [{dd}] · score {score(c):.2f}")
    L.append("")
    L.append("---")
    L.append("_Hilo A de la idea del idiolecto. El hilo B (convergencia entre MOSAICs · export/import "
             "de librerías) queda para el futuro. Regenera con `python3 idiolecto.py`._")

    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
