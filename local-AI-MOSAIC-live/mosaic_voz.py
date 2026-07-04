#!/usr/bin/env python3
# 🤖 =====================================================================
# 🤖 VOZ — el parte de guardia de MOSAIC en la mesa (idea de Gustavo,
# 🤖 arnés de Opus, construcción de Fable — carta del 2-jul-2026).
# 🤖 En FASE 0, MOSAIC deja en info/CARTAS.md un TELEGRAMA factual:
# 🤖 determinista, parseado de sus datos reales (perfil + última acta),
# 🤖 SIN modelo, SIN adornos — "el sistema dando su parte", no un diario.
# 🤖 Guardia anti-inundación: solo escribe si su parte CAMBIÓ desde el
# 🤖 último (huella en data/.voz_ultimo). Auditable por Opus contra las fuentes.
# 🤖 Uso:  python3 mosaic_voz.py [--forzar]
# 🤖 =====================================================================
import hashlib
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
PERFIL = os.path.join(BASE, "data", "perfil_lanzamiento.json")
ACTAS = os.path.join(BASE, "data", "actas")
CARTAS = os.path.join(BASE, "info", "CARTAS.md")
HUELLA = os.path.join(BASE, "data", ".voz_ultimo")


def leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


def ultima_acta():
    if not os.path.isdir(ACTAS):
        return None
    fs = sorted(f for f in os.listdir(ACTAS) if f.startswith("acta_") and f.endswith(".json"))
    return leer_json(os.path.join(ACTAS, fs[-1]), None) if fs else None


def main():
    forzar = "--forzar" in sys.argv
    if not os.path.isfile(CARTAS):
        return  # sin mesa, sin parte
    perfil = leer_json(PERFIL, {})
    m = perfil.get("mandos", {})
    acta = ultima_acta()

    # ── el telegrama (solo hechos, cada número tiene fuente auditable) ──
    lineas = []
    if m:
        ej = m.get("ejercitar") or []
        lineas.append(
            f"Arranco. El gobernador me manda: juicio={m.get('muestra_juicio', '?')} · "
            f"recup+{m.get('recup_extra', '?')} · lote={m.get('lote', '?')} · banco tope {m.get('max_cola', '?')}"
            + (f" · ejercitar×{len(ej)}" if ej else " · nada que ejercitar")
            + (" · perfil neutro (aún aprendo de mis actas)" if perfil.get("neutro") else "")
        )
    else:
        lineas.append("Arranco sin perfil: mandos de fábrica.")
    if acta:
        r, h, ab = acta.get("tanda_resumen", {}), acta.get("huecos", {}), acta.get("ab", {})
        lineas.append(
            f"Mi última acta ({acta.get('tanda', '?')}): CRAG {r.get('crag_medio', '?')} "
            f"(var {r.get('crag_var', '?')}) · resueltos {r.get('resueltos', '?')}/{r.get('ejecuciones', '?')} · "
            f"{h.get('huecos_nuevos', '?')} huecos nuevos ({h.get('huecos_total', '?')} históricos) · "
            f"banco {acta.get('banco', {}).get('pendientes', '?')} · "
            f"A/B {ab.get('gana_a', 0)}-{ab.get('gana_b', 0)}-{ab.get('empates', 0)}"
        )
    else:
        lineas.append("Aún no tengo actas: este será mi primer ciclo con memoria.")
    cuerpo = "\n".join(lineas)

    # ── guardia anti-inundación: si el parte no cambió, callar ──
    huella = hashlib.sha1(cuerpo.encode()).hexdigest()
    try:
        if not forzar and open(HUELLA, encoding="utf-8").read().strip() == huella:
            return
    except FileNotFoundError:
        pass

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(CARTAS, "a", encoding="utf-8") as f:
        f.write(
            f"\n## 🤖 MOSAIC → la mesa · {ts}\n\n{cuerpo}\n\n"
            "*(parte de guardia determinista — parseado de `data/perfil_lanzamiento.json` y "
            "`data/actas/`, sin modelo; auditable línea a línea)*\n"
        )
    with open(HUELLA, "w", encoding="utf-8") as f:
        f.write(huella)
    print(f"🤖 MOSAIC dejó su parte en la mesa ({ts})")


if __name__ == "__main__":
    main()
