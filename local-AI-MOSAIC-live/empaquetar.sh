#!/bin/bash
# 📦 =====================================================================
# 📦 EMPAQUETAR — exporta una MÁSCARA de dominio como pack portable (VISIÓN Opus 4-jul 17:16).
# 📦   MOSAIC = motor abierto + máscara portátil + corpus privado. Esto exporta la
# 📦   MÁSCARA: capacidades del dominio + sinergias aprendidas (state.json), CURADA
# 📦   y SANEADA — whitelist de campos, PII redactada, archivadas fuera, referencias
# 📦   a ids de fuera del pack podadas. Exportar = CURAR + SANEAR, jamás volcar a pelo.
# 📦   JAMÁS exporta lo PRIVADO: historial, huecos, silo, CARTAS, trazas, tokens.
# 📦 Pack = packs/<dominio>_vN.mosaic (tar.gz: manifest.json + capabilities.yaml + graph.json)
# 📦   Contrato: schema_version + degradación elegante (el importador ignora lo que
# 📦   no entiende) · agnóstico de flota (declara roles, no modelos) · ⚔️ el 24B jamás.
# 📦 Uso:  ./empaquetar.sh <dominio>                    (DRY-RUN: plan + redacciones)
# 📦       ./empaquetar.sh <dominio> --aplicar [--autor NOMBRE]
# 📦   dominio = capabilities/<dominio>.yaml entero, y/o coincidencia exacta en
# 📦   domain_expertise/tags de cualquier capacidad viva (minúsculas).
# 📦 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
CAPS_DIR="$BASE/capabilities"
STATE="$BASE/data/state.json"
PACKS="$BASE/packs"
LICENCIA="${PACK_LICENCIA:-sin-especificar}"

DOMINIO="${1:-}"; APLICAR=0; AUTOR="${PACK_AUTOR:-Gustavo}"
shift || true
while [ $# -gt 0 ]; do case "$1" in
    --aplicar) APLICAR=1 ;;
    --autor)   shift; AUTOR="${1:-$AUTOR}" ;;
    *) ;;
esac; shift || true; done

TMPS=()
cleanup() { for t in "${TMPS[@]:-}"; do [ -n "${t:-}" ] && rm -rf "$t" 2>/dev/null || true; done; }
trap cleanup EXIT

log() { printf '[%s] 📦 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    [ -n "$DOMINIO" ] || { err "uso: ./empaquetar.sh <dominio> [--aplicar] [--autor NOMBRE]"; exit 1; }
    [[ "$DOMINIO" =~ ^[A-Za-z0-9_-]+$ ]] || { err "dominio inválido (solo letras/números/_/-): $DOMINIO"; exit 1; }
    [ -d "$CAPS_DIR" ] || { err "no encuentro $CAPS_DIR"; exit 1; }
    [ -r "$STATE" ]    || { err "no encuentro $STATE (el peso de la máscara)"; exit 1; }
    for c in tar date python3; do command -v "$c" >/dev/null || { err "falta $c"; exit 1; }; done
    python3 -c 'import yaml' 2>/dev/null || { err "falta pyyaml (python3 -m pip install pyyaml)"; exit 1; }
}

ejecutar() {
    local tmpd rc=0; tmpd="$(mktemp -d)"; TMPS+=("$tmpd")

    # ── CURAR + SANEAR (python: selección, whitelist, PII, poda, grafo) ──
    SANEADO_CONF="${SANEADO_CONF:-$BASE/saneado_patrones.conf}" \
    python3 - "$CAPS_DIR" "$STATE" "$DOMINIO" "$AUTOR" "$LICENCIA" "$tmpd" <<'PY' || rc=$?
import json, os, re, sys, datetime
from pathlib import Path
import yaml

caps_dir, state_f, dominio, autor, licencia, outd = sys.argv[1:7]
dom = dominio.lower()

# --- SANEO PII: LA FUENTE ÚNICA saneado_patrones.conf (P8 plan 6-jul — antes esta lista
#     vivía DUPLICADA con el gate de exportar_publico.sh y divergían en silencio).
#     Ámbito `pack`: (regex → reemplazo), VERBATIM los de siempre ((?i) sustituye al re.I).
#     Sin fichero o vacío → FALLAR ALTO: jamás empaquetar con el colador roto. ---
PII = []
try:
    for _ln in open(os.environ["SANEADO_CONF"], encoding="utf-8"):
        _ln = _ln.rstrip("\n")
        if not _ln.strip() or _ln.lstrip().startswith("#"):
            continue
        _c = _ln.split("\t")
        if len(_c) >= 3 and _c[0] == "pack" and _c[2]:
            PII.append((re.compile(_c[2]), _c[1]))
except (OSError, KeyError, re.error) as _e:
    sys.exit(f"🛑 empaquetar: patrones PII ilegibles ({_e}) — no empaqueto a ciegas")
if not PII:
    sys.exit("🛑 empaquetar: 0 patrones PII (¿falta saneado_patrones.conf?) — no empaqueto a ciegas")
def sanear(txt, cuenta):
    if not isinstance(txt, str):
        return txt
    for rx, sub in PII:
        txt, n = rx.subn(sub, txt)
        if n:
            cuenta[sub] = cuenta.get(sub, 0) + n
    return txt

# --- cargar TODAS las capacidades vivas (mismo glob que load_capabilities) ---
items, origen = {}, {}
for f in sorted(Path(caps_dir).glob("**/*.y*ml")):
    try:
        data = yaml.safe_load(f.read_text()) or {}
    except Exception:
        continue
    lst = data if isinstance(data, list) else data.get("capabilities", [])
    for it in lst:
        if isinstance(it, dict) and it.get("id") and it["id"] not in items:
            items[it["id"]] = it
            origen[it["id"]] = f.stem

state = json.load(open(state_f))
archivadas = set(state.get("archived", []))
vivos = state.get("capabilities", {})

# --- selección: fichero <dominio>.yaml entero y/o match exacto en expertise/tags ---
sel, por_fichero, por_dominio, n_arch = {}, 0, 0, 0
for cid, it in items.items():
    de = [str(x).lower() for x in (it.get("domain_expertise") or [])]
    tg = [str(x).lower() for x in (it.get("tags") or [])]
    encaja = origen[cid] == dominio or dom in de or dom in tg
    if not encaja:
        continue
    if cid in archivadas:
        n_arch += 1; continue
    if origen[cid] == dominio:
        sel[cid] = it; por_fichero += 1
    else:
        sel[cid] = it; por_dominio += 1
if not sel:
    print(f"PLAN|0 capacidades para «{dominio}» (ni fichero ni expertise/tags). Nada que empaquetar.")
    sys.exit(3)

# --- whitelist de campos (esquema ESTABLE del pack) + score VIVO + poda de refs ---
CAMPOS = ("id", "role", "domain_expertise", "behavioral_pattern",
          "performance_score", "tags", "compatible_capabilities", "incompatible_capabilities")
redacciones, con_redaccion, limpio = {}, [], []
for cid, it in sel.items():
    c = {k: it[k] for k in CAMPOS if k in it and it[k] not in (None, "", [])}
    sc = vivos.get(cid, {}).get("performance_score", c.get("performance_score", 0.5))
    c["performance_score"] = round(float(sc), 3)
    for k in ("compatible_capabilities", "incompatible_capabilities"):
        if k in c:
            c[k] = [r for r in c[k] if r in sel]
            if not c[k]:
                del c[k]
    antes = dict(redacciones)
    c["behavioral_pattern"] = sanear(c.get("behavioral_pattern", ""), redacciones)
    c["domain_expertise"] = [sanear(x, redacciones) for x in c.get("domain_expertise", [])]
    c["tags"] = [sanear(x, redacciones) for x in c.get("tags", [])]
    if redacciones != antes:
        con_redaccion.append(cid)
    limpio.append(c)

# --- grafo: solo aristas con AMBOS extremos dentro del pack, razones saneadas ---
grafo = []
for e in state.get("graph", []):
    if e.get("a") in sel and e.get("b") in sel:
        arista = {"a": e["a"], "b": e["b"], "weight": round(float(e.get("weight", 0)), 3),
                  "type": e.get("type", "synergy")}
        if e.get("reason"):
            arista["reason"] = sanear(str(e["reason"])[:80], redacciones)
        grafo.append(arista)

roles = {}
for c in limpio:
    roles[c.get("role", "?")] = roles.get(c.get("role", "?"), 0) + 1

manifest = {
    "schema_version": 1,
    "formato": "mosaic-pack",
    "dominio": dominio,
    "autor": autor,
    "procedencia": "MOSAIC (local-first, RAG de capacidades)",
    "licencia": licencia,
    "creado": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "n_capacidades": len(limpio),
    "roles": roles,                      # roles REQUERIDOS: el importador los mapea a SU flota
    "n_sinergias": len(grafo),
    "saneado": True,
    "nota": "scores = aprendizaje del MOSAIC de origen; el importador aplica su prior.",
}
out = Path(outd)
out.joinpath("manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
out.joinpath("capabilities.yaml").write_text(
    yaml.safe_dump({"capabilities": limpio}, allow_unicode=True, sort_keys=False))
out.joinpath("graph.json").write_text(json.dumps(grafo, ensure_ascii=False, indent=2))

print(f"PLAN|seleccionadas {len(limpio)} (fichero {por_fichero} + dominio {por_dominio}) · "
      f"archivadas fuera {n_arch} · sinergias {len(grafo)} · roles {roles}")
if con_redaccion:
    det = " · ".join(f"{k}×{v}" for k, v in redacciones.items())
    print(f"PLAN|🧹 PII redactada en {len(con_redaccion)} capacidad(es): {det}")
    print(f"PLAN|   → revisa a mano antes de compartir: {', '.join(con_redaccion[:12])}")
else:
    print("PLAN|🧹 PII: nada que redactar")
print("PLAN|ids: " + ", ".join(c["id"] for c in limpio[:20]) + (" …" if len(limpio) > 20 else ""))
PY
    [ "$rc" = 3 ] && { err "sin capacidades para «${DOMINIO}» — nada que empaquetar"; return 3; }
    [ "$rc" != 0 ] && { err "el curado falló (rc=$rc)"; return "$rc"; }

    # ── versión siguiente ──
    local ult=0 n f
    for f in "$PACKS/${DOMINIO}"_v*.mosaic; do
        [ -e "$f" ] || continue
        n="${f##*_v}"; n="${n%.mosaic}"
        [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -gt "$ult" ] && ult=$n
    done
    local destino="$PACKS/${DOMINIO}_v$((ult + 1)).mosaic"

    if [ "$APLICAR" = 1 ]; then
        mkdir -p "$PACKS"
        tar -czf "$destino" -C "$tmpd" manifest.json capabilities.yaml graph.json
        log "✅ pack creado: ${destino#$BASE/} ($(du -h "$destino" | cut -f1 | tr -d ' '))"
        log "compartir = enviar ESE fichero a mano. packs/ está fuera del repo público (.gitignore)."
    else
        log "DRY-RUN — nada escrito. Destino si aplicas: ${destino#$BASE/}"
        log "aplica con: ./empaquetar.sh $DOMINIO --aplicar"
    fi
    return $rc
}

validar
log "dominio «${DOMINIO}» · autor «${AUTOR}» · $([ "$APLICAR" = 1 ] && echo APLICAR || echo DRY-RUN)"
ejecutar
