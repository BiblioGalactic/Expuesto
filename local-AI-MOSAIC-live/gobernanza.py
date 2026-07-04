#!/usr/bin/env python3
"""
GOBERNANZA — la puerta por la que una capacidad PROPUESTA (del oráculo o de defensa) entra
(o no) en la biblioteca viva, SIN diluir. Tres filtros encadenados:
  #66 NOVEDAD      : ¿aporta algo nuevo? distancia al catálogo (semántica con MiniLM; léxica si no hay).
  #65 VERIFICACIÓN : ¿es una capacidad válida, general, no trivial? juez de curación (cuarentena).
  #67 STAGING      : lo que pasa va a un área de pruebas; 'promover' lo sube a capabilities/.

Uso:
  ./gobernanza.py revisar [--fuente data/seguridad_propuestas.yaml]   # propuestas -> staging / rechazo
  ./gobernanza.py promover                                            # staging -> capabilities/ (vivo)
  ./gobernanza.py estado
  ... --offline   # salta el juez (no bloquea), para probar el flujo
"""
import os
import sys
import time
import glob
import json
import shutil
from pathlib import Path
import yaml

OFFLINE = "--offline" in sys.argv
CAPS_DIR = Path(os.getenv("MOSAIC_CAPS_DIR", "capabilities"))
PROP_DEF = os.getenv("GOB_FUENTE", "data/seguridad_propuestas.yaml")
STAGING = Path(os.getenv("GOB_STAGING", "data/capabilities_staging.yaml"))
RECHAZ = Path(os.getenv("GOB_RECHAZADAS", "data/gobernanza_rechazadas.yaml"))
PROMOV = Path(os.getenv("GOB_PROMOVIDAS", "capabilities/promovidas.yaml"))
UMBRAL_RED = float(os.getenv("GOB_UMBRAL_REDUNDANTE", "0.82"))   # sim >= esto = redundante
UMBRAL_CUR = float(os.getenv("GOB_UMBRAL_CURACION", "6"))        # nota < esto = no pasa
JUEZ_URL = os.getenv("MOSAIC_JUDGE_URL") or os.getenv("MOSAIC_LLM_BASE_URL", "http://127.0.0.1:8090/v1")
EMB_MODEL = os.getenv("EMB_MODEL", os.path.expanduser("~/modelo/modelos_grandes/semantico/"
                      "models--sentence-transformers--all-MiniLM-L6-v2/snapshots"))


def _load(path):
    try:
        d = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    if isinstance(d, dict):
        return d.get("capabilities", [])
    return d if isinstance(d, list) else []


def _dump(path, caps):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.tmp{os.getpid()}")
    tmp.write_text(yaml.safe_dump({"capabilities": caps}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(tmp, p)


def _append(path, nuevas):
    if nuevas:
        _dump(path, _load(path) + nuevas)


def live_patterns():
    pats = []
    for f in glob.glob(str(CAPS_DIR / "*.yaml")):
        for c in _load(f):
            bp = c.get("behavioral_pattern")
            if bp:
                pats.append(bp)
    return pats


# make_sim se extrajo a dedup.py (#60): servicio común de similitud (lo usan también las fuentes).
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from dedup import make_sim                      # MiniLM (semántica) → léxica de respaldo
except Exception:                                   # respaldo si dedup.py no fuese importable
    import difflib as _difflib
    def make_sim(patterns):
        def sim(t):
            return max((_difflib.SequenceMatcher(None, t, p).ratio() for p in patterns), default=0.0)
        return sim, "léxica"


def juez_curacion(cap):
    if OFFLINE:
        return 10.0                       # sin red: no bloquea el flujo (se verifica con juez real)
    import urllib.request
    prompt = (f"Eres un revisor ESTRICTO de capacidades reutilizables. ¿Es GENERAL, clara y NO trivial "
              f"(no la respuesta a un caso concreto)?\n id={cap.get('id')}\n patrón={cap.get('behavioral_pattern', '')[:600]}\n"
              f'Devuelve SOLO JSON: {{"nota": <0-10>}}')
    body = json.dumps({"model": "local", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 60, "temperature": 0.1}).encode("utf-8")
    try:
        req = urllib.request.Request(JUEZ_URL.rstrip("/") + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            t = json.loads(r.read())["choices"][0]["message"]["content"]
        return float(json.loads(t[t.find("{"):t.rfind("}") + 1]).get("nota", 0))
    except Exception:
        return 5.0


def revisar():
    fuente = PROP_DEF
    if "--fuente" in sys.argv:
        i = sys.argv.index("--fuente")
        if i + 1 < len(sys.argv):
            fuente = sys.argv[i + 1]
    cands = _load(fuente)
    if not cands:
        print(f"Sin propuestas en {fuente}.")
        return
    pats = live_patterns()
    sim, modo = make_sim(pats)
    print(f"Gobernanza: {len(cands)} propuestas · {len(pats)} capacidades vivas · similitud {modo}")
    ids_staging = {c.get("id") for c in _load(STAGING)}
    a_staging, rechazadas = [], []
    for c in cands:
        cid = c.get("id", "?"); bp = c.get("behavioral_pattern", "")
        if cid in ids_staging:
            print(f"  · {cid} ya en staging, salto"); continue
        s = sim(bp)
        if s >= UMBRAL_RED:                         # #66 novedad
            c = dict(c); c["_rechazo"] = f"redundante (sim {s:.2f} >= {UMBRAL_RED})"
            rechazadas.append(c); print(f"  ✗ {cid}: {c['_rechazo']}"); continue
        nota = juez_curacion(c)                     # #65 verificación / cuarentena
        if nota < UMBRAL_CUR:
            c = dict(c); c["_rechazo"] = f"no pasa curación (nota {nota} < {UMBRAL_CUR})"
            rechazadas.append(c); print(f"  ✗ {cid}: {c['_rechazo']}"); continue
        c = dict(c); c["_novedad"] = round(1 - s, 2); c["_curacion"] = nota
        a_staging.append(c); print(f"  ✓ {cid} -> staging (novedad {1 - s:.2f}, curación {nota})")
    _append(STAGING, a_staging)                     # #67 staging
    _append(RECHAZ, rechazadas)
    print(f"-> {len(a_staging)} a staging · {len(rechazadas)} rechazadas")


def promover():
    cands = _load(STAGING)
    if not cands:
        print("Staging vacío."); return
    vivos = set()
    for f in glob.glob(str(CAPS_DIR / "*.yaml")):
        for c in _load(f):
            vivos.add(c.get("id"))
    nuevos = []
    for c in cands:
        if c.get("id") in vivos:
            continue
        c = {k: v for k, v in c.items() if not k.startswith("_")}    # limpia metadatos internos
        nuevos.append(c)
    if not nuevos:
        print("Nada nuevo que promover (todo ya vivo)."); _dump(STAGING, []); return
    if PROMOV.exists():                                              # backup (política Gustavo)
        bak = PROMOV.parent.parent / "trash" / "backups" / f"{PROMOV.name}.{time.strftime('%Y%m%d_%H%M%S')}.bak"
        bak.parent.mkdir(parents=True, exist_ok=True); shutil.copy(PROMOV, bak)
    _append(PROMOV, nuevos)
    _dump(STAGING, [])                                              # staging consumido
    print(f"Promovidas {len(nuevos)} -> {PROMOV} · staging vaciado.")
    for c in nuevos:
        print(f"   + {c.get('id')}")


def estado():
    print(f"propuestas ({PROP_DEF}): {len(_load(PROP_DEF))}")
    print(f"staging ({STAGING}): {len(_load(STAGING))}")
    print(f"rechazadas ({RECHAZ}): {len(_load(RECHAZ))}")
    print(f"vivas ({CAPS_DIR}): {sum(len(_load(f)) for f in glob.glob(str(CAPS_DIR / '*.yaml')))}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "estado"
    {"revisar": revisar, "promover": promover, "estado": estado}.get(cmd, estado)()


if __name__ == "__main__":
    main()
