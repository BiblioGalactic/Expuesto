#!/bin/bash
# 🔎 =====================================================================
# 🔎 CHEQUEO MINI — ¿puede el mini REPONER en paralelo mientras el MacBook
# 🔎 hace FASE 1? Comprueba 3 cosas y no cambia NADA (solo lee y prueba):
# 🔎   1) SSH sin contraseña al mini
# 🔎   2) recolector + dependencias (crawler, venv, token, OCR) EN el mini
# 🔎   3) si el silo es disco COMPARTIDO (lo ve el mini en la misma ruta)
# 🔎 Ejecuta EN EL MACBOOK:   bash chequeo_mini.sh
# 🔎 Si el usuario del mini difiere:   MINI="usuario@localhost" bash chequeo_mini.sh
# 🔎 (a propósito SIN 'set -e': un chequeo debe seguir aunque una prueba dé "no")
# 🔎 =====================================================================
MINI="${MINI:-localhost}"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=6"
SILO="$HOME/Mosaic_privado/silo"

echo "🔎 Coordinación MacBook ↔ mini  ($MINI)"
echo "═══════════════════════════════════════════════════════════"

# 1) SSH sin contraseña ------------------------------------------------------
echo "1) SSH sin contraseña:"
if $SSH "$MINI" 'echo ok' >/dev/null 2>&1; then
    SSH_OK=1
    echo "   ✅ sí (entro por clave · mini se llama: $($SSH "$MINI" hostname 2>/dev/null))"
else
    SSH_OK=0
    echo "   ❌ no — falta clave, o el user/host no es '$MINI'"
    echo "      manual:   ssh $MINI 'echo ok'"
    echo "      arreglar: ssh-keygen   (si no tienes clave)  →  ssh-copy-id $MINI"
fi

# 2) recolector + dependencias en el mini (necesita SSH) ---------------------
echo "2) Recolector y dependencias EN el mini:"
if [ "$SSH_OK" = 1 ]; then
    $SSH "$MINI" '
      p(){ [ -e "$1" ] && echo "   ✅ $2" || echo "   ❌ $2   ($1)"; }
      p ~/Mosaic_privado/oraculo_auto.sh                        "recolector oraculo_auto.sh"
      p ~/proyecto/laboratorio/script/completo/oraculo_codigo.sh "crawler oraculo_codigo.sh"
      p ~/wikirag/venv                                          "venv wikirag"
      p ~/Mosaic_privado/apikey.sh                              "store de token (apikey.sh)"
      command -v tesseract >/dev/null 2>&1 && echo "   ✅ tesseract (OCR)"   || echo "   ❌ tesseract (OCR)"
      command -v whisper   >/dev/null 2>&1 && echo "   ✅ whisper (audio)"   || echo "   ❌ whisper (audio)"
    '
else
    echo "   ⏭️  sin SSH no puedo mirar el mini desde aquí (míralo en el propio mini)"
fi

# 3) silo compartido ---------------------------------------------------------
echo "3) Silo compartido (¿el mini ve el silo en la misma ruta?):"
if [ "$SSH_OK" = 1 ] && [ -d "$SILO" ]; then
    marca="$SILO/.prueba_compartido"
    touch "$marca" 2>/dev/null
    if $SSH "$MINI" '[ -f ~/Mosaic_privado/silo/.prueba_compartido ]' 2>/dev/null; then
        echo "   ✅ COMPARTIDO — el mini puede rellenar el silo / hacer OCR directo"
    else
        echo "   ❌ NO compartido — el silo vive solo en el MacBook"
        echo "      (para que el mini lo rellene habría que compartirlo o sincronizarlo)"
    fi
    rm -f "$marca" 2>/dev/null
else
    echo "   ⏭️  necesito SSH y que exista $SILO"
fi

echo "═══════════════════════════════════════════════════════════"
echo "Pégame esta salida y te propongo el montaje exacto (SSH+barrera condicional)."
