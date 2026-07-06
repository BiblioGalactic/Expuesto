#!/usr/bin/env python3
# 💹 =====================================================================
# 💹 VALORAR_EMPRESA — el ticker DERIVADO de una empresa (ronda bursátil 5-jul:
# 💹   propuesta Sombra 17:53 + requisitos Opus 17:20 + recon Fable 17:57).
# 💹   N3 DETERMINISTA: cero LLM, cero red — lee ficheros que YA existen
# 💹   (actas · capabilities · acciones · escalaciones · turnos · herramientas)
# 💹   y PESA con data/formula_valor.yaml (fórmula ABIERTA, auditable con cat).
# 💹   Líneas rojas (grabadas): valor derivado y reproducible · sin actas =
# 💹   «sin cotizar», jamás un cero inventado · el ranking PROPONE, nadie
# 💹   ejecuta por cotización (palabra, jamás manos).
# 💹 Uso:  ./valorar_empresa.py                    (la sede → data/ticker.json)
# 💹       ./valorar_empresa.py --base RUTA        (otra empresa)
# 💹       ./valorar_empresa.py --grupo            (sede + ~/Empresas/* → data/ranking.json)
# 💹       ./valorar_empresa.py --json             (además, el resultado por stdout)
# 💹 =====================================================================
import glob
import json
import os
import sys
import time

BASE = os.environ.get("MOSAIC_BASE", os.path.expanduser("~/Mosaic_privado"))
EMPRESAS_DIR = os.environ.get("EMPRESAS_DIR", os.path.expanduser("~/Empresas"))

DEF_PESOS = {"crag": 60, "capacidades": 20, "resueltos": 20}
DEF_MADUREZ = {"sillas_debutadas": 40, "acciones_selladas": 30, "tools_conectadas": 30}


def _leer_formula(base):
    """La fórmula de LA EMPRESA (su data/formula_valor.yaml); defaults del motor si falta."""
    f = {"pesos": dict(DEF_PESOS), "madurez": dict(DEF_MADUREZ), "score_techo": 350, "quiebra_crag": 0.25}
    try:
        import yaml
        d = yaml.safe_load(open(os.path.join(base, "data", "formula_valor.yaml"), encoding="utf-8")) or {}
        for k in ("pesos", "madurez"):
            if isinstance(d.get(k), dict):
                f[k] = {str(a): float(b) for a, b in d[k].items()}
        for k in ("score_techo", "quiebra_crag"):
            if k in d:
                f[k] = float(d[k])
    except Exception:
        pass
    return f


def _actas(base):
    out = []
    for p in sorted(glob.glob(os.path.join(base, "data", "actas", "acta_*.json"))):
        try:
            out.append(json.load(open(p, encoding="utf-8")))
        except Exception:
            continue
    return out


def _biblioteca(base):
    """(nº caps, Σ performance_score) — mejora #1 de Opus 19:05: la biblioteca pesa por
    CALIDAD, no por recuento (500 caps a 0.1 pesan como 50 buenas). Cierra el Goodhart."""
    try:
        import yaml
        caps = yaml.safe_load(open(os.path.join(base, "capabilities", "auto_generadas.yaml"),
                                   encoding="utf-8")) or []
        if isinstance(caps, dict):
            caps = caps.get("capabilities") or []
        scores = [float(c.get("performance_score", 0) or 0) for c in caps if isinstance(c, dict)]
        return len(scores), sum(scores)
    except Exception:
        return 0, 0.0


def _rotar_historia(p, tope_mb=30):
    """Política de Gustavo: el libro llega a 30MB → se comprime a trash y nace uno nuevo."""
    try:
        if os.path.getsize(p) > tope_mb * 1024 * 1024:
            import gzip
            import shutil
            dest = os.path.join(BASE, "trash", "backups",
                                f"ticker_historia.{time.strftime('%Y%m%d_%H%M%S')}.jsonl.gz")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(p, "rb") as f_in, gzip.open(dest, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.replace(p + ".tmp", p) if os.path.exists(p + ".tmp") else open(p, "w").close()
    except OSError:
        pass


def _madurez(base, pesos):
    """La barra «Hack» aterrizada (voto Sombra+Fable): MADUREZ = % del circuito que corre solo."""
    import yaml
    sillas = deb = 0
    try:
        sillas = len([f for f in os.listdir(os.path.join(base, "roles", "turnos")) if f.endswith(".yaml")])
        deb = len([f for f in os.listdir(os.path.join(base, "data", "turnos")) if f.endswith(".ultimo")])
    except OSError:
        pass
    m_sillas = min(1.0, deb / sillas) if sillas else 0.0
    acc = sell = 0
    try:
        for a in (json.load(open(os.path.join(base, "data", "acciones.json"), encoding="utf-8"))
                  .get("acciones") or []):
            acc += 1
            if a.get("sellos"):
                sell += 1
    except Exception:
        pass
    m_sellos = (sell / acc) if acc else 0.0
    t_tot = t_con = 0
    try:
        for t in (yaml.safe_load(open(os.path.join(base, "data", "herramientas.yaml"), encoding="utf-8"))
                  or {}).get("tools", []):
            t_tot += 1
            if t.get("cmd"):
                t_con += 1
    except Exception:
        pass
    m_tools = (t_con / t_tot) if t_tot else 0.0
    tot = sum(pesos.values()) or 1.0
    pct = (pesos.get("sillas_debutadas", 0) * m_sillas + pesos.get("acciones_selladas", 0) * m_sellos
           + pesos.get("tools_conectadas", 0) * m_tools) / tot
    return round(100 * pct), {"sillas": f"{deb}/{sillas}", "sellos": f"{sell}/{acc}", "tools": f"{t_con}/{t_tot}"}


def valorar(base):
    """El ticker de UNA empresa — derivado, reproducible, auditable. v2 (auditoría Opus
    19:05): CRAG/resueltos por MEDIANA de las últimas 3 actas (histéresis del gobernador —
    un fluke no mueve la bolsa) · biblioteca por Σscore×CRAG (calidad, no bulto)."""
    import statistics
    f = _leer_formula(base)
    nombre = os.path.basename(os.path.abspath(base).rstrip("/")) or "empresa"
    actas = _actas(base)
    n_caps, suma_score = _biblioteca(base)
    madurez, m_detalle = _madurez(base, f["madurez"])
    tck = {"empresa": nombre, "base": os.path.abspath(base),
           "generado": time.strftime("%Y-%m-%d %H:%M:%S"),
           "madurez_pct": madurez, "madurez_detalle": m_detalle,
           "capacidades": n_caps, "suma_score": round(suma_score, 1)}
    if not actas:
        # línea roja de la Sombra: sin actas NO hay cero inventado — no cotiza todavía
        tck.update(estado="sin cotizar", valor=None, delta_pct=None,
                   nota="sin actas aún — cotiza cuando complete su primer ciclo")
        return tck

    def _ventana(sub):
        """Valor de una VENTANA de actas (mediana de crag y de resueltos-ratio)."""
        crags, ratios = [], []
        for acta in sub:
            r = acta.get("tanda_resumen") or {}
            crags.append(float(r.get("crag_medio", 0) or 0))
            ej = int(r.get("ejecuciones", 0) or 0)
            ratios.append((int(r.get("resueltos", 0) or 0) / ej) if ej else 0.0)
        crag_med = statistics.median(crags) if crags else 0.0
        res_med = statistics.median(ratios) if ratios else 0.0
        # mejora #1: Σscore saturado en el techo, REFORZADO ×CRAG (basura en empresa floja no cotiza)
        m_caps = min(1.0, suma_score / max(1.0, f["score_techo"])) * crag_med
        p = f["pesos"]
        tot = sum(p.values()) or 1.0
        v = 1000 * (p.get("crag", 0) * crag_med + p.get("capacidades", 0) * m_caps
                    + p.get("resueltos", 0) * res_med) / tot
        return v, crag_med

    valor, crag_med = _ventana(actas[-3:])
    tck["valor"] = round(valor)
    tck["crag"] = round(crag_med, 3)
    if len(actas) >= 2:
        prev, crag_prev = _ventana(actas[-4:-1] if len(actas) >= 4 else actas[:-1])
        tck["delta_pct"] = round(100 * (valor - prev) / prev, 1) if prev else 0.0
        en_quiebra = crag_med < f["quiebra_crag"] and crag_prev < f["quiebra_crag"]
    else:
        tck["delta_pct"] = None
        en_quiebra = False
    tck["estado"] = "quiebra" if en_quiebra else ("sede" if os.path.abspath(base) == os.path.abspath(BASE)
                                                  else "neutral")
    tck["actas"] = len(actas)
    # mejora #3: la HISTORIA de cotización (append-only, alimenta la [A] AGENDA) + rotación 30MB
    try:
        hist = os.path.join(base, "data", "ticker_historia.jsonl")
        _rotar_historia(hist)
        with open(hist, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": tck["generado"], "empresa": nombre, "valor": tck["valor"],
                                 "delta_pct": tck["delta_pct"], "crag": tck["crag"],
                                 "madurez_pct": madurez}, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return tck


def main():
    base = BASE
    if "--base" in sys.argv:
        base = sys.argv[sys.argv.index("--base") + 1]
    if not os.path.isdir(base):
        print(f"⚠️  no existe la base: {base}", file=sys.stderr)
        raise SystemExit(1)

    if "--grupo" in sys.argv:
        bases = [BASE]
        if os.path.isdir(EMPRESAS_DIR):
            bases += sorted(os.path.join(EMPRESAS_DIR, d) for d in os.listdir(EMPRESAS_DIR)
                            if os.path.isdir(os.path.join(EMPRESAS_DIR, d)))
        tickers = [valorar(b) for b in bases]
        # cotizadas primero (por valor), luego las sin-cotizar
        tickers.sort(key=lambda t: (t["valor"] is None, -(t["valor"] or 0)))
        rk = {"_": "ranking del GRUPO (bursátil 5-jul) — DERIVADO y reproducible; PROPONE, "
                   "jamás ejecuta (la flota/fundar/jubilar los decide Gustavo)",
              "generado": time.strftime("%Y-%m-%d %H:%M:%S"), "empresas": tickers}
        dest = os.path.join(BASE, "data", "ranking.json")
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rk, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, dest)
        print(f"💹 ranking → {dest} ({len(tickers)} empresas)", file=sys.stderr)
        if "--json" in sys.argv:
            print(json.dumps(rk, ensure_ascii=False, indent=1))
        return

    tck = valorar(base)
    dest = os.path.join(base, "data", "ticker.json")
    tmp = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(tck, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, dest)
    v = tck["valor"]
    print(f"💹 {tck['empresa']}: {'sin cotizar' if v is None else v} · madurez {tck['madurez_pct']}% "
          f"· estado {tck['estado']} → {dest}", file=sys.stderr)
    if "--json" in sys.argv:
        print(json.dumps(tck, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
