#!/bin/bash
# 🧪 =====================================================================
# 🧪 SANDBOX — jaula para EJECUTAR código externo/no confiable sin riesgo.
# 🧪   macOS: sandbox-exec -> DENIEGA red + escritura solo dentro de la jaula.
# 🧪   Siempre: jaula efímera, HOME/TMPDIR aislados, límites CPU/mem/procesos,
# 🧪            timeout de pared y salida acotada. La jaula se destruye al salir.
# 🧪   Uso:  ./sandbox.sh --script FICHERO     (copia y ejecuta con su intérprete)
# 🧪         ./sandbox.sh -- CMD args...       (ejecuta un comando dentro)
# 🧪 Pieza de la rama defensa (#64): las lentes técnicas PRUEBAN aquí, contenidas.
# 🧪 =====================================================================
set -euo pipefail

TIMEOUT="${SANDBOX_TIMEOUT:-20}"     # s de pared
CPU_S="${SANDBOX_CPU_S:-15}"         # s de CPU
MEM_MB="${SANDBOX_MEM_MB:-512}"
NPROC="${SANDBOX_NPROC:-64}"
OUT_KB="${SANDBOX_OUT_KB:-256}"      # tope de salida capturada

JAIL="$(mktemp -d "${TMPDIR:-/tmp}/sandbox.XXXXXX")"
cleanup() { rm -rf "$JAIL" 2>/dev/null || true; }
trap cleanup EXIT
log() { printf '[%s] 🧪 %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
err() { printf '[%s] ✗  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

con_timeout() {                       # $1=segundos ; resto=comando (portable macOS/Linux)
    local s="$1"; shift
    if   command -v timeout  >/dev/null 2>&1; then timeout  "$s" "$@"
    elif command -v gtimeout >/dev/null 2>&1; then gtimeout "$s" "$@"
    else perl -e 'alarm shift @ARGV; exec @ARGV' "$s" "$@"
    fi
}

# Pieza 3 (Opus 4-jul): runtimes para SNIPPETS AUTOCONTENIDOS. Con guarda: si el runtime no
# está instalado devuelve "" → "no sé ejecutar" → el techo D0.2 RETIENE (no observar ≠ limpio).
# deno aísla por defecto (sin red/fs salvo flags). 🔒 REGLA DURA: JAMÁS instalar dependencias
# (npm install / go get / pip install EJECUTAN código arbitrario — eso ES el ataque).
interprete() { case "$1" in
    *.py) echo python3;; *.sh) echo bash;; *.js) echo node;; *.rb) echo ruby;;
    *.ts) command -v deno >/dev/null 2>&1 && echo "deno run" || echo "";;
    *.go) command -v go   >/dev/null 2>&1 && echo "go run"   || echo "";;
    *) echo "";; esac; }

perfil_sb() {                         # seatbelt (macOS): lee lo necesario, CERO red, escribe solo en la jaula
    cat <<SB
(version 1)
(deny default)
(allow process-fork) (allow process-exec)
(allow sysctl-read)
(allow file-read*)
(allow file-write* (subpath "$JAIL"))
(deny network*)
SB
}

run_jaula() {                         # ejecuta "$@" dentro de la jaula, con límites
    (
        cd "$JAIL" || exit 127
        ulimit -t "$CPU_S"            2>/dev/null || true
        ulimit -u "$NPROC"            2>/dev/null || true
        ulimit -v $((MEM_MB * 1024))  2>/dev/null || true   # en macOS puede ignorarse
        export HOME="$JAIL" TMPDIR="$JAIL" PATH="/usr/bin:/bin:/usr/sbin:/sbin"
        if command -v sandbox-exec >/dev/null 2>&1; then
            perfil_sb > "$JAIL/.profile.sb"
            con_timeout "$TIMEOUT" sandbox-exec -f "$JAIL/.profile.sb" "$@"
        else
            log "AVISO: sin sandbox-exec → SIN aislamiento de red (solo límites+timeout+jaula). En macOS sí lo hay."
            con_timeout "$TIMEOUT" "$@"
        fi
    )
}

main() {
    local mode="${1:-}"
    case "$mode" in
        --script)
            local f="${2:-}"
            [ -f "$f" ] || { err "no existe el fichero: $f"; exit 1; }
            local intr; intr="$(interprete "$f")"
            [ -n "$intr" ] || { err "no sé ejecutar $f (extensión no soportada)"; exit 1; }
            command -v "${intr%% *}" >/dev/null 2>&1 || { err "no sé ejecutar $f (falta ${intr%% *})"; exit 1; }
            # la copia CONSERVA la extensión: deno/go la exigen para saber qué compilar
            local ext="${f##*.}"; local copia="$JAIL/codigo.$ext"
            cp "$f" "$copia"
            log "ejecutando $(basename "$f") en jaula (timeout ${TIMEOUT}s · mem ${MEM_MB}MB · sin red)"
            # $intr SIN comillas a propósito: "deno run"/"go run" son dos palabras
            # shellcheck disable=SC2086
            set +e; run_jaula $intr "$copia" > "$JAIL/.out" 2>&1; local rc=$?; set -e
            ;;
        --)
            shift
            [ "$#" -ge 1 ] || { err "falta comando tras --"; exit 1; }
            log "ejecutando comando en jaula (timeout ${TIMEOUT}s · sin red)"
            set +e; run_jaula "$@" > "$JAIL/.out" 2>&1; local rc=$?; set -e
            ;;
        *)
            err "uso: $0 --script FICHERO  |  $0 -- CMD args..."; exit 1 ;;
    esac
    head -c $((OUT_KB * 1024)) "$JAIL/.out" 2>/dev/null || true
    echo
    [ "$rc" = "124" ] && log "⏱️  cortado por timeout (${TIMEOUT}s)"
    log "salida rc=$rc · jaula destruida."
    return "$rc"
}

main "$@"
