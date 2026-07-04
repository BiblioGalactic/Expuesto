#!/bin/bash
# 🪑 =====================================================================
# 🪑 AUTODIAGNOSIS — el TURNO de MOSAIC en la mesa (v1 · diseño Opus 17:24/17:38).
# 🪑   MOSAIC se observa a sí mismo y OPINA — pero con la mano quieta:
# 🪑   PROPONE-texto, jamás aplica. SOLO dos rutas (permiso acotado):
# 🪑     1) leer/componer  → mosaic.sh (la máscara sobre un modelo)
# 🪑     2) escribir UN reporte → reportar.sh (autor=MOSAIC, append-only, con cerrojo)
# 🪑   CERO acceso a: código, comandos, configs, borrado, red. Su turno es PALABRA, no manos.
# 🪑   Input COMPACTO (debrief + incidencias/subsistemas + flejes) → cabe en 4096 (medianos).
# 🪑   Rotación de modelo entre corridas (bake-off en la carta). Kill-switch: AUTODIAG=0.
# 🪑 Uso:  ./autodiagnosis.sh            (su turno: analiza y postea a la mesa)
# 🪑       ./autodiagnosis.sh --dry      (enseña el prompt y el modelo; NO postea)
# 🪑 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
MOSAIC_SH="$BASE/mosaic.sh"                 # RUTA 1 (única de lectura/composición)
REPORTAR="$BASE/reportar.sh"                # RUTA 2 (única de escritura: un reporte)
SERVIDORES="$BASE/servidores.conf"
DEBRIEF_MD="$BASE/data/debrief_ultimo.md"
ESTADO="$BASE/data/estado_sistema.json"
PENDIENTES="$BASE/PENDIENTES.md"
CURSOR="$BASE/data/.autodiag_modelo.cursor"
MAX_PROMPT_C="${AUTODIAG_MAX_C:-6000}"      # tope duro de caracteres (~1500 tokens): NUNCA petar 4096
LLAMA_LAUNCH="${LLAMA_LAUNCH:-$HOME/cluster/lanzar_cluster.sh}"  # el lanzador IDEMPOTENTE (sube SOLO lo caído)
ESPERA="${ESPERA:-120}"                     # tope de espera tras un `subir` — jamás colgarse (Opus 18:15)
HOSTIP="${AUTODIAG_HOST:-127.0.0.1}"
DRY=0; [ "${1:-}" = "--dry" ] && DRY=1

TMPS=()
cleanup() { for t in "${TMPS[@]:-}"; do [ -n "${t:-}" ] && rm -f "$t" 2>/dev/null || true; done; }
trap cleanup EXIT
log() { printf '[%s] 🪑 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    [ "${AUTODIAG:-1}" = "1" ] || { log "AUTODIAG=0 → turno de MOSAIC desactivado"; exit 0; }
    command -v python3 >/dev/null || { err "falta python3"; exit 1; }
    command -v curl >/dev/null    || { err "falta curl (el pre-vuelo sonda con él)"; exit 1; }
    [ -x "$MOSAIC_SH" ] || { err "no encuentro mosaic.sh ejecutable (la única ruta de composición)"; exit 1; }
    [ -f "$REPORTAR" ]  || { err "no encuentro reportar.sh (la única ruta de escritura)"; exit 1; }
    [ -f "$DEBRIEF_MD" ] || { err "sin debrief_ultimo.md — corre ./debrief.sh o un ciclo primero"; exit 1; }
}

# rotación de modelo (como el generador de temas): un cursor sobre la lista de ANALISTAS.
# Default = principal(8092) + razonamiento(8094); override con AUTODIAG_PUERTOS. Nombre desde
# servidores.conf (⚔️ el 24B jamás; el juez pequeño no analiza). Devuelve "puerto|nombre".
nombre_de() {
    local nom
    nom="$(awk -F'|' -v pt="$1" '$1=="macbook" && $2==pt {print $5}' "$SERVIDORES" \
          | sed -E 's#.*/##; s#\*##g; s#\.gguf##' | head -1)"
    echo "${nom:-modelo-$1}"
}

elegir_modelo() {
    local puertos idx p
    puertos=(${AUTODIAG_PUERTOS:-8092 8094})
    idx=0; [ -f "$CURSOR" ] && idx="$(cat "$CURSOR" 2>/dev/null || echo 0)"
    [[ "$idx" =~ ^[0-9]+$ ]] || idx=0
    p="${puertos[$(( idx % ${#puertos[@]} ))]}"
    echo $(( (idx + 1) % ${#puertos[@]} )) > "$CURSOR" 2>/dev/null || true
    echo "${p}|$(nombre_de "$p")"
}

vivo() { curl -s -m 3 "$1/models" >/dev/null 2>&1; }    # ¿ese endpoint infiere? (pieza de ciclo.sh)

# 🛫 PRE-VUELO (Opus 18:15): proba los candidatos de la rotación (el elegido PRIMERO) → si
#    NINGUNO responde, UN `subir` del lanzador (IDEMPOTENTE: comprueba roster+gguf, levanta
#    SOLO lo caído y espera a que infiera — NO duplicamos su lógica, delegamos) → re-proba
#    con tope ESPERA → echo del puerto VIVO, o return 1 (el fail-safe de arriba no postea).
#    Todo lo informativo va a stderr: el stdout es SOLO el puerto (va por $(...)).
asegurar_analista() {
    local pref="$1" cands=() p t
    cands=("$pref")
    for p in ${AUTODIAG_PUERTOS:-8092 8094}; do [ "$p" != "$pref" ] && cands+=("$p"); done
    for p in "${cands[@]}"; do
        vivo "http://${HOSTIP}:${p}/v1" && { echo "$p"; return 0; }
    done
    [ -f "$BASE/data/pausa.flag" ] && err "aviso: data/pausa.flag presente (vigía) — la flota puede estar ocupada"
    if [ ! -x "$LLAMA_LAUNCH" ]; then
        err "ningún analista arriba y no encuentro el lanzador: $LLAMA_LAUNCH"
        return 1
    fi
    log "ningún analista arriba → «${LLAMA_LAUNCH} subir» (idempotente; tope ${ESPERA}s)…" >&2
    "$LLAMA_LAUNCH" subir >&2 2>&1 || err "el subir devolvió error — re-pruebo igual (quizá subió a medias)"
    t=0
    until [ "$t" -ge "$ESPERA" ]; do
        for p in "${cands[@]}"; do
            vivo "http://${HOSTIP}:${p}/v1" && { echo "$p"; return 0; }
        done
        sleep 3; t=$((t + 3))
    done
    err "ningún analista arriba tras ${ESPERA}s; revisa a mano: $LLAMA_LAUNCH subir"
    return 1
}

# el estado COMPACTO (unos cientos de tokens): debrief + incidencias/subsistemas + flejes abiertos
ensamblar_prompt() {
    local prompt_f; prompt_f="$(mktemp "${TMPDIR:-/tmp}/autodiag.XXXXXX")"; TMPS+=("$prompt_f")
    {
        printf 'Eres MOSAIC, observándote a ti mismo como un compañero más del equipo. Abajo tienes tu\n'
        printf 'ESTADO REAL (panel del último ciclo + incidencias + flejes abiertos). Analízalo y da tu\n'
        printf 'opinión a la mesa: 1) qué va BIEN, 2) qué te PREOCUPA, 3) qué PROPONDRÍAS (concreto y breve).\n'
        printf 'IMPORTANTE: solo PROPONES para que el equipo humano decida y aplique; tú NO ejecutas cambios.\n'
        printf 'Sé honesto y específico; si algo no lo sabes desde este estado, dilo. Máximo ~250 palabras.\n\n'
        printf '===== PANEL DEL ÚLTIMO CICLO =====\n'
        cat "$DEBRIEF_MD" 2>/dev/null
        if [ -f "$ESTADO" ]; then
            printf '\n===== INCIDENCIAS Y SUBSISTEMAS (del estado) =====\n'
            ESTADO_JSON="$ESTADO" python3 - <<'PY' 2>/dev/null || true
import json, os
d = json.load(open(os.environ["ESTADO_JSON"]))
inc = d.get("incidencias", [])
print("incidencias:", "; ".join(i.get("texto","") for i in inc) or "ninguna")
subs = d.get("subsistemas", [])
print("subsistemas:", "; ".join(f"{s.get('id')}={s.get('estado')}" for s in subs))
b = d.get("banco", {})
print(f"banco: {b.get('pendientes')}/{b.get('tope')} · fábrica saltada {b.get('fabrica_saltos_seguidos')}×")
PY
        fi
        if [ -f "$PENDIENTES" ]; then
            printf '\n===== FLEJES ABIERTOS (backlog) =====\n'
            grep -iE '⏳|abierto|pendiente' "$PENDIENTES" 2>/dev/null | head -6 || true
        fi
    } > "$prompt_f"
    # tope DURO de caracteres: recorta si se pasa (nunca petar 4096) — la lección del contexto
    if [ "$(wc -c < "$prompt_f")" -gt "$MAX_PROMPT_C" ]; then
        head -c "$MAX_PROMPT_C" "$prompt_f" > "$prompt_f.cut" && mv "$prompt_f.cut" "$prompt_f"
        printf '\n[…estado recortado a %s c para caber en el modelo…]\n' "$MAX_PROMPT_C" >> "$prompt_f"
    fi
    echo "$prompt_f"
}

ejecutar() {
    local modelo puerto nom prompt_f out_json url respuesta caps ncaps fecha cuerpo puerto_vivo
    modelo="$(elegir_modelo)"; puerto="${modelo%%|*}"; nom="${modelo##*|}"
    prompt_f="$(ensamblar_prompt)"
    log "turno de MOSAIC · modelo: $nom (@$puerto) · prompt $(wc -c < "$prompt_f")c"

    if [ "$DRY" = 1 ]; then
        if vivo "http://${HOSTIP}:${puerto}/v1"; then
            log "pre-vuelo (sonda): analista @${puerto} VIVO"
        else
            log "pre-vuelo (sonda): analista @${puerto} CAÍDO — el turno real haría «subir» y esperaría (tope ${ESPERA}s)"
        fi
        log "DRY-RUN (no postea). El prompt que se compondría:"
        sed 's/^/    /' "$prompt_f"
        return 0
    fi

    # 🛫 PRE-VUELO: usa el candidato VIVO (levantando la flota UNA vez si hace falta), o aborta limpio
    puerto_vivo="$(asegurar_analista "$puerto")" || { err "sin analista no hay turno — no posteo (fail-safe)"; exit 1; }
    if [ "$puerto_vivo" != "$puerto" ]; then
        log "el elegido @${puerto} no respondía → uso el analista vivo @${puerto_vivo}"
        puerto="$puerto_vivo"; nom="$(nombre_de "$puerto")"
    fi
    url="http://${HOSTIP}:${puerto}/v1"

    # RUTA 1 · la máscara sobre el modelo elegido → --out guarda composed+model+output (fuente limpia)
    out_json="$(mktemp "${TMPDIR:-/tmp}/autodiag_out.XXXXXX")"; TMPS+=("$out_json")
    MOSAIC_LLM_BASE_URL="$url" MOSAIC_LLM_MODEL="$nom" \
        bash "$MOSAIC_SH" --out "$out_json" "$(cat "$prompt_f")" >/dev/null 2>&1 || true

    # captura ROBUSTA (errors=replace, la lección): respuesta + receta (composed) del JSON
    read -r respuesta ncaps caps < <(OUT_JSON="$out_json" python3 - <<'PY' 2>/dev/null || echo "|0|"
import json, os
try:
    d = json.load(open(os.environ["OUT_JSON"], encoding="utf-8", errors="replace"))
except Exception:
    d = {}
out = (d.get("output") or "").strip()
comp = d.get("composed") or []
# una línea: respuesta en base64 (para no romper el read con saltos), nº caps, primeras ids
import base64
print(base64.b64encode(out.encode("utf-8","replace")).decode(), len(comp), ",".join(comp[:5]))
PY
)
    respuesta="$(printf '%s' "$respuesta" | base64 -d 2>/dev/null || true)"
    if [ -z "${respuesta// /}" ]; then
        err "MOSAIC no produjo respuesta (¿cluster caído? ¿modelo @$puerto?). No posteo vacío."
        exit 1
    fi

    # el PIE DE TRANSPARENCIA (Opus): con qué modelo y qué máscara lo dijo — que nadie lo confunda con hecho
    fecha="$(date '+%Y-%m-%d %H:%M')"
    cuerpo="$respuesta

---
*auto · sin verificar · modelo: ${nom} (@${puerto}) · máscara: ${ncaps} capacidades$( [ -n "$caps" ] && printf ' (%s…)' "$caps" ) · el equipo revisa antes de aplicar*"

    # RUTA 2 · su turno en la mesa (reportar.sh añade la cabecera y firma '— MOSAIC 🤖')
    MOSAIC_BASE="$BASE" bash "$REPORTAR" "Informe" "Autodiagnóstico $fecha" "$cuerpo" "autodiagnosis auto" "MOSAIC" \
        && log "🪑 MOSAIC ha hablado en la mesa (modelo $nom · $ncaps caps) — léelo en [C]"
}

validar
ejecutar
