#!/bin/bash
# 👁️ =====================================================================
# 👁️ VER MINI — muestra EN VIVO qué está haciendo el Mac mini
# 👁️ (sus peticiones al llama-server: a quién juzga, qué procesa).
# 👁️ Política: si algo se delega al mini, tiene que VERSE en una terminal.
# 👁️ Uso:  ./ver_mini.sh        (Ctrl+C para salir)
# 👁️ =====================================================================
set -euo pipefail

MINI_SSH="${MINI_SSH:-$USER@localhost}"
MINI_LOG="${MINI_LOG:-mini_llama.log}"   # donde asegurar_mini redirige el server

command -v ssh >/dev/null 2>&1 || { echo "falta ssh" >&2; exit 1; }
echo "👁️  Mirando al mini ($MINI_SSH) — Ctrl+C para salir."
echo "    (resalto las peticiones de chat: cada una es un juicio o tarea ligera)"
echo

# -t para que el tail -f se vea en vivo; resaltamos lo legible (peticiones + tiempos).
ssh -t "$MINI_SSH" "
  if [ ! -f ~/$MINI_LOG ]; then echo '⚠️  no existe ~/$MINI_LOG todavía (¿está el mini lanzado?)'; exit 0; fi
  tail -n 40 -f ~/$MINI_LOG 2>/dev/null \
    | grep --line-buffered -E 'chat/completions|prompt eval|eval time|slot launch|model loaded' \
    || tail -n 40 -f ~/$MINI_LOG
"
