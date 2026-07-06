#!/bin/bash
# 🏙️ =====================================================================
# 🏙️ CREAR_EMPRESA — funda una empresa nueva del GRUPO (decisiones firmadas 5-jul).
# 🏙️   El principio (Opus): «el motor se comparte y es genérico; la inteligencia
# 🏙️   es privada y se cultiva». En código:
# 🏙️     · N BASES: la empresa = ÁRBOL DE DATOS en ~/Empresas/<nombre>; el MOTOR
# 🏙️       no se copia — se SYMLINKA desde la sede (una sola fuente de verdad;
# 🏙️       un fix en la sede arregla a todas).
# 🏙️     · CARTA NUEVA (hallazgo de Gustavo): epistolar virgen con ACTA FUNDACIONAL,
# 🏙️       su libro de sellos, sus actas, su historia. La fundación deja además una
# 🏙️       Decisión en la carta de la mesa FUNDADORA.
# 🏙️     · ANDAMIO: arranca con las sillas default de roles/turnos (voto de Opus:
# 🏙️       "equipo funcional el día 1") — luego se customiza con [E].
# 🏙️     · MÁSCARA SIEMPRE VACÍA (decisión 4, razón de Gustavo: una semilla podría
# 🏙️       corromper el CRAG): capabilities/ nace vacía; la inteligencia se cultiva.
# 🏙️     · FLOTA: hereda servidores.conf de la sede (mismo hierro del grupo); el
# 🏙️       candado global (~/.mosaic/flota_de) impone UNA empresa a la vez.
# 🏙️ Uso:  ./crear_empresa.sh <nombre>            (DRY-RUN: el plan de fundación)
# 🏙️       ./crear_empresa.sh <nombre> --aplicar
# 🏙️   Operar la empresa: MOSAIC_BASE=~/Empresas/<nombre> ./monitor.py  (o cualquier script)
# 🏙️ =====================================================================
set -euo pipefail

SEDE="${MOSAIC_SEDE:-$HOME/Mosaic_privado}"
EMPRESAS_DIR="${EMPRESAS_DIR:-$HOME/Empresas}"
NOMBRE="${1:-}"; APLICAR=0; [ "${2:-}" = "--aplicar" ] && APLICAR=1
DEST="$EMPRESAS_DIR/${NOMBRE}"

log() { printf '[%s] 🏙️  %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    [ -n "$NOMBRE" ] || { err "uso: ./crear_empresa.sh <nombre> [--aplicar]"; exit 2; }
    [[ "$NOMBRE" =~ ^[A-Za-z0-9_-]{2,32}$ ]] || { err "nombre inválido (letras/números/-/_ · 2-32): $NOMBRE"; exit 2; }
    [ -d "$SEDE" ] || { err "no encuentro la sede: $SEDE"; exit 1; }
    [ -f "$SEDE/reportar.sh" ] && [ -f "$SEDE/setup.sh" ] || { err "la sede no parece el motor MOSAIC"; exit 1; }
    [ -e "$DEST" ] && { err "ya existe $DEST — las empresas no se pisan (bórrala TÚ a trash si procede)"; exit 1; }
    command -v python3 >/dev/null || { err "falta python3"; exit 1; }
}

ejecutar() {
    local motor_n=0 f ts
    ts="$(date '+%Y-%m-%d %H:%M')"

    if [ "$APLICAR" != 1 ]; then
        log "DRY-RUN — el plan de fundación de «${NOMBRE}»:"
        log "  sede/motor : $SEDE (symlinks de *.sh *.py + alpaca.jinja — $(ls "$SEDE"/*.sh "$SEDE"/*.py 2>/dev/null | wc -l | tr -d ' ') ficheros)"
        log "  árbol      : $DEST (estructura de datos completa, la de setup.sh)"
        log "  epistolar  : info/CARTAS.md VIRGEN + acta fundacional"
        log "  andamio    : roles/ copiados de la sede ($(ls "$SEDE"/roles/turnos/*.yaml 2>/dev/null | wc -l | tr -d ' ') sillas de turno)"
        log "  máscara    : capabilities/ VACÍA (decisión 4 — la inteligencia se cultiva)"
        log "  flota      : servidores.conf heredado + candado global del grupo"
        log "aplica con: ./crear_empresa.sh $NOMBRE --aplicar"
        return 0
    fi

    # 1 · el árbol de datos (la estructura de setup.sh, sin depender de él: la empresa aún no tiene motor)
    local d
    for d in data data/actas data/cola data/turnos silo silo/extraciones silo/.pendiente silo/.procesando \
             resultados logs cuarentena cuarentena/.procesando procesados/silo procesados/cuarentena \
             info packs oraculo/hallazgos oraculo/lotes \
             capabilities trash/logs trash/historico trash/backups trash/otros; do
        mkdir -p "$DEST/$d"
    done
    log "1/6 · árbol de datos ✅ ($DEST)"

    # 2 · el MOTOR por symlink (no se copia: una sola fuente de verdad)
    for f in "$SEDE"/*.sh "$SEDE"/*.py "$SEDE"/alpaca.jinja; do
        [ -e "$f" ] || continue
        ln -s "$f" "$DEST/$(basename "$f")" && motor_n=$((motor_n + 1))
    done
    log "2/6 · motor symlinkado ✅ ($motor_n ficheros — un fix en la sede arregla a todas)"

    # 3 · el ANDAMIO: roles (prompts de defensa/juicio/trampa + las sillas de turno default)
    cp -R "$SEDE/roles" "$DEST/roles"
    rm -f "$DEST/roles/organigrama.yaml" 2>/dev/null || true    # el organigrama NO viaja (decisión 3): cada empresa escribe el suyo
    # herramientas: los SCRIPTS son motor (symlink); la POLÍTICA (data/herramientas.yaml)
    # se COPIA — cada empresa gradúa su techo/niveles sin tocar a las demás (Opus 13:26/13:36)
    if [ -d "$SEDE/tools" ]; then
        mkdir -p "$DEST/tools"
        for f in "$SEDE"/tools/*.py; do [ -e "$f" ] && ln -s "$f" "$DEST/tools/$(basename "$f")"; done
    fi
    [ -f "$SEDE/data/herramientas.yaml" ] && cp "$SEDE/data/herramientas.yaml" "$DEST/data/herramientas.yaml"
    # economía (ronda bursátil 5-jul): la FÓRMULA del valor y la POLÍTICA MONETARIA también son
    # POR EMPRESA — cada una gradúa sus pesos/tasas sin tocar a las demás (cambiarlas = Acción)
    for pol in formula_valor.yaml politica_monetaria.yaml; do
        [ -f "$SEDE/data/$pol" ] && cp "$SEDE/data/$pol" "$DEST/data/$pol"
    done
    log "3/6 · andamio ✅ ($(ls "$DEST"/roles/turnos/*.yaml 2>/dev/null | wc -l | tr -d ' ') sillas · organigrama propio · tools: motor symlink + políticas COPIADAS)"

    # 4 · config: flota heredada + .env + el entorno de la empresa
    cp "$SEDE/servidores.conf" "$DEST/servidores.conf" 2>/dev/null || cp "$SEDE/publico/servidores.conf.example" "$DEST/servidores.conf"
    [ -f "$SEDE/.env.example" ] && cp "$SEDE/.env.example" "$DEST/.env.example"
    cat > "$DEST/empresa.env" <<ENV
# 🏙️ entorno de la empresa «${NOMBRE}» — cárgalo (source empresa.env) o antepón MOSAIC_BASE=…
export MOSAIC_BASE="$DEST"
export MOSAIC_DIR="$DEST"
export LOCK_BASE="$DEST/data"
export ORACULO_DIR="$DEST/oraculo"
ENV
    log "4/6 · config ✅ (flota heredada de la sede · empresa.env con MOSAIC_BASE/ORACULO_DIR propios)"

    # 5 · LA CARTA NUEVA: el epistolar virgen con su acta fundacional (empresa nueva = carta nueva)
    cat > "$DEST/info/CARTAS.md" <<CARTA
# 📁 CARTAS — la mesa de «${NOMBRE}» (epistolar vivo)

## 🏛️ ACTA FUNDACIONAL · ${ts}

Hoy nace **${NOMBRE}**, empresa del grupo. Fundada por **Gustavo** (Dirección General del grupo)
desde la sede MOSAIC, con el motor compartido de la franquicia.

- **Motor:** symlink a la sede (\`${SEDE}\`) — el código es del grupo, un fix arregla a todas.
- **Andamio:** las sillas de turno default (equipo funcional el día 1 — customiza con [E]).
- **Máscara:** VACÍA a propósito (decisión de la mesa fundadora, 5-jul): la inteligencia de
  esta casa se cultivará de SUS huecos y SU material — jamás de semillas que corrompan su CRAG.
- **Flota:** el hierro del grupo (compartido, una empresa a la vez, las dos máquinas juntas).
- **Reglas de la casa (heredadas del grupo):** palabra jamás manos · doble sello para ejecutar ·
  nunca borrar (todo a trash) · backup antes de tocar · el 24B jamás como flota.

La historia de esta mesa empieza aquí. Primer paso sugerido: \`source empresa.env && ./mosaic.sh --selftest\`,
y que el silo reciba su primer documento.

---
CARTA
    log "5/6 · epistolar virgen + acta fundacional ✅ (carta nueva = mesa nueva)"

    # 6 · la Decisión en la carta de la mesa FUNDADORA (quede en la historia de quién funda)
    MOSAIC_BASE="$SEDE" LOCK_BASE="$SEDE/data" bash "$SEDE/reportar.sh" "Decisión" \
        "Fundada la empresa «${NOMBRE}»" \
        "La mesa funda **${NOMBRE}** en \`${DEST}\` (motor symlinkado de la sede · andamio de sillas default · máscara VACÍA por decisión 4 · flota del grupo con candado global). Su epistolar arranca con el acta fundacional. Operarla: \`MOSAIC_BASE=${DEST}\` o \`source ${DEST}/empresa.env\`." \
        "grupo empresas fundacion" "Gustavo" >/dev/null \
        && log "6/6 · Decisión registrada en la mesa fundadora ✅" \
        || err "6/6 · no pude registrar la Decisión en la mesa fundadora (la empresa queda fundada igual)"

    log "🏙️ «${NOMBRE}» FUNDADA. Opérala:  MOSAIC_BASE=$DEST ./monitor.py   (o source $DEST/empresa.env)"
}

validar
log "fundación de «${NOMBRE}» · sede: $SEDE · $([ "$APLICAR" = 1 ] && echo APLICAR || echo DRY-RUN)"
ejecutar
