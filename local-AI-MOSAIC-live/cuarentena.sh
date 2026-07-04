#!/bin/bash
# 🛡️ =====================================================================
# 🛡️ CUARENTENA — código EXTERNO no confiable (de GitHub) → defensa → cola.
# 🛡️ Misma lógica de LOTES que el silo, PERO aquí cada item es código de
# 🛡️ desconocidos: pasa por defensa.py (sandbox + 3 lentes + juez) ANTES de
# 🛡️ confiar. Lo SEGURO entra a la cola (fuente=cuarentena); lo que huele a
# 🛡️ TRAMPA/DUDOSO genera capacidad de seguridad (vía gobernanza) y NO entra.
# 🛡️ Uso:  ./cuarentena.sh clonar     (trae los hallazgos KEEP del oráculo)
# 🛡️       ./cuarentena.sh procesar   (analiza por lotes lo que haya)
# 🛡️       ./cuarentena.sh estado
# 🛡️ =====================================================================
set -euo pipefail
# 🔒 4-jul (Opus): en un ciclo DESATENDIDO git JAMÁS debe pedir credenciales por TTY. Con esto,
#   un repo con auth (privado/borrado/rate-limit) FALLA y se SALTA — nunca cuelga el ciclo pidiendo usuario.
export GIT_TERMINAL_PROMPT=0

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
CUAR="${CUARENTENA_DIR:-$BASE/cuarentena}"
# 👁️ 4-jul: procesados a carpeta VISIBLE (Finder), fuera de cuarentena/ (los globs no la pisan)
PROC="$CUAR/.procesando"; HECHOS="${CUAR_HECHOS:-$BASE/procesados/cuarentena}"
COLA_SH="${COLA_SH:-$BASE/cola.sh}"
DEFENSA="${DEFENSA_PY:-$BASE/defensa.py}"
HALLAZGOS="${ORACULO_HALLAZGOS:-$HOME/oraculo/hallazgos}"
LOTES="${ORACULO_LOTES:-$HOME/oraculo/lotes}"             # el crawler comprime hallazgos→lotes/*.tar.gz y borra los vivos
VISTOS="$CUAR/.clonados.txt"             # legado (lo importa memoria.sh migrar)
MEM="${MEMORIA:-$BASE/memoria.sh}"       # ¿ya visto? unificado (#61)
LOTE="${CUAR_LOTE:-4}"
MAX_PROC="${CUAR_MAX:-100000}"
MAXTEXTO="${CUAR_MAXTEXTO:-4000}"

log()  { printf '[%s] 🛡️  %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    command -v python3 >/dev/null || { warn "falta python3"; exit 1; }
    [ -f "$COLA_SH" ] || { warn "no encuentro cola.sh"; exit 1; }
    mkdir -p "$CUAR" "$PROC" "$HECHOS"; touch "$VISTOS"
}

# clona UN veredicto.json (si trae url y no está ya clonado) → repo a cuarentena. Suma en CLON_N.
_clonar_vj() {
    local vj="$1" url repo slug
    [ -e "$vj" ] || return 0
    url="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("url",""))' "$vj" 2>/dev/null)"
    repo="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("repo",""))' "$vj" 2>/dev/null)"
    [ -n "$url" ] || return 0
    bash "$MEM" visto cuarentena "$repo" && return 0         # ya clonado (memoria unificada)
    slug="$(printf '%s' "$repo" | tr '/ ' '__')"
    if git clone --depth 1 -q "$url" "$CUAR/$slug" 2>/dev/null; then
        bash "$MEM" marcar cuarentena "$repo"; CLON_N=$((CLON_N+1)); log "clonado a cuarentena: $repo"
    else
        warn "no pude clonar: $repo"
    fi
}

# trae a cuarentena el CÓDIGO de los hallazgos KEEP del oráculo (git clone superficial).
# Lee DOS sitios (igual que fuente_oraculo.sh): hallazgos/ vivos Y lotes/*.tar.gz comprimidos —
# el crawler comprime los hallazgos y BORRA los vivos, así que sin leer los lotes clonaría 0.
clonar() {
    command -v git >/dev/null || { warn "falta git"; return 1; }
    CLON_N=0
    # 1) hallazgos vivos (si el crawler aún no ha comprimido esta tanda)
    if [ -d "$HALLAZGOS" ]; then
        while IFS= read -r vj; do
            _clonar_vj "$vj"
            [ "$CLON_N" -ge "$MAX_PROC" ] && break
        done < <(find "$HALLAZGOS" -name veredicto.json 2>/dev/null)
    fi
    # 2) lotes comprimidos (donde acaban los hallazgos tras comprimir_lotes del crawler)
    if [ "$CLON_N" -lt "$MAX_PROC" ] && [ -d "$LOTES" ]; then
        local tmp; tmp="$(mktemp -d)"
        for tgz in "$LOTES"/*.tar.gz; do
            [ -e "$tgz" ] || continue
            local d="$tmp/$(basename "$tgz" .tar.gz)"; mkdir -p "$d"
            tar -xzf "$tgz" -C "$d" 2>/dev/null || continue
            while IFS= read -r vj; do
                _clonar_vj "$vj"
                [ "$CLON_N" -ge "$MAX_PROC" ] && break
            done < <(find "$d" -name veredicto.json 2>/dev/null)
            [ "$CLON_N" -ge "$MAX_PROC" ] && break
        done
        rm -rf "$tmp"
    fi
    log "clonar: $CLON_N repos nuevos en cuarentena."
}

# analiza UN item (repo clonado o fichero suelto) por la DEFENSA y enruta por veredicto
procesar_uno() {
    local item="$1" nom; nom="$(basename "$item")"
    local codefile="" readme=""
    if [ -d "$item" ]; then
        # Fix 3-jul (biblia): (1) el `find|head` moría por SIGPIPE bajo pipefail y abortaba el
        # lote a medias; (2) el PRIMER fichero solía ser trivial (embed.go) y las lentes soltaban
        # manuales genéricos. Ahora: el fichero de código MÁS GORDO (a prueba de espacios).
        local f t mejor=0
        while IFS= read -r f; do
            t="$(wc -c < "$f" 2>/dev/null || echo 0)"
            [[ "$t" =~ ^[0-9]+$ ]] || t=0
            if [ "$t" -gt "$mejor" ]; then mejor="$t"; codefile="$f"; fi
        done < <(find "$item" -type f \( -name '*.py' -o -name '*.sh' -o -name '*.js' -o -name '*.ts' -o -name '*.go' -o -name '*.rb' -o -name '*.c' -o -name '*.cpp' \) 2>/dev/null)
        [ -f "$item/README.md" ] && readme="$item/README.md"
    else
        codefile="$item"
    fi
    [ -n "$codefile" ] || { warn "sin código analizable: $nom"; mv "$item" "$HECHOS/" 2>/dev/null || true; return 0; }
    log "DEFENSA sobre $nom (transparente)…"
    local out
    out="$(DEFENSA_PROPUESTAS="$BASE/data/seguridad_propuestas.yaml" python3 "$DEFENSA" \
            --repo "$nom" ${readme:+--readme "$readme"} --codigo "$codefile" 2>&1)" || true
    # 🔎 transparencia (3-jul, Opus): guarda el intercambio COMPLETO por repo (cada lente HABLA) y
    #    muestra un extracto amplio. Antes `tail -n 25` recortaba las voces → "todos parecían jueces".
    local traza="$BASE/logs/defensa_${nom}.txt"
    mkdir -p "$BASE/logs"; printf '%s\n' "$out" > "$traza"
    printf '%s\n' "$out" | tail -n 60
    log "🔎 traza completa (qué dijo cada modelo): logs/defensa_${nom}.txt"
    # `|| true`: si una defensa muere sin línea JUEZ (RAM/juez ilegible) NO abortamos el lote bajo
    #    `set -euo pipefail`; caemos a DUDOSO (fail-closed) y seguimos con el siguiente repo.
    local veredicto; veredicto="$(printf '%s' "$out" | grep 'JUEZ' | grep -oE 'TRAMPA|SEGURO|DUDOSO' | tail -1 || true)"
    veredicto="${veredicto:-DUDOSO}"
    if [ "$veredicto" = "SEGURO" ]; then
        local texto; texto="$(head -c "$MAXTEXTO" "$codefile" 2>/dev/null)"
        "$COLA_SH" add "Código EXTERNO verificado SEGURO «${nom}»: extrae qué capacidad o patrón aporta: $texto" cuarentena >/dev/null \
            && log "✅ SEGURO → encolado: $nom"
    else
        log "⚠️ $veredicto → NO entra a la cola; la lección de seguridad ya fue a gobernanza: $nom"
    fi
    mv "$item" "$HECHOS/" 2>/dev/null || true
}

# 👓 D1 (2-jul): lentes del blue team bajo demanda. Sube Mythos@8092+Dolphin@8093 al activar
# el primer lote; las baja SIEMPRE al salir (trap). Sin ojos completos → el lote ESPERA
# (con el fail-closed D0, juzgar a medias solo produciría DUDOSOs vacíos — mejor no gastar).
LENTES_SH="${LENTES_SH:-$BASE/lentes.sh}"
LENTES_ARRIBA=0
_lentes_off() { [ "$LENTES_ARRIBA" = "1" ] && { bash "$LENTES_SH" bajar || true; LENTES_ARRIBA=0; }; }
_lentes_on() {
    [ "${MOSAIC_LENTES:-1}" = "0" ] && { log "👓 MOSAIC_LENTES=0 → defensa sin lentes extra (D0 protege)"; return 0; }
    [ -f "$LENTES_SH" ] || { log "👓 (sin lentes.sh — defensa con lo que haya; D0 protege)"; return 0; }
    [ "$LENTES_ARRIBA" = "1" ] && return 0
    if bash "$LENTES_SH" subir; then
        LENTES_ARRIBA=1; trap '_lentes_off; _juez_off' EXIT
        # 👓 reparto entre máquinas: si lentes.sh mudó una lente al mini, aquí se hereda su URL
        if [ -f "$BASE/data/.lentes_env" ]; then
            # shellcheck disable=SC1091
            . "$BASE/data/.lentes_env"
            log "👓 lente remota: DEFENSA_URL_CODIGO=${DEFENSA_URL_CODIGO:-local}"
        fi
        return 0
    fi
    return 1
}

# 🧑‍⚖️ P-A (3-jul, orden de Gustavo: los 4 roles de la defensa = 4 modelos DISTINTOS · voto A de
# Opus): el juez de seguridad es Phi-4-mini@8096 en modo DEMANDA — sube con el lote si no responde
# y BAJA al acabar (primer consumidor real del banco de especialistas). Espera de puerto ≤10s (la
# ley de Gustavo); el modelo calienta mientras las lentes hablan (~1 min antes del primer juicio).
# Si DEFENSA_URL_JUEZ apunta a otro puerto (un fijo), aquí no se toca nada. D0 protege siempre.
JUEZ_URL_DEF="${DEFENSA_URL_JUEZ:-http://127.0.0.1:8096/v1}"
JUEZ_GGUF_GLOB="${JUEZ_GGUF_GLOB:-$HOME/modelo/modelos_grandes/phi4-mini/*.gguf}"
JUEZ_BIN="${JUEZ_BIN:-$HOME/modelo/llama.cpp/build/bin/llama-server}"
JUEZ_PID=""
_juez_off() { if [ -n "$JUEZ_PID" ]; then kill "$JUEZ_PID" 2>/dev/null || true; JUEZ_PID=""; log "🧑‍⚖️ juez demanda abajo (Phi-4-mini@8096)"; fi; }
_juez_on() {
    [ "${MOSAIC_JUEZ_DEMANDA:-1}" = "0" ] && return 0
    curl -s -m 3 "$JUEZ_URL_DEF/models" >/dev/null 2>&1 && return 0      # ya responde → no toco nada
    case "$JUEZ_URL_DEF" in *:8096*) : ;; *) return 0 ;; esac            # solo gestiono el 8096 local
    [ -x "$JUEZ_BIN" ] || { warn "juez 8096: no encuentro llama-server ($JUEZ_BIN) — D0 protege"; return 0; }
    local g; g="$(ls $JUEZ_GGUF_GLOB 2>/dev/null | head -1 || true)"
    [ -n "$g" ] || { warn "juez 8096: sin GGUF en $JUEZ_GGUF_GLOB — D0 protege"; return 0; }
    mkdir -p "$BASE/logs"
    nohup "$JUEZ_BIN" -m "$g" --host 0.0.0.0 --port 8096 -c 4096 >> "$BASE/logs/servidor_8096.log" 2>&1 &
    JUEZ_PID=$!
    trap '_lentes_off; _juez_off' EXIT
    local i; for i in 1 2 3 4 5 6 7 8 9 10; do curl -s -m 1 "$JUEZ_URL_DEF/models" >/dev/null 2>&1 && break; sleep 1; done
    log "🧑‍⚖️ juez demanda arriba: Phi-4-mini@8096 ($(basename "$g")) · calienta mientras las lentes hablan"
}

ejecutar() {
    shopt -s nullglob
    for d in "$PROC"/*; do [ -e "$d" ] && mv "$d" "$CUAR/" 2>/dev/null || true; done   # recupera cortes
    local hechos=0
    while [ "$hechos" -lt "$MAX_PROC" ]; do
        local lote=() x; for x in "$CUAR"/*; do [ -e "$x" ] && lote+=("$x"); done
        local n=${#lote[@]}
        if [ "$n" -lt "$LOTE" ]; then log "cuarentena: $n item(s) < lote $LOTE → esperan"; break; fi
        if ! _lentes_on; then
            log "👓 sin trío completo (RAM/GGUF/arranque) → el lote ESPERA a mejor momento (nada juzgado a ciegas)"
            break
        fi
        _juez_on || true
        log "cuarentena: $n ≥ $LOTE → activo un lote de $LOTE"
        local i=0; for x in "${lote[@]}"; do [ "$i" -ge "$LOTE" ] && break; mv "$x" "$PROC/"; i=$((i+1)); done
        for x in "$PROC"/*; do [ -e "$x" ] || continue; procesar_uno "$x"; hechos=$((hechos+1)); [ "$hechos" -ge "$MAX_PROC" ] && break; done
    done
    shopt -u nullglob
    _lentes_off
    _juez_off
    log "cuarentena: $hechos analizados en esta pasada."
}

contar() { local n=0 x; shopt -s nullglob; for x in "$CUAR"/*; do [ -e "$x" ] && n=$((n+1)); done; shopt -u nullglob; echo "$n"; }

case "${1:-procesar}" in
    clonar)   validar; clonar ;;
    procesar) validar; ejecutar ;;
    estado)   validar; log "en cuarentena: $(contar) item(s) (lote = $LOTE)" ;;
    *)        warn "uso: cuarentena.sh clonar | procesar | estado"; exit 1 ;;
esac
