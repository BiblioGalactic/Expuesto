#!/bin/bash
# 🎫 =====================================================================
# 🎫 ESCALADO — el CLI humano del libro de ESCALACIONES (plan Opus 13:56:
# 🎫   modelo de mission-control adaptado — json, sin sqlite, sin web).
# 🎫   TODA la lógica vive en herramientas.py (--esc …): una sola fuente de
# 🎫   permisos en el sistema; esto solo enseña bonito y firma como «humano».
# 🎫   La escalera: denegado → ticket abierto → AUTO-DISPATCH por la cadena del
# 🎫   organigrama (lead → manager → N1 → humano). Los agentes resuelven EN SU
# 🎫   TURNO; aquí resuelve la mano de confianza (Gustavo = final de toda cadena).
# 🎫   conceder EJECUTA la tool (resuelto = concedido+ejecutado) · nivel 5 →
# 🎫   esperando_sello (el doble sello es el último peldaño) · TTL → caducado+archivo.
# 🎫 Uso:  ./escalado.sh listar [abierto|escalado|en_revision|resuelto|denegado|esperando_sello]
# 🎫       ./escalado.sh ver      <ESC-id>
# 🎫       ./escalado.sh conceder <ESC-id> ["nota"]
# 🎫       ./escalado.sh denegar  <ESC-id> ["porqué"]
# 🎫       ./escalado.sh escalar  <ESC-id> ["nota"]     (subirlo un peldaño a mano)
# 🎫       ./escalado.sh caducar                        (barrido TTL a mano)
# 🎫   (tickets TCK-… = libro LEGADO tickets_escalado.jsonl: solo canje --ticket)
# 🎫 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
MOTOR="$BASE/herramientas.py"

log() { printf '[%s] 🎫 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

ORDEN="${1:-listar}"; ID="${2:-}"; NOTA="${3:-}"

validar() {
    command -v python3 >/dev/null || { err "falta python3"; exit 1; }
    [ -f "$MOTOR" ] || { err "no encuentro el motor: $MOTOR"; exit 1; }
    case "$ORDEN" in
        listar|caducar) : ;;
        ver|conceder|denegar|escalar)
            [ -n "$ID" ] || { err "uso: escalado.sh $ORDEN <ESC-id> [nota]"; exit 2; }
            case "$ID" in
                ESC-*) : ;;
                TCK-*) err "TCK-… es el libro LEGADO (canje con --ticket en pedir_tool.sh); este CLI mueve ESC-…"; exit 2 ;;
                *) err "id raro: $ID (espero ESC-YYYYMMDD-NN)"; exit 2 ;;
            esac ;;
        *) err "orden: listar | ver | conceder | denegar | escalar | caducar"; exit 2 ;;
    esac
}

ejecutar() {
    # ⚠️ lección de la casa (bug 13:47 y OTRA VEZ hoy): `python3 - <<PY` OCUPA stdin —
    #    jamás pipe hacia un heredoc. La salida del motor viaja por ENV (SALIDA_J).
    local rc=0 salida
    case "$ORDEN" in
        listar)
            salida="$(MOSAIC_BASE="$BASE" python3 "$MOTOR" --esc listar ${ID:+--estado "$ID"})" || rc=$?
            SALIDA_J="$salida" python3 - <<'PY'
import json, os
ts = (json.loads(os.environ.get("SALIDA_J") or "{}").get("result")) or []
if not ts:
    print("(sin escalaciones que casen — nadie pide por encima de su rango)")
for t in ts:
    print(f'{t["id"]} · {t.get("prioridad","?"):7} · {t.get("estado","?"):15} · en «{t.get("rango_actual","?")}» · '
          f'{t.get("agente_origen","?")}(niv{t.get("nivel_agente","?")}) pide {t.get("herramienta","?")}'
          f'(niv{t.get("nivel_requerido","?")}) · cadena: {" → ".join(t.get("cadena",[]))}')
PY
            ;;
        ver)
            salida="$(MOSAIC_BASE="$BASE" python3 "$MOTOR" --esc listar)" || rc=$?
            SALIDA_J="$salida" ID_V="$ID" python3 - <<'PY'
import json, os
ts = (json.loads(os.environ.get("SALIDA_J") or "{}").get("result")) or []
t = next((x for x in ts if x.get("id") == os.environ["ID_V"]), None)
print(json.dumps(t, ensure_ascii=False, indent=1) if t
      else f'⚠️  {os.environ["ID_V"]} no está en el libro vivo (¿archivado? mira data/escalaciones_archivo.jsonl)')
PY
            ;;
        caducar)
            salida="$(MOSAIC_BASE="$BASE" python3 "$MOTOR" --esc caducar)" || rc=$?
            SALIDA_J="$salida" python3 - <<'PY'
import json, os
r = (json.loads(os.environ.get("SALIDA_J") or "{}").get("result")) or {}
print(f'barrido hecho · vivos: {r.get("vivos_tras_barrido","?")} · TTL: {r.get("ttl_h","?")}h · '
      'lo caducado duerme en data/escalaciones_archivo.jsonl')
PY
            ;;
        conceder|denegar|escalar)
            set +e
            salida="$(MOSAIC_BASE="$BASE" python3 "$MOTOR" --esc resolver --id "$ID" --como humano \
                        --decision "$ORDEN" --motivo "${NOTA:-$ORDEN por la mano de confianza (${USER:-humano})}")"
            rc=$?
            set -e
            SALIDA_J="$salida" python3 - <<'PY'
import json, os
try:
    d = json.loads(os.environ.get("SALIDA_J") or "")
except Exception:
    print("(salida no-JSON del motor — raro)"); raise SystemExit(0)
if d.get("ok"):
    r = d.get("result") or {}
    est = r.get("estado", "?")
    linea = f'✅ {r.get("id","?")} → {est}'
    if est == "resuelto":
        linea += f' (tool ejecutada: {"ok" if r.get("tool_ok") else "FALLÓ — mira el ticket"})'
    if est == "esperando_sello":
        linea += ' — nivel 5: el DOBLE SELLO (sellar.sh) es el último peldaño'
    if "de" in r:
        linea += f' · {r["de"]} → {r["a"]}'
    print(linea)
else:
    print(f'⛔ {d.get("error","?")}')
PY
            return $rc
            ;;
    esac
    return $rc
}

validar
ejecutar
