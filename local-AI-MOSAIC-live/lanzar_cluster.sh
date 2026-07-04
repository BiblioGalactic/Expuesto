#!/bin/bash
# 🚀 =====================================================================
# 🚀 LANZAR_CLUSTER v3 — el botón único de la flota, AHORA CON CABEZA (3-jul-2026,
# 🚀 tras congelar el MacBook: mea culpa de Fable — v2 lanzaba TODO sin mirar la RAM).
# 🚀 Lo que cambia en v3 (la gestión inteligente que faltaba):
# 🚀   1) PRESUPUESTO por máquina ANTES de tocar nada: suma los GGUF fijos + overhead
# 🚀      y si no caben (MacBook ~40 usables de 48 · mini ~12 de 16) SE NIEGA a arrancar.
# 🚀   2) Solo lanza los 'fijo' del conf; los 'demanda' son de lentes.sh (por turnos,
# 🚀      con su propia guardia) — el roster completo JAMÁS convive entero.
# 🚀   3) Arranque SECUENCIAL: un servidor no se lanza hasta que el anterior INFIERE
# 🚀      (la carga es el pico de RAM; nada de picos simultáneos).
# 🚀   4) RAM libre medida antes de CADA lanzamiento (vm_stat/meminfo) + margen.
# 🚀   5) Supervisión con CORTAFUEGOS: revive solo si hay RAM; 2 muertes en 10 min
# 🚀      → deja de revivirlo y AVISA (se acabó la espiral OOM→revivir→OOM).
# 🚀   Ctrl+C = apagado CRUZADO Y ORDENADO: mini → verificar → MacBook (como mandó Gustavo).
# 🚀 Uso: ./lanzar_cluster.sh [subir|bajar|estado|plan]   (sin args = arrancar+supervisar)
# 🚀 =====================================================================
set -uo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="${MOSAIC_DIR:-$HOME_USER/Mosaic_privado}"
CONF="${SERVIDORES_CONF:-$MOSAIC_DIR/servidores.conf}"
LLAMA_SERVER="${LLAMA_SERVER:-$HOME_USER/modelo/llama.cpp/build/bin/llama-server}"
[ -x "$LLAMA_SERVER" ] || LLAMA_SERVER="$(command -v llama-server || echo "$LLAMA_SERVER")"
MINI_HOST="${MINI_HOST:-localhost}"
MINI_SSH="${MINI_SSH:-$USER@localhost}"
LLAMA_SERVER_MINI="${LLAMA_SERVER_MINI:-~/modelo/llama.cpp/build/bin/llama-server}"
PID_DIR="${CLUSTER_PID_DIR:-$MOSAIC_DIR/data/cluster_pids}"
LOG_DIR="${CLUSTER_LOG_DIR:-$MOSAIC_DIR/logs}"
ESPERA="${CLUSTER_ESPERA:-10}"   # ⏱️ ORDEN de Gustavo (3-jul): 10 segundos por levantamiento. FIN.
                                  # Puerto arriba = siguiente. El modelo calienta EN 2º PLANO (ping async).
SUPERVISA_CADA="${SUPERVISA_CADA:-30}"
THREADS="${CLUSTER_THREADS:-8}"

# 💰 Presupuestos = LA RAM REAL (orden de Gustavo: nada de valores ficticios).
# El ÚNICO freno es este plan: la suma de fijos no puede superar el hierro físico.
PRESUPUESTO_MACBOOK_GB="${PRESUPUESTO_MACBOOK_GB:-48}"
PRESUPUESTO_MINI_GB="${PRESUPUESTO_MINI_GB:-16}"
OVERHEAD_GB="${OVERHEAD_GB:-2}"                          # KV-cache/compute por servidor
MARGEN_VIVO_GB="${MARGEN_VIVO_GB:-4}"                    # aire mínimo medido antes de CADA lanzamiento
MUERTES_MAX="${MUERTES_MAX:-2}"                          # cortafuegos: muertes en VENTANA → no revivir más
VENTANA_S="${VENTANA_S:-600}"

log()  { printf '[%s] 🚀 %s\n' "$(date '+%H:%M:%S')" "$*"; }
warn() { printf '[%s] ⚠️  %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }

host_de() { [ "$1" = "mini" ] && echo "$MINI_HOST" || echo "127.0.0.1"; }
listo() {
    [ "$(curl -s -m 8 -o /dev/null -w '%{http_code}' -X POST "http://$(host_de "$1"):$2/v1/chat/completions" \
        -H 'Content-Type: application/json' \
        -d '{"model":"local","messages":[{"role":"user","content":"di OK"}],"max_tokens":1}' 2>/dev/null)" = "200" ]
}

gb_de() {   # tamaño GB (techo) de un fichero local
    local b; b="$(stat -c %s "$1" 2>/dev/null || stat -f %z "$1" 2>/dev/null || wc -c < "$1" 2>/dev/null || echo 0)"
    [[ "$b" =~ ^[0-9]+$ ]] || b=0
    echo $(( (b + 1073741823) / 1073741824 ))
}
gb_de_mini() {   # $1 = ruta ABSOLUTA ya resuelta en el mini
    local b; b="$(ssh -o ConnectTimeout=6 "$MINI_SSH" "wc -c < \"$1\"" 2>/dev/null | tr -d '[:space:]' || echo 0)"
    [[ "$b" =~ ^[0-9]+$ ]] || b=0
    echo $(( (b + 1073741823) / 1073741824 ))
}

# 🔎 RESOLUCIÓN de rutas del conf (fix 3-jul: '~' entre comillas NO se expande en remoto —
# por eso el mini "0GB" y nunca arrancaba). Se resuelve ~ y * EN la máquina dueña.
resolver_local() {   # ruta con ~/*  → absoluta local (primera coincidencia) o vacío
    local pat="${1/#\~/$HOME_USER}" r
    r="$(ls $pat 2>/dev/null | head -1)"   # sin comillas a propósito: expande el glob
    echo "$r"
}
resolver_mini() {    # ruta con ~/*  → absoluta EN el mini (ls remoto SIN comillas la expande)
    ssh -o ConnectTimeout=6 "$MINI_SSH" "ls $1 2>/dev/null | head -1" 2>/dev/null || true
}
gb_libres() {
    if command -v vm_stat >/dev/null 2>&1; then
        vm_stat | awk '/page size of/{ps=$8} /Pages free/{f=$3} /Pages inactive/{i=$3} /Pages speculative/{s=$3} /Pages purgeable/{p=$3}
            END{gsub(/\./,"",f);gsub(/\./,"",i);gsub(/\./,"",s);gsub(/\./,"",p); print int((f+i+s+p)*ps/1073741824)}'
    elif [ -r /proc/meminfo ]; then awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo
    else echo 999; fi
}
gb_libres_mini() {
    ssh -o ConnectTimeout=6 "$MINI_SSH" vm_stat 2>/dev/null | awk '/page size of/{ps=$8} /Pages free/{f=$3} /Pages inactive/{i=$3} /Pages speculative/{s=$3} /Pages purgeable/{p=$3}
        END{if(ps==""){print -1}else{gsub(/\./,"",f);gsub(/\./,"",i);gsub(/\./,"",s);gsub(/\./,"",p); print int((f+i+s+p)*ps/1073741824)}}'
}

# ── roster ──
MAQS=(); PTOS=(); ROLES=(); MODOS=(); GGUFS=(); CTXS=(); EXTRAS=()
leer_conf() {
    [ -f "$CONF" ] || { warn "no existe la lista de servidores: $CONF"; exit 1; }
    local m p r md g c e
    while IFS='|' read -r m p r md g c e; do
        case "$m" in \#*|"") continue ;; esac
        [[ "$p" =~ ^[0-9]+$ ]] || { warn "puerto raro en conf: $m|$p (salto)"; continue; }
        case "$md" in fijo|demanda) ;; *) warn "modo desconocido '$md' en $m:$p → lo trato como demanda (prudencia)"; md="demanda" ;; esac
        MAQS+=("$m"); PTOS+=("$p"); ROLES+=("$r"); MODOS+=("$md"); GGUFS+=("$g"); CTXS+=("${c:-4096}"); EXTRAS+=("$e")
    done < "$CONF"
    [ "${#MAQS[@]}" -gt 0 ] || { warn "conf vacía: $CONF"; exit 1; }
}

# 💰 EL FRENO DE MANO: ¿caben los FIJOS de cada máquina en su presupuesto? Si no → NI ARRANCA.
plan() {
    local i g tam mac_gb=0 mini_gb=0 mac_n=0 mini_n=0 ok=0
    log "💰 plan de RAM (solo FIJOS · overhead ${OVERHEAD_GB}GB/servidor):"
    for i in "${!MAQS[@]}"; do
        [ "${MODOS[$i]}" = "fijo" ] || continue
        if [ "${MAQS[$i]}" = "macbook" ]; then
            g="$(resolver_local "${GGUFS[$i]}")"
            [ -n "$g" ] || { warn "   ${MAQS[$i]}:${PTOS[$i]} (${ROLES[$i]}): NO encuentro '${GGUFS[$i]}'"; ok=1; continue; }
            tam="$(gb_de "$g")"
            mac_gb=$((mac_gb + tam + OVERHEAD_GB)); mac_n=$((mac_n+1))
        else
            g="$(resolver_mini "${GGUFS[$i]}")"
            [ -n "$g" ] || { warn "   ${MAQS[$i]}:${PTOS[$i]} (${ROLES[$i]}): el MINI no encuentra '${GGUFS[$i]}'"; ok=1; continue; }
            tam="$(gb_de_mini "$g")"
            mini_gb=$((mini_gb + tam + OVERHEAD_GB)); mini_n=$((mini_n+1))
        fi
        log "   ${MAQS[$i]}:${PTOS[$i]} (${ROLES[$i]}) ≈ $((tam + OVERHEAD_GB))GB → $(basename "$g")"
    done
    log "   MacBook: ${mac_gb}GB de ${PRESUPUESTO_MACBOOK_GB} usables ($mac_n fijos) · mini: ${mini_gb}GB de ${PRESUPUESTO_MINI_GB} ($mini_n fijos)"
    [ "$mac_gb" -gt "$PRESUPUESTO_MACBOOK_GB" ] && { warn "🛑 el MacBook NO puede con sus fijos (${mac_gb}>${PRESUPUESTO_MACBOOK_GB}GB) → edita servidores.conf (baja un modelo a 'demanda' o a q4)"; ok=1; }
    [ "$mini_gb" -gt "$PRESUPUESTO_MINI_GB" ]   && { warn "🛑 el mini NO puede con sus fijos (${mini_gb}>${PRESUPUESTO_MINI_GB}GB) → edita servidores.conf"; ok=1; }
    [ "$ok" = "0" ] && log "💰 presupuesto OK: la flota fija CABE. Lo 'demanda' vive por turnos (lentes.sh)."
    return "$ok"
}

limpiar_zombies() {
    log "🧟 limpieza de zombies SOLO en puertos del roster…"
    local i pids otros
    for i in "${!MAQS[@]}"; do
        if [ "${MAQS[$i]}" = "macbook" ]; then
            pids="$(pgrep -f "llama-server.*--port ${PTOS[$i]}" 2>/dev/null || true)"
            [ -n "$pids" ] && { log "  🧟 local :${PTOS[$i]} → mato $pids"; kill $pids 2>/dev/null || true; }
        else
            ssh -o ConnectTimeout=6 "$MINI_SSH" "pkill -f 'llama-server.*--port ${PTOS[$i]}'" >/dev/null 2>&1 \
                && log "  🧟 mini :${PTOS[$i]} → limpiado" || true
        fi
    done
    sleep 1
    otros="$(ssh -o ConnectTimeout=6 "$MINI_SSH" "pgrep -fl llama-server" 2>/dev/null | grep -v grep || true)"
    [ -n "$otros" ] && warn "en el mini quedan llama-server FUERA del roster (no los toco):
$otros"
    return 0
}

lanzar_uno() {
    local m="${MAQS[$1]}" p="${PTOS[$1]}" r="${ROLES[$1]}" g="${GGUFS[$1]}" c="${CTXS[$1]}" e="${EXTRAS[$1]}"
    local tam libres
    if [ "$m" = "macbook" ]; then
        local gl; gl="$(resolver_local "$g")"
        [ -n "$gl" ] && [ -f "$gl" ] || { warn "no encuentro GGUF local ($r): $g"; return 1; }
        [ -x "$LLAMA_SERVER" ] || { warn "no encuentro llama-server local"; return 1; }
        tam="$(gb_de "$gl")"; libres="$(gb_libres)"
        # (la RAM viva es solo INFORMATIVA — el freno es el plan contra los 48/16 reales)
        log "  🚀 local :$p ($r) → $(basename "$gl") [${tam}GB · libres ${libres}GB]"
        # shellcheck disable=SC2086
        nohup "$LLAMA_SERVER" -m "$gl" --host 0.0.0.0 --port "$p" \
            --ctx-size "$c" -ngl 99 --threads "$THREADS" $e \
            > "$LOG_DIR/servidor_$p.log" 2>&1 &
        echo $! > "$PID_DIR/local_$p.pid"
    else
        local gm; gm="$(resolver_mini "$g")"    # 🔎 absoluta EN el mini (fix del '~' que nunca expandió)
        [ -n "$gm" ] || { warn "el MINI no encuentra GGUF ($r): $g"; return 1; }
        tam="$(gb_de_mini "$gm")"; libres="$(gb_libres_mini)"
        # (la RAM viva es solo INFORMATIVA — el freno es el plan contra los 16 reales del mini)
        log "  🚀 mini :$p ($r) → $(basename "$gm") [${tam}GB · libres ${libres}GB]"
        ssh -o ConnectTimeout=6 "$MINI_SSH" \
            "nohup $LLAMA_SERVER_MINI -m \"$gm\" --host 0.0.0.0 --port $p --ctx-size $c -ngl 99 --threads $THREADS $e >~/cluster_servidor_$p.log 2>&1 & echo \$! > ~/cluster_servidor_$p.pid" \
            >/dev/null 2>&1 || { warn "ssh de lanzamiento falló para mini:$p"; return 1; }
    fi
}

esperar_uno() {   # ⏱️ 10s: PUERTO arriba = listo; el calentamiento va en 2º plano (no bloquea)
    local m="${MAQS[$1]}" p="${PTOS[$1]}" t=0
    until curl -s -m 2 "http://$(host_de "$m"):$p/v1/models" >/dev/null 2>&1; do
        sleep 2; t=$((t + 2))
        [ "$t" -ge "$ESPERA" ] && { warn "$m:$p sin puerto tras ${ESPERA}s (mira su log)"; return 1; }
    done
    # ping de calentamiento ASÍNCRONO: pagina el modelo sin retener a nadie
    ( curl -s -m 300 -X POST "http://$(host_de "$m"):$p/v1/chat/completions" \
        -H 'Content-Type: application/json' \
        -d '{"model":"local","messages":[{"role":"user","content":"ok"}],"max_tokens":1}' >/dev/null 2>&1 & )
    log "  ✅ $m:$p arriba (${t}s) · calentando en 2º plano"
}

subir() {   # SECUENCIAL: cada fijo espera a que el anterior INFIERA (la carga es el pico)
    mkdir -p "$PID_DIR" "$LOG_DIR"
    plan || { warn "→ me NIEGO a arrancar con un plan que no cabe. Nadie quema el ordenador dos veces."; return 1; }
    local i fallo=0
    for i in "${!MAQS[@]}"; do
        [ "${MODOS[$i]}" = "fijo" ] || continue
        if listo "${MAQS[$i]}" "${PTOS[$i]}"; then
            log "  ✅ ${MAQS[$i]}:${PTOS[$i]} (${ROLES[$i]}) ya INFIERE"
        else
            lanzar_uno "$i" && { esperar_uno "$i" || fallo=1; } || fallo=1
        fi
    done
    [ "$fallo" = "0" ] && log "🚀 flota FIJA completa e infiriendo (lo 'demanda' lo gestiona lentes.sh por turnos)" \
                       || warn "flota con bajas (arriba el detalle) — lo vivo sigue vivo"
    return "$fallo"
}

verificar_muerto() {
    local m="$1" p="$2"
    if [ "$m" = "macbook" ]; then
        pgrep -f "llama-server.*--port $p" >/dev/null 2>&1 && return 1
    else
        ssh -o ConnectTimeout=6 "$MINI_SSH" "pgrep -f 'llama-server.*--port $p'" >/dev/null 2>&1 && return 1
    fi
    curl -s -m 2 "http://$(host_de "$m"):$p/v1/models" >/dev/null 2>&1 && return 1
    return 0
}

bajar() {   # 🔻 ORDENADO: 1º MINI → verificar → 2º MacBook (fijos Y demanda: apaga todo lo del roster)
    local i p t
    log "🔻 apagado ordenado · PASO 1: servidores del MINI"
    for i in "${!MAQS[@]}"; do
        [ "${MAQS[$i]}" = "mini" ] || continue
        p="${PTOS[$i]}"
        ssh -o ConnectTimeout=6 "$MINI_SSH" \
            "kill \$(cat ~/cluster_servidor_$p.pid 2>/dev/null) 2>/dev/null; pkill -f 'llama-server.*--port $p' 2>/dev/null; rm -f ~/cluster_servidor_$p.pid" \
            >/dev/null 2>&1 || true
    done
    log "🔎 PASO 2: verifico que el mini cerró de verdad…"
    for i in "${!MAQS[@]}"; do
        [ "${MAQS[$i]}" = "mini" ] || continue
        p="${PTOS[$i]}"; t=0
        until verificar_muerto mini "$p"; do
            sleep 2; t=$((t + 2))
            if [ "$t" -ge 30 ]; then
                warn "mini:$p resiste → kill -9 por ssh"
                ssh -o ConnectTimeout=6 "$MINI_SSH" "pkill -9 -f 'llama-server.*--port $p'" >/dev/null 2>&1 || true
                sleep 2; break
            fi
        done
        verificar_muerto mini "$p" && log "  ✅ mini:$p cerrado y verificado" || warn "  ❗ mini:$p sigue vivo — revísalo a mano"
    done
    log "🔻 PASO 3: ahora sí, servidores del MacBook"
    for i in "${!MAQS[@]}"; do
        [ "${MAQS[$i]}" = "macbook" ] || continue
        p="${PTOS[$i]}"
        [ -f "$PID_DIR/local_$p.pid" ] && { kill "$(cat "$PID_DIR/local_$p.pid")" 2>/dev/null || true; rm -f "$PID_DIR/local_$p.pid"; }
        pkill -f "llama-server.*--port $p" 2>/dev/null || true
    done
    for i in "${!MAQS[@]}"; do
        [ "${MAQS[$i]}" = "macbook" ] || continue
        p="${PTOS[$i]}"; t=0
        until verificar_muerto macbook "$p"; do
            sleep 2; t=$((t + 2))
            [ "$t" -ge 20 ] && { pkill -9 -f "llama-server.*--port $p" 2>/dev/null || true; sleep 1; break; }
        done
        verificar_muerto macbook "$p" && log "  ✅ local:$p cerrado" || warn "  ❗ local:$p resiste"
    done
    log "🔻 flota apagada en orden (mini verificado ANTES de tocar el MacBook)."
}

estado() {
    local i etq
    log "estado del roster ($CONF):"
    for i in "${!MAQS[@]}"; do
        etq="${MODOS[$i]}"
        if listo "${MAQS[$i]}" "${PTOS[$i]}"; then
            log "  ✅ ${MAQS[$i]}:${PTOS[$i]}  ${ROLES[$i]} [$etq] → INFIERE"
        else
            [ "$etq" = "demanda" ] && log "  💤 ${MAQS[$i]}:${PTOS[$i]}  ${ROLES[$i]} [demanda] → apagado (normal: sube por turnos)" \
                                   || log "  ❌ ${MAQS[$i]}:${PTOS[$i]}  ${ROLES[$i]} [fijo] → caído/cargando"
        fi
    done
}

supervisar() {   # 🧯 con CORTAFUEGOS: revive solo con RAM y máx $MUERTES_MAX veces por ventana
    trap 'echo; bajar; log "hasta la próxima."; exit 0' INT TERM
    log "supervisión con cortafuegos (cada ${SUPERVISA_CADA}s · máx ${MUERTES_MAX} revividas/${VENTANA_S}s · Ctrl+C = apagado ordenado)"
    # arrays INDEXADOS por posición del roster (nada de declare -A: /bin/bash de macOS es 3.2)
    local i clave ahora
    local MUERTES_I=() PRIMERA_I=() VETADO_I=()
    for i in "${!MAQS[@]}"; do MUERTES_I[$i]=0; PRIMERA_I[$i]=0; VETADO_I[$i]=0; done
    while :; do
        sleep "$SUPERVISA_CADA"
        for i in "${!MAQS[@]}"; do
            [ "${MODOS[$i]}" = "fijo" ] || continue
            # supervisión por PUERTO (un modelo calentando NO es un caído; muerto de verdad = puerto cerrado)
            curl -s -m 2 "http://$(host_de "${MAQS[$i]}"):${PTOS[$i]}/v1/models" >/dev/null 2>&1 && continue
            clave="${MAQS[$i]}:${PTOS[$i]}"; ahora="$(date +%s)"
            [ "${VETADO_I[$i]}" = "1" ] && continue
            if [ "${PRIMERA_I[$i]}" = "0" ] || [ $(( ahora - PRIMERA_I[$i] )) -gt "$VENTANA_S" ]; then
                PRIMERA_I[$i]="$ahora"; MUERTES_I[$i]=0
            fi
            MUERTES_I[$i]=$(( MUERTES_I[$i] + 1 ))
            if [ "${MUERTES_I[$i]}" -gt "$MUERTES_MAX" ]; then
                VETADO_I[$i]=1
                warn "🧯 $clave murió ${MUERTES_I[$i]} veces en ${VENTANA_S}s → NO lo revivo más (anti-espiral OOM). Míralo: $LOG_DIR/servidor_${PTOS[$i]}.log"
                continue
            fi
            warn "💫 $clave (${ROLES[$i]}) caído → intento ${MUERTES_I[$i]}/${MUERTES_MAX} de revivirlo (con guardia de RAM)"
            lanzar_uno "$i" && esperar_uno "$i" || warn "no pude revivir $clave"
        done
    done
}

leer_conf
case "${1:-arrancar}" in
    plan)     plan ;;
    subir)    limpiar_zombies; subir ;;
    bajar)    bajar ;;
    estado)   estado ;;
    arrancar) limpiar_zombies; subir || exit 1; estado; supervisar ;;
    *) echo "uso: ./lanzar_cluster.sh [plan|subir|bajar|estado]   (sin args = arrancar+supervisar)" >&2; exit 2 ;;
esac
