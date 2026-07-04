#!/bin/bash
# 🚚 =====================================================================
# 🚚 FLOTA — reparte los modelos entre  MacBook (48GB) · MacMini (16GB) · SSD (archivo maestro)
# 🚚 · Archiva los OBSOLETOS del MacBook a la SSD con VERIFICACIÓN antes de borrar
# 🚚 · Descarga/coloca el set de trabajo de cada máquina (Mini ≥3: 2+emergencia · MacBook 4-6)
# 🚚 · Comprueba: sin pérdidas, sin duplicados
# 🚚 REGLA DE ORO: NADA se borra del MacBook sin una copia CONFIRMADA (tamaño exacto) en la SSD.
# 🚚 La SSD está enchufada al MacMini → todo va por ssh+rsync (ojo al ESPACIO en "Extreme SSD").
# 🚚 Uso:  ./flota.sh reportar
# 🚚       ./flota.sh archivar            # DRY-RUN (enseña; no toca nada)
# 🚚       ./flota.sh archivar --aplicar  # ejecuta (rsync→verifica→borra original)
# 🚚       ./flota.sh descargar [--aplicar]
# 🚚       ./flota.sh verificar
# 🚚 =====================================================================
set -euo pipefail

# ── Config (rutas literales) ─────────────────────────────────────────
MINI_SSH="${MINI_SSH:-$USER@localhost}"
SSD="${SSD:-/Volumes/Extreme SSD/MODELOS/llm}"          # ruta EN el mini (con espacio)
MB_DIR="${MB_DIR:-$HOME/modelo/modelos_grandes}"        # disco interno del MacBook
LOGDIR="${LOGDIR:-$HOME/Mosaic_privado/logs}"
LOG="$LOGDIR/flota_$(date +%Y%m%d_%H%M%S).log"
APLICAR=0; [ "${2:-}" = "--aplicar" ] && APLICAR=1

# ── Set de trabajo (EDITA estas listas si cambias de idea; rutas relativas a MB_DIR) ──
# ✅ MacBook: 4-6 modelos que SE QUEDAN
MACBOOK_KEEP=(
  "mistral3/mistralai_Mistral-Small-3.1-24B-Instruct-2503-Q6_K.gguf"   # 24B · SOLO ARCHIVO (orden 3-jul: JAMÁS se sirve; ya borrado del MacBook, respaldo en SSD)
  "qwen3-14b/Qwen3-14B-Q4_K_M.gguf"                                     # intención (jubila a mythomax)
  "libres/Unholy-v2-13B.q8_0.gguf"                                      # adversarial
  "dolphin3/Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf"                         # código (interino → Qwen-Coder)
  "deepseek-r1-qwen3/DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf"             # razonamiento (5º)
)
# 📦 Archivar MacBook→SSD (categoría destino en la SSD tras los ':')
ARCHIVAR=(
  # ⛔ HOLD mythomax: lo usan generar_pregunta.sh (generador LOCAL de la fábrica) Y lentes.sh:20 (lente de
  #    intención). Archívalo SOLO cuando Fable repunte AMBOS a Qwen3-14B. (Opus · verificado por dependencias)
  # "libres/mythomax-l2-13b.Q4_K_M.gguf:creatividad"
  "mistral3/Ministral-8B-Instruct-2410-Q8_0.gguf:mistral3"  # ✅ copia redundante (el mini usa la SUYA, ~ en el mini)
  "qwen3/Qwen3-8B-Q4_K_M.gguf:_revisar"                     # ✅ solo etiqueta en elo.py (sin ruta ni lanzamiento)
)
# 🗑️ Rotos (0 bytes / descarga fallida): NO se archivan, solo se AVISAN
ROTOS=(
  "qwen3.5mini/Qwen3.5-9B-Q6_K.gguf"
)
# ⬇️ Descargar al MacBook  (repo_HF : fichero_gguf : categoria_destino)
DESCARGAR_MB=(
  "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF:qwen2.5-coder-14b-instruct-q4_k_m.gguf:qwen25-coder"
)

# ── Utilidades ───────────────────────────────────────────────────────
mkdir -p "$LOGDIR"
log()  { printf '[%s] 🚚 %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
warn() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG" >&2; }
die()  { warn "$*"; exit 1; }
cleanup() { :; }   # sin temporales que borrar; el trap deja constancia
trap cleanup EXIT

tam_local() {   # tamaño en bytes · a prueba de BSD/GNU (GNU stat -f "tiene éxito" con basura → guarda numérica)
    local b
    b="$(stat -f %z "$1" 2>/dev/null || true)"; [[ "$b" =~ ^[0-9]+$ ]] || \
    b="$(stat -c %s "$1" 2>/dev/null || true)"; [[ "$b" =~ ^[0-9]+$ ]] || \
    b="$(wc -c < "$1" 2>/dev/null || echo 0)"
    printf '%s' "${b//[!0-9]/}"; [ -n "${b//[!0-9]/}" ] || printf 0
}
tam_remoto() { ssh -o ConnectTimeout=8 "$MINI_SSH" "wc -c < \"$1\" 2>/dev/null" | tr -d '[:space:]' || echo 0; }  # wc: universal
hHR() { awk 'BEGIN{s='"$1"'; u="B K M G T"; split(u,a); i=1; while(s>=1024&&i<5){s/=1024;i++} printf "%.1f%s",s,a[i]}'; }

validar() {
    command -v ssh   >/dev/null || die "falta ssh"
    command -v rsync >/dev/null || die "falta rsync"
    [ -d "$MB_DIR" ] || die "no existe el dir de modelos del MacBook: $MB_DIR"
    ssh -o ConnectTimeout=8 "$MINI_SSH" "test -d \"$SSD\"" 2>/dev/null \
        || die "no veo la SSD en el mini ($SSD). ¿Está enchufada y montada?"
}

# ── reportar ─────────────────────────────────────────────────────────
reportar() {
    validar
    log "═══ ESTADO DE LA FLOTA ═══"
    log "MacBook · $MB_DIR"
    local f n=0 total=0
    while IFS= read -r f; do
        n=$((n+1)); local b; b="$(tam_local "$f")"; total=$((total+b))
        printf '   %-8s %s\n' "$(hHR "$b")" "${f#$MB_DIR/}" | tee -a "$LOG"
    done < <(find "$MB_DIR" -iname '*.gguf' | sort)
    log "MacBook: $n modelos · $(hHR "$total") en modelos"
    df -h "$MB_DIR" | tail -1 | awk '{print "   disco: usado "$3"/"$2" ("$5") · libre "$4}' | tee -a "$LOG"
    log "SSD (en el mini) · $SSD"
    ssh -o ConnectTimeout=8 "$MINI_SSH" "find \"$SSD\" -iname '*.gguf' | wc -l" 2>/dev/null \
        | awk '{print "   "$1" modelos .gguf archivados en la SSD"}' | tee -a "$LOG"
}

# ── archivar (MacBook→SSD, verifica, borra original solo si copia OK) ─
archivar() {
    validar
    [ "$APLICAR" = "1" ] && log "═══ ARCHIVAR · MODO --aplicar (REAL) ═══" || log "═══ ARCHIVAR · DRY-RUN (añade --aplicar) ═══"
    local item rel cat src dstdir dst bl br
    for item in "${ARCHIVAR[@]}"; do
        rel="${item%%:*}"; cat="${item##*:}"; src="$MB_DIR/$rel"
        if [ ! -f "$src" ]; then warn "no está en el MacBook (¿ya archivado?): $rel"; continue; fi
        dstdir="$SSD/$cat"; dst="$dstdir/$(basename "$rel")"
        bl="$(tam_local "$src")"
        log "· $rel  ($(hHR "$bl"))  →  SSD/$cat/"
        if [ "$APLICAR" != "1" ]; then
            log "    [dry] rsync → verifica tamaño → borra original si coincide"; continue
        fi
        ssh -o ConnectTimeout=8 "$MINI_SSH" "mkdir -p \"$dstdir\"" || { warn "no pude crear $dstdir en el mini"; continue; }
        log "    ⇢ copiando (tar+ssh · macOS trae openrsync sin -s; el espacio lo maneja el shell remoto)…"
        local sd sb cp_pid cp_ok now
        sd="$(dirname "$src")"; sb="$(basename "$src")"
        # copia en 2º plano + barra de progreso sondeando el tamaño que YA llegó a la SSD (cada 5s)
        tar -C "$sd" -cf - "$sb" | ssh -o ConnectTimeout=8 "$MINI_SSH" "tar -C \"$dstdir\" -xf -" &
        cp_pid=$!
        while kill -0 "$cp_pid" 2>/dev/null; do
            sleep 5; now="$(tam_remoto "$dst" 2>/dev/null || echo 0)"
            printf '\r    … %-7s / %-7s en la SSD   ' "$(hHR "${now:-0}")" "$(hHR "$bl")"
        done
        printf '\n'
        wait "$cp_pid" && cp_ok=1 || cp_ok=0
        [ "${cp_ok:-0}" = "1" ] || { warn "    copia falló → NO borro el original ($rel)"; continue; }
        br="$(tam_remoto "$dst")"
        if [ "$bl" = "$br" ] && [ "$bl" -gt 0 ]; then
            rm -f "$src" && log "    ✅ copiado y verificado ($(hHR "$br")) → original borrado del MacBook"
        else
            warn "    ✋ tamaños NO coinciden (MB=$bl · SSD=$br) → NO borro. Revisa a mano."
        fi
    done
    [ "$APLICAR" = "1" ] && df -h "$MB_DIR" | tail -1 | awk '{print "   disco tras archivar: libre "$4}' | tee -a "$LOG"
}

# ── descargar (los que faltan en el MacBook) ─────────────────────────
descargar() {   # baja al MacBook los que faltan · curl con descarga ATÓMICA (.part→rename, sin 0-bytes)
    command -v curl >/dev/null || die "falta curl"
    [ -d "$MB_DIR" ] || die "no existe $MB_DIR"
    [ "$APLICAR" = "1" ] && log "═══ DESCARGAR · REAL ═══" || log "═══ DESCARGAR · DRY-RUN ═══"
    local spec repo file cat dstdir url
    for spec in "${DESCARGAR_MB[@]}"; do
        repo="${spec%%:*}"; file="$(echo "$spec" | cut -d: -f2)"; cat="${spec##*:}"
        dstdir="$MB_DIR/$cat"; url="https://huggingface.co/$repo/resolve/main/$file"
        if [ -f "$dstdir/$file" ] && [ "$(tam_local "$dstdir/$file")" -gt 1048576 ]; then log "· ya está: $cat/$file"; continue; fi
        log "· $repo → $cat/$file"
        if [ "$APLICAR" != "1" ]; then log "    [dry] curl -L --fail --progress-bar -o \"$dstdir/$file\" \"$url\""; continue; fi
        mkdir -p "$dstdir"
        if curl -L --fail --progress-bar -o "$dstdir/$file.part" "$url"; then
            mv "$dstdir/$file.part" "$dstdir/$file"; log "    ✅ descargado en $cat/ ($(hHR "$(tam_local "$dstdir/$file")"))"
        else
            rm -f "$dstdir/$file.part" 2>/dev/null || true; warn "    descarga falló (se limpia el .part): $url"
        fi
    done
}

# ── verificar (set de trabajo presente · rotos · duplicados) ─────────
verificar() {
    validar
    log "═══ VERIFICAR ═══"
    local rel miss=0
    for rel in "${MACBOOK_KEEP[@]}"; do
        if [ -f "$MB_DIR/$rel" ]; then log "  ✅ keep: $rel"; else warn "  ❌ FALTA keep: $rel"; miss=$((miss+1)); fi
    done
    for rel in "${ROTOS[@]}"; do
        if [ -f "$MB_DIR/$rel" ] && [ "$(tam_local "$MB_DIR/$rel")" -lt 1048576 ]; then
            warn "  🗑️ ROTO (0 bytes / incompleto): $rel → re-descárgalo o bórralo a mano"
        fi
    done
    log "duplicados por nombre de fichero (mismo modelo en ≥2 sitios del MacBook):"
    find "$MB_DIR" -iname '*.gguf' -exec basename {} \; | sort | uniq -d | sed 's/^/     ⚠️ dup: /' | tee -a "$LOG" || true
    [ "$miss" -eq 0 ] && log "set de trabajo COMPLETO" || warn "faltan $miss modelo(s) del set de trabajo"
}

case "${1:-reportar}" in
    reportar)  reportar ;;
    archivar)  archivar ;;
    descargar) descargar ;;
    verificar) verificar ;;
    *) echo "uso: ./flota.sh reportar | archivar [--aplicar] | descargar [--aplicar] | verificar" >&2; exit 2 ;;
esac
