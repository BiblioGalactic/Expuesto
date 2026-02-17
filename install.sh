#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# 🚀 INSTALADOR GLOBAL — Ecosistema BiblioGalactic
# ═══════════════════════════════════════════════════════════
# Configura todo el ecosistema en un solo comando:
#   - Detecta SO y shell
#   - Instala dependencias (brew/apt)
#   - Compila llama.cpp
#   - Descarga modelo GGUF
#   - Configura rutas y permisos
#   - Valida instalación completa
#
# Uso: bash Expuesto/install.sh
# Desde: la raíz del workspace (donde están todos los repos)
#
# Autor: Eto Demerzel (Gustavo Silva Da Costa)
# Licencia: CC BY-NC-SA 4.0
# ═══════════════════════════════════════════════════════════
set -euo pipefail

# ── Colores ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

# ── Variables globales ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EXPUESTO_ROOT="$SCRIPT_DIR"
LOG_FILE="$EXPUESTO_ROOT/.expuesto/logs/install_$(date +%Y%m%d_%H%M%S).log"
ERRORS=0
WARNINGS=0
INSTALLED=0

# ── Rutas por defecto (macOS user) ──
LLAMA_DIR="${LLAMA_DIR:-$HOME/modelo/llama.cpp}"
MODELS_DIR="${MODELS_DIR:-$HOME/modelo/modelos_grandes/M6}"
DEFAULT_MODEL="mistral-7b-instruct-v0.1.Q6_K.gguf"
MODEL_URL="https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF/resolve/main/${DEFAULT_MODEL}"

# ── Funciones de logging ──
_ts() { date "+%H:%M:%S"; }
info()    { echo -e "  ${CYAN}[$(_ts)]${NC} $*"; echo "[$(_ts)] INFO: $*" >> "$LOG_FILE" 2>/dev/null; }
ok()      { echo -e "  ${GREEN}✅ $*${NC}"; echo "[$(_ts)] OK: $*" >> "$LOG_FILE" 2>/dev/null; INSTALLED=$((INSTALLED + 1)); }
warn()    { echo -e "  ${YELLOW}⚠️  $*${NC}"; echo "[$(_ts)] WARN: $*" >> "$LOG_FILE" 2>/dev/null; WARNINGS=$((WARNINGS + 1)); }
fail()    { echo -e "  ${RED}❌ $*${NC}"; echo "[$(_ts)] FAIL: $*" >> "$LOG_FILE" 2>/dev/null; ERRORS=$((ERRORS + 1)); }
section() { echo -e "\n${BOLD}═══ $* ═══${NC}"; echo "" >> "$LOG_FILE" 2>/dev/null; echo "=== $* ===" >> "$LOG_FILE" 2>/dev/null; }
step()    { echo -e "  ${DIM}→ $*${NC}"; }

# ── Cleanup ──
cleanup() {
    if [[ "$ERRORS" -gt 0 ]]; then
        echo -e "\n${RED}Instalación completada con $ERRORS error(es).${NC}"
        echo "Log completo: $LOG_FILE"
    fi
}
trap cleanup EXIT

# ── Detectar SO ──
detect_os() {
    section "Detectando sistema operativo"
    case "$(uname -s)" in
        Darwin)
            export OS="macos"
            PKG_MANAGER="brew"
            ok "macOS detectado ($(sw_vers -productVersion 2>/dev/null || echo 'unknown'))"
            ;;
        Linux)
            export OS="linux"
            if command -v apt-get >/dev/null 2>&1; then
                PKG_MANAGER="apt"
            elif command -v dnf >/dev/null 2>&1; then
                PKG_MANAGER="dnf"
            elif command -v pacman >/dev/null 2>&1; then
                PKG_MANAGER="pacman"
            else
                PKG_MANAGER="unknown"
                warn "Package manager no detectado"
            fi
            ok "Linux detectado ($(uname -r))"
            ;;
        *)
            fail "SO no soportado: $(uname -s)"
            exit 1
            ;;
    esac
    info "Package manager: $PKG_MANAGER"
    info "Shell: $SHELL (bash $(bash --version | head -1 | grep -oE '[0-9]+\.[0-9]+'))"
}

# ── Instalar dependencia ──
pkg_install() {
    local pkg="$1"
    local name="${2:-$pkg}"

    if command -v "$pkg" >/dev/null 2>&1; then
        ok "$name ya instalado ($(command -v "$pkg"))"
        return 0
    fi

    step "Instalando $name..."
    case "$PKG_MANAGER" in
        brew)
            if brew install "$pkg" >> "$LOG_FILE" 2>&1; then
                ok "$name instalado via brew"
            else
                fail "No se pudo instalar $name via brew"
            fi
            ;;
        apt)
            if apt-get install -y "$pkg" >> "$LOG_FILE" 2>&1; then
                ok "$name instalado via apt"
            else
                warn "$name: instalar manualmente con 'sudo apt-get install $pkg'"
            fi
            ;;
        dnf)
            if dnf install -y "$pkg" >> "$LOG_FILE" 2>&1; then
                ok "$name instalado via dnf"
            else
                warn "$name: instalar manualmente con 'sudo dnf install $pkg'"
            fi
            ;;
        *)
            warn "$name no instalado (package manager desconocido)"
            ;;
    esac
}

# ── Verificar dependencia (sin instalar) ──
check_dep() {
    local cmd="$1"
    local name="${2:-$cmd}"
    local install_hint="${3:-}"

    if command -v "$cmd" >/dev/null 2>&1; then
        ok "$name disponible"
        return 0
    else
        if [[ -n "$install_hint" ]]; then
            warn "$name no encontrado. Instalar: $install_hint"
        else
            warn "$name no encontrado"
        fi
        return 1
    fi
}

# ═══════════════════════════════════════
# FASE 1: DEPENDENCIAS DEL SISTEMA
# ═══════════════════════════════════════
install_system_deps() {
    section "Dependencias del sistema"

    # Esenciales
    check_dep "git" "Git" "brew install git / apt install git"
    check_dep "cmake" "CMake" "brew install cmake / apt install cmake"
    check_dep "make" "Make"
    check_dep "curl" "cURL"

    # Python
    if check_dep "python3" "Python 3"; then
        local py_ver
        py_ver=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        info "Python $py_ver"
    else
        pkg_install "python3" "Python 3"
    fi

    # Herramientas de análisis
    check_dep "shellcheck" "ShellCheck" "brew install shellcheck / apt install shellcheck"
    check_dep "jq" "jq" "brew install jq / apt install jq"

    # Multimedia (para light-sculpture)
    check_dep "ffmpeg" "FFmpeg" "brew install ffmpeg / apt install ffmpeg"
    check_dep "sox" "SoX" "brew install sox / apt install sox"

    # Python packages
    step "Verificando paquetes Python..."
    local pip_cmd="pip3"
    if ! command -v pip3 >/dev/null 2>&1; then
        pip_cmd="python3 -m pip"
    fi

    local py_packages=("pytest" "reportlab")
    for pkg in "${py_packages[@]}"; do
        if python3 -c "import $pkg" 2>/dev/null; then
            ok "Python: $pkg instalado"
        else
            step "Instalando $pkg..."
            if $pip_cmd install "$pkg" --break-system-packages >> "$LOG_FILE" 2>&1; then
                ok "Python: $pkg instalado"
            else
                warn "Python: $pkg falló (instalar manualmente: pip3 install $pkg)"
            fi
        fi
    done
}

# ═══════════════════════════════════════
# FASE 2: COMPILAR LLAMA.CPP
# ═══════════════════════════════════════
install_llama_cpp() {
    section "llama.cpp"

    local llama_bin="$LLAMA_DIR/build/bin/llama-cli"

    if [[ -x "$llama_bin" ]]; then
        ok "llama-cli ya compilado: $llama_bin"
        return 0
    fi

    if [[ ! -d "$LLAMA_DIR" ]]; then
        step "Clonando llama.cpp..."
        mkdir -p "$(dirname "$LLAMA_DIR")"
        if git clone --depth 1 https://github.com/ggerganov/llama.cpp.git "$LLAMA_DIR" >> "$LOG_FILE" 2>&1; then
            ok "llama.cpp clonado"
        else
            fail "No se pudo clonar llama.cpp"
            return 1
        fi
    else
        info "Directorio llama.cpp ya existe: $LLAMA_DIR"
    fi

    step "Compilando llama.cpp..."
    if (cd "$LLAMA_DIR" && cmake -B build >> "$LOG_FILE" 2>&1 && cmake --build build --config Release -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)" >> "$LOG_FILE" 2>&1); then
        ok "llama.cpp compilado exitosamente"
    else
        fail "Error compilando llama.cpp (ver $LOG_FILE)"
        return 1
    fi

    # Verificar binarios
    for bin in llama-cli llama-server llama-quantize; do
        if [[ -x "$LLAMA_DIR/build/bin/$bin" ]]; then
            ok "$bin disponible"
        else
            warn "$bin no encontrado después de compilar"
        fi
    done
}

# ═══════════════════════════════════════
# FASE 3: MODELO GGUF
# ═══════════════════════════════════════
install_model() {
    section "Modelo GGUF"

    local model_path="$MODELS_DIR/$DEFAULT_MODEL"

    if [[ -f "$model_path" ]]; then
        local size
        size=$(du -h "$model_path" 2>/dev/null | awk '{print $1}')
        ok "Modelo ya existe: $DEFAULT_MODEL ($size)"
        return 0
    fi

    step "Directorio de modelos: $MODELS_DIR"
    mkdir -p "$MODELS_DIR"

    echo -e "  ${YELLOW}El modelo Mistral 7B Q6_K pesa ~5.5 GB.${NC}"
    echo -e "  ${YELLOW}URL: $MODEL_URL${NC}"
    echo ""
    read -rp "  ¿Descargar ahora? [s/N]: " download_choice

    if [[ "$download_choice" =~ ^[sySY]$ ]]; then
        step "Descargando $DEFAULT_MODEL..."
        if curl -L --progress-bar -o "$model_path" "$MODEL_URL"; then
            ok "Modelo descargado: $model_path"

            # Verificar integridad básica
            local fsize
            fsize=$(wc -c < "$model_path" 2>/dev/null | tr -d ' ')
            if [[ "$fsize" -gt 1000000000 ]]; then
                ok "Tamaño verificado: $(du -h "$model_path" | awk '{print $1}')"
            else
                warn "Archivo sospechosamente pequeño ($fsize bytes). Verificar descarga."
            fi
        else
            fail "Error descargando modelo"
        fi
    else
        warn "Modelo no descargado. Descargar manualmente:"
        info "  curl -L -o '$model_path' '$MODEL_URL'"
    fi
}

# ═══════════════════════════════════════
# FASE 4: ESTRUCTURA Y PERMISOS
# ═══════════════════════════════════════
setup_structure() {
    section "Estructura del ecosistema"

    # Verificar repos
    local repos=(
        "Expuesto" "Prime_Radiant" "volumen_bucle" "volumen_overhead"
        "the-caves-of-steel" "Robotsdelamanecer"
        "volumen_linguistic_composition" "volumen_memoria"
        "light-sculpture" "we"
    )

    for repo in "${repos[@]}"; do
        if [[ -d "$WORKSPACE_ROOT/$repo" ]]; then
            ok "Repo: $repo"
        else
            warn "Repo no encontrado: $repo"
        fi
    done

    # Verificar archivos clave del ecosistema
    local key_files=(
        "Expuesto/lib/bash-common.sh"
        "Expuesto/.expuesto/config.env"
        "volumen_bucle/lib/base.sh"
        "the-caves-of-steel/guiaIA.md"
    )

    for f in "${key_files[@]}"; do
        if [[ -f "$WORKSPACE_ROOT/$f" ]]; then
            ok "Archivo: $f"
        else
            warn "Archivo no encontrado: $f"
        fi
    done

    # Crear directorios de trabajo
    mkdir -p "$EXPUESTO_ROOT/.expuesto/logs"

    # Permisos de ejecución en scripts
    step "Configurando permisos..."
    local count=0
    while IFS= read -r -d '' script; do
        [[ "$script" == */.git/* ]] && continue
        if [[ ! -x "$script" ]]; then
            chmod +x "$script" 2>/dev/null && count=$((count + 1))
        fi
    done < <(find "$WORKSPACE_ROOT" -name "*.sh" -type f -print0 2>/dev/null)
    ok "Permisos +x en $count script(s)"
}

# ═══════════════════════════════════════
# FASE 5: CONFIGURACIÓN
# ═══════════════════════════════════════
setup_config() {
    section "Configuración"

    local config_file="$EXPUESTO_ROOT/.expuesto/config.env"

    if [[ -f "$config_file" ]]; then
        ok "config.env existe"
    else
        step "Creando config.env..."
        mkdir -p "$EXPUESTO_ROOT/.expuesto"
        cat > "$config_file" << 'CONF'
# ═══════════════════════════════════════
# Configuración del Ecosistema BiblioGalactic
# ═══════════════════════════════════════
LLAMA_CLI="${LLAMA_CLI:-$HOME/modelo/llama.cpp/build/bin/llama-cli}"
MODELO="${MODELO:-$HOME/modelo/modelos_grandes/M6/mistral-7b-instruct-v0.1.Q6_K.gguf}"
MODELS_DIR="${MODELS_DIR:-$HOME/modelo/modelos_grandes/M6}"
LLAMA_CTX_SIZE="${LLAMA_CTX_SIZE:-4096}"
LLAMA_THREADS="${LLAMA_THREADS:-6}"
LLAMA_TEMP="${LLAMA_TEMP:-0.7}"
LLAMA_TOP_P="${LLAMA_TOP_P:-0.9}"
LLAMA_REPEAT_PENALTY="${LLAMA_REPEAT_PENALTY:-1.1}"
LOG_MAX_LINES="${LOG_MAX_LINES:-10000}"
LOG_BACKUP_COUNT="${LOG_BACKUP_COUNT:-3}"
CONF
        ok "config.env creado"
    fi

    # Generar env_check.sh para validar en runtime
    step "Generando script de validación rápida..."
    cat > "$EXPUESTO_ROOT/env_check.sh" << 'CHECK'
#!/usr/bin/env bash
# Quick environment check — run anytime to verify setup
set -euo pipefail
OK=0; FAIL=0
check() { if "$@" >/dev/null 2>&1; then echo "  ✅ $1"; OK=$((OK+1)); else echo "  ❌ $1"; FAIL=$((FAIL+1)); fi; }
echo "🔍 Environment Check"
check command -v bash
check command -v python3
check command -v git
check command -v cmake
check test -x "${LLAMA_CLI:-$HOME/modelo/llama.cpp/build/bin/llama-cli}"
check test -f "${MODELO:-$HOME/modelo/modelos_grandes/M6/mistral-7b-instruct-v0.1.Q6_K.gguf}"
check command -v ffmpeg
check command -v shellcheck
echo "  ── OK: $OK | FAIL: $FAIL ──"
CHECK
    chmod +x "$EXPUESTO_ROOT/env_check.sh"
    ok "env_check.sh generado"
}

# ═══════════════════════════════════════
# FASE 6: VALIDACIÓN FINAL
# ═══════════════════════════════════════
validate_installation() {
    section "Validación final"

    # Test bash-common.sh
    step "Probando bash-common.sh..."
    local result
    result=$(bash -c "
        export EXPUESTO_ROOT='$EXPUESTO_ROOT'
        source '$EXPUESTO_ROOT/lib/bash-common.sh' 2>/dev/null
        echo \"\${_BASH_COMMON_LOADED:-NOPE}\"
    " 2>&1)
    if [[ "$result" == *"1"* ]]; then
        ok "bash-common.sh carga correctamente"
    else
        fail "bash-common.sh no cargó: $result"
    fi

    # Test config.env
    step "Probando config.env..."
    result=$(bash -c "
        source '$EXPUESTO_ROOT/.expuesto/config.env' 2>/dev/null
        echo \"\${LLAMA_CTX_SIZE:-NOPE}\"
    " 2>&1)
    if [[ "$result" != "NOPE" ]]; then
        ok "config.env se carga correctamente"
    else
        fail "config.env no carga"
    fi

    # Test validate_prompt.py
    step "Probando validador Neopolilengua..."
    if python3 "$WORKSPACE_ROOT/volumen_linguistic_composition/tools/validate_prompt.py" \
        --json "Every Schlüssel con intención 使用せよ" >/dev/null 2>&1; then
        ok "validate_prompt.py funciona"
    else
        warn "validate_prompt.py no disponible"
    fi

    # Test e2e (si no es CI)
    if [[ -f "$EXPUESTO_ROOT/tests/e2e/test_sanitization.sh" ]]; then
        step "Ejecutando tests de sanitización..."
        if bash "$EXPUESTO_ROOT/tests/e2e/test_sanitization.sh" >/dev/null 2>&1; then
            ok "Tests e2e de sanitización PASS"
        else
            warn "Tests e2e de sanitización tienen fallos"
        fi
    fi
}

# ═══════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════
print_summary() {
    echo ""
    echo -e "${BOLD}═══════════════════════════════════════════${NC}"
    echo -e "${BOLD}  Instalación del Ecosistema BiblioGalactic${NC}"
    echo -e "  ✅ Completados: $INSTALLED"
    echo -e "  ⚠️  Advertencias: $WARNINGS"
    echo -e "  ❌ Errores: $ERRORS"
    echo -e "  📄 Log: $LOG_FILE"
    echo -e "${BOLD}═══════════════════════════════════════════${NC}"
    echo ""

    if [[ "$ERRORS" -eq 0 ]]; then
        echo -e "${GREEN}  🚀 Ecosistema listo. Próximos pasos:${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Instalación parcial. Resolver errores y re-ejecutar.${NC}"
    fi

    echo ""
    echo "  # Verificar entorno:"
    echo "  bash Expuesto/env_check.sh"
    echo ""
    echo "  # Tu primer prompt:"
    echo "  bash the-caves-of-steel/examples/01_hello_llama.sh"
    echo ""
    echo "  # Ejecutar tests:"
    echo "  bash Expuesto/tests/e2e/test_project_structure.sh"
    echo ""
    echo "  # Validar un prompt Neopolilengua:"
    echo "  python3 volumen_linguistic_composition/tools/validate_prompt.py \\"
    echo "    \"Every Schlüssel must be designed con intención 誤用を防止しなければならない\""
    echo ""
}

# ═══════════════════════════════════════
# HELP
# ═══════════════════════════════════════
show_help() {
    echo "Uso: bash Expuesto/install.sh [opciones]"
    echo ""
    echo "Opciones:"
    echo "  --help          Mostrar esta ayuda"
    echo "  --check-only    Solo verificar, no instalar nada"
    echo "  --skip-model    No descargar modelo GGUF"
    echo "  --skip-compile  No compilar llama.cpp"
    echo ""
    echo "Variables de entorno:"
    echo "  LLAMA_DIR       Ruta a llama.cpp (default: \$HOME/modelo/llama.cpp)"
    echo "  MODELS_DIR      Ruta a modelos (default: \$HOME/modelo/modelos_grandes/M6)"
    echo "  LLAMA_CLI       Ruta al binario (default: \$LLAMA_DIR/build/bin/llama-cli)"
    echo ""
}

# ═══════════════════════════════════════
# MAIN
# ═══════════════════════════════════════
main() {
    local skip_model=false
    local skip_compile=false
    local check_only=false

    for arg in "$@"; do
        case "$arg" in
            --help|-h)     show_help; exit 0 ;;
            --check-only)  check_only=true ;;
            --skip-model)  skip_model=true ;;
            --skip-compile) skip_compile=true ;;
        esac
    done

    echo -e "${BOLD}"
    echo "  ═══════════════════════════════════════"
    echo "  🚀 Instalador BiblioGalactic Ecosystem"
    echo "  ═══════════════════════════════════════"
    echo -e "${NC}"

    # Crear directorio de logs
    mkdir -p "$EXPUESTO_ROOT/.expuesto/logs"
    echo "Instalación iniciada: $(date)" > "$LOG_FILE"

    detect_os

    if [[ "$check_only" == "true" ]]; then
        install_system_deps
        setup_structure
        validate_installation
    else
        install_system_deps
        [[ "$skip_compile" == "false" ]] && install_llama_cpp
        [[ "$skip_model" == "false" ]] && install_model
        setup_structure
        setup_config
        validate_installation
    fi

    print_summary
}

main "$@"
