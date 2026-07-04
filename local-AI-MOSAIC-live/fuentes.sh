#!/bin/bash
# 🚰 =====================================================================
# 🚰 FUENTES — CASCADA de ingesta con CESIÓN y SUELO (nunca cero).
# 🚰 Orden fijo de lectura cada ciclo · unidades 1 + primos (2,3,5,7,11) = 29:
# 🚰   1º 📚 libro(1) · 2º 🔭 conversación(2) · 3º 🔮 oráculo(3)
# 🚰   4º 🛡️ cuarentena(5) · 5º 📰 noticias(7) · 6º 🏭 fábrica(11)
# 🚰 Cada fuente recibe base+arrastre; lo que NO aporta lo CEDE a la siguiente.
# 🚰 Si nadie real produce, la fábrica hereda hasta 29 (un día de suerte).
# 🚰 SUELO≥1: la cadena nunca cae a cero (invariante Collatz del teorema de memoria).
# 🚰 Antes de la fábrica se DRENA el silo (PDFs/libros/noticias REALES) y actúa la capa
# 🚰 RIEMANN (recuperación): sobre las unidades cedidas rescata HUECOS reales de la memoria.
# 🚰 El humo (fábrica) es el último cartucho: solo si no hay nada real ni que rescatar.
# 🚰 REPOSICIÓN: la fuente que aporta 0 (almacén vacío) dispara su RECOLECTOR aguas-arriba
# 🚰 en 2º plano al terminar la pasada (oráculo/cuarentena → oraculo_auto.sh), con
# 🚰 enfriamiento, para llegar llena al próximo ciclo. Ceder = pedir restock.
# 🚰 Uso:  ./fuentes.sh pull
# 🚰 =====================================================================
set -euo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="${MOSAIC_DIR:-$HOME_USER/Mosaic_privado}"
COLA_SH="${COLA_SH:-$MOSAIC_DIR/cola.sh}"
GEN="${GEN:-$MOSAIC_DIR/generar_pregunta.sh}"
FUENTE_ORACULO="${FUENTE_ORACULO:-$MOSAIC_DIR/fuente_oraculo.sh}"
SILO_SH="${SILO_SH:-$MOSAIC_DIR/silo.sh}"
CUARENTENA_SH="${CUARENTENA_SH:-$MOSAIC_DIR/cuarentena.sh}"
LIBROS_SH="${LIBROS_SH:-$MOSAIC_DIR/silo_libros.sh}"
CONV_SH="${CONV_SH:-$MOSAIC_DIR/silo_conversaciones.sh}"
NOTICIAS_SH="${NOTICIAS_SH:-$MOSAIC_DIR/silo_noticias.sh}"
SILO_DIR_R="${SILO_DIR:-$MOSAIC_DIR/silo}"
NOTAS_DIR_R="${NOTAS_DIR:-$HOME_USER/proyecto/calendario_mental/notas}"   # 1 nota de calendario por conversación
MAX_COLA="${MAX_COLA:-60}"   # capacidad del BANCO (reservorio para lotes discriminados, paso 3)

# unidades base por fuente (orden fijo). 1 + primos = 29.
U_LIBRO="${U_LIBRO:-1}"
U_CONVERSACION="${U_CONVERSACION:-2}"
U_ORACULO="${U_ORACULO:-3}"
U_CUARENTENA="${U_CUARENTENA:-5}"
U_NOTICIAS="${U_NOTICIAS:-7}"
U_FABRICA="${U_FABRICA:-11}"

# 🔁 reposición: recolectores aguas-arriba que rellenan el almacén de una fuente vacía.
ORACULO_AUTO_SH="${ORACULO_AUTO_SH:-$MOSAIC_DIR/oraculo_auto.sh}"   # repone hallazgos (oráculo) y clona repos (cuarentena)
REPONER="${REPONER:-1}"                         # 1 = al ceder por vacío, dispara el recolector en 2º plano
REPONER_COOLDOWN="${REPONER_COOLDOWN:-3600}"    # s mínimos entre reposiciones de una misma fuente (no martillear GitHub)
REPONER_TIMEOUT="${REPONER_TIMEOUT:-900}"       # s máximos que dejamos correr un recolector

# 🔁 recuperación (paso RIEMANN): rescata huecos reales de la memoria antes de fabricar humo.
RECUPERAR_PY="${RECUPERAR_PY:-$MOSAIC_DIR/recuperar.py}"
PYBIN="${PYBIN:-$HOME_USER/wikirag/venv/bin/python3}"; [ -x "$PYBIN" ] || PYBIN="$(command -v python3)"
MOSAIC_RECUP="${MOSAIC_RECUP:-1}"               # 1 = capa Riemann activa (rescata antes de la fábrica)

# 🏭 F13 (observación del Nuevo, 4-jul): contador PERSISTENTE de fábrica saltada. Cada salto
# suma; disparar la fábrica lo resetea. Señal legible para el gobernador/bucle continuo:
# si la racha crece sin fin, toca un "ciclo de humo" (las capacidades dormidas lo necesitan).
FAB_SALTOS="${FAB_SALTOS:-$MOSAIC_DIR/data/fabrica_saltos.txt}"

log() { printf '[%s] 🚰 %s\n' "$(date +%H:%M:%S)" "$*"; }

# --- medidores: cuánto material REAL hay ahora en cada destino (robustos si falta el dir) ---
cola_n()  { "$COLA_SH" size 2>/dev/null || echo 0; }
silo_n()  { [ -d "$SILO_DIR_R" ]  || { echo 0; return 0; }; local c; c="$(find "$SILO_DIR_R" -maxdepth 1 -type f 2>/dev/null | wc -l)"; echo "${c//[^0-9]/}"; }
notas_n() { [ -d "$NOTAS_DIR_R" ] || { echo 0; return 0; }; local c; c="$(find "$NOTAS_DIR_R" -maxdepth 1 -type f 2>/dev/null | wc -l)"; echo "${c//[^0-9]/}"; }

# --- fuentes (CONTRATO: reciben presupuesto N; imprimen SOLO 'aportado' en stdout;
#     todo su ruido va a stderr con >&2 para no ensuciar la medición) ---
fuente_libro() {        # 📚 feeder → silo · aporta = ficheros nuevos en silo
    local n="$1" a b; a="$(silo_n)"
    LIBROS_LOTE="$n" bash "$LIBROS_SH" "$n" >&2 || log "libros con incidencias" >&2
    b="$(silo_n)"; echo "$(( b>a ? b-a : 0 ))"
}
fuente_conversacion() { # 🔭 observer → calendario · aporta = notas nuevas (1 por conversación)
    local n="$1" a b; a="$(notas_n)"
    bash "$CONV_SH" "$n" >&2 || log "conversaciones con incidencias" >&2
    b="$(notas_n)"; echo "$(( b>a ? b-a : 0 ))"
}
fuente_oraculo() {      # 🔮 → cola directa
    local n="$1" a b; a="$(cola_n)"
    ORACULO_MAX="$n" bash "$FUENTE_ORACULO" >&2 || log "oráculo con incidencias" >&2
    b="$(cola_n)"; echo "$(( b>a ? b-a : 0 ))"
}
fuente_cuarentena() {   # 🛡️ → cola directa
    local n="$1" a b; a="$(cola_n)"
    CUAR_MAX="$n" bash "$CUARENTENA_SH" procesar >&2 || log "cuarentena con incidencias" >&2
    b="$(cola_n)"; echo "$(( b>a ? b-a : 0 ))"
}
fuente_noticias() {     # 📰 feeder → silo
    local n="$1" a b; a="$(silo_n)"
    NOTICIAS_LOTE="$n" bash "$NOTICIAS_SH" "$n" >&2 || log "noticias con incidencias" >&2
    b="$(silo_n)"; echo "$(( b>a ? b-a : 0 ))"
}
fuente_fabrica() {      # 🏭 → cola directa · último recurso (banco auto-regulado en paso 3)
    local n="$1" a b r; a="$(cola_n)"; r=$(( (n + 2) / 3 ))   # 3 modelos/ronda → ~n preguntas
    echo 0 > "$FAB_SALTOS" 2>/dev/null || true                # F13: disparó → racha de saltos a cero
    DESTINO=cola "$GEN" "$r" >&2 || log "fábrica con incidencias" >&2
    b="$(cola_n)"; echo "$(( b>a ? b-a : 0 ))"
}
fuente_recuperacion() { # 🔁 RIEMANN · rescata huecos REALES (peor calidad, rotando) → cola. Vive de lo cedido.
    local n="$1" libre rescatados=0 req
    if [ "${MOSAIC_RECUP:-1}" != "1" ]; then echo 0; return 0; fi
    n=$(( n + ${MOSAIC_RECUP_EXTRA:-0} ))                  # 🧭 FASE 6: presupuesto extra Riemann (el clamp de 'libre' protege)
    libre=$(( MAX_COLA - $(cola_n) ))
    if [ "$libre" -lt "$n" ]; then n="$libre"; fi          # no rebasar la cola
    if [ "$n" -le 0 ]; then echo 0; return 0; fi
    while IFS= read -r req; do
        [ -n "$req" ] || continue
        if "$COLA_SH" add "$req" recuperacion >/dev/null 2>&1; then rescatados=$((rescatados+1)); fi
    done < <(RECUP_MAX="$n" MOSAIC_DIR="$MOSAIC_DIR" "$PYBIN" "$RECUPERAR_PY" 2>/dev/null)
    echo "$rescatados"
}

# drena el silo (PDFs/libros/noticias REALES) → cola, acotado por la capacidad libre.
drenar_silo() {
    local libre; libre=$(( MAX_COLA - $(cola_n) ))
    if [ "$libre" -le 0 ]; then return 0; fi
    SILO_MAX="$libre" bash "$SILO_SH" procesar >&2 || log "silo con incidencias" >&2
}

# --- 🔁 REPOSICIÓN: la fuente vacía (aportó 0) pide restock a su recolector aguas-arriba ---
# recolector de una fuente (o vacío si no tiene). oraculo_auto.sh repone LOS DOS: los
# hallazgos del oráculo y los repos que clona a cuarentena. libro/conversación/noticias
# leen de corpus fijos (Gutenberg/chats/tu corpus) → no tienen recolector aquí.
recolector_de() {
    case "$1" in
        fuente_oraculo|fuente_cuarentena) echo "$ORACULO_AUTO_SH" ;;
        *) echo "" ;;
    esac
}

# lanza un recolector en 2º plano (repone para el PRÓXIMO ciclo), con enfriamiento por fuente.
lanzar_recolector() {   # $1 script  $2 etiqueta
    [ "${REPONER:-1}" = "1" ] || return 0
    local script="$1" etq="$2" base; base="$(basename "$script" .sh)"
    [ -f "$script" ] || return 0
    local stamp="$MOSAIC_DIR/data/.reponer_$base.stamp" logf="$MOSAIC_DIR/data/reponer_$base.log"
    mkdir -p "$MOSAIC_DIR/data"
    if [ -f "$stamp" ]; then
        # mtime portable: GNU (-c %Y) primero, BSD/macOS (-f %m) de reserva; head+saneado evita basura.
        local mtime; mtime="$( { stat -c %Y "$stamp" 2>/dev/null || stat -f %m "$stamp" 2>/dev/null || echo 0; } | head -1 )"
        mtime="${mtime//[^0-9]/}"; mtime="${mtime:-0}"
        local edad=$(( $(date +%s) - mtime ))
        if [ "$edad" -lt "$REPONER_COOLDOWN" ]; then
            log "  ↻ $etq vacía · recolector $base en enfriamiento (${edad}/${REPONER_COOLDOWN}s)"; return 0
        fi
    fi
    touch "$stamp"
    local TO=""
    if   command -v gtimeout >/dev/null 2>&1; then TO="gtimeout $REPONER_TIMEOUT"
    elif command -v timeout  >/dev/null 2>&1; then TO="timeout $REPONER_TIMEOUT"; fi
    ( $TO bash "$script" >"$logf" 2>&1 ) </dev/null >/dev/null 2>&1 &
    disown 2>/dev/null || true
    log "  ↻ $etq vacía → recolector $base en 2º plano (repone p/ próximo ciclo · log: data/reponer_$base.log)"
}

# recorre las fuentes agotadas y dispara sus recolectores (un recolector, una vez por pasada).
reponer_agotadas() {
    local fn rec lanzados=" "
    for fn in "$@"; do
        [ -n "$fn" ] || continue
        rec="$(recolector_de "$fn")"
        [ -n "$rec" ] || continue
        case "$lanzados" in *" $rec "*) continue ;; esac
        lanzados="$lanzados$rec "
        lanzar_recolector "$rec" "${fn#fuente_}"
    done
}

pull() {
    local libre; libre=$(( MAX_COLA - $(cola_n) ))
    if [ "$libre" -le 0 ]; then log "cola llena ($(cola_n)/$MAX_COLA) · backpressure, no pido nada"; return 0; fi
    local total; total=$(( U_LIBRO + U_CONVERSACION + U_ORACULO + U_CUARENTENA + U_NOTICIAS + U_FABRICA ))
    log "CASCADA · $total u (1+primos) · cesión en cadena · suelo≥1 (nunca cero)"
    local orden=(
        "fuente_libro:$U_LIBRO"
        "fuente_conversacion:$U_CONVERSACION"
        "fuente_oraculo:$U_ORACULO"
        "fuente_cuarentena:$U_CUARENTENA"
        "fuente_noticias:$U_NOTICIAS"
        "fuente_recuperacion:0"
        "fuente_fabrica:$U_FABRICA"
    )
    local carry=0 e fn base presup aport
    local agotadas=()
    for e in "${orden[@]}"; do
        fn="${e%%:*}"; base="${e##*:}"
        presup=$(( base + carry ))
        if [ "$presup" -lt 1 ]; then presup=1; fi          # 🔒 suelo Collatz: nunca cero
        # antes de rellenar (recuperación/fábrica): drena el silo → material REAL primero (idempotente)
        if [ "$fn" = "fuente_recuperacion" ] || [ "$fn" = "fuente_fabrica" ]; then
            drenar_silo
        fi
        # la fábrica es el ÚLTIMO cartucho: humo solo si NO hay nada real (ni vivo, ni silo, ni rescatado)
        if [ "$fn" = "fuente_fabrica" ] && [ "$(cola_n)" -gt 0 ]; then
            sk=$(( $(cat "$FAB_SALTOS" 2>/dev/null || echo 0) + 1 ))   # F13: racha persistente
            # 🏭 HUMO FORZADO (mesa 4-jul: plan del Nuevo + deseo original de Gustavo): si la racha
            # alcanza el umbral, la fábrica dispara IGUAL una vez con su presupuesto suelo (mínimo)
            # y la racha se resetea al disparar. Así las capacidades dormidas también entrenan
            # (el sesgo 'ejercitar' del gobernador apunta la pregunta). FAB_HUMO_CADA=0 = jamás forzar.
            if [ "${FAB_HUMO_CADA:-7}" -gt 0 ] && [ "$sk" -ge "${FAB_HUMO_CADA:-7}" ]; then
                log "  ▸ 🏭 fábrica · HUMO FORZADO (racha ${sk}× ≥ umbral ${FAB_HUMO_CADA:-7}) — un respiro para las dormidas"
            else
                echo "$sk" > "$FAB_SALTOS" 2>/dev/null || true
                log "  ▸ 🏭 fábrica · SALTADA — $(cola_n) real(es) en cola (humo = último cartucho) · van $sk seguidas"
                continue
            fi
        fi
        log "  ▸ ${fn#fuente_} · $base + arrastre $carry = $presup u"
        aport="$("$fn" "$presup")"; aport="${aport//[^0-9]/}"; aport="${aport:-0}"
        if [ "$aport" -gt "$presup" ]; then aport="$presup"; fi
        carry=$(( presup - aport ))
        log "     aportó $aport · cede $carry a la siguiente"
        if [ "$aport" -eq 0 ]; then agotadas+=("$fn"); fi   # 🔁 vacía → restock al final
    done
    log "CASCADA · fin (cola $(cola_n)/$MAX_COLA · arrastre final $carry)"
    if [ "${#agotadas[@]}" -gt 0 ]; then reponer_agotadas "${agotadas[@]}"; fi
}

case "${1:-pull}" in
    pull) pull ;;
    *)    log "uso: fuentes.sh pull"; exit 1 ;;
esac
