#!/usr/bin/env python3
# 🧰 leer_registro (nivel 1 · interno): cola de un registro PERMITIDO del árbol.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _contrato import ok, fail, payload, base, dentro_de_base

P = payload()
ruta = str(P.get("ruta", "")).strip()
PERMITIDAS = ("data/", "info/PROYECTO.md", "info/IDIOLECTO.md", "servidores.conf", "logs/")
if not ruta or not any(ruta == p or ruta.startswith(p) for p in PERMITIDAS):
    fail(f"ruta fuera del alcance interno permitido: «{ruta or 'vacía'}» (data/*, logs/*, PROYECTO, IDIOLECTO, servidores.conf)")
real = dentro_de_base(ruta)
if not real or not os.path.isfile(real):
    fail(f"no existe (o escapa de la base): {ruta}")
raw = open(real, "rb").read()[-int(P.get("max", 4000)):]
ok({"ruta": ruta, "texto": raw.decode("utf-8", errors="replace")})
