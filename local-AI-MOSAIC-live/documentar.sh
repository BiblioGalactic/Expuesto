#!/bin/bash
# 📖 =====================================================================
# 📖 DOCUMENTAR — genera un README por cada script (.sh/.py) a partir de su
# 📖 CABECERA (propósito + uso) y sus funciones/defs. Los deposita en
# 📖 README/<ext>/<nombre>README.md → subcarpetas por extensión (sh, py) para
# 📖 que NO colisionen cuando coincide el nombre y cambia la extensión.
# 📖 Re-ejecutable: regenera la doc cuando cambian los scripts.
# 📖 Uso:  ./documentar.sh
# 📖 =====================================================================
set -uo pipefail
BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
OUT="$BASE/README"
log() { printf '📖 %s\n' "$*"; }

cabecera() {  # bloque de cabecera (sin shebang, sin separadores ===, sin emoji inicial)
    awk 'NR==1 && /^#!/ {next}
         /====/ {got=1; next}
         /^#/ { s=$0; sub(/^#+[ ]?/,"",s); print s; got=1; next }
         got && !/^#/ {exit}
         !got && NR>8 {exit}' "$1" \
    | sed -E 's/^(📦|📰|📚|🧪|🔮|🛡️|🌐|🥇|🧠|🧬|🗂|🔎|📖|🎲|⚖️|🎯|👁|🎨|🗣|👤|🔤|📄|🎙|🎚|🪺|🔧|🔄|🧩|📊|🚰|🛠|🐣|🦃) ?//'
}
docstring() {  # primer docstring """...""" (para .py sin cabecera #)
    awk 'f&&/"""/{exit} /"""/{f=1; sub(/.*"""/,""); if($0!="")print; next} f{print}' "$1"
}
funciones() {
    case "$1" in
        *.sh) grep -oE '^[a-zA-Z_][a-zA-Z0-9_]*\(\)' "$1" 2>/dev/null | tr -d '()' ;;
        *.py) grep -oE '^def [a-zA-Z_][a-zA-Z0-9_]*' "$1" 2>/dev/null | sed 's/^def //' ;;
    esac | sort -u
}

mkdir -p "$OUT/sh" "$OUT/py"
n=0
while IFS= read -r f; do
    base="$(basename "$f")"; nom="${base%.*}"; ext="${base##*.}"
    cab="$(cabecera "$f")"
    [ -z "${cab// /}" ] && [ "$ext" = py ] && cab="$(docstring "$f")"
    [ -z "${cab// /}" ] && cab="(script $base — sin cabecera documentada)"
    fns="$(funciones "$f")"
    primera="$(printf '%s\n' "$cab" | grep -m1 . || echo "$nom")"
    out="$OUT/$ext/${nom}README.md"
    {
        printf '# %s\n\n> %s\n\n## Qué hace\n\n%s\n\n' "$base" "$primera" "$cab"
        if [ -n "${fns// /}" ]; then
            printf '## Piezas clave\n\n'; printf '%s\n' "$fns" | sed -E 's/^/- `/; s/$/`/'; printf '\n'
        fi
        printf -- '---\n_Auto-documentado desde la cabecera de `%s`. Parte de MOSAIC._\n' "$base"
    } > "$out"
    n=$((n + 1))
done < <(find "$BASE" -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' \) 2>/dev/null | sort)
log "generados $n README → $OUT/{sh,py}/  (un .md por script, por extensión)"
