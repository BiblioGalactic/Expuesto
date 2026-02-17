#!/usr/bin/env bash
# ============================================================
# 📦 EXPUESTO — Librería Bash Compartida
# ============================================================
# Funciones reutilizables para todos los scripts del proyecto.
# Uso: source "$(dirname "${BASH_SOURCE[0]}")/../lib/bash-common.sh"
#   o: source "${EXPUESTO_ROOT}/lib/bash-common.sh"
# ============================================================
# Evitar doble-source
[[ -n "${_BASH_COMMON_LOADED:-}" ]] && return 0
_BASH_COMMON_LOADED=1

# Si se ejecuta directamente (no sourced), mostrar documentación
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    cat <<'HELP'
EXPUESTO — Librería Bash Compartida

Uso: source "lib/bash-common.sh"

Funciones disponibles:
  info/ok/warn/error/die/step  Logging con timestamps y colores
  sanitize_path PATH LABEL     Valida ruta (rechaza ;|&><!"$`(){})
  sanitize_integer VAL LABEL   Valida entero positivo
  require_file PATH LABEL      Verifica existencia de archivo
  require_executable PATH LABEL Verifica ejecutable
  require_dir PATH LABEL       Verifica directorio
  require_command CMD           Verifica comando instalado
  rotate_log FILE [MAX_LINES]  Rota log si excede límite
  verify_sha256 FILE HASH      Verifica SHA256 (sha256sum/shasum)
  cleanup_generic              Limpia archivos en CLEANUP_FILES[]
  load_config                  Carga .expuesto/config.env

Variables de entorno:
  EXPUESTO_ROOT     Raíz del proyecto
  LOG_MAX_LINES     Máximo líneas antes de rotar (default: 10000)
  LOG_ROTATE_COUNT  Rotaciones a mantener (default: 5)
HELP
    exit 0
fi

# ============================================================
# 🎨 COLORES
# ============================================================
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; BOLD=''; NC=''
fi

# ============================================================
# 📢 LOGGING (stdout + stderr + timestamps)
# ============================================================
_ts() { date +"[%Y-%m-%d %H:%M:%S]"; }

info()  { echo -e "${BLUE}$(_ts) [INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}$(_ts) [✅]${NC} $*"; }
warn()  { echo -e "${YELLOW}$(_ts) [⚠️]${NC} $*" >&2; }
error() { echo -e "${RED}$(_ts) [❌]${NC} $*" >&2; }
step()  { echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}\n"; }
die()   { error "$*"; exit 1; }

# ============================================================
# 🔒 SANITIZACIÓN DE INPUT
# ============================================================
sanitize_path() {
    local input="$1"
    local label="${2:-path}"
    if [[ -z "$input" ]]; then
        die "Ruta vacía para $label"
    fi
    # Single-quoted regex: incluye backtick y todos los metacaracteres peligrosos
    local _bad_chars='[;|&><!\$`"(){}]'
    if [[ $input =~ $_bad_chars ]]; then
        die "Ruta inválida para $label: caracteres prohibidos detectados"
    fi
    echo "$input"
}

sanitize_integer() {
    local input="$1"
    local label="${2:-valor}"
    if ! [[ "$input" =~ ^[0-9]+$ ]]; then
        die "$label debe ser un número entero positivo, recibido: '$input'"
    fi
    echo "$input"
}

# ============================================================
# ✅ VALIDACIONES
# ============================================================
require_file() {
    local path="$1"
    local label="${2:-archivo}"
    [[ -f "$path" ]] || die "$label no encontrado: $path"
}

require_executable() {
    local path="$1"
    local label="${2:-ejecutable}"
    [[ -x "$path" ]] || die "$label no encontrado o sin permisos: $path"
}

require_dir() {
    local path="$1"
    local label="${2:-directorio}"
    [[ -d "$path" ]] || die "$label no encontrado: $path"
}

require_command() {
    local cmd="$1"
    command -v "$cmd" &>/dev/null || die "Comando requerido no instalado: $cmd"
}

# ============================================================
# 📊 ROTACIÓN DE LOGS
# ============================================================
rotate_log() {
    local log_file="$1"
    local max_lines="${2:-${LOG_MAX_LINES:-10000}}"
    local max_rotations="${3:-${LOG_ROTATE_COUNT:-5}}"

    [[ ! -f "$log_file" ]] && return 0

    local current_lines
    current_lines=$(wc -l < "$log_file" 2>/dev/null || echo 0)

    if [[ "$current_lines" -gt "$max_lines" ]]; then
        # Rotar archivos existentes (.4 → .5, .3 → .4, etc.)
        local i=$max_rotations
        while [[ $i -gt 1 ]]; do
            local prev=$((i - 1))
            [[ -f "${log_file}.${prev}" ]] && mv "${log_file}.${prev}" "${log_file}.${i}"
            ((i--))
        done
        mv "$log_file" "${log_file}.1"
        touch "$log_file"
        info "Log rotado: $log_file ($current_lines líneas → archivo .1)"
    fi
}

# ============================================================
# 🔐 VERIFICACIÓN SHA256
# ============================================================
verify_sha256() {
    local file="$1"
    local expected="$2"

    [[ "$expected" == "REPLACE_WITH_ACTUAL_SHA256_HASH" ]] && {
        warn "SHA256 hash es placeholder, omitiendo verificación para $file"
        return 0
    }

    local actual
    if command -v sha256sum >/dev/null 2>&1; then
        actual=$(sha256sum "$file" | awk '{print $1}')
    elif command -v shasum >/dev/null 2>&1; then
        actual=$(shasum -a 256 "$file" | awk '{print $1}')
    else
        warn "No se encontró herramienta SHA256, omitiendo verificación"
        return 0
    fi

    if [[ "$actual" != "$expected" ]]; then
        error "SHA256 no coincide para $file"
        error "  Esperado: $expected"
        error "  Obtenido: $actual"
        rm -f "$file"
        return 1
    fi
    ok "SHA256 verificado: $(basename "$file")"
    return 0
}

# ============================================================
# 🧹 CLEANUP GENÉRICO
# ============================================================
# Uso: CLEANUP_FILES+=("/tmp/mi_archivo")
#      trap cleanup_generic EXIT
CLEANUP_FILES=()

cleanup_generic() {
    local exit_code=$?
    for f in "${CLEANUP_FILES[@]:-}"; do
        [[ -n "$f" ]] || continue
        [[ -f "$f" ]] && rm -f "$f" 2>/dev/null
        [[ -d "$f" ]] && rm -rf "$f" 2>/dev/null
    done
    if [[ $exit_code -ne 0 && $exit_code -ne 130 ]]; then
        error "Script terminado con código: $exit_code"
    fi
}

# ============================================================
# 🔧 CARGAR CONFIGURACIÓN CENTRALIZADA
# ============================================================
load_config() {
    local config_path="${EXPUESTO_ROOT:-.}/.expuesto/config.env"
    if [[ -f "$config_path" ]]; then
        # shellcheck source=/dev/null
        source "$config_path"
    fi
}
