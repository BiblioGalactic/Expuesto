#!/usr/bin/env python3
# 🧭 =====================================================================
# 🧭 GOBERNADOR — FASE 6 · auto-afinar el LANZAMIENTO sobre valores ACOTADOS.
# 🧭 Lee las últimas actas (FASE 7, data/actas/*.json) y escribe el perfil:
# 🧭   data/perfil_lanzamiento.json  (mandos → ciclo.sh los exporta al arrancar)
# 🧭   data/perfil_lanzamiento.md    (el PORQUÉ de cada decisión — auditable)
# 🧭 Reglas DETERMINISTAS con histéresis: 1 paso por mando y por ejecución,
# 🧭 siempre dentro de [min,max] duros. Con <3 actas NO decide (perfil neutro).
# 🧭 ⚠️  Decide por CRAG / huecos / A-B — JAMÁS por la nota (saturada).
# 🧭 ⚠️  FNC lleva CANDADO: el gobernador no puede encenderlo (falta evidencia).
# 🧭 Uso:  python3 gobernador.py [--n 5]     (n = actas a digerir)
# 🧭 = realización del #0: "normas de lanzamiento que emergen".
# 🧭 =====================================================================
import json, os, sys
from collections import Counter
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ACTAS = os.path.join(BASE, "data", "actas")
PERFIL_JSON = os.path.join(BASE, "data", "perfil_lanzamiento.json")
PERFIL_MD = os.path.join(BASE, "data", "perfil_lanzamiento.md")
EJERCITAR_TXT = os.path.join(BASE, "data", "ejercitar.txt")   # consumidores shell (fábrica)

# Mandos: (defecto, min, max, paso máximo por ejecución)
LIMITES = {
    "max_cola":       (60, 30, 90, 15),
    "muestra_juicio": (3, 1, 5, 1),
    "recup_extra":    (0, 0, 11, 2),
}
PRIMOS_LOTE = [17, 19, 23, 29]          # el lote SIEMPRE primo (Goldbach)
MIN_ACTAS = 3


def leer_actas(n):
    if not os.path.isdir(ACTAS):
        return []
    fs = sorted(f for f in os.listdir(ACTAS) if f.startswith("acta_") and f.endswith(".json"))
    actas = []
    for f in fs[-n:]:
        try:
            with open(os.path.join(ACTAS, f), encoding="utf-8") as fh:
                actas.append(json.load(fh))
        except Exception:
            pass
    return actas


def perfil_previo():
    """Histéresis: el punto de partida es el último perfil (o los defectos)."""
    base = {k: v[0] for k, v in LIMITES.items()}
    base["lote"] = 23
    try:
        with open(PERFIL_JSON, encoding="utf-8") as f:
            prev = json.load(f).get("mandos", {})
        for k in list(base):
            if isinstance(prev.get(k), int):
                base[k] = prev[k]
    except Exception:
        pass
    return base


def media(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return sum(xs) / len(xs) if xs else None


def acotar(mando, valor, desde):
    """Clamp a [min,max] y a 1 paso desde el valor previo."""
    _, lo, hi, paso = LIMITES[mando]
    valor = max(desde - paso, min(desde + paso, valor))
    return max(lo, min(hi, valor))


def decidir(actas, prev):
    """Reglas deterministas. Devuelve (mandos, razones). Nunca mira la nota."""
    mandos, razones = dict(prev), []
    crag = media([a["tanda_resumen"].get("crag_medio") for a in actas])
    crag_var = media([a["tanda_resumen"].get("crag_var") for a in actas])
    h_tanda = media([a["tanda_resumen"].get("huecos_tanda") for a in actas])
    h_nuevos = media([a["huecos"].get("huecos_nuevos") for a in actas])
    bancos = media([a["banco"].get("pendientes") for a in actas if a["banco"].get("pendientes") is not None])
    cs = [a["tanda_resumen"].get("crag_medio") for a in actas if a["tanda_resumen"].get("crag_medio") is not None]
    tendencia = (cs[-1] - cs[0]) if len(cs) >= 2 else 0.0

    def fija(mando, nuevo, razon):
        v = acotar(mando, nuevo, prev[mando])
        if v != prev[mando]:
            razones.append(f"{mando}: {prev[mando]} → {v} — {razon}")
        mandos[mando] = v

    # 1) max_cola — dimensionar el banco al material real que de verdad llega
    if bancos is not None and bancos > 0.8 * prev["max_cola"]:
        fija("max_cola", prev["max_cola"] + 15, f"banco lleno de media ({bancos:.0f}) → más reservorio")
    elif bancos is not None and bancos < 0.2 * prev["max_cola"]:
        fija("max_cola", prev["max_cola"] - 15, f"banco corto de media ({bancos:.0f}) → tope realista, menos presión a la fábrica")

    # 2) lote (primo) — varianza CRAG alta = lotes más pequeños (más control)
    i = PRIMOS_LOTE.index(prev["lote"]) if prev["lote"] in PRIMOS_LOTE else 2
    if crag_var is not None and crag_var > 0.03 and i > 0:
        mandos["lote"] = PRIMOS_LOTE[i - 1]
        razones.append(f"lote: {prev['lote']} → {mandos['lote']} — CRAG con varianza alta ({crag_var:.3f})")
    elif crag_var is not None and crag_var < 0.01 and bancos and bancos >= prev["lote"] and i < len(PRIMOS_LOTE) - 1:
        mandos["lote"] = PRIMOS_LOTE[i + 1]
        razones.append(f"lote: {prev['lote']} → {mandos['lote']} — CRAG estable ({crag_var:.3f}) y banco con fondo")

    # 3) muestra_juicio — el tribunal es caro: menos si todo estable, más si aparecen huecos
    if h_tanda is not None and h_tanda == 0 and abs(tendencia) < 0.02:
        fija("muestra_juicio", prev["muestra_juicio"] - 1, "CRAG estable y 0 huecos de tanda → tribunal más barato")
    elif (h_tanda is not None and h_tanda >= 2) or tendencia < -0.05:
        fija("muestra_juicio", prev["muestra_juicio"] + 1,
             f"huecos de tanda ({h_tanda:.1f}) o CRAG cayendo ({tendencia:+.3f}) → más vigilancia")

    # 4) recup_extra — más Riemann cuando brotan huecos y la recuperación flojea
    if h_nuevos is not None and h_nuevos >= 10 and (crag is None or crag < 0.5):
        fija("recup_extra", prev["recup_extra"] + 2, f"brotan huecos ({h_nuevos:.0f}/tanda) con CRAG {crag:.2f} → más práctica real")
    elif h_nuevos is not None and h_nuevos <= 2:
        fija("recup_extra", prev["recup_extra"] - 2, f"pocos huecos nuevos ({h_nuevos:.0f}) → recuperación al mínimo")

    # 5) ejercitar — dormidas (usos=0) recurrentes en ≥2 actas, máx 5
    cuenta = Counter()
    for a in actas:
        for e in a.get("estancadas", []):
            if e.get("usos") == 0:
                cuenta[e["capacidad"]] += 1
    mandos["ejercitar"] = [c for c, n in cuenta.most_common(5) if n >= 2]
    if mandos["ejercitar"]:
        razones.append(f"ejercitar: {', '.join(mandos['ejercitar'])} — dormidas en ≥2 actas")

    # 6) FNC — CANDADO (no es decisión del gobernador)
    mandos["fnc"] = "off"
    return mandos, razones, {"crag": crag, "crag_var": crag_var, "huecos_tanda": h_tanda,
                             "huecos_nuevos": h_nuevos, "banco": bancos, "tendencia_crag": tendencia}


def escribir(perfil):
    with open(PERFIL_JSON, "w", encoding="utf-8") as f:
        json.dump(perfil, f, ensure_ascii=False, indent=1)
    ejercitar = perfil["mandos"].get("ejercitar", [])
    with open(EJERCITAR_TXT, "w", encoding="utf-8") as f:   # vacío = nada que ejercitar
        f.write("\n".join(ejercitar) + ("\n" if ejercitar else ""))
    m, r = perfil["mandos"], perfil["razones"]
    lineas = [
        "# 🧭 Perfil de lanzamiento (FASE 6 · gobernador)", "",
        f"_Generado {perfil['generado']} · digiere {perfil['actas_digeridas']} actas · decide por CRAG/huecos/A-B, jamás por la nota._", "",
        f"- `MAX_COLA={m['max_cola']}` · `LOTE_DISPATCH={m['lote']}` · `MUESTRA_JUICIO={m['muestra_juicio']}`"
        f" · `MOSAIC_RECUP_EXTRA={m['recup_extra']}` · FNC: **{m['fnc']} 🔒**",
        f"- ejercitar: {', '.join(m['ejercitar']) or '—'}", "",
        "## Porqués" if r else "## Sin cambios (statu quo)",
    ] + [f"- {x}" for x in r] + ["", f"> Señales: {json.dumps(perfil['seniales'], ensure_ascii=False)}", ""]
    with open(PERFIL_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))


def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 5
    actas = leer_actas(n)
    prev = perfil_previo()
    # 🔒 sello del bucle (4-jul, Opus): el gobernador FIRMA qué acta digirió → el panel verifica
    #   "acta→gobernador" por NOMBRE (acuse de recibo), no solo por mtime.
    _af = sorted(f for f in os.listdir(ACTAS) if f.startswith("acta_") and f.endswith(".json"))
    _ultima_acta = _af[-1][:-5] if _af else ""
    if len(actas) < MIN_ACTAS:
        perfil = {"version": 1, "generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  "actas_digeridas": len(actas), "ultima_acta": _ultima_acta, "neutro": True,
                  "mandos": {**prev, "ejercitar": [], "fnc": "off"},
                  "razones": [f"solo {len(actas)} actas (<{MIN_ACTAS}) → no decido, statu quo"],
                  "seniales": {}}
    else:
        mandos, razones, seniales = decidir(actas, prev)
        perfil = {"version": 1, "generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  "actas_digeridas": len(actas), "ultima_acta": _ultima_acta, "neutro": False,
                  "mandos": mandos, "razones": razones or ["todo en rango → statu quo"],
                  "seniales": seniales}
    escribir(perfil)
    print(f"🧭 perfil escrito: {PERFIL_MD}")
    for r in perfil["razones"]:
        print(f"   · {r}")


if __name__ == "__main__":
    main()
