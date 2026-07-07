#!/bin/bash
# 🖋️ =====================================================================
# 🖋️ SELLAR — el ÚNICO escritor de sellos del libro de acciones (P2 orquesta).
# 🖋️   Doctrina (Opus 22:21 · espec Fable 23:36): un "✅" en el TEXTO de una carta
# 🖋️   vale CERO — un agente alucinado se auto-aprobaría. Los sellos viven en
# 🖋️   data/acciones.json, los escribe SOLO esta herramienta, invocada por la mano
# 🖋️   de confianza (Gustavo, o la sesión del auditor). El futuro ejecutor (F2)
# 🖋️   verificará: DOBLE sello (auditor+humano) + hash del cuerpo intacto.
# 🖋️   Estados: propuesta → auditada (sello auditor) → LISTA (ambos sellos).
# 🖋️   Rechazar también es sellar: --veto deja el porqué y cierra la Acción.
# 🖋️ Uso:  ./sellar.sh <ACC-id> <auditor|humano> ["veredicto/nota"]
# 🖋️       ./sellar.sh <ACC-id> <auditor|humano> --veto "porqué"
# 🖋️       ./sellar.sh listar [estado]     ·      ./sellar.sh ver <ACC-id>
# 🖋️       ./sellar.sh archivar <ACC-id> ["motivo"]   (higiene 7-jul: propuesta de
# 🖋️         pleno-de-prueba → trash/propuestas_archivadas/<id>.json — JAMÁS se borra,
# 🖋️         sale del libro vivo con su motivo y su fecha; solo estados sin sellos)
# 🖋️ =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
ACCIONES="${ACCIONES_JSON:-$BASE/data/acciones.json}"

# shellcheck disable=SC1091
export LOCK_MAXEDAD="${LOCK_MAXEDAD:-60}"
source "$BASE/lock.sh"
cleanup() { soltar_locks 2>/dev/null || true; }
trap cleanup EXIT

log() { printf '[%s] 🖋️  %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

ORDEN="${1:-}"; ROL="${2:-}"; NOTA="${3:-}"; VETO=0
[ "${3:-}" = "--veto" ] && { VETO=1; NOTA="${4:-sin motivo}"; }

validar() {
    command -v python3 >/dev/null || { err "falta python3"; exit 1; }
    [ -n "$ORDEN" ] || { err 'uso: sellar.sh <ACC-id|listar|ver|archivar> …'; exit 2; }
    if [ "$ORDEN" = "archivar" ]; then
        [ -n "$ROL" ] || { err "uso: sellar.sh archivar <ACC-id> [motivo]"; exit 2; }
        [ -f "$ACCIONES" ] || { err "sin libro todavía: $ACCIONES"; exit 1; }
        return 0
    fi
    if [ "$ORDEN" != "listar" ] && [ "$ORDEN" != "ver" ]; then
        [ -f "$ACCIONES" ] || { err "sin libro todavía: $ACCIONES (nace con la 1ª Acción)"; exit 1; }
        case "$ROL" in auditor|humano) : ;; *) err "rol de sello: auditor | humano (fue: «${ROL}»)"; exit 2 ;; esac
    fi
}

ejecutar() {
    if [ "$ORDEN" = "listar" ] || [ "$ORDEN" = "ver" ]; then
        [ -f "$ACCIONES" ] || { log "el libro está vacío (ninguna Acción registrada aún)"; return 0; }
        ACCIONES_F="$ACCIONES" MODO="$ORDEN" FILTRO="${ROL:-}" python3 - <<'PY'
import json, os
libro = json.load(open(os.environ["ACCIONES_F"], encoding="utf-8"))
modo, filtro = os.environ["MODO"], os.environ.get("FILTRO", "")
for a in libro.get("acciones", []):
    if modo == "ver" and a["id"] != filtro:
        continue
    if modo == "listar" and filtro and a["estado"] != filtro:
        continue
    sellos = ",".join(s["rol"] for s in a.get("sellos", [])) or "—"
    print(f'{a["id"]} · {a["estado"]:9} · sellos[{sellos}] · {a["autor"]} · {a["titulo"][:56]}')
    if modo == "ver":
        print(json.dumps(a, ensure_ascii=False, indent=2))
PY
        return 0
    fi

    local i=0
    until tomar_lock acciones 2>/dev/null; do
        i=$((i + 1)); [ "$i" -ge 10 ] && { err "libro ocupado — reintenta"; exit 1; }
        sleep 0.2
    done
    local rc=0

    # 🗄️ ARCHIVAR (higiene del libro, auditoría 7-jul): la propuesta huérfana sale del libro
    #    VIVO y duerme ENTERA en trash/propuestas_archivadas/<id>.json — jamás se borra.
    #    Guardia: solo estados SIN sellos (propuesta) — lo sellado/vetado es historia y se queda.
    if [ "$ORDEN" = "archivar" ]; then
        mkdir -p "$BASE/trash/propuestas_archivadas"
        cp "$ACCIONES" "$BASE/trash/backups/acciones.json.$(date +%Y%m%d_%H%M%S).pre-archivo.bak" 2>/dev/null || true
        ACCIONES_F="$ACCIONES" ACC_A="$ROL" MOTIVO_A="${NOTA:-pleno de prueba}" \
            DEST_A="$BASE/trash/propuestas_archivadas" QUIEN="${USER:-humano}" python3 - <<'PY' || rc=$?
import datetime, json, os, sys
f = os.environ["ACCIONES_F"]
libro = json.load(open(f, encoding="utf-8"))
acc_id = os.environ["ACC_A"]
acc = next((a for a in libro.get("acciones", []) if a["id"] == acc_id), None)
if acc is None:
    print(f"⚠️  no existe {acc_id} en el libro", file=sys.stderr); sys.exit(1)
if acc.get("sellos") or acc.get("estado") not in ("propuesta",):
    print(f"⚠️  {acc_id} está «{acc.get('estado')}» con {len(acc.get('sellos', []))} sello(s) — "
          "lo sellado/vetado es HISTORIA y se queda en el libro", file=sys.stderr); sys.exit(1)
acc["archivado"] = {"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "por": os.environ["QUIEN"], "motivo": os.environ["MOTIVO_A"]}
dest = os.path.join(os.environ["DEST_A"], f"{acc_id}.json")
with open(dest, "w", encoding="utf-8") as fh:
    json.dump(acc, fh, ensure_ascii=False, indent=1)
libro["acciones"] = [a for a in libro["acciones"] if a["id"] != acc_id]
tmp = f + ".tmp"
json.dump(libro, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.replace(tmp, f)
print(f"{acc_id} → archivada en trash/propuestas_archivadas/ ({os.environ['MOTIVO_A']})")
PY
        soltar_locks
        return $rc
    fi
    ACCIONES_F="$ACCIONES" ACC="$ORDEN" ROL_S="$ROL" QUIEN="${USER:-desconocido}" \
        NOTA_S="$NOTA" VETO_S="$VETO" python3 - <<'PY' || rc=$?
import json, os, sys, datetime
f = os.environ["ACCIONES_F"]
libro = json.load(open(f, encoding="utf-8"))
acc_id, rol, veto = os.environ["ACC"], os.environ["ROL_S"], os.environ["VETO_S"] == "1"
acc = next((a for a in libro.get("acciones", []) if a["id"] == acc_id), None)
if acc is None:
    print(f"⚠️  no existe {acc_id} en el libro", file=sys.stderr); sys.exit(1)
if acc["estado"] in ("lista", "vetada", "ejecutada"):
    print(f"⚠️  {acc_id} ya está {acc['estado']} — no se re-sella", file=sys.stderr); sys.exit(1)
if any(s["rol"] == rol for s in acc["sellos"]):
    print(f"⚠️  {acc_id} ya lleva el sello de {rol} — un rol sella UNA vez", file=sys.stderr); sys.exit(1)
sello = {"rol": rol, "quien": os.environ["QUIEN"],
         "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "sha256_sellado": acc["sha256"], "nota": os.environ.get("NOTA_S", "")}
if veto:
    sello["veto"] = True
    acc["estado"] = "vetada"
else:
    if rol == "humano" and not any(s["rol"] == "auditor" for s in acc["sellos"]):
        print(f"⚠️  {acc_id}: el sello HUMANO va DESPUÉS del auditor (la auditoría informa la aprobación) — falta el sello del auditor", file=sys.stderr); sys.exit(1)
    acc["sellos"].append(sello)
    roles = {s["rol"] for s in acc["sellos"]}
    acc["estado"] = "lista" if {"auditor", "humano"} <= roles else "auditada"
if veto:
    acc["sellos"].append(sello)
tmp = f + ".tmp"
json.dump(libro, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.replace(tmp, f)
print(f'{acc_id} → {acc["estado"]} (sello {rol} de {sello["quien"]})')
PY
    soltar_locks
    return $rc
}

validar
ejecutar
