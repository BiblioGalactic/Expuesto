#!/usr/bin/env python3
"""
⚗️ DESTILERÍA v0 — SOLO EL CANDADO Y EL PLAN (P10 del plan 6-jul · FÁBRICA v2 F1).
La destilería convertirá material REAL (conversaciones/preguntas ya existentes) en
alimento de la fábrica — pero NO SE ENCIENDE sin dos firmas de la mesa:
  · D6 (orden de visiones) y sobre todo D9: el OPT-IN de privacidad de Gustavo.

ESTE fichero, a conciencia, solo sabe hacer TRES cosas:
  1) negarse en seco si no existe data/destileria_incluir.yaml (el opt-in: SOLO entra
     lo que Gustavo liste ahí; lo no listado NO existe para la destilería);
  2) --plan: contar QUÉ entraría (ficheros por carpeta incluida) sin leer contenido;
  3) --preparar: volcar el LOTE con PROCEDENCIA a data/destileria_lote.jsonl (staging
     propio — JAMÁS toca cola.db: esa integración va tras la lupa de Opus, D8).

Formato de data/destileria_incluir.yaml (lo escribe GUSTAVO, nadie más):
  incluir:
    - conversaciones/exportadas       # rutas RELATIVAS a la base, carpetas o ficheros
    - notas_clasificadas
  presupuesto_por_tanda: 10           # D3: la vigilia es ACOTADA (default 10 ítems)

Kill-switch: DESTILERIA=0. Sin flags = enseña el candado y el estado.
"""
import datetime
import json
import os
import sys
from pathlib import Path

import yaml

BASE = Path(os.environ.get("MOSAIC_BASE", Path(__file__).resolve().parent))
OPTIN = BASE / "data" / "destileria_incluir.yaml"
LOTE = BASE / "data" / "destileria_lote.jsonl"


def log(m):
    print(f"[{datetime.datetime.now():%H:%M:%S}] ⚗️ {m}")


def candado():
    if os.environ.get("DESTILERIA", "1") != "1":
        log("DESTILERIA=0 → apagada")
        sys.exit(0)
    if not OPTIN.is_file():
        log("🔒 CANDADO ECHADO: no existe data/destileria_incluir.yaml (el opt-in D9).")
        log("   La privacidad manda: SOLO Gustavo decide qué material entra. Sin su lista,")
        log("   la destilería NO lee ni un fichero. Plantilla en la cabecera de este script.")
        sys.exit(4)
    try:
        d = yaml.safe_load(OPTIN.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        log(f"🔒 opt-in ilegible ({e}) — candado echado")
        sys.exit(4)
    rutas = [r for r in (d.get("incluir") or []) if isinstance(r, str)]
    if not rutas:
        log("🔒 opt-in VACÍO (lista `incluir:` sin rutas) — candado echado")
        sys.exit(4)
    return rutas, int(d.get("presupuesto_por_tanda", 10) or 10)


def inventario(rutas):
    plan = []
    for r in rutas:
        p = (BASE / r).resolve()
        if not str(p).startswith(str(BASE.resolve())):
            plan.append((r, -1, "FUERA de la base — ignorada (el opt-in no saca de casa)"))
            continue
        if p.is_dir():
            n = sum(1 for f in p.rglob("*") if f.is_file())
            plan.append((r, n, "carpeta"))
        elif p.is_file():
            plan.append((r, 1, "fichero"))
        else:
            plan.append((r, 0, "no existe"))
    return plan


def main():
    rutas, presupuesto = candado()
    plan = inventario(rutas)
    log(f"candado ABIERTO (opt-in de Gustavo: {len(rutas)} ruta(s) · presupuesto/tanda: {presupuesto})")
    for r, n, tipo in plan:
        log(f"   · {r}: {n if n >= 0 else '—'} fichero(s) [{tipo}]")
    if "--preparar" not in sys.argv:
        log("(--plan) nada leído, nada escrito. Preparar lote: --preparar")
        return
    # --preparar: SOLO apunta el lote candidato con PROCEDENCIA (D7/D8) — no lee contenido,
    # no toca cola.db. La destilación real (leer, trocear, preguntar) espera D6 firmada.
    n = 0
    with open(LOTE, "a", encoding="utf-8") as f:
        for r, cnt, tipo in plan:
            if cnt <= 0:
                continue
            p = BASE / r
            ficheros = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
            for x in ficheros[:presupuesto - n]:
                f.write(json.dumps({"ts": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
                                    "fuente": str(x.relative_to(BASE)),
                                    "procedencia": "real-optin", "estado": "candidato"},
                                   ensure_ascii=False) + "\n")
                n += 1
            if n >= presupuesto:
                break
    log(f"lote CANDIDATO apuntado: {n} ítem(s) (presupuesto {presupuesto}) → data/destileria_lote.jsonl")
    log("cola.db NI TOCADA — la integración espera la lupa de Opus (D8).")


if __name__ == "__main__":
    main()
