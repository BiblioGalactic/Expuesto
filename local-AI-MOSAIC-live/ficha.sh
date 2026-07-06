#!/bin/bash
# 🪪 =====================================================================
# 🪪 FICHA — la identidad CONSOLIDADA de un agente (DERIVADA, no un store nuevo).
# 🪪   Núcleo + carácter (su yaml) · trayectoria (CARTAS) · credenciales (acciones
# 🪪   selladas) · red (a quién escucha) · biométrica (idiolecto). Todo se LEE de
# 🪪   donde YA vive — cero duplicación (doctrina anti-doble-fuente-de-verdad).
# 🪪   La identidad del agente es el INVERSO del humano: unificada, transparente, propia.
# 🪪 Uso:  ./ficha.sh <rol>        (una ficha)
# 🪪       ./ficha.sh --todos      (la plantilla entera)
# 🪪 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
TURNOS="$BASE/roles/turnos"

err() { printf '⚠️  %s\n' "$*" >&2; }

validar() {
    command -v python3 >/dev/null || { err "falta python3"; exit 1; }
    python3 -c 'import yaml' 2>/dev/null || { err "falta pyyaml (ver venv wikirag/ligero)"; exit 1; }
    [ -d "$TURNOS" ] || { err "no hay $TURNOS"; exit 1; }
}

ficha_de() {
    ROL="$1" BASE_D="$BASE" python3 - <<'PY'
import os, re, json, yaml

base, rol = os.environ["BASE_D"], os.environ["ROL"]
yp = os.path.join(base, "roles", "turnos", rol + ".yaml")
if not os.path.isfile(yp):
    print(f"⚠️  no existe el rol: {rol}"); raise SystemExit(1)

d = yaml.safe_load(open(yp, encoding="utf-8")) or {}
p = d.get("persona", {}) or {}
firma = d.get("firma", f"MOSAIC-{rol}")
alias = p.get("alias", rol); emoji = p.get("emoji", "🪪"); nombre = p.get("nombre_humano", "")

# ── TRAYECTORIA · derivada de CARTAS (sus intervenciones firmadas) ──
n, last, tipos = 0, "—", {}
cartas = os.path.join(base, "info", "CARTAS.md")
if os.path.isfile(cartas):
    for line in open(cartas, encoding="utf-8", errors="replace"):
        if line.startswith("## ") and firma in line:
            n += 1
            m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", line)
            if m:
                last = m.group(1)
            for t in ("Acción", "Accion", "Parte de estado", "Informe", "Decisión", "Incidente"):
                if t in line:
                    tipos[t.replace("Accion", "Acción")] = tipos.get(t.replace("Accion", "Acción"), 0) + 1
                    break

# ── CREDENCIALES · acciones selladas que firmó (data/acciones.json) ──
cred = []
acc = os.path.join(base, "data", "acciones.json")
if os.path.isfile(acc):
    try:
        for a in json.load(open(acc, encoding="utf-8")).get("acciones", []):
            if a.get("autor") == firma:
                sellos = ",".join(s["rol"] for s in a.get("sellos", [])) or "sin sellar"
                cred.append(f"{a['id']} [{a['estado']}·{sellos}]")
    except Exception:
        pass

# ── SALUD · dignidad del modelo (solo si es razonador con modelo) ──
salud = "—"
dig = os.path.join(base, "data", "dignidad_modelos.json")
tipo = d.get("tipo_reporte", "Informe")
if tipo == "parte-de-estado":
    salud = "N3 determinista — no depende de modelo (ficha con la flota abajo)"
elif os.path.isfile(dig):
    try:
        dg = json.load(open(dig, encoding="utf-8"))
        salud = " · ".join(f"{k}:{v}" for k, v in list(dg.items())[:4]) if isinstance(dg, dict) else "registro presente"
    except Exception:
        salud = "registro presente"

lecturas = d.get("lecturas", []) or []
sep = "═" * 60
print(f"🪪 {sep}")
print(f"   FICHA DE IDENTIDAD · {(nombre + ' · ') if nombre else ''}«{alias}» {emoji}   ({firma})")
print(f"🪪 {sep}")
print(f" NÚCLEO       depto: {d.get('departamento','?')} · nivel: {d.get('nivel','?')} · "
      f"acceso: {d.get('nivel_acceso','?')}/5 · emite: {tipo}")
print(f" CARÁCTER     tono: {p.get('tono','—')}")
print(f"              bio:  {p.get('bio','—')}")
print(f" TRAYECTORIA  {n} intervenciones en la mesa · última: {last}"
      + (f" · ({' · '.join(f'{k} {v}' for k, v in tipos.items())})" if tipos else ""))
print(f" CREDENCIALES {' · '.join(cred) if cred else 'ninguna acción sellada aún'}")
print(f" SALUD        {salud}")
print(f" RED (escucha){'' if lecturas else ' —'}" + ("  " + " · ".join(lecturas[:6]) if lecturas else ""))
print(f" BIOMÉTRICA   autoría verificable por su idiolecto (idiolecto.py) — cómo habla la delata")
print(f"🪪 {sep}")
PY
}

validar
if [ "${1:-}" = "--todos" ]; then
    for y in "$TURNOS"/*.yaml; do ficha_de "$(basename "$y" .yaml)"; echo; done
elif [ -n "${1:-}" ]; then
    ficha_de "$1"
else
    err "uso: ./ficha.sh <rol> | --todos   · roles: $(ls "$TURNOS" 2>/dev/null | sed 's/\.yaml//' | tr '\n' ' ')"
    exit 2
fi
