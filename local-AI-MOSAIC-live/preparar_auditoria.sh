#!/bin/bash
# 📦 === EMPAQUETADOR DE CÓDIGO PARA AUDITORÍA DE REPOSITORIO === 🚀
set -euo pipefail

# Configuración de rutas locales fijas
PROYECTO_DIR="${PROYECTO_DIR:-$HOME/Mosaic_privado}"
REPORTE_MD="${REPORTE_MD:-$PROYECTO_DIR/resultados/bundle_auditoria.md}"
LOG_TXT="${LOG_TXT:-$PROYECTO_DIR/resultados/preparar_auditoria.log}"

# Crear directorio temporal seguro
TMP_DIR=$(mktemp -d /tmp/mosaic_bundle.XXXXXX)

function cleanup() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🧹 === PROCESO TERMINADO · LIMPIANDO TEMPORALES ===" >> "$LOG_TXT" 2>&1
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# ═════════════════════════════════════════════════════════════════
# FASE 0: VALIDACIONES MÍNIMAS DE ENTORNO
# ═════════════════════════════════════════════════════════════════
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🟢 Iniciando empaquetado..."

# Verificar existencia de directorios críticos
if [ ! -d "$PROYECTO_DIR" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: El directorio del proyecto no existe." >> "$LOG_TXT" 2>&1
    exit 1
fi

# Comprobar permisos de lectura y escritura
if [ ! -r "$PROYECTO_DIR" ] || [ ! -w "$PROYECTO_DIR" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: Permisos insuficientes en el proyecto." >> "$LOG_TXT" 2>&1
    exit 1
fi

# Validar comandos externos requeridos
for cmd in find grep basename; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: El comando indispensable '$cmd' no está instalado." >> "$LOG_TXT" 2>&1
        exit 1
fi
done

# ═════════════════════════════════════════════════════════════════
# FASE 1: CONSTRUCCIÓN DEL BUNDLE DE AUDITORÍA
# ═════════════════════════════════════════════════════════════════
echo "# BUNDLE DE AUDITORÍA DE CÓDIGO FUENTE — MOSAIC" > "$REPORTE_MD"
echo "Generado el: $(date '+%Y-%m-%d %H:%M:%S')" >> "$REPORTE_MD"
echo -e "\n## 🗺️ 1. TOPOLOGÍA FILTRADA DEL PROYECTO\n\`\`\`text" >> "$REPORTE_MD"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 📊 Mapeando estructura del proyecto..." >> "$LOG_TXT" 2>&1

# Generar un mapa del directorio ignorando datos pesados, temporales y entornos virtuales
find "$PROYECTO_DIR" -not -path '*/.*' -not -path '*/venv*' -not -path '*/silo*' -not -path '*/data*' -not -path '*/resultados*' -not -path '*/cuarentena*' | sed "s|$PROYECTO_DIR/||g" >> "$REPORTE_MD"

echo -e "\`\`\`\n\n## 🔩 2. CONTENIDO DE LOS SCRIPTS Y ARCHIVOS DE LOGICA\n" >> "$REPORTE_MD"

# Buscar todos los scripts de bash y python del core
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🔍 Concatenando lógica de programación..." >> "$LOG_TXT" 2>&1
ARCHIVOS_CODE=$(find "$PROYECTO_DIR" -maxdepth 2 \( -name "*.sh" -o -name "*.py" \) -not -path '*/.*')

TOTAL_ARCHIVOS=$(echo "$ARCHIVOS_CODE" | wc -l | xargs)
CONTADOR=0

for archivo in $ARCHIVOS_CODE; do
    CONTADOR=$((CONTADOR + 1))
    NOMBRE_BASE=$(basename "$archivo")
    
    # Indicador de progreso en la terminal estándar
    echo " -> Procesando archivo [$CONTADOR/$TOTAL_ARCHIVOS]: $NOMBRE_BASE"
    
    echo "### Archivo: \`$NOMBRE_BASE\`" >> "$REPORTE_MD"
    if [[ "$archivo" == *.py ]]; then
        echo -e "\`\`\`python" >> "$REPORTE_MD"
    else
        echo -e "\`\`\`bash" >> "$REPORTE_MD"
    fi
    
    # Inyectar el código fuente limpio en el reporte
    cat "$archivo" >> "$REPORTE_MD"
    echo -e "\n\`\`\`\n" >> "$REPORTE_MD"
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Reporte consolidado con éxito en: $REPORTE_MD" >> "$LOG_TXT" 2> /dev/null
echo "🎉 ¡Hecho! Proceso completado. Revisa tus resultados."
