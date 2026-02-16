#!/usr/bin/env bash
# ============================================================
# 🧪 E2E TEST — Sanitización e2e
# ============================================================
# Verifica que las funciones de sanitización funcionan de
# extremo a extremo, incluyendo integración con config y scripts.
# Uso: bash tests/e2e/test_sanitization.sh
# ============================================================
set -euo pipefail

# EXPUESTO_ROOT → raíz del repo Expuesto (lib/, tests/, .expuesto/)
EXPUESTO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0
FAIL=0
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

pass() { PASS=$((PASS + 1)); echo -e "  ${GREEN}✅ PASS${NC}: $*"; }
fail() { FAIL=$((FAIL + 1)); echo -e "  ${RED}❌ FAIL${NC}: $*"; }
section() { echo -e "\n${YELLOW}═══ $* ═══${NC}"; }

COMMON_LIB="$EXPUESTO_ROOT/lib/bash-common.sh"

# Helper: ejecutar función de bash-common y capturar exit code sin trigger set -e
# Uso: run_func "sanitize_path" "/tmp/test" "label"
run_func() {
    local func_name="$1"; shift
    if bash -c '
        source "$1" 2>/dev/null
        '"$func_name"' "${@:2}" >/dev/null 2>&1
    ' _ "$COMMON_LIB" "$@" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# ============================================================
# 1. SANITIZE_PATH: INJECTION ATTEMPTS
# ============================================================
section "sanitize_path rechaza inyecciones"

INJECTIONS=(
    '/tmp/test;rm -rf /'
    '/tmp/test|cat /etc/passwd'
    '/tmp/test&background'
    '/tmp/test>overwrite'
    '/tmp/test<redirect'
    '/tmp/test!bang'
)

for inj in "${INJECTIONS[@]}"; do
    if run_func sanitize_path "$inj" "test"; then
        fail "Acepta inyección: $inj"
    else
        pass "Rechaza: $inj"
    fi
done

# Test $() y backtick por separado (problemas de quoting)
for inj_desc in 'dollar-paren:$/tmp/test$(whoami)' 'backtick:/tmp/test`id`'; do
    desc="${inj_desc%%:*}"
    inj="${inj_desc#*:}"
    if bash -c 'source "$1" 2>/dev/null; sanitize_path "$2" "test" >/dev/null 2>&1' _ "$COMMON_LIB" "$inj" >/dev/null 2>&1; then
        fail "Acepta inyección ($desc)"
    else
        pass "Rechaza inyección ($desc)"
    fi
done

# ============================================================
# 2. SANITIZE_PATH: VALID PATHS
# ============================================================
section "sanitize_path acepta rutas válidas"

VALID_PATHS=(
    '/tmp/test'
    '/home/user/documents'
    '/var/log/app.log'
    './relative/path'
    'simple_name'
    '/tmp/archivo-con-guiones'
    '/tmp/archivo_con_underscores'
    '/tmp/ruta/con/multiples/niveles'
)

for valid in "${VALID_PATHS[@]}"; do
    if run_func sanitize_path "$valid" "test"; then
        pass "Acepta ruta válida: $valid"
    else
        fail "Rechaza ruta válida: $valid"
    fi
done

# ============================================================
# 3. SANITIZE_INTEGER: BOUNDARY TESTING
# ============================================================
section "sanitize_integer: boundary testing"

# Válidos
for val in "0" "1" "42" "999999" "100"; do
    if run_func sanitize_integer "$val" "test"; then
        pass "Acepta entero: $val"
    else
        fail "Rechaza entero válido: $val"
    fi
done

# Inválidos
for val in "-1" "3.14" "abc" "12abc" "" "1e5" "0xFF" "--5"; do
    if run_func sanitize_integer "$val" "test"; then
        fail "Acepta no-entero: '$val'"
    else
        pass "Rechaza no-entero: '$val'"
    fi
done

# ============================================================
# 4. VERIFY_SHA256: INTEGRACIÓN COMPLETA
# ============================================================
section "verify_sha256: integración e2e"

TMPFILE=$(mktemp)
echo -n "test content for sha256" > "$TMPFILE"

# Calcular hash real
if command -v sha256sum >/dev/null 2>&1; then
    EXPECTED=$(sha256sum "$TMPFILE" | awk '{print $1}')
elif command -v shasum >/dev/null 2>&1; then
    EXPECTED=$(shasum -a 256 "$TMPFILE" | awk '{print $1}')
else
    echo "⚠️  Sin herramienta SHA256, saltando tests"
    EXPECTED=""
fi

if [[ -n "$EXPECTED" ]]; then
    # Hash correcto
    if run_func verify_sha256 "$TMPFILE" "$EXPECTED"; then
        pass "SHA256 correcto pasa verificación"
    else
        fail "SHA256 correcto falló"
    fi

    # Hash incorrecto — archivo debe ser eliminado
    TMPFILE2=$(mktemp)
    echo -n "another test" > "$TMPFILE2"
    if run_func verify_sha256 "$TMPFILE2" "deadbeef123456789abcdef"; then
        : # No debería pasar
    fi
    if [[ ! -f "$TMPFILE2" ]]; then
        pass "SHA256 incorrecto elimina archivo"
    else
        fail "SHA256 incorrecto NO eliminó archivo"
        rm -f "$TMPFILE2"
    fi

    # Placeholder hash — skip verification
    TMPFILE3=$(mktemp)
    echo -n "skip test" > "$TMPFILE3"
    if run_func verify_sha256 "$TMPFILE3" "REPLACE_WITH_ACTUAL_SHA256_HASH"; then
        pass "Placeholder hash omite verificación"
    else
        fail "Placeholder hash no omitió verificación"
    fi
    rm -f "$TMPFILE3"
fi

rm -f "$TMPFILE"

# ============================================================
# 5. ROTATE_LOG: INTEGRACIÓN
# ============================================================
section "rotate_log: rotación funcional"

TMPLOG=$(mktemp /tmp/test_rotation_XXXXXX.log)
for i in $(seq 1 200); do echo "line $i"; done > "$TMPLOG"

if run_func rotate_log "$TMPLOG" 100 3; then
    : # ok
fi

if [[ -f "${TMPLOG}.1" ]]; then
    LINES_AFTER=$(wc -l < "$TMPLOG" 2>/dev/null | tr -d ' ')
    if [[ "$LINES_AFTER" -lt 10 ]]; then
        pass "Log rotado: original vacío, backup en .1"
    else
        fail "Log rotado pero original tiene $LINES_AFTER líneas"
    fi
else
    fail "Log no fue rotado (${TMPLOG}.1 no existe)"
fi

rm -f "$TMPLOG" "${TMPLOG}.1" "${TMPLOG}.2" "${TMPLOG}.3"

# No rotar si está bajo el límite
TMPLOG2=$(mktemp /tmp/test_norotation_XXXXXX.log)
for i in $(seq 1 50); do echo "line $i"; done > "$TMPLOG2"

if run_func rotate_log "$TMPLOG2" 100; then
    : # ok
fi

if [[ ! -f "${TMPLOG2}.1" ]]; then
    pass "Log bajo límite NO rotado"
else
    fail "Log bajo límite fue rotado innecesariamente"
fi

rm -f "$TMPLOG2"

# ============================================================
# 6. REQUIRE FUNCTIONS
# ============================================================
section "require_* funciones de validación"

# require_file con archivo existente
TMPFILE=$(mktemp)
if run_func require_file "$TMPFILE" "test"; then
    pass "require_file acepta archivo existente"
else
    fail "require_file rechaza archivo existente"
fi
rm -f "$TMPFILE"

# require_file con archivo inexistente
if run_func require_file "/nonexistent/file" "test"; then
    fail "require_file acepta archivo inexistente"
else
    pass "require_file rechaza archivo inexistente"
fi

# require_command con comando existente
if run_func require_command "bash"; then
    pass "require_command acepta 'bash'"
else
    fail "require_command rechaza 'bash'"
fi

# require_command con comando inexistente
if run_func require_command "nonexistent_cmd_xyz"; then
    fail "require_command acepta comando inexistente"
else
    pass "require_command rechaza comando inexistente"
fi

# ============================================================
# RESUMEN
# ============================================================
echo ""
echo "════════════════════════════════════════"
echo "  Tests e2e de sanitización completados"
echo "  ✅ Pass: $PASS"
echo "  ❌ Fail: $FAIL"
TOTAL=$((PASS + FAIL))
echo "  Total:  $TOTAL"
echo -e "  Estado: $([ "$FAIL" -eq 0 ] && echo -e "${GREEN}PASS${NC}" || echo -e "${RED}FAIL${NC}")"
echo "════════════════════════════════════════"

exit "$FAIL"
