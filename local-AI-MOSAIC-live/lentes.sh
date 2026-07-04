#!/bin/bash
# 👓 =====================================================================
# 👓 LENTES v2.1 — sirve las lentes del blue team BAJO DEMANDA repartidas entre
# 👓 las DOS máquinas (doctrina 3-jul: MacBook 48GB · mini 16GB — usar el hierro real):
# 👓   código    → Dolphin (8B)   : intenta MINI primero (dolphin3 vive allí) → local
# 👓   intención → Mythos (13B)   : intenta MINI si le queda sitio (Mythos3 vive allí) → local
# 👓   (remotas → data/.lentes_env exporta DEFENSA_URL_* y cuarentena.sh lo hereda)
# 👓 La adversarial (Unholy@8091) es del cluster: NO se toca. (El 24B: JAMÁS — orden 3-jul.)
# 👓 Mythos SIEMPRE con --chat-template (llama2 sin plantilla = lente ciega, Opus 3-jul).
# 👓 TODO-O-NADA: sin Unholy viva o sin trío completable → no levanta nada (D0 protege).
# 👓 Uso:  ./lentes.sh subir | bajar | estado
# 👓 =====================================================================
set -uo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="${MOSAIC_DIR:-$HOME_USER/Mosaic_privado}"
LLAMA_SERVER="${LLAMA_SERVER:-$HOME_USER/modelo/llama.cpp/build/bin/llama-server}"
[ -x "$LLAMA_SERVER" ] || LLAMA_SERVER="$(command -v llama-server || echo "$LLAMA_SERVER")"

MYTHOS_GGUF="${MYTHOS_GGUF:-$HOME_USER/modelo/modelos_grandes/qwen3-14b/Qwen3-14B-Q4_K_M.gguf}"          # intención → Qwen3-14B (jubila mythomax/503) · (var conserva el nombre "MYTHOS"=slot intención)
DOLPHIN_GGUF="${DOLPHIN_GGUF:-$HOME_USER/modelo/modelos_grandes/qwen25-coder/qwen2.5-coder-14b-instruct-q4_k_m.gguf}"  # código → Qwen2.5-Coder-14B (fallback local)
MYTHOS_TEMPLATE="${MYTHOS_TEMPLATE:-}"   # Qwen3 trae plantilla embebida → NO forzar chatml (evitó el 503, ahora estorba)
PUERTO_MYTHOS="${PUERTO_MYTHOS:-8092}"
PUERTO_DOLPHIN="${PUERTO_DOLPHIN:-8093}"
PUERTO_UNHOLY="${PUERTO_UNHOLY:-8091}"

# ── reparto entre máquinas (números REALES: mini=16GB, cabe pequeño+mediano) ──
LENTES_MINI="${LENTES_MINI:-1}"
MINI_HOST="${MINI_HOST:-localhost}"
MINI_SSH="${MINI_SSH:-$USER@localhost}"
DOLPHIN_DIR_MINI="${DOLPHIN_DIR_MINI:-~/modelo/modelos_grandes/qwen25-coder}"   # código → el mini sirve el Coder-7B (reparto 2+2)
MYTHOS_DIR_MINI="${MYTHOS_DIR_MINI:-~/modelo/modelos_grandes/qwen3-14b}"        # el mini NO tiene 14B aquí → lente_al_mini cae a local: intención queda en el MacBook
MINI_MARGEN_GB="${MINI_MARGEN_GB:-2}"

LENTES_CTX="${LENTES_CTX:-4096}"
LENTES_THREADS="${LENTES_THREADS:-6}"
LENTES_ESPERA="${LENTES_ESPERA:-120}"
OVERHEAD_GB="${OVERHEAD_GB:-2}"
MARGEN_GB="${MARGEN_GB:-5}"
DATA="$MOSAIC_DIR/data"; LOGS="$MOSAIC_DIR/logs"
ENV_FILE="$DATA/.lentes_env"

log()  { printf '[%s] 👓 %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
vivo()        { curl -s -m 3 "http://127.0.0.1:$1/v1/models" >/dev/null 2>&1; }
vivo_remoto() { curl -s -m 3 "http://$MINI_HOST:$1/v1/models" >/dev/null 2>&1; }

# 🩺 Fix 3-jul (biblia de Gustavo, el 503 de Mythos): llama-server responde /v1/models
# MIENTRAS AÚN CARGA el modelo (y devuelve 503 al inferir). "Arriba" solo cuenta si
# INFIERE de verdad: sonda de 1 token con HTTP 200.
listo() {   # $1 = base URL (http://host:puerto)
    [ "$(curl -s -m 8 -o /dev/null -w '%{http_code}' -X POST "$1/v1/chat/completions" \
        -H 'Content-Type: application/json' \
        -d '{"model":"local","messages":[{"role":"user","content":"di OK"}],"max_tokens":1}' 2>/dev/null)" = "200" ]
}
listo_local()  { listo "http://127.0.0.1:$1"; }
listo_remoto() { listo "http://$MINI_HOST:$1"; }

gb_fichero() {
    local b; b="$(stat -c %s "$1" 2>/dev/null || stat -f %z "$1" 2>/dev/null || wc -c < "$1")"
    echo $(( (b + 1073741823) / 1073741824 ))
}

gb_libres() {
    if command -v vm_stat >/dev/null 2>&1; then
        vm_stat | awk '
            /page size of/      { ps=$8 }
            /Pages free/        { f=$3 }
            /Pages inactive/    { i=$3 }
            /Pages speculative/ { s=$3 }
            /Pages purgeable/   { p=$3 }
            END { gsub(/\./,"",f); gsub(/\./,"",i); gsub(/\./,"",s); gsub(/\./,"",p);
                  print int((f+i+s+p) * ps / 1073741824) }'
    elif [ -r /proc/meminfo ]; then
        awk '/MemAvailable/ { print int($2/1048576) }' /proc/meminfo
    else
        echo 999
    fi
}

gb_libres_mini() {
    ssh -o ConnectTimeout=6 "$MINI_SSH" vm_stat 2>/dev/null | awk '
        /page size of/      { ps=$8 }
        /Pages free/        { f=$3 }
        /Pages inactive/    { i=$3 }
        /Pages speculative/ { s=$3 }
        /Pages purgeable/   { p=$3 }
        END { if (ps=="") { print -1 } else {
              gsub(/\./,"",f); gsub(/\./,"",i); gsub(/\./,"",s); gsub(/\./,"",p);
              print int((f+i+s+p) * ps / 1073741824) } }'
}

lanzar_local() {  # $1 nombre  $2 gguf  $3 puerto  $4 template ('' = ninguna)
    local extra=()
    [ -n "$4" ] && extra=(--chat-template "$4")
    log "  🚀 $1 (LOCAL) → $(basename "$2") @ :$3 (ctx $LENTES_CTX${4:+ · plantilla $4})"
    nohup "$LLAMA_SERVER" -m "$2" --host 127.0.0.1 --port "$3" \
        -ngl 99 --ctx-size "$LENTES_CTX" --threads "$LENTES_THREADS" "${extra[@]}" \
        > "$LOGS/lente_$3.log" 2>&1 &
    echo $! > "$DATA/.lente_$3.pid"
}

lente_al_mini() {   # $1 nombre  $2 dir_en_mini  $3 puerto  $4 template ('' = ninguna)
    [ "$LENTES_MINI" = "1" ] || return 1
    command -v ssh >/dev/null 2>&1 || { warn "sin ssh → $1 no puede ir al mini"; return 1; }
    local gguf_mini tam libres tpl=""
    gguf_mini="$(ssh -o ConnectTimeout=6 "$MINI_SSH" "ls $2/*.gguf 2>/dev/null | head -1" 2>/dev/null || true)"
    [ -n "$gguf_mini" ] || { warn "el mini no tiene GGUF en $2 → $1 irá local"; return 1; }
    tam="$(ssh -o ConnectTimeout=6 "$MINI_SSH" "wc -c < '$gguf_mini'" 2>/dev/null | tr -d '[:space:]' || echo 0)"
    [[ "$tam" =~ ^[0-9]+$ ]] || tam=0
    tam=$(( (tam + 1073741823) / 1073741824 ))
    libres="$(gb_libres_mini)"
    if [ "$libres" -ge 0 ] && [ "$(( libres - MINI_MARGEN_GB ))" -lt "$(( tam + OVERHEAD_GB ))" ]; then
        warn "mini sin sitio para $1 (${libres}GB libres; pide ${tam}+${OVERHEAD_GB} + ${MINI_MARGEN_GB} de aire) → irá local"
        return 1
    fi
    [ "$libres" -lt 0 ] && warn "no pude medir la RAM del mini — sigo (el arranque dirá)"
    [ -n "$4" ] && tpl="--chat-template $4"
    log "  🚀 $1 → MINI: $(basename "$gguf_mini") @ $MINI_HOST:$3${4:+ (plantilla $4)}"
    ssh -o ConnectTimeout=6 "$MINI_SSH" \
        "nohup ~/modelo/llama.cpp/build/bin/llama-server -m '$gguf_mini' --host 0.0.0.0 --port $3 -ngl 99 --ctx-size $LENTES_CTX --threads $LENTES_THREADS $tpl >~/mini_lente_$3.log 2>&1 & echo \$! > ~/mini_lente_$3.pid" \
        >/dev/null 2>&1 || { warn "ssh de lanzamiento falló para $1 → irá local"; return 1; }
    local t=0
    until listo_remoto "$3"; do    # 🩺 listo = INFIERE (no solo puerto abierto)
        sleep 3; t=$((t + 3))
        if [ "$t" -ge "$LENTES_ESPERA" ]; then
            warn "$1 en el mini no INFIERE tras ${LENTES_ESPERA}s → lo apago; irá local"
            ssh -o ConnectTimeout=6 "$MINI_SSH" "kill \$(cat ~/mini_lente_$3.pid 2>/dev/null) 2>/dev/null; rm -f ~/mini_lente_$3.pid" >/dev/null 2>&1 || true
            return 1
        fi
    done
    touch "$DATA/.lente_remota_$3"
    log "  ✅ $1 arriba EN EL MINI (${t}s)"
}

escribir_env() {   # reconstruye .lentes_env según qué lentes quedaron remotas
    rm -f "$ENV_FILE" 2>/dev/null || true
    [ -f "$DATA/.lente_remota_$PUERTO_DOLPHIN" ] && \
        printf 'export DEFENSA_URL_CODIGO="http://%s:%s/v1"\n' "$MINI_HOST" "$PUERTO_DOLPHIN" >> "$ENV_FILE"
    [ -f "$DATA/.lente_remota_$PUERTO_MYTHOS" ] && \
        printf 'export DEFENSA_URL_INTENCION="http://%s:%s/v1"\n' "$MINI_HOST" "$PUERTO_MYTHOS" >> "$ENV_FILE"
    [ -s "$ENV_FILE" ] && log "  🧾 lentes remotas exportadas en data/.lentes_env ($(grep -c export "$ENV_FILE") URL)"
    return 0
}

subir() {
    [ "${MOSAIC_LENTES:-1}" = "0" ] && { log "MOSAIC_LENTES=0 → no levanto lentes"; return 1; }
    mkdir -p "$DATA" "$LOGS"
    if ! listo_local "$PUERTO_UNHOLY"; then    # 🩺 debe INFERIR, no solo tener el puerto abierto
        warn "adversarial (Unholy:$PUERTO_UNHOLY) CAÍDA o sin inferir — sin ella el trío va cojo → no levanto nada"
        warn "→ arranca el cluster (lanzar_cluster.sh sirve Unholy) y el lote comerá en la próxima"
        return 1
    fi

    # ── cada lente: ¿ya vive? → ¿cabe en el MINI? → local (el guard del mini decide con SU RAM) ──
    local dolphin_local=0 mythos_local=0
    if listo_remoto "$PUERTO_DOLPHIN" && [ -f "$DATA/.lente_remota_$PUERTO_DOLPHIN" ]; then
        log "  ✅ codigo (Dolphin) ya INFIERE en el MINI:$PUERTO_DOLPHIN"
    elif listo_local "$PUERTO_DOLPHIN"; then
        log "  ✅ codigo (Dolphin) ya INFIERE local en :$PUERTO_DOLPHIN"
    elif lente_al_mini "codigo (Dolphin)" "$DOLPHIN_DIR_MINI" "$PUERTO_DOLPHIN" ""; then :
    else dolphin_local=1; fi

    if listo_remoto "$PUERTO_MYTHOS" && [ -f "$DATA/.lente_remota_$PUERTO_MYTHOS" ]; then
        log "  ✅ intencion (Mythos) ya INFIERE en el MINI:$PUERTO_MYTHOS"
    elif listo_local "$PUERTO_MYTHOS"; then
        log "  ✅ intencion (Mythos) ya INFIERE local en :$PUERTO_MYTHOS"
    elif lente_al_mini "intencion (Mythos)" "$MYTHOS_DIR_MINI" "$PUERTO_MYTHOS" "$MYTHOS_TEMPLATE"; then :
    else mythos_local=1; fi

    # ── lo que quedó para el MacBook (48GB: hay sitio de sobra, pero se mide igual) ──
    local faltan=() necesito=0
    if [ "$mythos_local" = "1" ]; then
        [ -f "$MYTHOS_GGUF" ] || { warn "falta el GGUF de intencion: $MYTHOS_GGUF → no levanto NADA"; bajar >/dev/null; return 1; }
        faltan+=("intencion:$MYTHOS_GGUF:$PUERTO_MYTHOS:$MYTHOS_TEMPLATE")
        necesito=$(( necesito + $(gb_fichero "$MYTHOS_GGUF") + OVERHEAD_GB ))
    fi
    if [ "$dolphin_local" = "1" ]; then
        [ -f "$DOLPHIN_GGUF" ] || { warn "falta el GGUF de codigo: $DOLPHIN_GGUF → no levanto NADA"; bajar >/dev/null; return 1; }
        faltan+=("codigo:$DOLPHIN_GGUF:$PUERTO_DOLPHIN:")
        necesito=$(( necesito + $(gb_fichero "$DOLPHIN_GGUF") + OVERHEAD_GB ))
    fi

    if [ "${#faltan[@]}" -gt 0 ]; then
        [ -x "$LLAMA_SERVER" ] || { warn "no encuentro llama-server ($LLAMA_SERVER)"; bajar >/dev/null; return 1; }
        local libres; libres="$(gb_libres)"
        if [ "$(( libres - MARGEN_GB ))" -lt "$necesito" ]; then
            warn "RAM insuficiente aquí: necesito ${necesito}GB + ${MARGEN_GB}GB de aire y hay ${libres}GB"
            warn "→ no levanto NADA: el lote de cuarentena ESPERA (con D0, sin ojos no se firma nada)"
            bajar >/dev/null; return 1
        fi
        log "RAM ok (${libres}GB libres ≥ ${necesito}GB + ${MARGEN_GB}) → levanto ${#faltan[@]} lente(s) local(es)"
        local par nom gguf puerto plantilla
        for par in "${faltan[@]}"; do
            IFS=: read -r nom gguf puerto plantilla <<< "$par"
            lanzar_local "$nom" "$gguf" "$puerto" "$plantilla"
        done
        local p t
        for par in "${faltan[@]}"; do
            IFS=: read -r nom gguf p plantilla <<< "$par"
            t=0
            until listo_local "$p"; do    # 🩺 listo = INFIERE de verdad (adiós al 503 de Mythos)
                sleep 3; t=$((t + 3))
                if [ "$t" -ge "$LENTES_ESPERA" ]; then
                    warn "la lente :$p no INFIERE tras ${LENTES_ESPERA}s → bajo TODO (todo-o-nada)"
                    bajar; return 1
                fi
            done
            log "  ✅ lente :$p arriba E INFIRIENDO (${t}s)"
        done
    fi
    escribir_env
    local d="local" m="local"
    [ -f "$DATA/.lente_remota_$PUERTO_DOLPHIN" ] && d="MINI"
    [ -f "$DATA/.lente_remota_$PUERTO_MYTHOS" ] && m="MINI"
    log "👓 trío completo Y COMPROBADO: Mythos@$m:$PUERTO_MYTHOS ($MYTHOS_TEMPLATE) + Dolphin@$d:$PUERTO_DOLPHIN + Unholy:$PUERTO_UNHOLY"
}

bajar() {   # SOLO lo nuestro: pids locales + remotas marcadas — jamás 8090/8091
    local f pid p alguna=0
    for f in "$DATA"/.lente_*.pid; do
        [ -f "$f" ] || continue
        pid="$(cat "$f" 2>/dev/null || true)"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            log "  🔻 lente local pid $pid apagada ($(basename "$f"))"
        fi
        rm -f "$f"; alguna=1
    done
    for p in "$PUERTO_DOLPHIN" "$PUERTO_MYTHOS"; do
        [ -f "$DATA/.lente_remota_$p" ] || continue
        ssh -o ConnectTimeout=6 "$MINI_SSH" \
            "kill \$(cat ~/mini_lente_$p.pid 2>/dev/null) 2>/dev/null; rm -f ~/mini_lente_$p.pid" \
            >/dev/null 2>&1 && log "  🔻 lente del MINI :$p apagada" || warn "no pude apagar :$p en el mini (mira ~/mini_lente_$p.pid allí)"
        rm -f "$DATA/.lente_remota_$p"; alguna=1
    done
    rm -f "$ENV_FILE" 2>/dev/null || true
    [ "$alguna" = "1" ] && log "lentes bajadas (RAM devuelta en ambas máquinas)" || log "no había lentes nuestras arriba"
}

estado() {
    local p
    if vivo_remoto "$PUERTO_MYTHOS"; then log "  ✅ Mythos  :$PUERTO_MYTHOS (MINI)"
    elif vivo "$PUERTO_MYTHOS"; then log "  ✅ Mythos  :$PUERTO_MYTHOS (local)"
    else log "  ❌ Mythos  :$PUERTO_MYTHOS caído"; fi
    if vivo_remoto "$PUERTO_DOLPHIN"; then log "  ✅ Dolphin :$PUERTO_DOLPHIN (MINI)"
    elif vivo "$PUERTO_DOLPHIN"; then log "  ✅ Dolphin :$PUERTO_DOLPHIN (local)"
    else log "  ❌ Dolphin :$PUERTO_DOLPHIN caído"; fi
    for p in "$PUERTO_UNHOLY"; do
        vivo "$p" && log "  ✅ :$p responde" || log "  ❌ :$p caído"
    done
}

case "${1:-estado}" in
    subir)  subir ;;
    bajar)  bajar ;;
    estado) estado ;;
    *) echo "uso: ./lentes.sh subir | bajar | estado" >&2; exit 2 ;;
esac
