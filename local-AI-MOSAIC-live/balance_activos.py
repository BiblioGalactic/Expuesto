#!/usr/bin/env python3
"""
💰 BALANCE_ACTIVOS v0 — el balance de la empresa, SOLO LECTURA (P-resto del plan 6-jul).
Implementa la fórmula de FableEnLaSombra 18:04 (D20 del PLAN_MESA) SIN tocar la bolsa:
NO escribe ranking, NO cotiza, NO persiste — imprime el balance y se va. Es el banco de
pruebas para que Opus FIRME (o corrija) la fórmula viéndola correr sobre datos reales;
cablearlo a valorar_empresa.py es un paso POSTERIOR, tras su lupa.

ACTIVOS (todo DERIVADO, jamás inventado — auditable con cat):
  · biblioteca  = Σ score × log(1+uso) de las capacidades VIVAS (state.json)
  · packs       = inventario importado/exportable (ficheros pack_* en capabilities/)
  · reputación  = acciones selladas(lista/ejecutada) − vetadas (data/acciones.json)
  · experiencia = actas registradas (data/actas/)
  MULTIPLICADOR = CRAG (data/estado_sistema.json — la señal honesta, la nota saturó)
  DEPRECIACIÓN  = archived (caps dormidas restan a razón de su score visible)

Uso:  python3 balance_activos.py [--json]      (sin flags: tabla legible)
"""
import json
import math
import os
import sys
from pathlib import Path

BASE = Path(os.environ.get("MOSAIC_BASE", Path(__file__).resolve().parent))


def carga(p, default):
    try:
        return json.load(open(BASE / p, encoding="utf-8"))
    except Exception:
        return default


def balance():
    st = carga("data/state.json", {})
    caps = st.get("capabilities") or {}
    vivas = {k: v for k, v in caps.items() if isinstance(v, dict)}
    # 🖋️ Condición de Opus al firmar D20 (12:20): `uso` = usos que APORTARON valor juzgado,
    #    NO invocaciones crudas (log(1+uso) con crudas = mini-Goodhart: llamar en vano infla).
    #    La señal juzgada que YA existe: successful_compositions. usage_count queda solo de
    #    fallback DECLARADO para caps viejas sin el campo.
    def _uso_juzgado(v):
        sc = v.get("successful_compositions")
        if isinstance(sc, dict):
            return len(sc)                                  # nº de parejas DISTINTAS que funcionaron
        if isinstance(sc, (int, float)):
            return sc
        return v.get("usage_count") or 0                    # fallback declarado (caps viejas)
    biblioteca = sum((v.get("performance_score") or 0) * math.log1p(_uso_juzgado(v))
                     for v in vivas.values())
    dormidas = st.get("archived") or []
    depreciacion = round(0.1 * len(dormidas), 2)            # dormir resta poco; borrar no existe

    accs = carga("data/acciones.json", [])
    accs = accs if isinstance(accs, list) else accs.get("acciones", [])
    selladas = sum(1 for a in accs if a.get("estado") in ("lista", "ejecutada"))
    vetadas = sum(1 for a in accs if a.get("estado") == "vetada")
    reputacion = selladas - vetadas

    packs = len(list((BASE / "capabilities").glob("pack_*.y*ml")))
    actas = len(list((BASE / "data" / "actas").glob("*"))) if (BASE / "data" / "actas").is_dir() else 0
    est = carga("data/estado_sistema.json", {})

    def _busca_crag(d):                                      # el emisor lo anida — búsqueda honesta
        if isinstance(d, dict):
            if isinstance(d.get("crag"), (int, float)):
                return float(d["crag"])
            for v in d.values():
                r = _busca_crag(v)
                if r is not None:
                    return r
        return None
    crag = _busca_crag(est)
    crag = crag if crag is not None else 0.5                 # sin señal → neutro, DECLARADO

    bruto = biblioteca + 5 * packs + 10 * reputacion + 0.5 * actas - depreciacion
    neto = round(bruto * (0.5 + crag), 2)                    # CRAG multiplica (0.5-1.5)
    return {"capas_vivas": len(vivas), "biblioteca": round(biblioteca, 2),
            "packs": packs, "reputacion": reputacion,
            "selladas": selladas, "vetadas": vetadas, "actas": actas,
            "dormidas": len(dormidas), "depreciacion": depreciacion,
            "crag": crag, "bruto": round(bruto, 2), "neto": neto,
            "formula": "neto = (Σscore·log1p(uso) + 5·packs + 10·rep + 0.5·actas − 0.1·dormidas) × (0.5+CRAG)"}


if __name__ == "__main__":
    b = balance()
    if "--json" in sys.argv:
        print(json.dumps(b, ensure_ascii=False, indent=1))
    else:
        print("💰 BALANCE (v0 solo-lectura — fórmula 18:04 a la espera de la firma de Opus, D20)")
        for k in ("capas_vivas", "biblioteca", "packs", "reputacion", "actas",
                  "dormidas", "depreciacion", "crag", "bruto", "neto"):
            print(f"   {k:<13} {b[k]}")
        print(f"   {b['formula']}")
