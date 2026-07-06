#!/usr/bin/env python3
# 🧰 CONTRATO común de toda tool mosaic (molde: wa-llama-bridge/tools/rag_local.py —
#    ADAPTADO, no copiado): JSON por stdin → JSON por stdout {"ok": bool, "result"|"error"}.
import json
import os
import sys


def emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def ok(result):
    emit({"ok": True, "result": result})
    raise SystemExit(0)


def fail(msg):
    emit({"ok": False, "error": str(msg)})
    raise SystemExit(1)


def payload():
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) else {}
    except Exception as e:
        fail(f"JSON de entrada inválido: {e}")


def base():
    return os.environ.get("MOSAIC_BASE", os.path.expanduser("~/Mosaic_privado"))


def dentro_de_base(ruta):
    """Una ruta relativa BAJO la base — jamás fuera (la allowlist es el primer candado)."""
    b = os.path.realpath(base())
    p = os.path.realpath(os.path.join(b, ruta))
    return p if p.startswith(b + os.sep) else None
