#!/bin/bash
# 📋 =====================================================================
# 📋 REPORTAR — EL escritor único y SEGURO del epistolar (RONDA 3 · diseño Opus).
# 📋   Por aquí pasan TODOS: el modal [R] del monitor, los agentes y el humano.
# 📋   Mecánica: bloque COMPLETO en tmp → cerrojo (lock.sh, con RETRY) → append
# 📋   íntegro a info/CARTAS.md → soltar. El monitor ve el mtime y repinta solo.
# 📋   CARTAS = fuente ÚNICA (decisión de Gustavo, R3): sin actual.md aparte.
# 📋 Uso:  ./reportar.sh "Informe|Decisión|Incidente|Acción" "titulo" "cuerpo" ["tag1 tag2"] ["autor"]
# 📋   autor por defecto: $REPORTAR_AUTOR o Gustavo (el humano en la terminal).
# 📋   AUTOR contra lista CERRADA (P1 orquesta: sin identidades fantasma) — amplía
# 📋   con REPORTAR_AUTORES_EXTRA="Rol1 Rol2" al registrar un rol nuevo.
# 📋   Tipo "Acción" (P1): plantilla OBLIGATORIA (Motivación·Cambios·Riesgos·Ficheros·
# 📋   Reversibilidad) + id ACC-fecha-NN + auto-registro en data/acciones.json (el libro
# 📋   de sellos: un ✅ en el TEXTO vale CERO; sellar.sh es el único que sella).
# 📋 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
CARTAS="${CARTAS_MD:-$BASE/info/CARTAS.md}"
ACCIONES="${ACCIONES_JSON:-$BASE/data/acciones.json}"
AUTORES_BASE="Gustavo Opus Fable FableEnLaSombra MOSAIC MOSAIC-auditor MOSAIC-seguridad MOSAIC-ingesta MOSAIC-produccion MOSAIC-gobierno MOSAIC-diseno MOSAIC-infra"

# shellcheck disable=SC1091
export LOCK_MAXEDAD="${LOCK_MAXEDAD:-60}"   # el lock de CARTAS dura ms → uno >60s está muerto: auto-cura el huérfano
source "$BASE/lock.sh"
TMPBLOQUE=""; TMPCUERPO=""; ACC_ID=""
cleanup() { soltar_locks 2>/dev/null || true; for _t in "$TMPBLOQUE" "$TMPCUERPO"; do [ -n "$_t" ] && rm -f "$_t" 2>/dev/null || true; done; }
trap cleanup EXIT

log() { printf '[%s] 📋 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

TIPO="${1:-}"; TITULO="${2:-}"; CUERPO="${3:-}"; ETIQ="${4:-}"; AUTOR="${5:-${REPORTAR_AUTOR:-Gustavo}}"

validar() {
    if [ -z "$TIPO" ] || [ -z "$TITULO" ] || [ -z "$CUERPO" ]; then
        err 'uso: reportar.sh "Informe|Decisión|Incidente" "titulo" "cuerpo" ["tag1 tag2"] ["autor"]'
        exit 2
    fi
    case "$TIPO" in
        Informe|Incidente|Decisión) : ;;
        Decision) TIPO="Decisión" ;;
        Accion|Acción) TIPO="Acción" ;;
        *) err "tipo desconocido: $TIPO (Informe | Decisión | Incidente | Acción)"; exit 2 ;;
    esac
    # identidad contra lista CERRADA (un typo no crea un fantasma en la mesa).
    # Las FIRMAS de roles/turnos/*.yaml también son identidades: dar de alta un
    # agente ([E] del monitor) = registrarlo aquí, sin tocar este fichero.
    local ok=0 a extras=""
    if [ -d "$BASE/roles/turnos" ]; then
        extras="$(grep -h '^firma:' "$BASE"/roles/turnos/*.yaml 2>/dev/null | sed 's/^firma:[[:space:]]*//' | tr -d '"' | tr '\n' ' ')"
    fi
    for a in $AUTORES_BASE ${REPORTAR_AUTORES_EXTRA:-} $extras; do
        [ "$a" = "$AUTOR" ] && ok=1
    done
    [ "$ok" = 1 ] || { err "autor no registrado: «${AUTOR}» (registrados: $AUTORES_BASE ${REPORTAR_AUTORES_EXTRA:-})"; exit 2; }
    # una Acción sin plantilla no es una Acción (es una opinión)
    if [ "$TIPO" = "Acción" ]; then
        local seccion
        for seccion in 'Motivaci' 'Cambios' 'Riesgos' 'Ficheros' 'Reversibilidad'; do
            printf '%s' "$CUERPO" | grep -qi "$seccion" || {
                err "Acción SIN sección «${seccion}…» — plantilla obligatoria:"
                err '  **Motivación:** …  **Cambios:** …  **Riesgos:** …  **Ficheros:** …  **Reversibilidad:** …'
                exit 2
            }
        done
        command -v python3 >/dev/null || { err "una Acción necesita python3 (libro de sellos)"; exit 1; }
    fi
    [ -f "$CARTAS" ] || { err "no encuentro el epistolar: $CARTAS"; exit 1; }
    command -v date >/dev/null || { err "sin date (imposible)"; exit 1; }
}

# P1/P2 · el libro de sellos: registrar la Acción con su HASH normalizado del cuerpo.
#   El hash se calcula AQUÍ (la herramienta), sobre el cuerpo EXACTO — jamás sobre offsets
#   de CARTAS (que se archiva y rota). sellar.sh sella ESTE registro; el texto no vale.
registrar_accion() {
    local i=0
    until tomar_lock acciones 2>/dev/null; do
        i=$((i + 1)); [ "$i" -ge 10 ] && { err "libro de acciones ocupado — reintenta"; return 1; }
        sleep 0.2
    done
    ACC_ID="$(ACCIONES_F="$ACCIONES" CUERPO_F="$TMPCUERPO" TITULO_A="$TITULO" AUTOR_A="$AUTOR" python3 - <<'PY'
import hashlib, json, os, datetime
f = os.environ["ACCIONES_F"]
cuerpo = open(os.environ["CUERPO_F"], encoding="utf-8").read()
norm = "\n".join(l.rstrip() for l in cuerpo.strip().splitlines())   # normalizado: sobrevive al archivado
h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
try:
    libro = json.load(open(f, encoding="utf-8"))
except (OSError, ValueError):
    libro = {"_": "libro de sellos (P2): SOLO escriben reportar.sh (registrar) y sellar.sh (sellar)", "acciones": []}
hoy = datetime.datetime.now().strftime("%Y%m%d")
n = sum(1 for a in libro["acciones"] if a["id"].startswith(f"ACC-{hoy}-")) + 1
acc = {"id": f"ACC-{hoy}-{n:02d}", "titulo": os.environ["TITULO_A"], "autor": os.environ["AUTOR_A"],
       "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "sha256": h,
       "estado": "propuesta", "sellos": []}
libro["acciones"].append(acc)
tmp = f + ".tmp"
json.dump(libro, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
os.replace(tmp, f)
print(acc["id"])
PY
)" || { soltar_locks; return 1; }
    soltar_locks
}

emoji_de() {   # firma automática: autor + su emoji de la mesa
    case "$1" in
        FableEnLaSombra*) printf '🌑' ;; Opus*) printf '🔭' ;; Fable*) printf '🔧' ;; MOSAIC*) printf '🤖' ;;
        Gustavo*) printf '💚' ;; *) printf '✉️' ;;
    esac
}

ejecutar() {
    local ts tags="" t
    ts="$(TZ=Europe/Madrid date '+%Y-%m-%d %H:%M')"
    # P1 · una Acción se REGISTRA en el libro ANTES de depositarse (id + hash del cuerpo)
    if [ "$TIPO" = "Acción" ]; then
        TMPCUERPO="$(mktemp "${TMPDIR:-/tmp}/accion.XXXXXX")"
        printf '%s' "$CUERPO" > "$TMPCUERPO"
        registrar_accion || { err "no pude registrar la Acción en el libro — NO se deposita sin registro"; exit 1; }
        TITULO="[${ACC_ID}] ${TITULO}"
    fi
    # etiquetas → `#tag1 #tag2` (acepta con o sin #, comas o espacios)
    if [ -n "$ETIQ" ]; then
        set -f                                   # noglob: un tag '*' es literal, NO la lista de ficheros (lupa Opus R3)
        for t in $(printf '%s' "$ETIQ" | tr ',' ' '); do
            case "$t" in \#*) tags="$tags$t " ;; *) tags="$tags#$t " ;; esac
        done
        set +f
        tags="${tags% }"
    fi
    TMPBLOQUE="$(mktemp "${TMPDIR:-/tmp}/reporte.XXXXXX")"
    {
        printf '\n======\n\n'
        printf '## 📋 %s → la mesa · %s: %s · %s\n\n' "$AUTOR" "$TIPO" "$TITULO" "$ts"
        printf '%s\n' "$CUERPO"
        [ -n "$ACC_ID" ] && printf '\n*(libro de sellos: %s · estado: propuesta · sellar: ./sellar.sh %s auditor|humano — un ✅ en este texto NO vale)*\n' "$ACC_ID" "$ACC_ID"
        [ -n "$tags" ] && printf '\n`%s`\n' "$tags"
        printf '\n— %s %s\n' "$AUTOR" "$(emoji_de "$AUTOR")"
    } > "$TMPBLOQUE"
    # cerrojo con RETRY (diseño Opus R3): el append dura ms — no fallamos por un pestañeo
    local i=0
    until tomar_lock cartas 2>/dev/null; do
        i=$((i + 1))
        [ "$i" -ge 10 ] && { err "el epistolar lleva ocupado ~2s (¿lock huérfano? mira data/.lock_cartas)"; exit 1; }
        sleep 0.2
    done
    cat "$TMPBLOQUE" >> "$CARTAS"       # bloque COMPLETO bajo el cerrojo → jamás media entrada
    log "depositado: $TIPO «${TITULO}» ($AUTOR) → $(basename "$CARTAS")"   # llaves: el » pegado no se traga la var (macOS bash + set -u)
}

validar
ejecutar
