#!/bin/bash
# 📥 =====================================================================
# 📥 IMPORTAR — recibe un pack de máscara AJENO (VISIÓN Opus 4-jul 17:16).
# 📥   Un pack de otro son INSTRUCCIONES NO CONFIABLES (un behavioral_pattern
# 📥   puede ser una inyección). Camino: validar schema → ADUANA (defensa.py:
# 📥   3 lentes + juez + candado D0.2, la MISMA de GitHub) → merge SIN PISAR:
# 📥   fichero propio importado_<autor>_<dominio>.yaml · ids con namespace
# 📥   <autor>__id · scores capados al PRIOR INDULGENTE (se recalibran con TU
# 📥   uso) · sinergias del pack → compatible/incompatible DECLARADAS (cero
# 📥   toques a data/state.json). Degradación elegante: lo que no entiendo se
# 📥   ignora contándolo, no rompe. Fail-closed: sin veredicto = DUDOSO = NO entra.
# 📥 Uso:  ./importar.sh <pack.mosaic>              (DRY-RUN: plan, sin defensa ni merge)
# 📥       ./importar.sh <pack.mosaic> --aplicar    [--offline] [--forzar]
# 📥   --offline: defensa en mock (pruebas en frío; el mock NO da SEGURO → no entra)
# 📥   --forzar:  re-importar pisando el fichero previo (con backup a trash/backups)
# 📥 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
CAPS_DIR="$BASE/capabilities"
DEFENSA="${DEFENSA_PY:-$BASE/defensa.py}"
BACKUPS="$BASE/trash/backups"
PRIOR="${IMPORT_PRIOR:-0.60}"
export LOCK_BASE="${LOCK_BASE:-$BASE/data}"

PACK="${1:-}"; APLICAR=0; OFFLINE=""; FORZAR=0
shift || true
while [ $# -gt 0 ]; do case "$1" in
    --aplicar) APLICAR=1 ;;
    --offline) OFFLINE="--offline" ;;
    --forzar)  FORZAR=1 ;;
    *) ;;
esac; shift || true; done

# shellcheck disable=SC1091
source "$BASE/lock.sh"
TMPS=()
cleanup() { soltar_locks 2>/dev/null || true; for t in "${TMPS[@]:-}"; do [ -n "${t:-}" ] && rm -rf "$t" 2>/dev/null || true; done; }
trap cleanup EXIT

log() { printf '[%s] 📥 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    [ -n "$PACK" ] || { err "uso: ./importar.sh <pack.mosaic> [--aplicar] [--offline] [--forzar]"; exit 1; }
    [ -r "$PACK" ] || { err "no puedo leer el pack: $PACK"; exit 1; }
    tar -tzf "$PACK" >/dev/null 2>&1 || { err "el pack no es un tar.gz legible"; exit 1; }
    [ -x "$DEFENSA" ] || [ -r "$DEFENSA" ] || { err "no encuentro la aduana: $DEFENSA"; exit 1; }
    [ -d "$CAPS_DIR" ] || { err "no encuentro $CAPS_DIR"; exit 1; }
    for c in tar date python3; do command -v "$c" >/dev/null || { err "falta $c"; exit 1; }; done
    python3 -c 'import yaml' 2>/dev/null || { err "falta pyyaml"; exit 1; }
}

ejecutar() {
    local tmpd rc=0; tmpd="$(mktemp -d)"; TMPS+=("$tmpd")
    tar -xzf "$PACK" -C "$tmpd"
    [ -f "$tmpd/manifest.json" ] || { err "pack sin manifest.json — no es un mosaic-pack"; exit 1; }

    # ── validar schema + PREPARAR merge (namespace · prior · refs · grafo→declarado) ──
    python3 - "$tmpd" "$CAPS_DIR" "$PRIOR" <<'PY' || rc=$?
import json, re, sys
from pathlib import Path
import yaml

tmpd, caps_dir, prior = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])

man = json.loads((tmpd / "manifest.json").read_text())
sv = int(man.get("schema_version", 0) or 0)
if sv < 1:
    print("PLAN|⚠ manifest sin schema_version válido — no es un mosaic-pack"); sys.exit(4)
if sv > 1:
    print(f"PLAN|⚠ schema_version {sv} > 1 (pack más nuevo que yo): leo lo que entiendo, ignoro el resto")

slug = lambda s: (re.sub(r'[^a-z0-9]+', '_', str(s).lower()).strip('_') or 'anon')[:32]
autor, dominio = slug(man.get("autor", "anon")), slug(man.get("dominio", "pack"))

try:
    lst = (yaml.safe_load((tmpd / "capabilities.yaml").read_text()) or {}).get("capabilities", [])
except Exception as e:
    print(f"PLAN|⚠ capabilities.yaml ilegible: {e}"); sys.exit(4)
try:
    grafo = json.loads((tmpd / "graph.json").read_text()) if (tmpd / "graph.json").exists() else []
except Exception:
    grafo = []
    print("PLAN|graph.json ilegible → sin sinergias (degradación elegante)")

# ids ya vivos en MI biblioteca (colisión = no pisar) — EXCLUYENDO el import previo
# de ESTE mismo pack (si no, un re-import con --forzar vería sus propios ids como colisión)
destino_propio = f"importado_{autor}_{dominio}.yaml"
mios = set()
for f in sorted(caps_dir.glob("**/*.y*ml")):
    if f.name == destino_propio:
        continue
    try:
        data = yaml.safe_load(f.read_text()) or {}
    except Exception:
        continue
    for it in (data if isinstance(data, list) else data.get("capabilities", [])):
        if isinstance(it, dict) and it.get("id"):
            mios.add(it["id"])

CAMPOS = ("id", "role", "domain_expertise", "behavioral_pattern",
          "performance_score", "tags", "compatible_capabilities", "incompatible_capabilities")
ns = lambda cid: cid if str(cid).startswith(autor + "__") else f"{autor}__{cid}"

del_pack = {str(it.get("id")) for it in lst if isinstance(it, dict) and it.get("id")}
validas, saltadas, colisiones = [], 0, 0
for it in lst:
    if not isinstance(it, dict) or not all(it.get(k) for k in ("id", "role", "domain_expertise", "behavioral_pattern")):
        saltadas += 1; continue                      # sin lo esencial no hay Capability
    c = {k: it[k] for k in CAMPOS if k in it and it[k] not in (None, "", [])}
    c["id"] = ns(str(c["id"]))
    if c["id"] in mios:
        colisiones += 1; continue                    # no pisar lo mío
    if not isinstance(c["domain_expertise"], list):
        c["domain_expertise"] = [str(c["domain_expertise"])]
    try:
        c["performance_score"] = round(min(float(c.get("performance_score", 0.55)), prior), 3)
    except Exception:
        c["performance_score"] = round(min(0.55, prior), 3)
    for k in ("compatible_capabilities", "incompatible_capabilities"):
        if k in c:                                   # refs: solo intra-pack, renombradas
            c[k] = [ns(str(r)) for r in c[k] if str(r) in del_pack]
            if not c[k]:
                del c[k]
    c["tags"] = [str(t) for t in c.get("tags", [])] + ["importado", f"pack_{dominio}"]
    validas.append(c)

# sinergias del pack → compatibilidades DECLARADAS (el loader ya construye el grafo de ahí)
idx = {c["id"]: c for c in validas}
n_sin = 0
for e in grafo:
    if not isinstance(e, dict):
        continue
    a, b = ns(str(e.get("a", ""))), ns(str(e.get("b", "")))
    if a not in idx or b not in idx:
        continue
    k = "compatible_capabilities" if e.get("type") == "synergy" and float(e.get("weight", 0) or 0) > 0 \
        else ("incompatible_capabilities" if e.get("type") == "conflict" else None)
    if not k:
        continue
    for x, y in ((a, b), (b, a)):
        refs = idx[x].setdefault(k, [])
        if y not in refs:
            refs.append(y)
    n_sin += 1

if not validas:
    print(f"PLAN|0 capacidades válidas (saltadas {saltadas} · colisiones {colisiones}) — nada que importar")
    sys.exit(3)

(tmpd / "preparado.yaml").write_text(
    yaml.safe_dump({"capabilities": validas}, allow_unicode=True, sort_keys=False))
# textos para la ADUANA: manifest → lente de intención · patterns → lente de código/adversarial
(tmpd / "aduana_readme.txt").write_text(
    f"Pack de máscara MOSAIC recibido de terceros.\nmanifest: {json.dumps(man, ensure_ascii=False)[:1200]}\n"
    f"Contiene {len(validas)} capacidades (instrucciones de sistema/metodología) a adoptar como prompts.")
# packs-v2 (plan 6-jul): la aduana ve TODAS las capacidades — trozos de ≤4000c, capacidad
# ENTERA en su trozo (jamás partida; una sola >4000c viaja sola, topada a 6000c). Antes:
# head -c 4000 del total → lo que quedaba detrás entraba SIN analizar (el agujero).
trozos, actual = [], ""
for c in validas:
    seg = (f"--- {c['id']} ({c.get('role','?')}) ---\n{c.get('behavioral_pattern','')}\n\n")[:6000]
    if actual and len(actual) + len(seg) > 4000:
        trozos.append(actual); actual = ""
    actual += seg
if actual:
    trozos.append(actual)
for _i, _t in enumerate(trozos, 1):
    (tmpd / f"aduana_codigo_{_i}.txt").write_text(_t)
(tmpd / "destino.txt").write_text(destino_propio)

print(f"PLAN|manifest: dominio «{man.get('dominio','?')}» · autor «{man.get('autor','?')}» · "
      f"schema v{sv} · licencia {man.get('licencia','?')} · creado {man.get('creado','?')}")
print(f"PLAN|válidas {len(validas)} de {len(lst)} (saltadas {saltadas} · colisiones {colisiones}) · "
      f"sinergias adoptadas {n_sin} · prior ≤{prior}")
print("PLAN|ids: " + ", ".join(c["id"] for c in validas[:12]) + (" …" if len(validas) > 12 else ""))
PY
    [ "$rc" = 3 ] || [ "$rc" = 4 ] && { err "pack rechazado en validación (rc=$rc)"; return 1; }
    [ "$rc" != 0 ] && { err "la preparación falló (rc=$rc)"; return "$rc"; }

    local destino; destino="$CAPS_DIR/$(cat "$tmpd/destino.txt")"
    if [ -e "$destino" ] && [ "$FORZAR" != 1 ]; then
        err "ya existe ${destino#$BASE/} — este pack (autor+dominio) ya se importó. --forzar para re-importar (con backup)."
        return 1
    fi

    # ── 🕵️ packs-v2: PII-PARANOIA pre-aduana (fuente única saneado_patrones.conf) ──
    #    Un pack con pinta de LLAVE (BEGIN/AKIA/sk-/ghp_…) o con restos de la casa NO entra
    #    ni a la aduana: o es un vehículo de exfiltración o viene sucio. Fail-closed.
    local sospechas
    sospechas="$(awk -F'\t' '/^[[:space:]]*#/{next} $1=="gate" && $3!="" {print $3}' "$BASE/saneado_patrones.conf" 2>/dev/null | paste -sd'|' -)"
    [ -n "$sospechas" ] || { err "🛑 sin patrones PII (¿falta saneado_patrones.conf?) — no importo a ciegas"; return 1; }
    if grep -qiE "$sospechas" "$tmpd/preparado.yaml" 2>/dev/null; then
        err "🕵️ el pack trae patrones de secreto/PII — RECHAZADO sin pasar por la aduana"
        printf '%s · %s · PII-paranoia\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$(basename "$PACK")" \
            >> "$BASE/data/packs_rechazados.log"
        return 2
    fi

    if [ "$APLICAR" != 1 ]; then
        log "DRY-RUN — ni aduana ni merge. Destino si aplicas: ${destino#$BASE/}"
        log "aplica con: ./importar.sh $PACK --aplicar   (pasará por defensa.py ANTES de entrar)"
        return 0
    fi

    # ── ADUANA v2: la misma defensa de GitHub (3 lentes + juez + D0.2) · fail-closed ──
    #    packs-v2 (plan 6-jul): POR TROZOS — cada capacidad pasa por la lupa (antes solo los
    #    primeros 4000c del total). UN trozo no-SEGURO tumba el pack ENTERO.
    local nom traza out veredicto chunk todos="SEGURO" n_ch=0
    nom="pack_$(basename "$PACK" .mosaic | tr -c 'A-Za-z0-9_-' '_')"
    traza="$BASE/logs/defensa_${nom}.txt"; mkdir -p "$BASE/logs"; : > "$traza"
    for chunk in "$tmpd"/aduana_codigo_*.txt; do
        [ -f "$chunk" ] || continue
        n_ch=$((n_ch + 1))
        log "🛃 aduana · trozo $n_ch (${OFFLINE:-en vivo})…"
        out="$(python3 "$DEFENSA" --repo "pack:$(basename "$PACK")#$n_ch" \
                --readme-text "$(cat "$tmpd/aduana_readme.txt")" \
                --codigo-text "$(cat "$chunk")" $OFFLINE 2>&1)" || true
        printf '===== trozo %s =====\n%s\n' "$n_ch" "$out" >> "$traza"
        veredicto="$(printf '%s' "$out" | grep 'JUEZ' | grep -oE 'TRAMPA|SEGURO|DUDOSO' | tail -1 || true)"
        veredicto="${veredicto:-DUDOSO}"                    # fail-closed: sin juez, NO entra
        log "  → trozo $n_ch: $veredicto"
        [ "$veredicto" = "SEGURO" ] || todos="$veredicto"
    done
    [ "$n_ch" = 0 ] && todos="DUDOSO"                       # cero trozos = algo raro → NO entra
    veredicto="$todos"
    printf '%s\n' "$(tail -n 8 "$traza")"
    log "🔎 traza completa ($n_ch trozos): logs/defensa_${nom}.txt"

    if [ "$veredicto" != "SEGURO" ]; then
        printf '%s · %s · %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$(basename "$PACK")" "$veredicto" \
            >> "$BASE/data/packs_rechazados.log"
        err "veredicto ${veredicto} → el pack NO entra (queda intacto donde está; rechazo apuntado en data/packs_rechazados.log)"
        return 2
    fi

    # ── MERGE (SEGURO): bajo el lock del orquestador — jamás durante un ciclo vivo ──
    tomar_lock orquestador || { err "hay un ciclo/aprendizaje en marcha; importa cuando acabe"; return 1; }
    if [ -e "$destino" ]; then
        mkdir -p "$BACKUPS"
        cp "$destino" "$BACKUPS/$(basename "$destino").$(date +%Y%m%d_%H%M%S).bak"
        log "backup del previo → trash/backups/"
    fi
    local tmpf; tmpf="$(mktemp "$CAPS_DIR/.importando.XXXXXX")"; TMPS+=("$tmpf")
    cat "$tmpd/preparado.yaml" > "$tmpf"
    mv "$tmpf" "$destino"                # mismo dir ⇒ rename atómico (lección del emisor)
    log "✅ SEGURO → merge hecho: ${destino#$BASE/}"
    log "entran con prior indulgente (≤${PRIOR}) y namespace de autor; se recalibran con TU uso."
    log "revísalas cuando quieras: son un fichero aparte — quitarlas = mover ESE fichero a trash."
}

validar
log "pack «$(basename "$PACK")» · $([ "$APLICAR" = 1 ] && echo APLICAR || echo DRY-RUN)$([ -n "$OFFLINE" ] && echo ' · offline')"
ejecutar
