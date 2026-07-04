#!/bin/bash
# 🎬 =====================================================================
# 🎬 DEMO REPOSICIÓN (paso 2.6) — enseña cómo la CASCADA dispara el recolector
# 🎬 cuando una fuente CEDE por vacía. Usa fuentes de MENTIRA (no toca las tuyas,
# 🎬 ni el cluster, ni GitHub). Solo para VER el mecanismo. ~3 segundos.
# 🎬 Ejecuta:  bash demo_reposicion.sh
# 🎬 =====================================================================
set -uo pipefail
FUENTES="${FUENTES:-$HOME/Mosaic_privado/fuentes.sh}"
[ -f "$FUENTES" ] || { echo "no encuentro fuentes.sh en $FUENTES"; exit 1; }

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }        # limpieza (temporal de mktemp, no toca tu repo)
trap cleanup EXIT
mkdir -p "$TMP/cola" "$TMP/silo" "$TMP/notas" "$TMP/data"

# cola de mentira (cuenta ficheros) · fuentes reales = scripts vacíos → aportan 0 (ceden)
cat > "$TMP/cola.sh" <<'EOF'
#!/bin/bash
d="$(dirname "$0")/cola"
case "${1:-size}" in size) find "$d" -maxdepth 1 -type f 2>/dev/null|wc -l|tr -d ' ';; add) mktemp "$d/i.XXXXXX">/dev/null;; esac
EOF
for s in oraculo cuarentena libros noticias conv; do printf '#!/bin/bash\n' > "$TMP/$s.sh"; done
printf '#!/bin/bash\n[ "$1" = procesar ] || exit 0\n' > "$TMP/silo.sh"
printf '#!/bin/bash\nfor i in $(seq 1 $(( ${1:-0} * 3 ))); do mktemp "%s/cola/f.XXXXXX">/dev/null; done\n' "$TMP" > "$TMP/gen.sh"
# RECOLECTOR de mentira: apunta cada vez que corre (aquí, en real, iría el crawl de GitHub)
printf '#!/bin/bash\necho "[$(date +%%H:%%M:%%S)] recolector llamado" >> "%s/recolector.log"\n' "$TMP" > "$TMP/recolector.sh"
chmod +x "$TMP"/*.sh

correr() { env MOSAIC_DIR="$TMP" COLA_SH="$TMP/cola.sh" GEN="$TMP/gen.sh" \
    FUENTE_ORACULO="$TMP/oraculo.sh" SILO_SH="$TMP/silo.sh" CUARENTENA_SH="$TMP/cuarentena.sh" \
    LIBROS_SH="$TMP/libros.sh" CONV_SH="$TMP/conv.sh" NOTICIAS_SH="$TMP/noticias.sh" \
    SILO_DIR="$TMP/silo" NOTAS_DIR="$TMP/notas" ORACULO_AUTO_SH="$TMP/recolector.sh" \
    MAX_COLA=40 "$@" bash "$FUENTES" pull 2>&1; }
veces() { wc -l < "$TMP/recolector.log" 2>/dev/null | tr -d ' ' || echo 0; }

echo "══ PASADA 1 · todo seco → cada fuente cede a la siguiente → oráculo/cuarentena vacías ══"
correr | grep -E '▸|aportó|cede|↻|SALTADA'
sleep 1; echo "   → recolector llamado: $(veces) vez  (1 = dedup: un crawl repone oráculo Y cuarentena)"

echo; echo "══ PASADA 2 · inmediata → NO repite (enfriamiento, no martillea GitHub) ══"
correr | grep -E '↻'
sleep 1; echo "   → recolector llamado en total: $(veces)  (sigue 1)"

echo; echo "══ PASADA 3 · con REPONER_COOLDOWN=0 → vuelve a reponer ══"
correr REPONER_COOLDOWN=0 >/dev/null 2>&1
sleep 1; echo "   → recolector llamado en total: $(veces)  (ahora 2)"

echo
echo "En real: 'recolector' = oraculo_auto.sh (crawl de GitHub), en 2º plano, enfriamiento 1h."
echo "En un ciclo de verdad lo verás en la FASE 1 como:  ↻ oraculo vacía → recolector oraculo_auto en 2º plano"
