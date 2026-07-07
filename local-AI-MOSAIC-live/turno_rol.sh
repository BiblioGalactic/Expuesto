#!/usr/bin/env bash
# 🎭 =====================================================================
# 🎭 TURNO_ROL — el motor GENÉRICO de sillas (P4 orquesta · molde de autodiagnosis).
# 🎭   Un rol = un yaml en roles/turnos/<rol>.yaml (prompt · lecturas · puertos ·
# 🎭   firma · tipo de reporte). N roles = N yamls, UNA sola fuente de salvaguardas:
# 🎭     · permiso ACOTADO: leer lo listado → componer (mosaic.sh) → depositar UNA
# 🎭       carta (reportar.sh). Palabra, jamás manos. Cero rm/curl-de-datos/ssh/eval.
# 🎭     · pre-vuelo de analista (sonda → un `subir` idempotente → tope de espera).
# 🎭     · tope duro de contexto por lectura y total (jamás petar el modelo).
# 🎭     · captura base64 + no-postear-vacío + pie de transparencia con la receta.
# 🎭     · si el rol promete una Acción y no cumple la plantilla → cae a Informe
# 🎭       avisando (no se pierde la palabra, no se cuela una Acción coja).
# 🎭   Kill-switches: TURNOS=0 (todos) · TURNO_<ROL>=0 (uno).
# 🎭 Uso:  ./turno_rol.sh <rol>          (el turno: lee, compone y postea)
# 🎭       ./turno_rol.sh <rol> --dry    (enseña prompt y sonda; NO postea)
# 🎭 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
MOSAIC_SH="$BASE/mosaic.sh"                 # RUTA 1 (única de composición)
REPORTAR="$BASE/reportar.sh"                # RUTA 2 (única de escritura: un reporte)
SERVIDORES="$BASE/servidores.conf"
TURNOS_DIR="${TURNOS_DIR:-$BASE/roles/turnos}"
LLAMA_LAUNCH="${LLAMA_LAUNCH:-$HOME/cluster/lanzar_cluster.sh}"
ESPERA="${ESPERA:-120}"
# host de la flota: de la CONFIG, no fijo (auditoría Opus 00:14 — regresión de portabilidad).
# Prioridad: TURNO_HOST > el host de MOSAIC_LLM_BASE_URL (.env) > el default de la casa.
_host_de_url() { printf '%s' "$1" | sed -E 's#^[a-z]+://([^:/]+).*#\1#'; }
HOSTIP="${TURNO_HOST:-$(_host_de_url "${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8092/v1}")}"

ROL="${1:-}"; DRY=0; [ "${2:-}" = "--dry" ] && DRY=1
# ⚓ el ANCLA de respuesta (fix eco Opus 15:41): última línea del prompt Y tijera de la captura
ANCLA="${TURNO_ANCLA:-Mi parte (en ESPAÑOL, empiezo aquí, sin repetir nada de lo anterior):}"

# 🔒 anti-solape (estudio 15:46, hueco 1): el lock de la casa — se toma SOLO si este turno
#    es manual y razonador (dentro de ciclo/pleno ya lo sostiene el padre: EN_ORQUESTADOR)
export LOCK_BASE="${LOCK_BASE:-$BASE/data}"
# shellcheck disable=SC1091
source "$BASE/lock.sh" 2>/dev/null || true

TMPS=()
cleanup() { soltar_locks 2>/dev/null || true; for t in "${TMPS[@]:-}"; do [ -n "${t:-}" ] && rm -f "$t" 2>/dev/null || true; done; }
trap cleanup EXIT
log() { printf '[%s] 🎭 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    [ -n "$ROL" ] || { err "uso: ./turno_rol.sh <rol> [--dry] · roles: $(ls "$TURNOS_DIR" 2>/dev/null | sed 's/\.yaml//' | tr '\n' ' ')"; exit 2; }
    [[ "$ROL" =~ ^[a-z0-9_-]+$ ]] || { err "rol inválido: $ROL"; exit 2; }
    [ "${TURNOS:-1}" = "1" ] || { log "TURNOS=0 → todos los turnos desactivados"; exit 0; }
    # expansión INDIRECTA ${!sw} — cero eval en el fichero (auditoría 2 de Opus; $ROL ya saneado)
    local sw; sw="TURNO_$(printf '%s' "$ROL" | tr 'a-z-' 'A-Z_')"
    [ "${!sw:-1}" = "1" ] || { log "$sw=0 → turno de $ROL desactivado"; exit 0; }
    [ -f "$TURNOS_DIR/$ROL.yaml" ] || { err "no existe el rol: $TURNOS_DIR/$ROL.yaml"; exit 1; }
    for c in python3 curl; do command -v "$c" >/dev/null || { err "falta $c"; exit 1; }; done
    python3 -c 'import yaml' 2>/dev/null || { err "falta pyyaml"; exit 1; }
    # mosaic.sh solo lo necesitan los RAZONADORES — se comprueba en su rama (un N3
    # parte-de-estado funciona hasta en una caja sin motor, con la flota abajo)
    [ -f "$REPORTAR" ]  || { err "no encuentro reportar.sh (la única ruta de escritura)"; exit 1; }
}

vivo() { curl -s -m 3 "$1/models" >/dev/null 2>&1; }

# pre-vuelo (molde de autodiagnosis · Opus 18:15): stdout = SOLO el puerto; logs a stderr
asegurar_analista() {
    local cands_str="$1" cands=() p t
    read -r -a cands <<< "$cands_str"
    for p in "${cands[@]}"; do
        vivo "http://${HOSTIP}:${p}/v1" && { echo "$p"; return 0; }
    done
    if [ ! -x "$LLAMA_LAUNCH" ]; then
        err "ningún analista arriba y no encuentro el lanzador: $LLAMA_LAUNCH"; return 1
    fi
    log "ningún analista arriba → «${LLAMA_LAUNCH} subir» (idempotente; tope ${ESPERA}s)…" >&2
    "$LLAMA_LAUNCH" subir >&2 2>&1 || err "el subir devolvió error — re-pruebo igual"
    t=0
    until [ "$t" -ge "$ESPERA" ]; do
        for p in "${cands[@]}"; do
            vivo "http://${HOSTIP}:${p}/v1" && { echo "$p"; return 0; }
        done
        sleep 3; t=$((t + 3))
    done
    err "ningún analista tras ${ESPERA}s; revisa: $LLAMA_LAUNCH subir"
    return 1
}

nombre_de() {
    # 🩹 P8 (prima de la mina 627, clase distinta): bajo `pipefail`, si $SERVIDORES faltara,
    #    awk sale 2 → la asignación mata el turno a mitad de vuelo. El `|| true` en el primer
    #    eslabón lo desactiva; el fallback ${nom:-} de abajo ya hacía el resto.
    local nom
    nom="$( { awk -F'|' -v pt="$1" '$1=="macbook" && $2==pt {print $5}' "$SERVIDORES" 2>/dev/null || true; } \
          | sed -E 's#.*/##; s#\*##g; s#\.gguf##' | head -1)"
    echo "${nom:-modelo-$1}"
}

# 🎯 DEBUT (diagnóstico Opus 21:15, arreglo #3): LA ORQUESTA ES DUEÑA DE SU PROMPT.
#   Antes turno_rol pasaba el prompt ENTERO a mosaic.py, que lo RE-ENVOLVÍA en su máscara
#   efímera (doble envoltorio → el razonador divagaba en <think> y no cerraba → vacío ×6).
#   El yaml del rol YA ES la máscara: se llama al modelo DIRECTO (system=rol, user=tarea),
#   saltando mosaic.py. Aire para razonar (max_tokens holgado) + /no_think a Qwen3 (arreglo
#   #2). Escribe out.json compatible {output, composed:[]}. Requiere: curl + python3 (ya
#   validados). Devuelve 0 si el server respondió (aunque el content venga vacío: eso lo
#   juzga el parser con red, arreglo #1).
generar_directo() {
    local url="$1" modelo="$2" prompt_f="$3" out_json="$4"
    local sys_txt user_txt maxtok="${TURNO_MAXTOK:-1200}"
    sys_txt="$(cat "$prompt_f")"
    user_txt="Da tu parte para la mesa AHORA, en español, directo y sin repetir estas instrucciones."
    # 🩺 DIAGNÓSTICO 6-jul (Gustavo · el pleno mudo): TODOS los N2 razonadores salían VACÍOS
    #    y el portavoz NO. Causa: cuando 8092 está ocupado en un pleno de 7 llamadas, la sonda
    #    cae a 8094 = DeepSeek-R1-Qwen3-8B. Su nombre contiene «Qwen3» → el case de abajo le
    #    metía «/no_think»… pero DeepSeek-R1 es un RAZONADOR OBLIGATORIO que lo IGNORA y quema
    #    los 1200 tokens pensando → content vacío. (auditor e infraestructura comparten el
    #    fallback [8092,8094]: por eso «infra falla como el auditor».)
    # EL FIX: DeepSeek PRIMERO en el case (su nombre matchea ambos ramas) — SIN /no_think y
    #    con sitio para pensar Y responder; la tijera </think> de la captura extrae la parte.
    #    Qwen3-chat (14B) sí obedece /no_think → responde directo. Configurable por env.
    # 🗂️ CATÁLOGO probado (Opus 00:45, 11 modelos) — REGLA 1: los RAZONADORES primero (el
    #    *Thinking* matchearía el /no_think de abajo y lo silenciaría); Qwen3-CHAT sí frena.
    case "$modelo" in
        *[Tt]hinking*)
            # regla 1 (Opus 00:45): el director (30B-A3B) es PESADO pensando — ~2000 para
            # rematar. VA PRIMERO: si cayera al *Qwen3* de abajo el /no_think lo silenciaría
            # (la trampa que la regla mata). Env ÚNICO TURNO_MAXTOK_THINK (nit Opus 14:55).
            maxtok="${TURNO_MAXTOK_THINK:-2000}" ;;
        *[Dd]eep[Ss]eek*|*-R1*|*_R1*)
            maxtok="${TURNO_MAXTOK_RAZON:-800}" ;;           # R1-distill: con 600-800 remata (probado)
            # ⚠️ PRESUPUESTO (Opus 03:35): @8092/@8094 dan 4096 de ctx efectivo (--parallel 2).
        *[Qq]wen3*)
            user_txt="/no_think $user_txt" ;;               # Qwen3-CHAT: apaga el pensamiento
    esac
    # 🧮 P1 (plan 6-jul · estudio Opus 03:55): PRESUPUESTO determinista PRE-envío — maxtok
    #    calculado por modelo (ctx÷parallel + oxígeno + techo por tipo + reserva de pensar R1,
    #    D23) y recorte de lecturas-viejas-primero si el prompt no cabe (D13). Salvaguardas:
    #    PRESUPUESTO=0 lo apaga · un env TURNO_MAXTOK*/TURNO_MAXTOK_RAZON explícito MANDA (modo
    #    manual, ni se llama) · si la calculadora falla, sigue el maxtok de arriba (un turno
    #    JAMÁS muere por su contable). bash 3.2-safe: python por FICHERO, cero heredoc aquí.
    if [ "${PRESUPUESTO:-1}" = "1" ] && [ -z "${TURNO_MAXTOK:-}${TURNO_MAXTOK_RAZON:-}" ] \
       && [ -f "$BASE/presupuesto_contexto.py" ]; then
        local _tipo_p _plan _mt _rec
        case "${TIPO:-Informe}" in Accion|Acción) _tipo_p="accion" ;; *) _tipo_p="informe" ;; esac
        _plan="$(MOSAIC_BASE="$BASE" python3 "$BASE/presupuesto_contexto.py" --url "$url" \
                 --modelo "$modelo" --tipo "$_tipo_p" --prompt-file "$prompt_f" \
                 --trim-out "$prompt_f.rec" --plano 2>>"$out_json.err" || true)"
        _mt="$(printf '%s' "$_plan" | sed -n 's/.*maxtok=\([0-9]*\).*/\1/p')"
        _rec="$(printf '%s' "$_plan" | sed -n 's/.*recortado=\([0-9]*\).*/\1/p')"
        if [ -n "$_mt" ]; then
            maxtok="$_mt"
            [ "$_rec" = "1" ] && [ -s "$prompt_f.rec" ] && sys_txt="$(cat "$prompt_f.rec")"
            log "🧮 presupuesto: $_plan"
        else
            err "presupuesto sin respuesta (mira $out_json.err) — sigo con maxtok=$maxtok"
        fi
    fi
    SYS_T="$sys_txt" USER_T="$user_txt" MODELO_T="$modelo" URL_T="$url/chat/completions" \
        MAXTOK_T="$maxtok" OUT_T="$out_json" python3 - <<'PY'
import json, os, urllib.request
# 🗂️ REGLA 2 del catálogo (Opus 00:45): content vacío + reasoning_content lleno = el modelo
#    AÚN PENSABA → no es un vacío: se reintenta UNA vez con más aire; si sigue rematando en
#    el razonamiento, ese razonamiento es el RESPALDO (mejor palabra pensada que silencio).
maxtok = int(os.environ["MAXTOK_T"])
content = reasoning = ""
for intento in (1, 2):
    payload = {"model": os.environ["MODELO_T"],
               "messages": [{"role": "system", "content": os.environ["SYS_T"]},
                            {"role": "user", "content": os.environ["USER_T"]}],
               "max_tokens": maxtok, "temperature": 0.7}
    req = urllib.request.Request(os.environ["URL_T"], data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer not-needed"})
    try:
        with urllib.request.urlopen(req, timeout=int(os.environ.get("TURNO_TIMEOUT", "150"))) as r:
            d = json.loads(r.read().decode())
        msg = (d.get("choices") or [{}])[0].get("message", {}) or {}
        content = (msg.get("content") or "").strip()
        reasoning = (msg.get("reasoning_content") or "").strip()
    except Exception as e:
        content = reasoning = ""
        open(os.environ["OUT_T"] + ".err", "w", encoding="utf-8").write(f"{type(e).__name__}: {e}")
        break
    if content or not reasoning:
        break                                              # respuesta real, o vacío de verdad
    maxtok = min(maxtok * 2, 2400)                         # pensaba → más aire y otra vez
if not content and reasoning:
    content = "(respaldo: el modelo remató en su razonamiento)\n" + reasoning[-1600:]
json.dump({"output": content, "composed": []},
          open(os.environ["OUT_T"], "w", encoding="utf-8"), ensure_ascii=False)
PY
}

ejecutar() {
    local tmpd conf prompt_f out_json puerto nom respuesta ncaps caps fecha cuerpo pie titulo
    ROUTER_AVISO=""
    tmpd="$(mktemp -d "${TMPDIR:-/tmp}/turno.XXXXXX")"; TMPS+=("$tmpd/conf.env" "$tmpd/prompt.txt" "$tmpd/out.json" "$tmpd/parte.txt" "$tmpd/externo.flag" "$tmpd/rep.err" "$tmpd/esc_ids" "$tmpd/sin_datos.flag" "$tmpd/parse.py" "$tmpd/herr.py" "$tmpd/esc.py" "$tmpd/prompt.txt.rec")

    # ── cargar el yaml del rol (python: valores shell-safe + prompt + lecturas) ──
    ROL_YAML="$TURNOS_DIR/$ROL.yaml" TMPD="$tmpd" BASE_D="$BASE" ANCLA_T="$ANCLA" python3 - <<'PY'
import os, shlex, yaml
d = yaml.safe_load(open(os.environ["ROL_YAML"], encoding="utf-8"))
tmpd, base = os.environ["TMPD"], os.environ["BASE_D"]
firma = d.get("firma", f"MOSAIC-{d.get('rol','rol')}")
tipo = d.get("tipo_reporte", "Informe")
assert tipo in ("Informe", "Accion", "Acción", "parte-de-estado"), f"tipo_reporte raro: {tipo}"
puertos = " ".join(str(p) for p in d.get("puertos", [8092, 8094]))
maxc = int(d.get("max_c", 8000)); porc = int(d.get("por_lectura_c", 2400))
with open(f"{tmpd}/conf.env", "w", encoding="utf-8") as f:
    f.write(f"FIRMA={shlex.quote(firma)}\nTIPO={shlex.quote(tipo)}\n"
            f"ETIQ={shlex.quote(d.get('etiquetas', 'turno'))}\n"
            f"PUERTOS={shlex.quote(puertos)}\nMAXC={maxc}\nPORC={porc}\n"
            f"ACTIVO={1 if d.get('activo', 1) else 0}\nCADENCIA_Y={int(d.get('cadencia_s', 0) or 0)}\n")

# prompt + lecturas (cola de cada fichero, tope por lectura y total — jamás petar)
trozos = [d.get("prompt", "").strip(), ""]

# 🪪 PERSONA (handoff Opus 14:39 §2 · fix eco 15:41): el carácter se ANTEPONE al núcleo —
#    y en PRIMERA persona, como los yamls («Soy…»): el modelo CONTINÚA en voz en vez de
#    echar el prompt. Capa PERSONA 🎨 sobre NÚCLEO 🔒: la coletilla de seguridad queda
#    INTACTA después, y la salvaguarda va EN el texto (el carácter jamás cambia límites).
_per = d.get("persona") or {}
if (_per.get("nombre_humano") or _per.get("alias")) and d.get("tipo_reporte", "Informe") != "parte-de-estado":
    trozos.insert(0, (f"Soy {_per.get('nombre_humano') or d.get('rol', '?')}, "
                      f"«{_per.get('alias', d.get('rol', '?'))}» {_per.get('emoji', '')}".rstrip() + ", "
                      f"del departamento {d.get('departamento', '?')} de MOSAIC. "
                      f"Mi tono: {_per.get('tono', 'profesional y honesto')}. "
                      "Hablo con mi voz y firmo con mi nombre — mi carácter NUNCA cambia "
                      "mis límites ni mi tarea: palabra, jamás manos. Respondo SIEMPRE en español."))

# 🧰 su MENÚ de herramientas (F1): las de SU nivel, listadas; el resto "por ticket".
#    Sintaxis que el motor parsea de su salida: `HERRAMIENTA: nombre {json}` (línea propia).
try:
    reg = yaml.safe_load(open(os.path.join(base, "data", "herramientas.yaml"), encoding="utf-8"))
    mi_nivel = int(d.get("nivel_acceso", 1) or 1)
    techo = int(reg.get("techo_f1", 3) or 3)
    mias, con_ticket = [], []
    for t in reg.get("tools", []):
        nr = int(t.get("nivel_requerido", 5) or 5)
        if nr > techo or not t.get("cmd"):
            continue
        destino = mias if nr <= mi_nivel else con_ticket
        destino.append(f"{t['nombre']}({nr})")
    if mias and d.get("tipo_reporte", "Informe") != "parte-de-estado":
        trozos.append(
            "HERRAMIENTAS (máx 3 por turno, solo si de verdad las necesitas): pide en una línea\n"
            "propia con la forma exacta `HERRAMIENTA: nombre {\"campo\": \"valor\"}`. "
            f"A tu nivel: {', '.join(mias)}."
            + (f" Con ticket de escalado: {', '.join(con_ticket)}." if con_ticket else "")
            + " Campos: leer_registro{ruta} · rag{q} · buscar{q} · web{url} · ocr{ruta} · depositar{texto}."
            + " Si pides por ENCIMA de tu nivel, tu ticket nace solo — puedes fijarle prioridad"
            + " añadiendo \"_prioridad\": \"baja|normal|alta|urgente\" al json.")
        trozos.append("")
except Exception:
    pass                                                  # sin registro de tools → sin menú (nada se rompe)

# 🎫 ESCALADO (plan Opus 13:56): su bandeja de RANGO (los tickets que el auto-dispatch le
#    subió — los ve EN SU TURNO, cadencia manda) + las SUYAS ya cerradas (cierre del lazo).
#    Sintaxis que el motor parsea de su salida: `ESCALACION: ESC-… conceder|denegar|escalar motivo`.
try:
    if d.get("tipo_reporte", "Informe") != "parte-de-estado":
        import json as _json
        import subprocess as _sp

        def _esc(*fl):
            r = _sp.run(["python3", os.path.join(base, "herramientas.py"), "--esc", "listar", *fl],
                        capture_output=True, text=True, timeout=25, env={**os.environ, "MOSAIC_BASE": base})
            try:
                return _json.loads(r.stdout or "{}").get("result") or []
            except Exception:
                return []
        rol_n = str(d.get("rol", ""))
        bandeja = _esc("--rango", rol_n)[:3]
        if bandeja:
            lin = ["🎫 ESCALACIONES EN TU RANGO — decide cada una con UNA línea propia EXACTA:",
                   "`ESCALACION: <id> conceder|denegar|escalar <motivo breve>`",
                   "(conceder EJECUTA la tool con el payload del ticket; sin línea = sigue en revisión)."]
            for t in bandeja:
                lin.append(f"- {t['id']} · {t.get('prioridad','?')} · {t.get('agente_origen','?')} pide "
                           f"{t.get('herramienta','?')}(niv {t.get('nivel_requerido','?')}) · "
                           f"payload: «{str(t.get('payload',''))[:90]}»")
            trozos.append("\n".join(lin))
            trozos.append("")
            open(f"{tmpd}/esc_ids", "w", encoding="utf-8").write("\n".join(t["id"] for t in bandeja))
        cerradas = [t for t in _esc("--origen", rol_n)
                    if t.get("estado") in ("resuelto", "denegado", "esperando_sello")][:2]
        if cerradas:
            lin = ["🎫 TUS ESCALACIONES (ya cerradas — el resultado, si lo hay, es LECTURA):"]
            for t in cerradas:
                res = t.get("resultado") or {}
                lin.append(f"- {t['id']} {t.get('herramienta','?')} → {t.get('estado','?')} · "
                           f"{str(res.get('extracto') or res.get('motivo') or res.get('nota') or '')[:120]}")
            trozos.append("\n".join(lin))
            trozos.append("")
except Exception:
    pass                                                  # sin libro de escalaciones → sin bandeja (nada se rompe)
parte = [f"📋 PARTE DE ESTADO · {d.get('rol','?')} (determinista — sin modelo, N3)", ""]
import time as _t
trago_exterior = False
tot_lect, con_datos = 0, 0                                 # anti-alucinación (fix Opus 15:41)
for ruta in d.get("lecturas", []):
    tot_lect += 1
    p = os.path.join(base, ruta)
    if os.path.isdir(p):
        # 📮 lectura de DIRECTORIO (buzones): los 3 ficheros más recientes, tail-capados
        ficheros = sorted((os.path.join(p, f) for f in os.listdir(p)
                           if os.path.isfile(os.path.join(p, f))), key=os.path.getmtime)[-3:]
        if not ficheros:
            trozos.append(f"===== {ruta}/ — (vacío) =====")
            parte.append(f"- {ruta}/: 📭 vacío")
            continue
        if "buzones/" in ruta.replace(os.sep, "/"):
            trago_exterior = True                          # anti-poisoning: este turno tragó EXTERIOR
        con_datos += 1
        cupo = max(400, porc // len(ficheros))
        for fp in ficheros:
            raw = open(fp, "rb").read()[-cupo:]
            trozos.append(f"===== {ruta}/{os.path.basename(fp)} (cola de {len(raw)}c) =====\n"
                          + raw.decode("utf-8", errors="replace"))
        parte.append(f"- {ruta}/: 📬 {len(ficheros)} mensaje(s) recientes")
        continue
    if not os.path.isfile(p):
        trozos.append(f"===== {ruta} — (no existe; me lo salto) =====")
        parte.append(f"- {ruta}: ✗ no existe")
        continue
    raw = open(p, "rb").read()[-porc:]
    txt = raw.decode("utf-8", errors="replace")
    if txt.strip():
        con_datos += 1
    trozos.append(f"===== {ruta} (cola de {len(raw)}c) =====\n{txt}")
    st = os.stat(p)
    edad_min = int((_t.time() - st.st_mtime) // 60)
    ultima = next((l.strip()[:90] for l in reversed(txt.splitlines()) if l.strip()), "(vacío)")
    parte.append(f"- {ruta}: ✅ {st.st_size}c · modificado hace {edad_min}min · última línea: «{ultima}»")
if trago_exterior:
    open(f"{tmpd}/externo.flag", "w").write("1")           # el motor bloqueará HERRAMIENTA: este turno
# 🛡️ ANTI-ALUCINACIÓN (fix Opus 15:41): declaró lecturas y TODAS están vacías/ausentes →
#    un razonador confabularía (producción se inventó tickets). El motor CALLA por él,
#    determinista — el flag lo recoge el bash (deposita una línea honesta, sin modelo).
if tot_lect > 0 and con_datos == 0 and d.get("tipo_reporte", "Informe") != "parte-de-estado":
    open(f"{tmpd}/sin_datos.flag", "w").write("1")
full = "\n\n".join(trozos)
if len(full) > maxc:
    full = full[:maxc] + f"\n[…recortado a {maxc}c para caber en el modelo…]"
# ⚓ ANCLA de respuesta (fix eco Opus 15:41): SIEMPRE la última línea (sobrevive al recorte) —
#    el modelo continúa AQUÍ; y en la captura, todo lo anterior al ancla se puede recortar.
full += "\n\n" + os.environ.get("ANCLA_T", "Mi parte (en ESPAÑOL, empiezo aquí, sin repetir nada de lo anterior):")
open(f"{tmpd}/prompt.txt", "w", encoding="utf-8").write(full)
open(f"{tmpd}/parte.txt", "w", encoding="utf-8").write("\n".join(parte))
print(f"prompt: {len(full)}c · lecturas: {len(d.get('lecturas', []))}")
PY
    # shellcheck disable=SC1091
    source "$tmpd/conf.env"
    prompt_f="$tmpd/prompt.txt"; out_json="$tmpd/out.json"

    # 💤 ACTIVO (alta desde [E]): un agente dado de baja calla — TURNO_FORZAR=1 lo despierta
    if [ "${ACTIVO:-1}" != "1" ] && [ "${TURNO_FORZAR:-0}" != "1" ] && [ "$DRY" = 0 ]; then
        log "«${ROL}» está INACTIVO (activo: 0 en su yaml) — TURNO_FORZAR=1 para despertarlo"
        return 0
    fi
    # 🕰️ CADENCIA (línea roja de Opus, afinada en su auditoría 2): la unidad natural es el
    #    CICLO — 1 turno por rol por ciclo (acta nueva = ventana nueva). El RELOJ queda de
    #    SUELO para runs manuales sin ciclos de por medio (TURNO_CADENCIA > cadencia_s yaml
    #    > 3600s). --dry no cuenta · TURNO_FORZAR=1 la salta a conciencia.
    local marca="$BASE/data/turnos/$ROL.ultimo" antes edad ventana acta_marca ultima_acta
    if [ -n "${TURNO_CADENCIA:-}" ]; then ventana="$TURNO_CADENCIA"
    elif [ "${CADENCIA_Y:-0}" -gt 0 ] 2>/dev/null; then ventana="$CADENCIA_Y"
    else ventana=3600; fi
    ultima_acta="$(ls -t "$BASE"/data/actas/acta_*.json 2>/dev/null | head -1 || true)"   # || true: sin actas aún, pipefail no mata
    ultima_acta="$(basename "${ultima_acta:-sin_acta}")"
    if [ "$DRY" = 0 ] && [ "${TURNO_FORZAR:-0}" != "1" ] && [ -f "$marca" ]; then
        read -r antes acta_marca < "$marca" 2>/dev/null || { antes=0; acta_marca=""; }
        [[ "$antes" =~ ^[0-9]+$ ]] || antes=0
        edad=$(( $(date +%s) - antes ))
        if [ "$acta_marca" = "$ultima_acta" ] && [ "$edad" -lt "$ventana" ]; then
            log "cadencia: «${ROL}» ya habló ESTE ciclo (${acta_marca:-sin_acta}) hace ${edad}s (<${ventana}s de suelo) — TURNO_FORZAR=1 para saltarla"
            return 0
        fi
    fi
    log "turno de «${ROL}» · firma ${FIRMA} · tipo ${TIPO} · candidatos: ${PUERTOS}"

    # 📋 N3 · PARTE-DE-ESTADO (panel 3 niveles, Opus 00:44): determinista — SIN modelo,
    #    SIN pre-vuelo (funciona con la flota ABAJO). Su voz es el estado de sus registros.
    if [ "$TIPO" = "parte-de-estado" ]; then
        if [ "$DRY" = 1 ]; then
            log "DRY-RUN (no postea). El parte que depositaría:"
            sed 's/^/    /' "$tmpd/parte.txt"
            return 0
        fi
        respuesta="$(cat "$tmpd/parte.txt")"
        fecha="$(date '+%Y-%m-%d %H:%M')"
        cuerpo="${respuesta}

---
*parte de estado · determinista · sin modelo · rol: ${ROL} · el equipo revisa*"
        if MOSAIC_BASE="$BASE" bash "$REPORTAR" "Informe" "Parte de estado · ${ROL} — ${fecha}" "$cuerpo" "$ETIQ parte_estado" "$FIRMA" 2>"$tmpd/rep.err"; then
            mkdir -p "$BASE/data/turnos" && printf '%s %s\n' "$(date +%s)" "$ultima_acta" > "$BASE/data/turnos/$ROL.ultimo" 2>/dev/null || true
            log "📋 ${FIRMA} ha dado su parte de estado — léelo en [C]"
        else
            err "reportar.sh rechazó el parte: $(head -2 "$tmpd/rep.err" 2>/dev/null | tr '\n' ' ')"
            exit 1
        fi
        return 0
    fi

    # 🛡️ ANTI-ALUCINACIÓN (fix Opus 15:41): todas sus lecturas vacías → NO se llama al modelo
    #    (producción se inventó tickets sobre registros vacíos). Una línea honesta y a callar.
    if [ -f "$tmpd/sin_datos.flag" ]; then
        if [ "$DRY" = 1 ]; then
            log "DRY-RUN: todas las lecturas VACÍAS → el turno real depositaría «sin datos» SIN modelo"
            return 0
        fi
        fecha="$(date '+%Y-%m-%d %H:%M')"
        cuerpo="Todas mis lecturas están vacías o no existen este ciclo: **no tengo datos**. Callo para
no confabular — esta línea es determinista, sin modelo (anti-alucinación, fix Opus 15:41).

---
*turno de rol · sin datos · rol: ${ROL} · cero invención: el silencio también es disciplina*"
        if MOSAIC_BASE="$BASE" bash "$REPORTAR" "Informe" "Turno de ${ROL} — sin datos — ${fecha}" "$cuerpo" "$ETIQ turno_$ROL sin_datos" "$FIRMA" 2>"$tmpd/rep.err"; then
            mkdir -p "$BASE/data/turnos" && printf '%s %s\n' "$(date +%s)" "$ultima_acta" > "$BASE/data/turnos/$ROL.ultimo" 2>/dev/null || true
            log "🛡️ ${FIRMA}: sin datos este ciclo — depositada la línea honesta (sin modelo)"
        else
            err "reportar.sh rechazó el «sin datos»: $(head -2 "$tmpd/rep.err" 2>/dev/null | tr '\n' ' ')"
            exit 1
        fi
        return 0
    fi

    # 🧭 ROUTER de 5 capas (encargo Gustavo 7-jul · nace APAGADO): con ROUTER=1 el router
    #    elige la boca (oficio→talla→contenido→breaker) y su puerto va PRIMERO — los del
    #    yaml quedan de red (asegurar_analista sonda en orden, cero cambio de contrato).
    #    TURNO_PUERTOS="8094 8092" = override MANUAL (pruebas de flota sin tocar yamls).
    #    v1 no cruza máquinas: si elige otra caja, se respeta el yaml (y se dice). Corre
    #    también en --dry (solo-lectura): el seco ENSEÑA la decisión antes del real.
    if [ -n "${TURNO_PUERTOS:-}" ]; then
        PUERTOS="$TURNO_PUERTOS"
        log "🧭 puertos por env (manual): $PUERTOS"
    elif [ "${ROUTER:-1}" = "1" ] && [ -f "$BASE/router.py" ]; then    # D4 Opus 14:20: de serie
        local _rt _pto _rhost _deg _crit
        _rt="$(MOSAIC_BASE="$BASE" python3 "$BASE/router.py" --decidir --rol "$ROL" \
               --prompt-file "$prompt_f" --plano 2>>"$out_json.err" || true)"
        _pto="$(printf '%s' "$_rt" | sed -n 's/.*puerto=\([0-9]*\).*/\1/p')"
        _rhost="$(printf '%s' "$_rt" | sed -n 's/.*host=\([^ ]*\).*/\1/p')"
        _deg="$(printf '%s' "$_rt" | sed -n 's/.*degradado=\([0-9]\).*/\1/p')"
        _crit="$(printf '%s' "$_rt" | sed -n 's/.*critico=\([0-9]\).*/\1/p')"
        if [ -n "$_pto" ] && [ "$_rhost" = "$HOSTIP" ]; then
            PUERTOS="$_pto $PUERTOS"
            log "🧭 router: $_rt"
            # 🔻 D2 transparencia: si el router degradó de talla, el pie lo DIRÁ (y una silla
            #    crítica degradada NO se sella como el modelo bueno — el aviso viaja en la carta).
            if [ "${_deg:-0}" = "1" ]; then
                if [ "${_crit:-0}" = "1" ]; then
                    ROUTER_AVISO="⚠️ SILLA CRÍTICA DEGRADADA — output servido por un modelo por debajo del pedido; NO sellar como si fuera del modelo bueno (D2, Opus 14:20)."
                else
                    ROUTER_AVISO="ℹ️ modelo degradado a un hermano del oficio (aceptable en no-crítica) — declarado por transparencia."
                fi
            fi
        elif [ -n "$_pto" ]; then
            log "🧭 router eligió $_rhost:$_pto (otra máquina) — v1 no cruza hosts, sigo con el yaml"
        else
            err "router sin respuesta (mira $out_json.err) — sigo con los puertos del yaml"
        fi
    fi

    if [ "$DRY" = 1 ]; then
        local p1="${PUERTOS%% *}"
        if vivo "http://${HOSTIP}:${p1}/v1"; then log "sonda: @${p1} VIVO"; else log "sonda: @${p1} caído (el turno real haría el pre-vuelo)"; fi
        log "DRY-RUN (no postea). El prompt:"
        sed 's/^/    /' "$prompt_f"
        return 0
    fi

    # 🔒 ANTI-SOLAPE (estudio 15:46 · encargo perpetuo de Gustavo): un razonador MANUAL no
    #    pisa un ciclo/pleno en marcha — mismo patrón que mosaic.sh:199. Si el lock está
    #    ocupado, ceder el paso es DISCIPLINA (exit 0), no fallo. type -t: si lock.sh no
    #    cargó (clon raro), se sigue sin candado como hasta hoy.
    if [ -z "${MOSAIC_EN_ORQUESTADOR:-}" ] && [ "$(type -t tomar_lock)" = "function" ]; then
        if tomar_lock orquestador; then
            export MOSAIC_EN_ORQUESTADOR=1
        else
            log "hay un ciclo/pleno en marcha — «${ROL}» cede el paso (reintenta en el próximo punto seguro)"
            return 0
        fi
    fi

    # 🛫 pre-vuelo → puerto vivo o abortar limpio (fail-safe: sin analista no hay turno).
    #    (mosaic.sh YA no es la ruta de la orquesta — arreglo #3: llamada directa. Ya no se
    #    exige: el yaml del rol es la máscara y el modelo se llama por /chat/completions.)
    puerto="$(asegurar_analista "$PUERTOS")" || { err "sin analista no hay turno — no posteo"; exit 1; }
    nom="$(nombre_de "$puerto")"

    # RUTA 1 · GENERAR con llamada DIRECTA — con REINTENTO (el vacío suele ser transitorio:
    #   modelo ocupado/timeout bajo un pleno de 7 llamadas seguidas · Opus 5-jul). Entre
    #   intentos: respiro + re-sonda (si 8092 hipó, asegurar_analista puede saltar a 8094).
    local intento=0 max_int="${TURNO_REINTENTOS:-2}" _parsed=""
    while :; do
        # 🎯 arreglo #3: LLAMADA DIRECTA (la orquesta dueña de su prompt — sin la máscara
        #    de mosaic.py que causaba el doble envoltorio). El yaml del rol ES la máscara.
        generar_directo "http://${HOSTIP}:${puerto}/v1" "$nom" "$prompt_f" "$out_json" || true
        # 🩹 bash 3.2 (macOS · fix REAL Opus 03:25, mea culpa del 22:10): el heredoc rompe
        #    DENTRO de `<(…)` Y TAMBIÉN de `$(…)` en 3.2. Ahora alimenta un `cat >` plano
        #    (3.2-safe) y la sustitución va SIN heredoc. MISMO bloque python, cero lógica.
        cat > "$tmpd/parse.py" <<'PY'
import base64, json, os, re
try:
    d = json.load(open(os.environ["OUT_JSON"], encoding="utf-8", errors="replace"))
except Exception:
    d = {}
crudo = (d.get("output") or "").strip()
comp = d.get("composed") or []
out = crudo
# ✂️ FIX <think> CON RED (diagnóstico Opus 21:15, arreglo #1): los razonadores (@8092 Qwen3,
#    @8094 DeepSeek-R1) piensan en <think>…</think>. JAMÁS devolver vacío si el modelo habló:
#    1) si hay </think>, quédate con lo POSTERIOR (la respuesta vive tras el pensamiento);
#    2) si aun así queda vacío pero el crudo traía texto, quítale solo las etiquetas think;
#    3) último recurso: el crudo tal cual (mejor pensamiento visible que silencio).
if "</think>" in out:
    out = out.rsplit("</think>", 1)[1].strip()
if not out and crudo:
    out = re.sub(r"</?think>", "", crudo, flags=re.S).strip()
out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
if not out:
    out = crudo                                            # el modelo habló (aunque sea think) → no lo tiro
# ✂️ FIX ECO (Opus 15:41): tijera del eco del prompt — de la más precisa a la heurística.
try:
    prompt = open(os.environ.get("PROMPT_F", ""), encoding="utf-8", errors="replace").read()
except OSError:
    prompt = ""
ancla = os.environ.get("ANCLA_T", "")
if ancla and ancla in out:
    out = out.rsplit(ancla, 1)[1].strip()                  # 1) el eco trae el ANCLA → corta ahí
elif prompt:
    if out.startswith(prompt[:80]):                        # 2) eco desde el inicio → prefijo común fuera
        i, m = 0, min(len(out), len(prompt))
        while i < m and out[i] == prompt[i]:
            i += 1
        out = out[i:].strip()
    else:                                                   # 3) eco parcial: ≥60% de las líneas largas
        lineas_p = [l for l in prompt.splitlines() if len(l.strip()) > 20]
        presentes = [l for l in lineas_p if l in out]
        if lineas_p and len(presentes) >= max(3, int(0.6 * len(lineas_p))):
            pos = max(out.rfind(l) + len(l) for l in presentes)
            out = out[pos:].strip()
print(base64.b64encode(out.encode("utf-8", "replace")).decode(), len(comp), ",".join(comp[:5]))
PY
        _parsed="$(OUT_JSON="$out_json" PROMPT_F="$prompt_f" ANCLA_T="$ANCLA" python3 "$tmpd/parse.py" 2>/dev/null || echo "|0|")"
        read -r respuesta ncaps caps <<<"$_parsed"
        respuesta="$(printf '%s' "$respuesta" | base64 -d 2>/dev/null || true)"
        [ -n "${respuesta// /}" ] && break
        intento=$((intento + 1))
        # 🔎 arreglo #4: NUNCA tragar vacío en silencio — loguea el crudo (para no volver a
        #    diagnosticar a ciegas). El crudo está en out.json; su cola, al log del turno.
        local crudo_cola; crudo_cola="$(OUT_JSON="$out_json" python3 -c 'import json,os;print((json.load(open(os.environ["OUT_JSON"])).get("output") or "")[-300:])' 2>/dev/null || true)"
        err "«${ROL}» salió vacío (intento ${intento}/${max_int}) · crudo[-300]: ${crudo_cola:-<sin content del server; mira ${out_json}.err>}"
        [ "$intento" -gt "$max_int" ] && break
        sleep 4
        puerto="$(asegurar_analista "$PUERTOS")" || break
        nom="$(nombre_de "$puerto")"
    done
    if [ -z "${respuesta// /}" ]; then
        err "el rol no produjo palabra tras ${max_int} reintentos (¿cluster? ¿modelo @${puerto}?). No posteo vacío."
        exit 1
    fi

    # 🧰 F1 (manifiesto Opus 13:36 §5): el agente PIDE en su salida — `HERRAMIENTA: tool {json}` —
    #    el dispatcher chequea SU nivel_acceso y despacha o escala; el resultado VUELVE a su
    #    informe (lectura: cero efecto). Máximo 3 peticiones por turno (presupuesto).
    local herr_out=""
    if [ -f "$tmpd/externo.flag" ]; then
        # 🛡️ ANTI-POISONING (recon 13:19 + propuesta 13:54): este turno tragó texto EXTERIOR
        #    no verificado (buzón) → las peticiones HERRAMIENTA: NO se ejecutan. Un mail
        #    envenenado no mueve nuestras manos ni nuestras lecturas.
        if printf '%s' "$respuesta" | grep -qE '^\s*HERRAMIENTA:'; then
            herr_out="

---
### 🛡️ Herramientas BLOQUEADAS este turno (anti-poisoning)
El turno incluyó texto EXTERIOR no verificado (buzón): las peticiones \`HERRAMIENTA:\` de esta
salida se IGNORAN por doctrina. Si el rol necesita esa herramienta, que la pida en un turno
sin correo o que la ejecute un humano con pedir_tool.sh."
        fi
    else
    # 🩹 bash 3.2: heredoc fuera del `$(…)` — mismo fix que parse.py (Opus 03:25).
    cat > "$tmpd/herr.py" <<'PY'
import base64, json, os, re, subprocess
# la respuesta viaja por ENV en base64 — el heredoc ya ocupa stdin (la trampa clásica)
resp = base64.b64decode(os.environ["RESP_B64"]).decode("utf-8", "replace")
rol, base = os.environ["RESP_ROL"], os.environ["BASE_H"]
peticiones = re.findall(r"(?m)^\s*HERRAMIENTA:\s*([a-z0-9_-]+)\s*(\{.*\})?\s*$", resp)[:3]
if not peticiones:
    raise SystemExit(0)
partes = ["", "---", "### 🧰 Herramientas pedidas por el rol (F1 · lectura · vía dispatcher)"]
for tool, payload in peticiones:
    try:
        r = subprocess.run(["python3", os.path.join(base, "herramientas.py"),
                            "--agente", rol, "--tool", tool],
                           input=payload or "{}", capture_output=True, text=True,
                           errors="replace", timeout=120,
                           env={**os.environ, "MOSAIC_BASE": base})
        d = json.loads(r.stdout or "{}")
    except Exception as e:
        d = {"ok": False, "error": f"dispatcher irrompible no era: {e}"}
    if d.get("ok"):
        res = json.dumps(d.get("result"), ensure_ascii=False)[:1200]
        partes.append(f"- ✅ `{tool}` → {res}")
    else:
        extra = f" · 🎫 {d['ticket']} (P{d.get('prioridad','?')})" if d.get("ticket") else ""
        partes.append(f"- ⛔ `{tool}` → {d.get('error','?')}{extra}")
print("\n".join(partes))
PY
    herr_out="$(RESP_B64="$(printf '%s' "$respuesta" | base64)" RESP_ROL="$ROL" BASE_H="$BASE" python3 "$tmpd/herr.py" 2>/dev/null || true)"
    fi

    # 🎫 ESCALADO (plan Opus 13:56): si su bandeja traía tickets, el rango DECIDE en su salida
    #    (`ESCALACION: ESC-… conceder|denegar|escalar motivo`). El motor re-verifica TODO
    #    (rango_actual + capacidad); aquí solo se parsea. Vistos = en_revision.
    local esc_out=""
    if [ -s "$tmpd/esc_ids" ]; then
        if [ -f "$tmpd/externo.flag" ]; then
            # 🛡️ misma doctrina anti-poisoning que HERRAMIENTA: un turno que tragó buzón
            #    NO concede permisos — los tickets se quedan en su rango, sin marcar visto.
            if printf '%s' "$respuesta" | grep -qE '^\s*ESCALACION:'; then
                esc_out="

---
### 🛡️ Decisiones de escalado BLOQUEADAS este turno (anti-poisoning)
El turno incluyó texto EXTERIOR no verificado (buzón): las líneas \`ESCALACION:\` se IGNORAN
por doctrina — un mail envenenado no concede permisos. Los tickets siguen en su rango."
            fi
        else
            # 🩹 bash 3.2: heredoc fuera del `$(…)` — mismo fix que parse.py (Opus 03:25).
            cat > "$tmpd/esc.py" <<'PY'
import base64, json, os, re, subprocess
resp = base64.b64decode(os.environ["RESP_B64"]).decode("utf-8", "replace")   # env: el heredoc ya ocupa stdin
rol, base = os.environ["RESP_ROL"], os.environ["BASE_H"]
ids = set(open(os.environ["ESC_IDS_F"], encoding="utf-8").read().split())

def motor(*args):
    r = subprocess.run(["python3", os.path.join(base, "herramientas.py"), "--esc", *args],
                       capture_output=True, text=True, timeout=180,
                       env={**os.environ, "MOSAIC_BASE": base})
    try:
        return json.loads(r.stdout or "{}")
    except Exception as e:
        return {"ok": False, "error": f"motor ilegible: {e}"}

for i in ids:                                                     # miró su bandeja → en_revision
    motor("visto", "--id", i, "--como", rol)
dec = re.findall(r"(?m)^\s*ESCALACION:\s*(ESC-[0-9]{8}-[0-9]+)\s+(conceder|denegar|escalar)\b\s*(.*)$", resp)[:2]
dec = [(t, d, m) for (t, d, m) in dec if t in ids]                # solo su bandeja (el motor re-verifica igual)
if not dec:
    raise SystemExit(0)
partes = ["", "---", "### 🎫 Escalaciones decididas por el rol (motor re-verifica rango y capacidad)"]
for tid, d, mot in dec:
    r = motor("resolver", "--id", tid, "--como", rol, "--decision", d, "--motivo", (mot or "").strip()[:200])
    if r.get("ok"):
        res = r.get("result") or {}
        linea = f"- ✅ {tid} → {res.get('estado','?')}"
        if res.get("estado") == "resuelto":
            linea += f" (tool {'ok' if res.get('tool_ok') else 'FALLÓ'})"
        if "a" in res:
            linea += f" · subió a «{res['a']}»"
        partes.append(linea)
    else:
        partes.append(f"- ⛔ {tid} → {r.get('error','?')}")
print("\n".join(partes))
PY
            esc_out="$(RESP_B64="$(printf '%s' "$respuesta" | base64)" RESP_ROL="$ROL" BASE_H="$BASE" ESC_IDS_F="$tmpd/esc_ids" python3 "$tmpd/esc.py" 2>/dev/null || true)"
        fi
    fi

    # 💰 F2 ECONOMÍA (ronda bursátil 5-jul): APUNTA el gasto REAL del turno — los tokens del
    #    campo usage que mosaic.py ya mide (P1-3) y ahora viajan en el --out. Escritor único
    #    (turno_rol) + flock + tmp/replace. SOLO apunta: el enforcement es F3 y NO existe.
    #    ⏸️ APAGADA POR DEFECTO (auditoría Opus 18:20 — "primero el latido; luego el mercado"):
    #    el contador arranca LIMPIO cuando la mesa estrene la economía tras el debut, con
    #    ECONOMIA=1. Así los libros nacen a cero en un momento firmado, sin ruido pre-debut.
    if [ "${ECONOMIA:-0}" = "1" ]; then
        OUT_JSON="$out_json" ROL_E="$ROL" BASE_E="$BASE" python3 - <<'PY' 2>/dev/null || true
import datetime, fcntl, json, os
try:
    u = (json.load(open(os.environ["OUT_JSON"], encoding="utf-8")) or {}).get("usage") or {}
except Exception:
    u = {}
base, rol = os.environ["BASE_E"], os.environ["ROL_E"]
led = os.path.join(base, "data", "economia.json")
os.makedirs(os.path.dirname(led), exist_ok=True)
with open(led + ".lock", "a+") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    try:
        st = json.load(open(led, encoding="utf-8"))
    except Exception:
        st = {"_": "ledger de GASTO real por agente (F2 bursátil 5-jul): escribe SOLO turno_rol · "
                   "tokens del usage de llama-server · el enforcement (F3) NO está encendido",
              "version": 1, "agentes": {}}
    a = st.setdefault("agentes", {}).setdefault(rol, {"turnos": 0, "tokens_entrada": 0,
                                                      "tokens_salida": 0, "ultimo": ""})
    a["turnos"] += 1
    a["tokens_entrada"] += int(u.get("prompt_tokens", 0) or 0)
    a["tokens_salida"] += int(u.get("completion_tokens", 0) or 0)
    a["ultimo"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tmp = led + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, led)
PY
    fi

    fecha="$(date '+%Y-%m-%d %H:%M')"
    # 🔻 D2 (Opus 14:20): la transparencia de degradación viaja EN la carta — el sello lo sabe.
    local pie_deg=""
    [ -n "${ROUTER_AVISO:-}" ] && pie_deg="
> ${ROUTER_AVISO}"
    pie="${pie_deg}
---
*turno de rol · auto · sin verificar · rol: ${ROL} · modelo: ${nom} (@${puerto}) · máscara: ${ncaps} capacidades$( [ -n "$caps" ] && printf ' (%s…)' "$caps" || true ) · el equipo revisa antes de aplicar*"
    cuerpo="${respuesta}${herr_out}${esc_out}${pie}"
    titulo="Turno de ${ROL} — ${fecha}"

    # RUTA 2 · depositar. Una Acción coja (sin plantilla) cae a Informe AVISANDO.
    if MOSAIC_BASE="$BASE" bash "$REPORTAR" "$TIPO" "$titulo" "$cuerpo" "$ETIQ turno_$ROL" "$FIRMA" 2>"$tmpd/rep.err"; then
        mkdir -p "$BASE/data/turnos" && printf '%s %s\n' "$(date +%s)" "$ultima_acta" > "$BASE/data/turnos/$ROL.ultimo" 2>/dev/null || true
        log "🎭 ${FIRMA} ha hablado en la mesa (${TIPO} · modelo ${nom}) — léelo en [C]"
    elif [ "$TIPO" = "Acción" ] || [ "$TIPO" = "Accion" ]; then
        err "la Acción no cumplió la plantilla → la deposito como Informe (no se pierde la palabra)"
        cuerpo="⚠️ *(el rol prometía una Acción pero no cumplió la plantilla — va como Informe; el hallazgo puede re-proponerse bien formado)*

${cuerpo}"
        MOSAIC_BASE="$BASE" bash "$REPORTAR" "Informe" "$titulo" "$cuerpo" "$ETIQ turno_$ROL sin_plantilla" "$FIRMA" \
            && { mkdir -p "$BASE/data/turnos" && printf '%s %s\n' "$(date +%s)" "$ultima_acta" > "$BASE/data/turnos/$ROL.ultimo" 2>/dev/null || true
                 log "🎭 ${FIRMA} ha hablado (degradado a Informe)"; }
    else
        err "reportar.sh rechazó el depósito: $(head -2 "$tmpd/rep.err" 2>/dev/null | tr '\n' ' ')"
        exit 1
    fi
}

validar
ejecutar
