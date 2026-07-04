#!/bin/bash
# 🎨 =====================================================================
# 🎨 colores.sh — paleta ANSI + COLOR POR FASE (verde fase 1, azul fase 2, …).
# 🎨 Se apaga solo si la salida NO es una terminal o si NO_COLOR está puesto,
# 🎨 así los logs a fichero no se llenan de códigos raros.
# 🎨 =====================================================================
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C_RESET=$'\033[0m';    C_BOLD=$'\033[1m';     C_DIM=$'\033[2m'
    C_VERDE=$'\033[32m';   C_AZUL=$'\033[34m';    C_AMARILLO=$'\033[33m'
    C_MAGENTA=$'\033[35m'; C_CYAN=$'\033[36m';    C_ROJO=$'\033[31m';   C_GRIS=$'\033[90m'
else
    C_RESET=; C_BOLD=; C_DIM=; C_VERDE=; C_AZUL=; C_AMARILLO=; C_MAGENTA=; C_CYAN=; C_ROJO=; C_GRIS=
fi

# FASE -> color general (lo que pediste: cada fase su color)
fase_color() {
    case "${1:-}" in
        0) printf '%s' "$C_CYAN" ;;      # infra
        1) printf '%s' "$C_VERDE" ;;     # fuentes / fábrica
        2) printf '%s' "$C_AZUL" ;;      # ingesta
        3) printf '%s' "$C_MAGENTA" ;;   # juicio / tribunal
        4) printf '%s' "$C_AMARILLO" ;;  # aprender
        5) printf '%s' "$C_CYAN" ;;      # panel
        *) printf '%s' "$C_RESET" ;;
    esac
}
