#!/usr/bin/env bash
# ============================================================
# 🔍 ShellCheck — Lint de todos los scripts .sh
# ============================================================
# Uso: ./tests/shellcheck/run_shellcheck.sh
# Requiere: shellcheck (brew install shellcheck / apt install shellcheck)
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ERRORS=0
CHECKED=0
SKIPPED=0

# Colores
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

if ! command -v shellcheck &>/dev/null; then
    echo -e "${RED}❌ shellcheck no instalado${NC}"
    echo "   brew install shellcheck  (macOS)"
    echo "   apt install shellcheck   (Linux)"
    exit 1
fi

echo "🔍 ShellCheck scan: $REPO_ROOT"
echo ""

while IFS= read -r -d '' script; do
    # Saltar git, node_modules, venvs
    [[ "$script" == */.git/* ]] && continue
    [[ "$script" == */node_modules/* ]] && continue
    [[ "$script" == */venv/* ]] && continue
    [[ "$script" == */.bak ]] && continue

    ((CHECKED++))

    # Nota: shellcheck con severidad warning+, excluir SC1091 (source no seguido)
    if shellcheck -S warning -e SC1091,SC2059,SC2086 "$script" 2>/dev/null; then
        echo -e "${GREEN}  ✅${NC} $(basename "$script")"
    else
        echo -e "${RED}  ❌${NC} $script"
        ((ERRORS++))
    fi
done < <(find "$REPO_ROOT" -name "*.sh" -type f -print0 2>/dev/null)

echo ""
echo "════════════════════════════════"
echo -e "  Revisados: ${CHECKED}"
echo -e "  Errores:   ${ERRORS}"
echo -e "  Estado:    $([ "$ERRORS" -eq 0 ] && echo -e "${GREEN}PASS${NC}" || echo -e "${RED}FAIL${NC}")"
echo "════════════════════════════════"

exit "$ERRORS"
