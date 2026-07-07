#!/usr/bin/env python3
"""
🚪 GATEWAY — la BOCA ÚNICA de MOSAIC: fusiona intención + router + flota (encargo Gustavo
7-jul: «fusionar la lógica del gateway con el router y el levantar server»). Reimplementación
mosaic-nativa del diseño de 3 capas del dossier (info/DEBATE_GATEWAY_ROUTER.md, decisiones
#1 «crece el server» + #2 «portar model_router»).

LAS 3 CAPAS (una entrada → un destino):
  1️⃣ INTENCIÓN  — ¿rag(pregunta) · accion(tool con sello) · comando(sistema) · charla?
     Heurística determinista SIN latencia; el micro-clasificador @8095 SOLO si duda y vive.
  2️⃣ MODELO     — delega en router.py (las 5 capas: oficio→talla→contenido→breaker→duelo).
  3️⃣ FLOTA      — ¿el modelo elegido está RESIDENTE? Si no, el gateway PREPARA el levantado
     (router.cambiar_modo / lanzar_cluster) — NACE APAGADO: plan, no manos.

Y LAS SALIDAS (por dónde vuelve): respuesta /v1 · buzón (estafeta) · carta (cartero).

DOCTRINA (no negociable, heredada del bridge + la casa):
  · NACE APAGADO: GATEWAY_MANOS=0 (default) → planifica y devuelve, JAMÁS levanta ni envía.
  · SOLO-INTERNO v1: la salida externa exige gesto humano (como el cartero) — decisión #5.
  · PALABRA JAMÁS MANOS: una `accion` propone; la ejecuta el sello, no el gateway.
  · ANTI-POISONING: entrada externa (--externa) entra ETIQUETADA y NO manda (no dispara accion/comando).
  · FALLBACK ELEGANTE: sin boca del tier pedido, baja de tier; nunca «responde en el sitio equivocado».

LEVANTAR SERVER (la fusión que pidió Gustavo):
  gateway.py --levantar <modo>   → une el PLAN de router.cambiar_modo con lanzar_cluster:
  con GATEWAY_MANOS=0 imprime el plan (bajar/subir exactos); con =1 (y no-nuclear) lo cablea
  a lanzar_cluster.sh. ☢️ nuclear: JAMÁS aquí (exige sello off-loop + gesto, como en router).

CLI:
  gateway.py --entrada --texto "…" [--canal api|buzon|correo] [--rol R] [--externa] [--json]
  gateway.py --levantar director [--rumbo "por qué"]
  gateway.py --topologia [--json]      (el mapa de servidores para la TUI — datos HONESTOS)
  gateway.py --self-test
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(os.environ.get("MOSAIC_BASE", Path(__file__).resolve().parent))
sys.path.insert(0, str(BASE))
LANZAR = os.environ.get("LLAMA_LAUNCH", str(BASE / "lanzar_cluster.sh"))

try:
    import router as R                                     # capas 2+3 + modos + inventario
except Exception as e:                                     # noqa: BLE001
    sys.exit(f"🚪 gateway: no cargo router.py ({e}) — es mi capa de modelo, no arranco sin él")


# 1️⃣ INTENCIÓN — heurística (0 latencia); micro-clasificador solo si duda
_RX_ACCION = re.compile(r"\b(ejecuta|lanza|env[ií]a|crea|borra|mueve|aplica|sella|despliega|instala)\b", re.I)
_RX_COMANDO = re.compile(r"^\s*(/|!|sudo |bash |python3? |\./)", re.I)
_RX_RAG = re.compile(r"\b(qu[eé]|c[oó]mo|cu[aá]l|cu[aá]ndo|d[oó]nde|por qu[eé]|resume|explica|busca|cita)\b", re.I)


def capa_intencion(texto, externa=False):
    t = texto.strip()
    if _RX_COMANDO.match(t):
        intent = "comando"
    elif _RX_ACCION.search(t):
        intent = "accion"
    elif _RX_RAG.search(t):
        intent = "rag"
    else:
        intent = "charla"
    # anti-poisoning: lo EXTERNO no manda — una acción/comando de fuera se degrada a material
    if externa and intent in ("accion", "comando"):
        return "rag", f"{intent}→rag (anti-poisoning: entrada externa no ejecuta, se lee como material)"
    return intent, "heuristica"


# salida (decisión #3/#5): a dónde vuelve la respuesta según el canal de entrada
SALIDA_POR_CANAL = {"api": "respuesta /v1", "buzon": "estafeta (buzón interno)",
                    "correo": "cartero (salida — interno pluma; externo espera sello humano)"}


def entrada(texto, canal="api", rol="", externa=False, critico=False):
    intent, fuente_i = capa_intencion(texto, externa)      # 1️⃣
    modelo = R.decidir(rol or "portavoz", texto, critico=critico)  # 2️⃣ (router: 5 capas)
    flota = {"residente": None, "plan": None}              # 3️⃣
    if modelo.get("ok"):
        e = modelo["eleccion"]
        flota["residente"] = e["vivo"]
        if not e["vivo"]:
            reco = R.recomendar_modo(texto).get("recomendado", "orquesta")
            flota["plan"] = (f"el modelo {e['modelo']} no está residente → "
                             f"gateway.py --levantar {reco} (o subir su puerto). NACE APAGADO: es plan.")
    permiso = "propone (palabra jamás manos: la acción la ejecuta el sello)" if intent == "accion" \
        else "solo-interno (la salida externa exige gesto humano)" if canal == "correo" \
        else "lectura"
    return {"ok": modelo.get("ok", False), "intencion": intent, "fuente_intencion": fuente_i,
            "canal": canal, "externa": externa, "permiso": permiso,
            "modelo": modelo, "flota": flota,
            "salida": SALIDA_POR_CANAL.get(canal, "respuesta /v1")}


def levantar(modo, rumbo=""):
    """La FUSIÓN: el plan de modo del router + el brazo de lanzar_cluster.
    GATEWAY_MANOS=0 → solo el plan. =1 (no-nuclear) → cablea a lanzar_cluster."""
    plan = R.cambiar_modo(modo, rumbo)                     # ya rechaza nuclear sin sello
    if not plan.get("ok"):
        return plan                                        # nuclear/guardia: el motivo viaja tal cual
    if os.environ.get("GATEWAY_MANOS", "0") != "1":
        plan["manos"] = False
        plan["nota"] = "GATEWAY_MANOS=0 → SOLO PLAN (nace apagado). =1 lo cablearía a lanzar_cluster."
        return plan
    # MANOS=1: el subir/bajar real lo hace lanzar_cluster con SU presupuesto (doble red).
    # v1 acotado: relanzamos la flota de servidores.conf; el roster por-modo se materializa
    # editando el conf (el router ya da el plan exacto) — la edición del conf es gesto humano.
    try:
        r = subprocess.run(["bash", LANZAR, "estado"], capture_output=True, text=True,
                           timeout=30, cwd=str(BASE), env={**os.environ, "MOSAIC_BASE": str(BASE)})
        plan["lanzar_cluster_estado"] = (r.stdout or r.stderr)[-800:]
        plan["manos"] = True
        plan["nota"] = ("MANOS=1: consulté lanzar_cluster estado. El subir/bajar por-modo exige "
                        "aplicar el plan al servidores.conf (gesto humano) y luego `lanzar_cluster subir`. "
                        "El gateway NO reescribe el conf solo — regla del hierro.")
    except Exception as e:                                 # noqa: BLE001
        plan["error"] = f"lanzar_cluster no respondió: {e}"
    return plan


def topologia():
    """El MAPA DE SERVIDORES — datos HONESTOS (anti-humo): nodos reales (2 máquinas), sus
    modelos del inventario con sonda VIVA + tier/gb/oficio, y el modo actual/recomendado.
    Sin '% hack' inventado ni empresas de ficción: la carga real es residente/caído + gb."""
    inv = R.INV
    modo = R.modo_actual()
    nodos = {}
    for maq, pres in R.PRESUPUESTO.items():
        nodos[maq] = {"host": R.HOSTS.get(maq, maq), "presupuesto_gb": pres,
                      "usado_gb": 0.0, "modelos": []}
    asig = R._asignacion_conf()
    for (m, pto), patron in asig.items():
        if m not in nodos:
            nodos[m] = {"host": R.HOSTS.get(m, m), "presupuesto_gb": 0, "usado_gb": 0.0, "modelos": []}
        nombre = next((n for n, mm in inv["modelos"].items() if R._conf_sirve(patron, mm.get("gguf", ""))), patron)
        meta = inv["modelos"].get(nombre, {})
        vivo = R.vivo(nodos[m]["host"], pto)
        gb = meta.get("gb", 0)
        if vivo:
            nodos[m]["usado_gb"] += gb
        nodos[m]["modelos"].append({"modelo": nombre, "puerto": pto, "vivo": vivo,
                                    "tier": meta.get("tier", "?"), "gb": gb,
                                    "oficios": meta.get("oficios", []), "modo_asignado": patron})
    return {"nodos": nodos, "modo_actual": modo["detectado"], "sondas_modo": modo["sondas"],
            "modos_disponibles": {k: {"gb": round(sum(inv["modelos"].get(f["modelo"], {}).get("gb", 0)
                                                      for f in v.get("roster", [])), 1),
                                      "bocas": len(v.get("roster", [])),
                                      "descripcion": v.get("descripcion", "")}
                                  for k, v in inv["modos"].items()}}


def self_test():
    fallos = []
    for canal in ("api", "buzon", "correo"):
        r = entrada("resume el estado del pleno", canal=canal, rol="auditor")
        if not isinstance(r.get("intencion"), str):
            fallos.append(f"entrada({canal}) sin intención")
    if capa_intencion("ejecuta el despliegue", externa=True)[0] != "rag":
        fallos.append("anti-poisoning NO degradó una acción externa")
    if capa_intencion("/reiniciar")[0] != "comando":
        fallos.append("comando no detectado")
    t = topologia()
    if "nodos" not in t or "macbook" not in t["nodos"]:
        fallos.append("topología sin nodo macbook")
    nuc = levantar("nuclear")
    if nuc.get("ok"):
        fallos.append("nuclear NO fue rechazado (debe exigir sello off-loop)")
    print(json.dumps({"ok": not fallos, "canales": 3, "nodos": list(t.get("nodos", {})),
                      "modo_actual": t.get("modo_actual"), "fallos": fallos}, ensure_ascii=False))
    return 0 if not fallos else 1


def main():
    a = sys.argv[1:]

    def arg(f, d=None):
        return a[a.index(f) + 1] if f in a and a.index(f) + 1 < len(a) else d
    if "--self-test" in a:
        sys.exit(self_test())
    if "--topologia" in a:
        print(json.dumps(topologia(), ensure_ascii=False, indent=(1 if "--json" in a else None)))
        return
    if "--levantar" in a:
        print(json.dumps(levantar(arg("--levantar"), arg("--rumbo", "")), ensure_ascii=False, indent=1))
        return
    if "--entrada" in a:
        r = entrada(arg("--texto", ""), canal=arg("--canal", "api"), rol=arg("--rol", ""),
                    externa="--externa" in a, critico="--critico" in a)
        print(json.dumps(r, ensure_ascii=False, indent=(1 if "--json" in a else None)))
        return
    print("uso: --entrada --texto T [--canal api|buzon|correo] [--rol R] [--externa] [--critico] [--json] | "
          "--levantar MODO [--rumbo T] | --topologia [--json] | --self-test", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
