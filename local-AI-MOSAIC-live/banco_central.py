#!/usr/bin/env python3
# 🏦 =====================================================================
# 🏦 BANCO CENTRAL — la CASA DE MONEDA respaldada por cómputo (estudio Opus
# 🏦   19:40 · pieza final de la ronda bursátil 5-jul). N3 DETERMINISTA:
# 🏦   cero LLM, cero red — MIDE la capacidad de la flota (servidores.conf ×
# 🏦   slots × throughput observado × horas) y la ACUÑA en el libro. No
# 🏦   imprime: no se emite más de lo que la flota computa (ancla anti-fiat:
# 🏦   el techo es la RAM de dos Macs, no una promesa).
# 🏦   El libro: data/tesoreria.jsonl — APPEND-ONLY con HASH ENCADENADO
# 🏦   (cada línea sella la anterior: alterar una rompe la cadena — nadie
# 🏦   cocina las cuentas; `verificar` es la fiscalización de Diógenes).
# 🏦   LÍNEAS ROJAS (cableadas): el banco PROPONE, jamás mueve solo (aplicar
# 🏦   una asignación = Acción + doble sello) · sin crédito · sin interés ·
# 🏦   🔔 LA CAMPANA: sin primera Acción SELLADA el banco NO acuña (el debut
# 🏦   abre el mercado — override a conciencia: MOSAIC_BANCO=1).
# 🏦 Uso:  ./banco_central.py acunar      (mide y ACUÑA el periodo → libro)
# 🏦       ./banco_central.py resumen     (activo vs pasivo del último periodo)
# 🏦       ./banco_central.py verificar   (la cadena de hashes, línea a línea)
# 🏦 =====================================================================
import hashlib
import json
import os
import sys
import time

BASE = os.environ.get("MOSAIC_BASE", os.path.expanduser("~/Mosaic_privado"))
LIBRO = os.path.join(BASE, "data", "tesoreria.jsonl")
POLITICA = os.path.join(BASE, "data", "politica_monetaria.yaml")
SERVIDORES = os.path.join(BASE, "servidores.conf")
GENESIS = "GENESIS"


def _err(m):
    print(f"⚠️  {m}", file=sys.stderr)


def _campana():
    """🔔 la misma campana que la bolsa: el banco abre con el DEBUT (1ª Acción sellada)."""
    if os.environ.get("MOSAIC_BANCO", "") == "1":
        return True
    try:
        acc = (json.load(open(os.path.join(BASE, "data", "acciones.json"), encoding="utf-8"))
               .get("acciones")) or []
        return any(a.get("sellos") for a in acc)
    except Exception:
        return False


def _politica():
    import yaml
    p = {"periodo_horas": 24, "tokens_s_medidos": 11.3, "utilizacion": 0.5,
         "asignacion_rangos": {"N1": 0.15, "N2": 0.55, "N3": 0.05}, "comun": 0.25,
         "depreciacion": 0.10, "credito": 0, "interes": 0}
    try:
        d = yaml.safe_load(open(POLITICA, encoding="utf-8")) or {}
        p.update({k: d[k] for k in p if k in d})
    except Exception:
        pass
    return p


def _flota():
    """La capacidad FÍSICA declarada: servidores fijos × slots (--parallel N, default 1).
    Determinista y sin red: lee servidores.conf — la verdad de la flota en papel."""
    servidores, slots_tot = [], 0
    try:
        for ln in open(SERVIDORES, encoding="utf-8"):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            c = ln.split("|")
            if len(c) < 6 or c[3] != "fijo":
                continue
            slots = 1
            if len(c) >= 7 and "--parallel" in c[6]:
                try:
                    slots = int(c[6].split("--parallel")[1].split()[0])
                except (ValueError, IndexError):
                    slots = 1
            servidores.append({"maquina": c[0], "puerto": c[1], "rol": c[2], "slots": slots})
            slots_tot += slots
    except OSError:
        pass
    return servidores, slots_tot


def _ultimo_hash():
    try:
        ult = None
        with open(LIBRO, encoding="utf-8") as f:
            for l in f:
                if l.strip():
                    ult = json.loads(l)
        return (ult or {}).get("hash", GENESIS)
    except (OSError, ValueError):
        return GENESIS


def _asentar(entrada):
    """Una línea en el libro: hash = sha256(prev + payload). Append-only, jamás se edita."""
    prev = _ultimo_hash()
    cuerpo = dict(entrada)
    cuerpo["prev"] = prev
    payload = json.dumps(cuerpo, ensure_ascii=False, sort_keys=True)
    cuerpo["hash"] = hashlib.sha256((prev + payload).encode("utf-8")).hexdigest()
    os.makedirs(os.path.dirname(LIBRO), exist_ok=True)
    with open(LIBRO, "a", encoding="utf-8") as f:
        f.write(json.dumps(cuerpo, ensure_ascii=False) + "\n")
    return cuerpo["hash"]


def acunar():
    if not _campana():
        _err("🔔 el banco abre con el DEBUT (primera Acción sellada) — hoy no acuña.")
        _err("   camino: ./pleno.sh → sellar ACC-… (Opus+Gustavo) · override: MOSAIC_BANCO=1")
        raise SystemExit(3)
    p = _politica()
    servidores, slots = _flota()
    if not servidores:
        _err("sin servidores fijos en servidores.conf — no hay flota que respalde: no se acuña")
        raise SystemExit(1)
    horas_utiles = float(p["periodo_horas"]) * float(p["utilizacion"])
    emision = int(slots * float(p["tokens_s_medidos"]) * 3600 * horas_utiles)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    h1 = _asentar({"ts": ts, "tipo": "emision",
                   "activo_respaldo_tokens": emision, "pasivo_emitido_tokens": emision,
                   "detalle": {"servidores_fijos": len(servidores), "slots": slots,
                               "tokens_s": p["tokens_s_medidos"], "horas_utiles": horas_utiles},
                   "regla": "no se emite más de lo que la flota computa (anti-fiat)"})
    reparto = {r: int(emision * float(f)) for r, f in (p.get("asignacion_rangos") or {}).items()}
    comun = int(emision * float(p.get("comun", 0)))
    _asentar({"ts": ts, "tipo": "propuesta_asignacion",
              "reparto_rangos": reparto, "comun_infraestructura": comun,
              "resto_reserva": emision - sum(reparto.values()) - comun,
              "estado": "PROPUESTA — SIN SELLOS: no aplicada",
              "regla": "aplicar = Acción + doble sello (el banco PROPONE, jamás mueve solo); "
                       "asignación por VALOR JUZGADO, jamás por actividad"})
    print(f"🏦 acuñado el periodo: {emision:,} tokens (={len(servidores)} fijos · {slots} slots · "
          f"{p['tokens_s_medidos']} tok/s medidos · {horas_utiles:.0f}h útiles)")
    print(f"   propuesta de asignación: {reparto} · común {comun:,} · libro sella {h1[:12]}…")
    print("   ⚠️ NADA se mueve sin doble sello — la propuesta espera en el libro.")


def resumen():
    try:
        lineas = [json.loads(l) for l in open(LIBRO, encoding="utf-8") if l.strip()]
    except (OSError, ValueError):
        print("(tesorería vacía — el banco aún no acuñó: abre con el debut)")
        return
    em = [x for x in lineas if x.get("tipo") == "emision"]
    if not em:
        print("(sin emisiones en el libro)")
        return
    u = em[-1]
    activo, pasivo = u.get("activo_respaldo_tokens", 0), u.get("pasivo_emitido_tokens", 0)
    print(f"🏦 último periodo ({u.get('ts','?')}):")
    print(f"   ACTIVO (respaldo: lo que la flota computa) : {activo:,} tokens")
    print(f"   PASIVO (emitido en presupuestos)           : {pasivo:,} tokens")
    print(f"   cuadre: {'✅ CUADRA' if activo >= pasivo else '⚠️ SOBRESUSCRITO (cola/lentitud real)'}"
          f" · entradas en el libro: {len(lineas)}")


def verificar():
    """La fiscalización: recorre la cadena — una línea alterada la ROMPE (y se dice dónde)."""
    try:
        lineas = [json.loads(l) for l in open(LIBRO, encoding="utf-8") if l.strip()]
    except (OSError, ValueError) as e:
        _err(f"libro ilegible: {e}")
        raise SystemExit(1)
    prev = GENESIS
    for i, x in enumerate(lineas, 1):
        h = x.pop("hash", "")
        payload = json.dumps(x, ensure_ascii=False, sort_keys=True)
        if x.get("prev") != prev or hashlib.sha256((prev + payload).encode()).hexdigest() != h:
            _err(f"⛓️ CADENA ROTA en la línea {i} ({x.get('ts','?')} · {x.get('tipo','?')}) — "
                 "alguien tocó el libro")
            raise SystemExit(2)
        prev = h
    print(f"⛓️ cadena ÍNTEGRA: {len(lineas)} asientos, nadie cocinó las cuentas ✅")


def main():
    orden = (sys.argv[1] if len(sys.argv) > 1 else "resumen").lstrip("-")
    if orden == "acunar":
        acunar()
    elif orden == "resumen":
        resumen()
    elif orden == "verificar":
        verificar()
    else:
        _err("uso: banco_central.py acunar | resumen | verificar")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
