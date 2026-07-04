#!/usr/bin/env python3
# 📜 =====================================================================
# 📜 ACTA — FASE 7 · el acta del ciclo (propiocepción)
# 📜 Destila la última tanda (resultados/aprendizaje_*) + panel en UN acta:
# 📜   data/actas/acta_<ts_tanda>.json  (máquina → para la FASE 6)
# 📜   data/actas/acta_<ts_tanda>.md    (humano, media página)
# 📜 Sin modelos, sin red: parse determinista de lo ya destilado
# 📜 (registros.json / analisis.md / aprendizaje.md / ab.json / META.md).
# 📜 ⚠️  La NOTA solo se REGISTRA, jamás decide (señal real = CRAG).
# 📜 Uso:  python3 acta.py [--dir resultados/aprendizaje_X] [--forzar]
# 📜 =====================================================================
import json, os, re, sys, sqlite3, statistics
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))   # portable (Mac y sandbox)
RES = os.path.join(BASE, "resultados")
DATA = os.path.join(BASE, "data")
ACTAS = os.path.join(DATA, "actas")


def ultima_tanda():
    """Última tanda COMPLETA (con registros.json) — no acta prematura de una en vuelo."""
    if not os.path.isdir(RES):
        sys.exit("⚠️  no existe resultados/ — nada que destilar")
    ts = sorted(d for d in os.listdir(RES) if d.startswith("aprendizaje_")
                and os.path.isfile(os.path.join(RES, d, "registros.json")))
    if not ts:
        sys.exit("⚠️  sin tandas completas (con registros.json) en resultados/")
    return os.path.join(RES, ts[-1])


def leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


def leer_texto(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def destilar_registros(tanda):
    """CRAG medio+varianza, resueltos, huecos de la tanda, nota (solo registro)."""
    regs = leer_json(os.path.join(tanda, "registros.json"), [])
    quals = [r["crag"]["quality"] for r in regs
             if isinstance(r.get("crag"), dict) and isinstance(r["crag"].get("quality"), (int, float))]
    gaps = sum(1 for r in regs if isinstance(r.get("crag"), dict) and r["crag"].get("gap"))
    notas = [r["nota"] for r in regs if isinstance(r.get("nota"), (int, float))]
    return {
        "ejecuciones": len(regs),
        "crag_medio": round(statistics.mean(quals), 3) if quals else None,
        "crag_var": round(statistics.pvariance(quals), 4) if len(quals) > 1 else 0.0,
        "resueltos": sum(1 for r in regs if r.get("resuelto")),
        "huecos_tanda": gaps,
        "nota_registrada": round(statistics.mean(notas), 2) if notas else None,  # NO decide
    }


def destilar_capacidades(tanda):
    """De la tabla de aprendizaje.md: top mejoras y estancadas (Δ=0)."""
    mejoras, estancadas = [], []
    for ln in leer_texto(os.path.join(tanda, "aprendizaje.md")).splitlines():
        m = re.match(r"\|\s*([\w\-]+)\s*\|[^|]*\|[^|]*\|[^|]*\|\s*([+\-]?[\d.]+)\s*\|\s*(\d+)\s*\|", ln)
        if not m:
            continue
        cap, delta, usos = m.group(1), float(m.group(2)), int(m.group(3))
        if delta > 0:
            mejoras.append({"capacidad": cap, "delta": delta, "usos": usos})
        elif delta == 0:
            estancadas.append({"capacidad": cap, "usos": usos})
    mejoras.sort(key=lambda x: -x["delta"])
    estancadas.sort(key=lambda x: x["usos"])          # las más dormidas primero
    return mejoras[:5], estancadas[:10]


def destilar_analisis(tanda):
    """Las 4 secciones fijas del analisis.md + capacidades propuestas + flags."""
    txt = leer_texto(os.path.join(tanda, "analisis.md"))
    secciones = {}
    for m in re.finditer(r"^\s*([1-4])\.\s*\*\*[^*]+\*\*:?\s*(.+?)(?=^\s*[1-4]\.\s*\*\*|\Z)",
                         txt, re.M | re.S):
        secciones[int(m.group(1))] = " ".join(m.group(2).split())
    hueco_txt = secciones.get(3, "")
    propuestas = [p for p in re.findall(r'["“”`]([\wáéíóúñü\-]{4,})["“”`]', hueco_txt) if "_" in p or "-" in p]
    reco = secciones.get(4, "")
    reco_low = reco.lower()
    return {
        "sinergias": secciones.get(2, "")[:300],
        "capacidades_propuestas": sorted(set(propuestas)),
        "recomendacion": reco[:300],
        "pide": [f for f, pat in [("diversidad", r"diversidad|variad"),
                                  ("aumentar", r"aumentar|más peticiones|complejidad"),
                                  ("ejercitar", r"ejercit|entrenar|frecuencia de uso|estancadas")]
                 if re.search(pat, reco_low)],
    }


def destilar_ab(tanda):
    g = [a.get("ganador") for a in leer_json(os.path.join(tanda, "ab.json"), [])]
    return {"n": len(g), "gana_a": g.count("A"), "gana_b": g.count("B"), "empates": g.count("=")}


def huecos_globales(ts_tanda, ts_fin=None):
    """Total histórico + nuevos en la VENTANA de la tanda [inicio, siguiente tanda).
    Sin ts_fin (tanda más reciente) la ventana llega hasta ahora — igual que en producción."""
    hs = leer_json(os.path.join(DATA, "huecos.consolidado.json"), [])
    nuevos = 0
    for h in hs:
        try:
            t = datetime.strptime(h["timestamp"], "%Y-%m-%d %H:%M:%S")
            if t >= ts_tanda and (ts_fin is None or t < ts_fin):
                nuevos += 1
        except Exception:
            pass
    return {"huecos_total": len(hs), "huecos_nuevos": nuevos}


def leer_meseta():
    """Línea de veredicto + tendencia del panel (META.md)."""
    txt = leer_texto(os.path.join(DATA, "META.md"))
    tend = re.search(r"\*\*Tendencia de nota:\*\*\s*(.+)", txt)
    vered = re.search(r"^- (🟢|🟡|🔴) (.+)$", txt, re.M)
    return {
        "tendencia": tend.group(1).strip() if tend else None,
        "meseta": bool(re.search(r"En meseta", txt)),
        "veredicto": (vered.group(1) + " " + vered.group(2)).strip() if vered else None,
    }


def leer_banco():
    """Estado del banco (solo lectura, sin bloquear la cola)."""
    try:
        db = sqlite3.connect(f"file:{os.path.join(DATA, 'cola.db')}?mode=ro", uri=True)
        estados = dict(db.execute("SELECT estado, COUNT(*) FROM cola GROUP BY estado"))
        fuentes = dict(db.execute(
            "SELECT COALESCE(fuente,'?'), COUNT(*) FROM cola WHERE estado=0 GROUP BY fuente"))
        db.close()
        # estados son ENTEROS: 0=pendiente · 1=procesando · 2=hecho (hallazgo de Opus, carta 2-jul)
        return {"pendientes": estados.get(0, 0), "estados": estados, "fuentes_pendientes": fuentes}
    except Exception as e:
        return {"pendientes": None, "error": str(e)[:80]}


def escribir_md(ruta, acta):
    r, a, ab, m, b = (acta[k] for k in ("tanda_resumen", "analisis", "ab", "panel", "banco"))
    est = ", ".join(f"{e['capacidad']}({e['usos']})" for e in acta["estancadas"][:6]) or "—"
    mej = ", ".join(f"{x['capacidad']}(+{x['delta']:.3f})" for x in acta["top_mejoras"][:3]) or "—"
    lineas = [
        f"# 📜 Acta del ciclo — {acta['tanda']}", "",
        f"_Generada {acta['generada']} · la nota solo se registra, la señal es el CRAG._", "",
        f"- **CRAG:** {r['crag_medio']} (var {r['crag_var']}) · resueltos {r['resueltos']}/{r['ejecuciones']}"
        f" · huecos en tanda: {r['huecos_tanda']} · nota registrada: {r['nota_registrada']}",
        f"- **Huecos:** {acta['huecos']['huecos_total']} históricos · {acta['huecos']['huecos_nuevos']} nuevos desde la tanda",
        f"- **A/B:** {ab['n']} duelos → A {ab['gana_a']} · B {ab['gana_b']} · empates {ab['empates']}",
        f"- **Panel:** {m['veredicto'] or '—'} · tendencia: {m['tendencia'] or '—'}",
        f"- **Banco:** {b.get('pendientes')} pendientes · por fuente: {b.get('fuentes_pendientes', {})}", "",
        f"**Mejoran:** {mej}", f"**Dormidas (usos):** {est}",
        f"**Propuestas del análisis:** {', '.join(a['capacidades_propuestas']) or '—'}",
        f"**El aprendizaje pide:** {', '.join(a['pide']) or '—'}", "",
        f"> Sinergias: {a['sinergias'] or '—'}", f"> Recomendación: {a['recomendacion'] or '—'}", "",
    ]
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))


def main():
    args = sys.argv[1:]
    forzar = "--forzar" in args
    tanda = None
    if "--dir" in args:
        tanda = os.path.join(BASE, args[args.index("--dir") + 1]) if not os.path.isabs(
            args[args.index("--dir") + 1]) else args[args.index("--dir") + 1]
    tanda = tanda or ultima_tanda()
    if not os.path.isdir(tanda):
        sys.exit(f"⚠️  no existe la tanda: {tanda}")
    nombre = os.path.basename(tanda).replace("aprendizaje_", "")
    ts_tanda = datetime.strptime(nombre, "%Y%m%d_%H%M%S")
    # ventana honesta: si existe una tanda POSTERIOR, los "huecos nuevos" se cortan ahí
    ts_fin = None
    posteriores = sorted(d for d in os.listdir(RES) if d.startswith("aprendizaje_")
                         and d > os.path.basename(tanda))
    if posteriores:
        try:
            ts_fin = datetime.strptime(posteriores[0].replace("aprendizaje_", ""), "%Y%m%d_%H%M%S")
        except ValueError:
            pass

    os.makedirs(ACTAS, exist_ok=True)
    ruta_json = os.path.join(ACTAS, f"acta_{nombre}.json")
    ruta_md = os.path.join(ACTAS, f"acta_{nombre}.md")
    if os.path.exists(ruta_json) and not forzar:
        print(f"📜 acta ya existe ({ruta_json}) — usa --forzar para regenerar")
        return

    mejoras, estancadas = destilar_capacidades(tanda)
    acta = {
        "tanda": os.path.basename(tanda),
        "generada": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tanda_resumen": destilar_registros(tanda),
        "top_mejoras": mejoras,
        "estancadas": estancadas,
        "analisis": destilar_analisis(tanda),
        "ab": destilar_ab(tanda),
        "huecos": huecos_globales(ts_tanda, ts_fin),
        "panel": leer_meseta(),
        "banco": leer_banco(),
    }
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(acta, f, ensure_ascii=False, indent=1)
    escribir_md(ruta_md, acta)
    print(f"📜 acta escrita: {ruta_md}")
    print(f"   CRAG {acta['tanda_resumen']['crag_medio']} · huecos nuevos {acta['huecos']['huecos_nuevos']}"
          f" · A/B {acta['ab']['gana_a']}-{acta['ab']['gana_b']}-{acta['ab']['empates']}"
          f" · pide: {', '.join(acta['analisis']['pide']) or '—'}")


if __name__ == "__main__":
    main()
