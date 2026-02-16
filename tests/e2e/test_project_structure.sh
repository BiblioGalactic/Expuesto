#!/usr/bin/env bash
# ============================================================
# 🧪 E2E TEST — Estructura del Proyecto
# ============================================================
# Verifica que todos los archivos clave existen, son sourced
# correctamente y las dependencias están resueltas.
# Uso: bash tests/e2e/test_project_structure.sh
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0
FAIL=0
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

pass() { PASS=$((PASS + 1)); echo -e "  ${GREEN}✅ PASS${NC}: $*"; }
fail() { FAIL=$((FAIL + 1)); echo -e "  ${RED}❌ FAIL${NC}: $*"; }
section() { echo -e "\n${YELLOW}═══ $* ═══${NC}"; }

# ============================================================
# 1. ARCHIVOS CRÍTICOS EXISTEN
# ============================================================
section "Archivos críticos del proyecto"

CRITICAL_FILES=(
    "lib/bash-common.sh"
    ".expuesto/config.env"
    "volumen_bucle/lib/base.sh"
    "volumen_bucle/lib/strings/es.sh"
    "volumen_bucle/lib/strings/en.sh"
    "volumen_bucle/lib/strings/cat.sh"
    "volumen_bucle/lib/strings/eus.sh"
    "volumen_bucle/lib/strings/jp.sh"
    "volumen_bucle/lib/strings/zh.sh"
    "volumen_bucle/lib/strings/fr.sh"
    "tests/shellcheck/run_shellcheck.sh"
    "tests/python/test_bash_common.py"
)

for f in "${CRITICAL_FILES[@]}"; do
    if [[ -f "$REPO_ROOT/$f" ]]; then
        pass "$f existe"
    else
        fail "$f NO encontrado"
    fi
done

# ============================================================
# 2. SHEBANGS CORRECTOS (no homebrew)
# ============================================================
section "Shebangs portables (sin /opt/homebrew)"

BAD_SHEBANGS=0
while IFS= read -r -d '' script; do
    [[ "$script" == */.git/* ]] && continue
    first_line=$(head -1 "$script" 2>/dev/null)
    if [[ "$first_line" == *"/opt/homebrew"* ]]; then
        fail "Shebang homebrew en: $script"
        BAD_SHEBANGS=$((BAD_SHEBANGS + 1))
    fi
done < <(find "$REPO_ROOT" -name "*.sh" -type f -print0 2>/dev/null)

if [[ "$BAD_SHEBANGS" -eq 0 ]]; then
    pass "Ningún script usa shebang homebrew"
fi

# ============================================================
# 3. bash-common.sh SE PUEDE CARGAR
# ============================================================
section "bash-common.sh se sourcea correctamente"

RESULT=$(bash -c "
    export EXPUESTO_ROOT='$REPO_ROOT'
    source '$REPO_ROOT/lib/bash-common.sh'
    echo \"\${_BASH_COMMON_LOADED:-NOPE}\"
" 2>&1)

if [[ "$RESULT" == *"1"* ]]; then
    pass "bash-common.sh carga y establece guard"
else
    fail "bash-common.sh no cargó: $RESULT"
fi

# Double-source guard
RESULT=$(bash -c "
    export EXPUESTO_ROOT='$REPO_ROOT'
    source '$REPO_ROOT/lib/bash-common.sh'
    source '$REPO_ROOT/lib/bash-common.sh'
    echo 'OK'
" 2>&1)

if [[ "$RESULT" == *"OK"* ]]; then
    pass "Double-source guard funciona"
else
    fail "Double-source guard falló: $RESULT"
fi

# ============================================================
# 4. FUNCIONES DE bash-common.sh EXISTEN
# ============================================================
section "Funciones exportadas por bash-common.sh"

EXPECTED_FUNCTIONS=(
    sanitize_path
    sanitize_integer
    require_file
    require_executable
    require_dir
    require_command
    rotate_log
    verify_sha256
    cleanup_generic
    load_config
    info
    ok
    warn
    error
    die
    step
)

for func in "${EXPECTED_FUNCTIONS[@]}"; do
    CHECK=$(bash -c "
        export EXPUESTO_ROOT='$REPO_ROOT'
        source '$REPO_ROOT/lib/bash-common.sh'
        type -t $func 2>/dev/null
    " 2>&1)
    if [[ "$CHECK" == "function" ]]; then
        pass "Función $func disponible"
    else
        fail "Función $func no encontrada (tipo: ${CHECK:-vacío})"
    fi
done

# ============================================================
# 5. config.env SE CARGA CORRECTAMENTE
# ============================================================
section "config.env se carga y define variables"

RESULT=$(bash -c "
    export EXPUESTO_ROOT='$REPO_ROOT'
    source '$REPO_ROOT/.expuesto/config.env'
    echo \"\${LLAMA_CTX_SIZE:-NOPE}|\${LOG_MAX_LINES:-NOPE}|\${LLAMA_THREADS:-NOPE}\"
" 2>&1)

if [[ "$RESULT" == *"4096"*"10000"*"6"* ]]; then
    pass "config.env define variables correctamente"
else
    fail "config.env variables incorrectas: $RESULT"
fi

# ============================================================
# 6. STRINGS i18n CARGAN Y DEFINEN VARIABLES
# ============================================================
section "Strings i18n se cargan correctamente"

for lang in es en cat eus jp zh fr; do
    RESULT=$(bash -c "
        source '$REPO_ROOT/volumen_bucle/lib/strings/${lang}.sh' 2>&1
        echo \"\${MSG_NOT_FOUND:-NOPE}|\${SESSION_PREFIX:-NOPE}\"
    " 2>&1)
    if [[ "$RESULT" != *"NOPE"* ]]; then
        pass "Strings $lang cargan (MSG_NOT_FOUND y SESSION_PREFIX definidos)"
    else
        fail "Strings $lang incompletas: $RESULT"
    fi
done

# ============================================================
# 7. VOLUMEN BUCLE: SCRIPTS VARIANTES SON WRAPPERS
# ============================================================
section "Loop scripts son wrappers mínimos (< 15 líneas)"

LOOP_SCRIPTS=(
    "volumen_bucle/bucleia/bucleia.sh"
    "volumen_bucle/loopai/loopai.sh"
    "volumen_bucle/rodaia/rodaia.sh"
    "volumen_bucle/birakaia/birakaia.sh"
)

for script in "${LOOP_SCRIPTS[@]}"; do
    if [[ -f "$REPO_ROOT/$script" ]]; then
        LINES=$(wc -l < "$REPO_ROOT/$script")
        if [[ "$LINES" -lt 15 ]]; then
            pass "$script es wrapper mínimo ($LINES líneas)"
        else
            fail "$script tiene $LINES líneas (debería ser < 15)"
        fi
    else
        fail "$script no encontrado"
    fi
done

# ============================================================
# 8. NO HAY sudo EN GLADIA SCRIPTS
# ============================================================
section "No hay sudo en scripts GLADIA"

SUDO_COUNT=0
while IFS= read -r -d '' script; do
    # Buscar sudo real: excluir líneas con echo/printf/comentarios
    if grep -v '^\s*#' "$script" 2>/dev/null \
       | grep -v 'echo\|printf\|info\|warn\|error' \
       | grep -q '\bsudo\b' 2>/dev/null; then
        fail "sudo ejecutable en: $script"
        SUDO_COUNT=$((SUDO_COUNT + 1))
    fi
done < <(find "$REPO_ROOT/light-sculpture" -name "*.sh" -type f -print0 2>/dev/null)

if [[ "$SUDO_COUNT" -eq 0 ]]; then
    pass "Ningún script GLADIA ejecuta sudo directamente"
fi

# ============================================================
# 9. NO HAY sed -i '' (SOLO sed -i.bak)
# ============================================================
section "Uso portable de sed -i"

SED_BAD=0
while IFS= read -r -d '' script; do
    [[ "$script" == */.git/* ]] && continue
    [[ "$script" == */tests/* ]] && continue  # Excluir tests propios
    if grep -qE "sed\s+-i\s+''" "$script" 2>/dev/null; then
        fail "sed -i '' no portable en: $script"
        SED_BAD=$((SED_BAD + 1))
    fi
done < <(find "$REPO_ROOT" -name "*.sh" -type f -print0 2>/dev/null)

if [[ "$SED_BAD" -eq 0 ]]; then
    pass "Ningún script usa sed -i '' (no portable)"
fi

# ============================================================
# 10. SECURITY.md TIENE CONTENIDO REAL
# ============================================================
section "SECURITY.md con política real"

while IFS= read -r -d '' sec; do
    if grep -q "gsilvadacosta0@gmail.com" "$sec" 2>/dev/null; then
        pass "$(echo "$sec" | sed "s|$REPO_ROOT/||") tiene email de contacto"
    else
        fail "$(echo "$sec" | sed "s|$REPO_ROOT/||") sin email de contacto real"
    fi
done < <(find "$REPO_ROOT" -name "SECURITY.md" -type f -print0 2>/dev/null)

# ============================================================
# 11. ROBOTSDELAMANECER SCRIPTS SOURCED bash-common
# ============================================================
section "Robotsdelamanecer scripts usan bash-common.sh"

ROBOT_SCRIPTS=(
    "Robotsdelamanecer/HAL_10/HAL_10.sh"
    "Robotsdelamanecer/Da1ta1/Da1ta1.sh"
    "Robotsdelamanecer/CC-33PPOO/CC-33PPOO.sh"
    "Robotsdelamanecer/VENDER/VENDER.sh"
)

for script in "${ROBOT_SCRIPTS[@]}"; do
    if [[ -f "$REPO_ROOT/$script" ]]; then
        if grep -q "bash-common.sh" "$REPO_ROOT/$script" 2>/dev/null; then
            pass "$script sourcea bash-common.sh"
        else
            fail "$script no sourcea bash-common.sh"
        fi
    else
        fail "$script no encontrado"
    fi
done

# ============================================================
# 12. REAMDE TYPO CORREGIDO (NO DEBEN EXISTIR)
# ============================================================
section "Typos corregidos (sin REAMDE)"

REAMDE_COUNT=$(find "$REPO_ROOT" -name "REAMDE*" -type f 2>/dev/null | wc -l | tr -d ' ')
if [[ "$REAMDE_COUNT" -eq 0 ]]; then
    pass "No hay archivos REAMDE (typo corregido)"
else
    fail "Aún existen $REAMDE_COUNT archivos REAMDE"
fi

# ============================================================
# RESUMEN
# ============================================================
echo ""
echo "════════════════════════════════════════"
echo "  Tests e2e de estructura completados"
echo "  ✅ Pass: $PASS"
echo "  ❌ Fail: $FAIL"
TOTAL=$((PASS + FAIL))
echo "  Total:  $TOTAL"
echo -e "  Estado: $([ "$FAIL" -eq 0 ] && echo -e "${GREEN}PASS${NC}" || echo -e "${RED}FAIL${NC}")"
echo "════════════════════════════════════════"

exit "$FAIL"
