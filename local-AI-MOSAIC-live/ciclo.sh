#!/bin/bash
# 🔄 =====================================================================
# 🔄 CICLO — el ciclo COMPLETO en UNA sola orden, por TANDAS, todo en terminal.
# 🔄 Sin segundo plano (lo que va al mini se ve con ./ver_mini.sh).
# 🔄   FASE 1 FÁBRICA  : llena la cola de preguntas hasta un tope (backpressure)
# 🔄   FASE 2 INGESTA  : vacía la cola por mosaic (respuesta A = composición)
# 🔄   FASE 3 JUICIO   : tribunal adversarial sobre una muestra (captura desde ya)
# 🔄   FASE 4 APRENDER : generar (huecos) + consolidar (juez + recompensa + poda + A/B)
# 🔄   FASE 5 PANEL    : refresca META.md y muestra el veredicto de madurez
# 🔄 Uso:  ./ciclo.sh [N]     (N ciclos; 0 o vacío = hasta Ctrl+C)
# 🔄 =====================================================================
set -euo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="$HOME_USER/Mosaic_privado"
GEN="$MOSAIC_DIR/generar_pregunta.sh"
COLA="$MOSAIC_DIR/cola.sh"
MOSAIC="$MOSAIC_DIR/mosaic.sh"
TRIBUNAL="$MOSAIC_DIR/tribunal.py"
PANEL="$MOSAIC_DIR/panel.sh"
MANT="$MOSAIC_DIR/mantenimiento.sh"
PLANTA="$MOSAIC_DIR/planta.sh"
FUENTES="$MOSAIC_DIR/fuentes.sh"
ACTA="$MOSAIC_DIR/acta.py"
GOB="$MOSAIC_DIR/gobernador.py"
# shellcheck disable=SC1091
source "$MOSAIC_DIR/lock.sh" 2>/dev/null || true
# shellcheck disable=SC1091
source "$MOSAIC_DIR/colores.sh" 2>/dev/null || true
HIST="$MOSAIC_DIR/data/historial.jsonl"
DIR_COLA="$MOSAIC_DIR/data/cola"
PAUSA_FLAG="$MOSAIC_DIR/data/pausa.flag"
CLUSTER_URL="${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8092/v1}"   # ⚔️ 3-jul: principal = Qwen3-14B (el 24B JAMÁS)
MINI="${MINI_URL:-http://localhost:8090/v1}"
LLAMA_LAUNCH="$HOME_USER/cluster/lanzar_cluster.sh"
MINI_SSH="${MINI_SSH:-$USER@localhost}"
MINI_LANZAR='m=$(ls ~/modelo/modelos_grandes/qwen25-3b/*.gguf 2>/dev/null | head -1); [ -n "$m" ] && nohup ~/modelo/llama.cpp/build/bin/llama-server -m "$m" --host 0.0.0.0 --port 8090 --ctx-size 4096 -ngl 99 --threads 8 >~/mini_llama.log 2>&1 & echo $! > ~/mini_llama.pid'   # P0 FINAL: juez = Qwen2.5-3B (especialista pequeño, doctrina de Gustavo)
ESPERA="${ESPERA_CLUSTER:-120}"

MAX_COLA="${MAX_COLA:-60}"               # capacidad del BANCO (reservorio; la cascada rellena hasta aquí)
MUESTRA_JUICIO="${MUESTRA_JUICIO:-3}"    # juicios por ciclo (el tribunal es caro)
CICLOS="${1:-1}"                        # UN ciclo por defecto; pasa "0" para bucle infinito
SILO_DIR="$MOSAIC_DIR/silo"
CUAR_DIR="$MOSAIC_DIR/cuarentena"
UMBRAL_TAREAS="${UMBRAL_TAREAS:-45}"    # rellena el banco hasta cerca del tope antes de volcar el lote
TMP_DIR="$(mktemp -d)"

log()  { printf '\n%s[%s] ▶ %s%s\n' "${FASE_COLOR:-${C_BOLD:-}}" "$(date '+%H:%M:%S')" "$*" "${C_RESET:-}"; }
# 🧭 DEBRIEF paso 1 (mesa 4-jul): fase() deja RASTRO de cada fase alcanzada (aditivo puro)
fase() { printf '%s\n' "$1" >> "$TMP_DIR/fases.log" 2>/dev/null || true; export FASE_COLOR="$(fase_color "$1")"; shift; log "$*"; }
# 🧭 DEBRIEF paso 2: incidencia VISIBLE en el log + rastro para el panel (qué falló y dónde)
ko()   { log "  ⚠ $*"; printf '%s\n' "$*" >> "$TMP_DIR/incidencias.log" 2>/dev/null || true; }
cleanup() { soltar_locks 2>/dev/null || true; rm -rf "$TMP_DIR" 2>/dev/null || true; }
trap cleanup EXIT
trap 'echo; log "Parado por ti. ./panel.sh para el estado."; exit 0' INT TERM

# 🧭 FASE 7 · si hay perfil del gobernador, manda (valores acotados y validados aquí también)
PERFIL="$MOSAIC_DIR/data/perfil_lanzamiento.json"
if [ "${MOSAIC_GOBERNADOR:-1}" = "1" ] && [ -f "$PERFIL" ]; then
    eval "$(python3 - "$PERFIL" <<'PY'
import json, sys
try: m = json.load(open(sys.argv[1])).get("mandos", {})
except Exception: m = {}
ok = lambda k, lo, hi: isinstance(m.get(k), int) and lo <= m[k] <= hi
if ok("max_cola", 30, 90):      print(f'MAX_COLA={m["max_cola"]}')
if ok("muestra_juicio", 1, 5):  print(f'MUESTRA_JUICIO={m["muestra_juicio"]}')
if ok("lote", 17, 29):          print(f'export LOTE_DISPATCH={m["lote"]}')
if ok("recup_extra", 0, 11):    print(f'export MOSAIC_RECUP_EXTRA={m["recup_extra"]}')
PY
)"
    log "🧭 perfil del gobernador: MAX_COLA=$MAX_COLA · lote=${LOTE_DISPATCH:-23} · juicio=$MUESTRA_JUICIO · recup+${MOSAIC_RECUP_EXTRA:-0}"
fi

cola_size() { "$COLA" size 2>/dev/null || echo 0; }
items_silo()       { local n=0 f; shopt -s nullglob; for f in "$SILO_DIR"/*;  do [ -f "$f" ] && n=$((n+1)); done; shopt -u nullglob; echo "$n"; }
items_cuarentena() { local n=0 f; shopt -s nullglob; for f in "$CUAR_DIR"/*; do [ -e "$f" ] && n=$((n+1)); done; shopt -u nullglob; echo "$n"; }   # cola en SQLite (cola.sh size)
esperar_si_pausa() {
    while [ -f "$PAUSA_FLAG" ]; do
        local m edad
        m="$(stat -c %Y "$PAUSA_FLAG" 2>/dev/null || stat -f %m "$PAUSA_FLAG" 2>/dev/null || echo 0)"
        [[ "$m" =~ ^[0-9]+$ ]] || m=0
        edad=$(( $(date +%s) - m ))
        if [ "$edad" -gt "${VIGIA_MAXEDAD:-900}" ]; then
            log "⚠️  bandera de pausa vieja (${edad}s, ¿vigía muerto?) → la quito y sigo"
            rm -f "$PAUSA_FLAG"; break
        fi
        log "⏸️  vigía: MacBook a tope, espero 30s…"; sleep 30
    done
}

vivo() { curl -s -m 3 "$1/models" >/dev/null 2>&1; }
asegurar_cluster() {
    # 🚀 Tarea 2 (Gustavo): ./mosaic.sh ciclo levanta la flota ENTERA automáticamente.
    # Si el lanzador nuevo existe (habla servidores.conf), 'subir' comprueba TODO el roster
    # (las 2 máquinas), levanta SOLO lo caído en orden y espera a que INFIERA. Idempotente.
    if [ -x "$LLAMA_LAUNCH" ] && grep -q 'SERVIDORES_CONF' "$LLAMA_LAUNCH" 2>/dev/null; then
        log "flota → $LLAMA_LAUNCH subir (roster completo: comprueba, levanta lo caído, espera inferencia)"
        "$LLAMA_LAUNCH" subir 2>&1 | sed 's/^/    /' || log "⚠️  flota con bajas (sigo con lo que vive)"
        vivo "$CLUSTER_URL" && { log "principal (8092) ✅ infiriendo"; return 0; }
        log "⚠️  el principal (8092) no responde tras el subir"; return 1
    fi
    # (fallback: lanzador antiguo — comportamiento de siempre)
    vivo "$CLUSTER_URL" && { log "cluster ✅ ya arriba"; return 0; }
    [ -x "$LLAMA_LAUNCH" ] || { log "⚠️  cluster caído y no encuentro $LLAMA_LAUNCH"; return 1; }
    log "cluster caído → lo lanzo (anunciado, no oculto): $LLAMA_LAUNCH"
    mkdir -p "$HOME_USER/cluster/logs"
    nohup "$LLAMA_LAUNCH" > "$HOME_USER/cluster/logs/cluster.auto.log" 2>&1 &
    local t=0; until vivo "$CLUSTER_URL"; do sleep 3; t=$((t + 3)); [ "$t" -ge "$ESPERA" ] && { log "⚠️  cluster sin respuesta tras ${t}s"; return 1; }; done
    log "cluster ✅ arriba (${t}s)"
}
asegurar_mini() {
    vivo "$MINI" && { log "mini ✅ ya arriba"; return 0; }
    command -v ssh >/dev/null 2>&1 || { log "⚠️  sin ssh; el juez caerá al principal (8092)"; return 1; }
    log "mini caído → lo lanzo por SSH (míralo con ./ver_mini.sh)"
    ssh -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new "$MINI_SSH" "$MINI_LANZAR" >/dev/null 2>&1 \
        || { log "⚠️  no pude lanzar el mini; el juez caerá al principal (8092)"; return 1; }
    local t=0; until vivo "$MINI"; do sleep 3; t=$((t + 3)); [ "$t" -ge "$ESPERA" ] && { log "⚠️  mini sin respuesta tras ${t}s; juez al principal (8092)"; return 1; }; done
    log "mini ✅ arriba (${t}s)"
}

# LOCK: solo un orquestador a la vez (evita pisar el aprendizaje y doble cluster).
tomar_lock orquestador || { log "Ya hay un ciclo/aprendizaje en marcha. Salgo."; exit 1; }
export MOSAIC_EN_ORQUESTADOR=1

# FASE 0 · ASEGURAR INFRA: enciende cluster + mini ANTES de empezar (visible).
fase 0 "═══════════ FASE 0 · ASEGURAR INFRA (cluster + mini) ═══════════"
asegurar_cluster || log "sigo igualmente (puede fallar la ingesta)"
if asegurar_mini; then
    export MOSAIC_JUDGE_URL="$MINI"           # 2º cerebro: el principal genera, el mini JUZGA (descarga el MacBook)
    log "juez → mini ($MINI) · el MacBook se libera para generar"
else
    log "sigo igualmente (juez al principal 8092)"
fi

# 🤖 la VOZ de MOSAIC: parte de guardia factual a la mesa (info/CARTAS.md; calla si nada cambió)
[ -f "$MOSAIC_DIR/mosaic_voz.py" ] && { python3 "$MOSAIC_DIR/mosaic_voz.py" | sed 's/^/    /' || true; }

i=0
while [ "$CICLOS" -eq 0 ] || [ "$i" -lt "$CICLOS" ]; do
    i=$((i + 1))
    export FASE_COLOR="${C_BOLD:-}${C_CYAN:-}"; log "═══════════ CICLO $i ═══════════"
    esperar_si_pausa

    # FASE 1 · FUENTES: ¿hay bastantes tareas? las proceso. ¿No? la cascada 29u (fuentes.sh) decide qué ingerir.
    fase 1 "FASE 1 · FUENTES (decide qué hacer según el estado)"
    # F6 handoff: trae la despensa del mini (recolector) en 2º plano — NO bloquea (timeout dentro del script)
    [ -x "$MOSAIC_DIR/recoger_del_mini.sh" ] && "$MOSAIC_DIR/recoger_del_mini.sh" >/dev/null 2>&1 &
    actual="$(cola_size)"
    if [ "$actual" -ge "$UMBRAL_TAREAS" ]; then
        log "  ✅ hay $actual tareas en cola → directo a procesarlas (no busco más)"
    else
        cuar="$(items_cuarentena)"; sil="$(items_silo)"
        log "  cola baja ($actual) · material local: cuarentena=$cuar · silo=$sil"
        # 🚰 orquestadora ÚNICA: la cascada 29u decide todo (libro→conversación→oráculo→
        #    cuarentena→noticias→fábrica) con cesión y suelo. Presupuestos exactos, sin
        #    pre-relleno ad-hoc que los descuadrara. (El crawler oraculo_auto.sh va aparte.)
        log "  🚰 cascada única: libro→conversación→oráculo→cuarentena→noticias→fábrica (29u · cesión · suelo)"
        if [ "${CASCADA_BG:-1}" = "1" ] && [ "$actual" -gt 0 ]; then
            # F7 (Opus · 4-jul): la cascada (CPU) rellena el banco en 2º PLANO mientras FASE 2 (GPU)
            #   ingiere lo que ya hay. El banco (SQLite WAL + claim atómico) es el buffer seguro.
            #   Solo si hay algo que ingerir YA (actual>0); en frío se rellena síncrono. Kill-switch: CASCADA_BG=0.
            log "  🚰⚡ F7: cascada en 2º plano (solapa con la ingesta GPU); se recoge al cierre del ciclo"
            MAX_COLA="$MAX_COLA" "$FUENTES" pull > "$TMP_DIR/cascada_bg.log" 2>&1 &
            CASCADA_PID=$!
        else
            MAX_COLA="$MAX_COLA" "$FUENTES" pull || ko "F1 fuentes: pull con incidencias (sigo) · fuentes.sh"
        fi
    fi

    # FASE 2 · INGESTA: vaciar la cola por mosaic (cada pregunta → composición A)
    fase 2 "FASE 2 · INGESTA: vaciar la cola ($(cola_size)) por mosaic"
    if [ "${PIPELINE:-auto}" != "0" ] && [ -n "${MOSAIC_JUDGE_URL:-}" ]; then   # PIPELINE automático si el mini está arriba (sin flags)
        log "  modo PIPELINE (auto): el principal (mediano) genera ‖ el mini juzga — ./mini.sh ver"
        "$COLA" discriminar > "$TMP_DIR/lote.txt" 2>/dev/null || true   # paso 3: lote diverso (no todo)
        if [ -s "$TMP_DIR/lote.txt" ]; then
            if "$MOSAIC" aprender --pipeline --peticiones "$TMP_DIR/lote.txt"; then
                "$COLA" confirmar >/dev/null || true
            else
                ko "F2 ingesta: pipeline con incidencias; items sin confirmar (reintentarán) · mosaic.py::aprender"
            fi
        else
            log "  (cola vacía, nada que pipelinear)"
        fi
    else
        "$COLA" run --once || ko "F2 ingesta: run --once con incidencias (sigo) · cola.sh"
    fi

    # FASE 3 · JUICIO: tribunal adversarial sobre una muestra de lo recién hecho
    fase 3 "FASE 3 · JUICIO: tribunal sobre $MUESTRA_JUICIO de la última tanda"
    python3 -c '
import json, os, sys
res, hist, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = []
# P0: preferir la ÚLTIMA tanda (registros.json con output); el historial (USO REAL) queda de reserva
try:
    ts = sorted(d for d in os.listdir(res) if d.startswith("aprendizaje_")
                and os.path.isfile(os.path.join(res, d, "registros.json")))
    if ts:
        rows = json.load(open(os.path.join(res, ts[-1], "registros.json"), encoding="utf-8"))
except Exception:
    rows = []
if not any((r.get("output") or "").strip() for r in rows):
    rows = []
    try:
        for ln in open(hist, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except Exception: pass
    except FileNotFoundError:
        pass
for r in rows[-n:]:
    req = (r.get("request") or "").replace("\t", " ").replace("\n", " ")
    ans = (r.get("output") or "").replace("\t", " ").replace("\n", " ")
    if req and ans:
        print(req + "\t" + ans)
' "$MOSAIC_DIR/resultados" "$HIST" "$MUESTRA_JUICIO" > "$TMP_DIR/muestra.tsv" 2>/dev/null || true
    if [ -s "$TMP_DIR/muestra.tsv" ]; then
        # P1: tribunal en 2º plano — solapa con FASE 4-generar; se recoge antes de consolidar
        python3 "$TRIBUNAL" --lote "$TMP_DIR/muestra.tsv" > "$TMP_DIR/tribunal.log" 2>&1 &
        TRIBUNAL_PID=$!
        log "  tribunal en 2º plano (solapa con FASE 4-generar; se recoge antes de consolidar)"
    else
        TRIBUNAL_PID=""
        log "  (sin respuestas que juzgar todavía)"
    fi

    # FASE 4 · APRENDER: cubrir huecos + consolidar (juez + recompensa + poda + A/B)
    fase 4 "FASE 4 · APRENDER: generar (huecos) + consolidar (juez + poda + A/B)"
    "$MOSAIC" generar    || ko "F4 aprender: generar con incidencias (sigo) · mosaic.py::generar_capacidades"
    if [ -n "${TRIBUNAL_PID:-}" ]; then                     # P1: recoge el tribunal solapado
        wait "$TRIBUNAL_PID" 2>/dev/null || true
        tail -n 12 "$TMP_DIR/tribunal.log" 2>/dev/null | sed 's/^/    /' || true
        log "  tribunal recogido ✅"
    fi
    if "$MANT" disco >/dev/null 2>&1; then
        "$MOSAIC" consolidar || ko "F4 aprender: consolidar con incidencias (sigo) · mosaic.py"
    else
        log "⚠️  disco bajo (./mantenimiento.sh disco) → salto consolidar este ciclo"
    fi
    # predictor de tokens: reentrena con la tanda nueva (solo datos, sin cluster) y queda encendido
    "$MOSAIC" entrenar-predictor >/dev/null 2>&1 && log "  🔮 predictor reentrenado con la tanda nueva" || true

    # FASE 5 · PANEL
    fase 5 "FASE 5 · PANEL"
    "$PANEL" >/dev/null 2>&1 || true
    tail -n 8 "$MOSAIC_DIR/data/META.md" 2>/dev/null | sed 's/^/    /' || true

    # FASE 6 · ACTA: destila el ciclo a data/actas/ (propiocepción; la FASE 7 leerá ESTO, no el stdout crudo)
    #   RENUMERADO 4-jul (Gustavo): el acta se ESCRIBE antes de que el gobernador la digiera →
    #   acta=6 · gobernador=7, para que números = orden real = orden en pantalla (ya no "7 antes que 6").
    fase 6 "FASE 6 · ACTA: destilar el ciclo → data/actas/"
    [ -f "$ACTA" ] && { python3 "$ACTA" | sed 's/^/    /' || ko "F6 acta: con incidencias (sigo) · acta.py"; } || log "  (sin acta.py, salto)"

    # FASE 7 · GOBERNADOR: digiere las actas y afina el PRÓXIMO lanzamiento (jamás mira la nota)
    fase 7 "FASE 7 · GOBERNADOR: perfil para el próximo lanzamiento"
    [ -f "$GOB" ] && { python3 "$GOB" | sed 's/^/    /' || ko "F7 gobernador: con incidencias (sigo) · gobernador.py"; } || log "  (sin gobernador.py, salto)"

    # planta de residuos: rota logs crecientes a frío, valoriza materia prima, poda + rotar trash (#71)
    "$PLANTA" tratar >/dev/null 2>&1 || true

    # F7 (Opus · 4-jul): recoge la cascada de 2º plano antes del próximo ciclo (fuentes.sh termina
    #   solo al llenar el banco). Calca el patrón del tribunal solapado (FASE 3).
    if [ -n "${CASCADA_PID:-}" ]; then
        wait "$CASCADA_PID" 2>/dev/null || true
        tail -n 6 "$TMP_DIR/cascada_bg.log" 2>/dev/null | sed 's/^/    /' || true
        log "  🚰 F7: cascada de 2º plano recogida ✅ (banco listo para el próximo ciclo)"
        CASCADA_PID=""
    fi

    # 🧭 DEBRIEF paso 4 (mesa 4-jul, diseño Opus 13:10): el mapa del ciclo en ~20 líneas con
    # anclas grep-ables y colores (petición de Gustavo). Aditivo puro · kill-switch DEBRIEF=0.
    # En frío (sin ciclo): ./debrief.sh reimprime el del último acta.
    [ "${DEBRIEF:-1}" = "1" ] && [ -x "$MOSAIC_DIR/debrief.sh" ] \
        && { DEBRIEF_FASES="$TMP_DIR/fases.log" DEBRIEF_INC="$TMP_DIR/incidencias.log" "$MOSAIC_DIR/debrief.sh" || true; }
done
log "Hecho: $i ciclos completos."

# 🔻 P4 (conectado 4-jul, petición de Gustavo: "los modelos se quedan esperando"): al ACABAR el
# one-shot, la flota BAJA en orden — 1º mini VERIFICADO (kill -9 si resiste) → 2º MacBook — y
# cubre fijos Y demanda (mopa también un 8096 adoptado). El bucle continuo exporta
# MOSAIC_MANTENER_FLOTA=1 (la mantiene entre ciclos y la baja ÉL al terminar TODO).
# MOSAIC_BAJAR_AL_ACABAR=0 → dejarla viva a propósito (p. ej. para probar a mano tras el ciclo).
# Ctrl+C NO baja nada (el trap INT sale antes): interrumpir ≠ apagar.
if [ "${MOSAIC_BAJAR_AL_ACABAR:-1}" = "1" ] && [ "${MOSAIC_MANTENER_FLOTA:-0}" != "1" ] \
   && [ -x "$LLAMA_LAUNCH" ] && grep -q 'SERVIDORES_CONF' "$LLAMA_LAUNCH" 2>/dev/null; then
    log "🔻 fin del ciclo → flota abajo en ORDEN (mini verificado → MacBook) · para dejarla viva: MOSAIC_BAJAR_AL_ACABAR=0"
    "$LLAMA_LAUNCH" bajar 2>&1 | sed 's/^/    /' || log "⚠️  apagado con incidencias — revisa: $LLAMA_LAUNCH estado"
else
    log "🛏️  flota se queda VIVA (bucle continuo o MOSAIC_BAJAR_AL_ACABAR=0)"
fi
