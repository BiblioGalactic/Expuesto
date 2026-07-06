#!/usr/bin/env python3
# 🧰 depositar (nivel 3 · interno): guarda un texto en el SILO de la empresa, etiquetado.
#    Deposita DENTRO del árbol: es lectura-del-mundo, escritura-en-casa (F1 lo permite).
import datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _contrato import ok, fail, payload, base

P = payload()
texto = str(P.get("texto", "")).strip()
if not texto:
    fail("depositar: sin texto")
rol = os.environ.get("HERR_ROL", "desconocido")
ts = datetime.datetime.now()
destino = os.path.join(base(), "silo", f"deposito_{rol}_{ts.strftime('%Y%m%d_%H%M%S')}.txt")
os.makedirs(os.path.dirname(destino), exist_ok=True)
with open(destino, "w", encoding="utf-8") as f:
    f.write(f"[DEPOSITADO POR: MOSAIC-{rol} · {ts.strftime('%Y-%m-%d %H:%M')} · via herramientas nivel 3]\n")
    titulo = str(P.get("titulo", "")).strip()
    if titulo:
        f.write(f"[TITULO: {titulo}]\n")
    f.write("\n" + texto + "\n")
ok({"depositado": os.path.relpath(destino, base()), "caracteres": len(texto)})
