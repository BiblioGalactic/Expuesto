#!/usr/bin/env python3
"""
🪪 IDENTIDAD v1 — el resolver ÚNICO de autodeclaración (D19 del PLAN_MESA, 6-jul).
Contrato: JSON-SUBPROCESS (mi recomendación en D19 — frontera dura contra el dios-módulo).
⚠️ AÚN NO CABLEADO A NADIE: Opus decide D19; si prefiere import, el mismo fichero sirve
(las funciones son importables). La migración de los 10 parsers será INCREMENTAL, cliente
a cliente, jamás big-bang (doctrina de la carta de Sombra 18:39).

Declara cada entidad en 3 capas DERIVADAS (fractal agente→depto→empresa):
  🔒 nucleo   — rol, nivel, departamento, tipo_reporte, puertos, nivel_acceso (roles/turnos/*.yaml)
  🎨 persona  — nombre, alias, emoji, tono (capa PERSONA del yaml; jamás cambia límites)
  💰 economia — derivada del libro: acciones propuestas/selladas/vetadas/ejecutadas por su firma

Uso (contrato JSON por stdout, un objeto por línea de invocación):
  python3 identidad.py --agente auditor
  python3 identidad.py --lista               (todas las sillas, núcleo mínimo)
  python3 identidad.py --self-test           (compara contra lectura yaml directa)
"""
import json
import os
import sys
from pathlib import Path

import yaml

BASE = Path(os.environ.get("MOSAIC_BASE", Path(__file__).resolve().parent))
TURNOS = BASE / "roles" / "turnos"


def _yaml(rol):
    p = TURNOS / f"{rol}.yaml"
    if not p.is_file():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return {"_error": f"yaml ilegible: {e}"}


def _economia(firma):
    try:
        d = json.load(open(BASE / "data" / "acciones.json", encoding="utf-8"))
        accs = d if isinstance(d, list) else d.get("acciones", [])
    except Exception:
        accs = []
    mias = [a for a in accs if a.get("autor") == firma]
    return {"propuestas": len(mias),
            "selladas": sum(1 for a in mias if a.get("estado") in ("lista", "ejecutada")),
            "ejecutadas": sum(1 for a in mias if a.get("estado") == "ejecutada"),
            "vetadas": sum(1 for a in mias if a.get("estado") == "vetada")}


def declarar(rol):
    d = _yaml(rol)
    if d is None:
        return {"ok": False, "error": f"no existe la silla: {rol}"}
    if "_error" in d:
        return {"ok": False, "error": d["_error"]}
    firma = d.get("firma", f"MOSAIC-{rol}")
    per = d.get("persona") or {}
    return {"ok": True, "entidad": rol, "capa": "agente",
            "nucleo": {"rol": d.get("rol", rol), "firma": firma,
                       "departamento": d.get("departamento", "?"),
                       "nivel": d.get("nivel", "?"), "nivel_acceso": d.get("nivel_acceso", 1),
                       "tipo_reporte": d.get("tipo_reporte", "Informe"),
                       "puertos": d.get("puertos", []), "activo": bool(d.get("activo", 1))},
            "persona": {"nombre": per.get("nombre_humano", ""), "alias": per.get("alias", ""),
                        "emoji": per.get("emoji", ""), "tono": per.get("tono", "")},
            "economia": _economia(firma)}


def lista():
    return {"ok": True, "sillas": sorted(f.stem for f in TURNOS.glob("*.yaml"))}


def self_test():
    """El resolver debe decir EXACTAMENTE lo que dicen los yaml — cero invención."""
    fallos = []
    for f in sorted(TURNOS.glob("*.yaml")):
        d = declarar(f.stem)
        crudo = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if not d.get("ok"):
            fallos.append(f"{f.stem}: {d.get('error')}")
        elif d["nucleo"]["firma"] != crudo.get("firma", f"MOSAIC-{f.stem}"):
            fallos.append(f"{f.stem}: firma difiere")
    print(json.dumps({"ok": not fallos, "sillas": len(list(TURNOS.glob('*.yaml'))),
                      "fallos": fallos}, ensure_ascii=False))
    return 0 if not fallos else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--lista" in a:
        print(json.dumps(lista(), ensure_ascii=False))
    elif "--agente" in a and a.index("--agente") + 1 < len(a):
        print(json.dumps(declarar(a[a.index("--agente") + 1]), ensure_ascii=False))
    else:
        print(json.dumps({"ok": False, "error": "uso: --agente <rol> | --lista | --self-test"}))
        sys.exit(2)
