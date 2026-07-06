#!/bin/bash
# 🗄️ ═══════════════════════════════════════════════════════════
# 🔎 INVENTARIO SSD del mini · clasifica por "dónde puede correr"
# 🗄️   Corre en el MacBook; consulta al mini por ssh (los .gguf viven allí).
# 🗄️ ═══════════════════════════════════════════════════════════
set -uo pipefail                     # archivo, no pegado → set/exit seguros
MINI="${MINI_SSH:-usuario@localhost}"
SSD="/Volumes/Extreme SSD"

# ── validar ──────────────────────────────────────────────
ssh -o ConnectTimeout=6 "${MINI}" "test -d \"${SSD}\"" 2>/dev/null \
  || { echo "❌ el mini no responde o la SSD no está montada allí"; exit 1; }

echo "🕒 $(date '+%Y-%m-%d %H:%M') · ${MINI}:${SSD}"
echo "💾 MacBook 48GB · mini 16GB · (tamaños = solo pesos; el contexto ancho suma KV)"
echo "════════════════════════════════════════════════════════════"

# ── ejecutar: una sola llamada ssh; fuera los vocab (no son modelos) ──
ssh "${MINI}" "find \"${SSD}\" -type f -iname '*.gguf' -exec stat -f '%z|%N' {} \;" 2>/dev/null \
 | grep -v 'ggml-vocab' \
 | sort -rn \
 | while IFS='|' read -r b f; do
     [ -n "${b}" ] || continue
     name=$(basename "${f}")
     par=$(echo "${name}" | grep -oiE '[0-9]+x?[0-9]*b' | head -1 | tr 'a-z' 'A-Z')
     q=$(echo "${name}"   | grep -oiE 'Q[0-9][0-9_A-Za-z]*|F16|BF16' | head -1)
     if   [ "${b}" -ge 47244640256 ]; then d="❌ ni MacBook solo"
     elif [ "${b}" -ge 21474836480 ]; then d="🖥️ SOLO MacBook off-loop (director/ultra-ctx)"
     elif [ "${b}" -ge 13958643712 ]; then d="🖥️ MacBook off-loop · ⚠️ mini NO"
     elif [ "${b}" -ge 7516192768 ];  then d="🍃 mini (si el juez cede) o MacBook"
     else                                  d="✅ ligero (cualquiera)"
     fi
     awk -v b="${b}" -v p="${par:-¿?}" -v q="${q:-¿?}" -v d="${d}" -v n="${name}" \
       'BEGIN{printf "%6.1f GB │ %-6s │ %-9s │ %s\n            └ %s\n", b/1073741824, p, q, d, n}'
   done
echo "════════════════════════════════════════════════════════════"
echo "🧭 Con la flota ARRIBA el MacBook deja ~14GB → los grandes SOLO entran off-loop."
# read-only: sin temporales, nada que limpiar
