#!/usr/bin/env python3
"""
🧭 ROUTER — el router INTELIGENTE de la casa (encargo Gustavo 7-jul: «las 5 propuestas,
5 modos, y que también decida cambios de modo»). Reimplementación mosaic-nativa del
model_router.py de /Expuesto (decisión #2 del dossier de Sombra) + FLOTA_RAM §6.

LAS 5 CAPAS (las 5 propuestas de Gustavo, apiladas — no compiten, se refinan):
  1️⃣ OFICIO   (P1): rol → oficio → modelo, tabla fija. La base determinista.
  2️⃣ TALLA    (P2): tokens del prompt → tier (micro/mediano/grande) — sube o baja la apuesta.
  3️⃣ CONTENIDO(P3): heurística determinista (código/razonamiento/visión/general) SIN latencia;
      el clasificador micro (@8095) SOLO si la heurística duda Y está vivo (latencia solo si aporta).
  4️⃣ BREAKER  (P4): dignidad (data/dignidad_modelos.json) + sonda de vivos + fallback ordenado.
      Dignidad < 0.5 en ese oficio → el modelo se salta (el ledger manda).
  5️⃣ DUELO    (P5): SOLO con --critico: 2 modelos en paralelo + árbitro. El router DEVUELVE EL
      PLAN del duelo (quién vs quién, árbitro) — ejecutarlo es del llamante (palabra, no manos).

LOS MODOS (data/inventario_modelos.yaml — la fuente única): 🏛️ orquesta(+v5) · 🎩 director ·
🐝 enjambre · 🔬 micro_masa · ☢️ nuclear. El router los CONOCE, detecta el actual (sondas),
RECOMIENDA cambio y prepara el PLAN de cambio (comandos exactos).

DOCTRINA (nace apagado · regla del hierro):
  · ROUTER_MANOS=0 (default): cambiar-modo IMPRIME el plan (bajar/subir), no toca nada.
  · ROUTER_MANOS=1: ejecuta el plan CON guardias (Σgb ≤ presupuesto verificado EN código).
  · ☢️ NUCLEAR: JAMÁS se ejecuta desde aquí — exige el sello off-loop de la mesa
    (data/senales/OFFLOOP_SELLADO) Y el gesto humano. Sin sello, ni el plan se da entero.
  · El enchufe en turno_rol es OPT-IN (ROUTER=1); sin él, todo sigue como siempre.

CLI:
  ./router.py --decidir --rol auditor [--prompt-file F] [--critico] [--plano]
  ./router.py --modo            (detecta el actual + recomienda)
  ./router.py --cambiar-modo director [--rumbo "por qué"]
  ./router.py --tabla | --self-test | --revalidar   (--revalidar: la hija verifica su herencia)
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import yaml

BASE = Path(os.environ.get("MOSAIC_BASE", Path(__file__).resolve().parent))
INVENTARIO = BASE / "data" / "inventario_modelos.yaml"
DIGNIDAD = BASE / "data" / "dignidad_modelos.json"
SELLO_OFFLOOP = BASE / "data" / "senales" / "OFFLOOP_SELLADO"
HOSTS = {"macbook": os.environ.get("ROUTER_HOST_MACBOOK", "127.0.0.1"),
         "mini": os.environ.get("ROUTER_HOST_MINI", "localhost")}
UMBRAL_DIGNIDAD = float(os.environ.get("ROUTER_DIGNIDAD_MIN", "0.5"))

# 1️⃣ OFICIO — P1 de Gustavo (tabla rol→oficio; el modelo sale del inventario por oficio)
ROL_A_OFICIO = {"auditor": "general", "diseno": "general", "gobierno": "general",
                "infra": "general", "infraestructura": "general", "ingesta": "general",
                "portavoz": "general", "produccion": "forja", "seguridad": "red-team",
                "central": "general", "celador": "general", "estafeta": "general"}


def _carga_inventario():
    d = yaml.safe_load(INVENTARIO.read_text(encoding="utf-8"))
    if not d or "modelos" not in d or "modos" not in d:
        sys.exit("🧭 router: inventario ilegible o sin modelos/modos — no decido a ciegas")
    return d


INV = _carga_inventario()
MODELOS, MODOS = INV["modelos"], INV["modos"]
PRESUPUESTO = INV.get("presupuesto_gb", {"macbook": 42, "mini": 11})

# D2 (Opus 14:20): sillas CRÍTICAS que NO degradan en silencio — esperan al bueno o piden
# subir flota; su output degradado JAMÁS se sella como si fuera del modelo bueno.
CRITICOS = set((os.environ.get("ROUTER_CRITICOS") or "auditor,seguridad").split(","))
_TIER_ORDEN = ["micro", "pequeno", "mediano", "grande", "ultra"]


def _flag_si(v):
    """YAML: `no`→False (bool), `si`→'si' (str) — se normaliza (misma regla que la calculadora)."""
    return v in (True, "si", "sí", "yes", "true", 1)


def _dignidad():
    try:
        return json.load(open(DIGNIDAD, encoding="utf-8"))
    except Exception:
        return {}


def vivo(host, puerto, timeout=None):
    # sonda configurable (la TUI la baja para que el mapa no se cuelgue si el mini duerme)
    if timeout is None:
        timeout = float(os.environ.get("ROUTER_SONDA_TIMEOUT", "2"))
    try:
        with urllib.request.urlopen(f"http://{host}:{puerto}/v1/models", timeout=timeout):
            return True
    except Exception:
        return False


def _tokens(texto):
    """Talla sin red: el estimador conservador de la casa (presupuesto_contexto)."""
    try:
        from presupuesto_contexto import CHARS_POR_TOKEN
        return int(len(texto) / CHARS_POR_TOKEN) + 1
    except Exception:
        return int(len(texto) / 3.0) + 1


# 2️⃣ TALLA — P2 de Gustavo (umbrales por tokens; el grande NO se despierta por capricho)
def capa_talla(tokens):
    if tokens < 200:
        return "micro"
    if tokens <= 2000:
        return "mediano"
    return "grande"


# 3️⃣ CONTENIDO — P3: heurística primero (0 latencia), micro-clasificador solo si duda
_RX_CODIGO = re.compile(r"```|def |import |function |#!/|\bclass\s+\w+|SELECT .* FROM|curl -|bash |\.py\b|\.sh\b")
_RX_RAZONA = re.compile(r"\b(por qué|porqué|demuestra|paso a paso|teorema|colisi[oó]n|contradic|deduce|analiza a fondo|multi-turno)\b", re.I)
_RX_VISION = re.compile(r"\b(imagen|foto|captura|\.png|\.jpg|\.heic)\b", re.I)


def capa_contenido(texto):
    hits = {"codigo": bool(_RX_CODIGO.search(texto)), "razonamiento": bool(_RX_RAZONA.search(texto)),
            "vision": bool(_RX_VISION.search(texto))}
    marcados = [k for k, v in hits.items() if v]
    if len(marcados) == 1:
        return marcados[0], "heuristica"
    if not marcados:
        return "general", "heuristica"
    # duda (varios) → clasificador micro SI está vivo (P3 sin pagar latencia cuando no aporta)
    host, puerto = HOSTS["mini"], 8095
    if vivo(host, puerto):
        try:
            cuerpo = json.dumps({"model": "local", "max_tokens": 8, "temperature": 0,
                                 "messages": [{"role": "user", "content":
                                               "Clasifica en UNA palabra (codigo|razonamiento|vision|general):\n"
                                               + texto[:1500]}]}).encode()
            req = urllib.request.Request(f"http://{host}:{puerto}/v1/chat/completions", data=cuerpo,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                out = json.loads(r.read().decode())["choices"][0]["message"]["content"].lower()
            for c in ("codigo", "razonamiento", "vision", "general"):
                if c in out:
                    return c, "clasificador@8095"
        except Exception:
            pass
    return marcados[0], "heuristica-ambigua"


OFICIO_POR_CONTENIDO = {"codigo": ["codigo", "forja", "codigo-largo"],
                        "razonamiento": ["razonamiento", "director"],
                        "vision": [], "general": ["general"]}


def _asignacion_conf():
    """servidores.conf → {(maquina,puerto): patrón_gguf} (VERDAD de asignación).
    El patrón conserva sus comodines: el conf usa rutas con * y el match es fnmatch."""
    m = {}
    try:
        for ln in (BASE / "servidores.conf").read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            c = ln.split("|")
            if len(c) >= 6:
                m[(c[0].strip(), c[1].strip())] = "/".join(c[4].split("/")[-2:])
    except OSError:
        pass
    return m


def _conf_sirve(patron, gguf):
    """¿La línea del conf sirve ESTE gguf del catálogo? Se comparan las DOS últimas
    componentes (carpeta/fichero): el conf discrimina por CARPETA (`qwen25-3b/*.gguf`)
    y el basename solo haría que `*.gguf` casara con todo (el bug del juez@8090)."""
    import fnmatch
    cola = "/".join(str(gguf).split("/")[-2:]).lower()
    return fnmatch.fnmatch(cola, patron.lower())


def _candidatos(oficios, tier_min):
    """Modelos del catálogo que sirven esos oficios (api chat). Orden: PRIMERO el oficio más
    prioritario de la lista (el del ROL va delante), luego el tier justo."""
    orden_tier = ["micro", "pequeno", "mediano", "grande", "ultra"]
    piso = orden_tier.index(tier_min) if tier_min in orden_tier else 2
    out = []
    for nombre, m in MODELOS.items():
        if m.get("api") != "chat":
            continue                                        # Unholy/ALPACA fuera (prueba 14:05)
        mios = set(m.get("oficios", [])) & set(oficios)
        if not mios:
            continue
        prio = min(oficios.index(o) for o in mios)          # el oficio del ROL pesa más
        t = orden_tier.index(m.get("tier", "mediano"))
        out.append((prio, abs(t - piso), t < piso, nombre, m))
    return [(n, m) for _, _, _, n, m in sorted(out)]


# 4️⃣ BREAKER — P4: dignidad + vivos + fallback (jamás quedarse sin boca si hay una viva)
def capa_breaker(candidatos, oficio_dig):
    dig = _dignidad()
    asig = _asignacion_conf()
    puertos_de = {}                                         # modelo → [(host,puerto)] asignados
    for (maq, pto), patron in asig.items():
        for nombre, m in MODELOS.items():
            if patron and _conf_sirve(patron, m.get("gguf", "")):
                puertos_de.setdefault(nombre, []).append((HOSTS.get(maq, maq), pto))
    elegidos, saltados = [], []
    for nombre, m in candidatos:
        clave = next((k for k in dig if k.lower().startswith(nombre.split("-")[0].lower())
                      and k.endswith("|" + oficio_dig)), None)
        d = dig.get(clave, {}).get("dignidad") if clave else None
        if d is not None and d < UMBRAL_DIGNIDAD:
            saltados.append(f"{nombre}(dignidad {d})")
            continue
        for host, pto in puertos_de.get(nombre, []):
            elegidos.append({"modelo": nombre, "host": host, "puerto": int(pto),
                             "url": f"http://{host}:{pto}/v1", "razonador": _flag_si(m.get("razonador")),
                             "reserva": int(m.get("reserva", 0) or 0),
                             "tier": m.get("tier", "mediano"), "vivo": vivo(host, pto)})
    vivos = [e for e in elegidos if e["vivo"]]
    return (vivos or elegidos), saltados                    # vivos primero; sin vivos → asignados (que suba la flota)


def decidir(rol, texto, critico=False):
    oficio_rol = ROL_A_OFICIO.get(rol, "general")           # 1️⃣
    tokens = _tokens(texto)
    talla = capa_talla(tokens)                              # 2️⃣
    contenido, fuente_c = capa_contenido(texto)             # 3️⃣
    # política (probada 7-jul): con SILLA conocida el ROL manda y el contenido AÑADE fallbacks
    # (el auditor no cambia de gremio porque sus LECTURAS traigan código); sin rol conocido,
    # el contenido decide (uso libre del router: chat/API/gateway).
    ofic_cont = OFICIO_POR_CONTENIDO.get(contenido, [])
    if rol in ROL_A_OFICIO:
        oficios = [oficio_rol] + [o for o in ofic_cont if o != oficio_rol]
    else:
        oficios = ofic_cont or [oficio_rol]
    if contenido == "vision":
        return {"ok": False, "motivo": "visión: el VL-7B está en safetensors SIN gguf — ruta pendiente (inventario no_llm)"}
    tier_min = {"micro": "micro", "mediano": "mediano", "grande": "grande"}[talla]
    cands = _candidatos(oficios, tier_min)
    bocas, saltados = capa_breaker(cands, oficios[0])       # 4️⃣
    if not bocas:
        return {"ok": False, "motivo": f"sin boca para oficios {oficios} (saltados: {saltados})",
                "recomendacion": "cambiar de modo o subir flota"}
    r = {"ok": True, "rol": rol, "tokens": tokens, "talla": talla,
         "contenido": contenido, "fuente_contenido": fuente_c, "oficios": oficios,
         "eleccion": bocas[0], "fallbacks": bocas[1:3], "saltados_por_dignidad": saltados}
    # 🔻 D2 (Opus 14:20): ¿la elección DEGRADA de talla? — el modelo VIVO elegido está por
    #    debajo del tier que pedía la talla. Se DECLARA (transparencia): la silla crítica no
    #    degrada en silencio y su output no se sella como del bueno; una silla normal acepta
    #    al HERMANO (mismo oficio, ya garantizado por _candidatos). El llamante decide.
    piso = _TIER_ORDEN.index(tier_min) if tier_min in _TIER_ORDEN else 2
    tier_elegido = _TIER_ORDEN.index(bocas[0].get("tier", "mediano"))
    critico = rol in CRITICOS
    r["critico"] = critico
    if tier_elegido < piso:
        r["degradado"] = {"pedido": tier_min, "servido": bocas[0].get("tier", "mediano"),
                          "hermano_del_oficio": oficios[0],
                          "no_sellar_como_bueno": True,
                          "aviso": (f"silla CRÍTICA «{rol}» degradada a {bocas[0].get('tier')} "
                                    "(pedía " + tier_min + "): NO sellar como el modelo bueno; "
                                    "mejor esperar al bueno o subir flota" if critico else
                                    f"degradado a hermano {bocas[0].get('tier')} del oficio "
                                    f"{oficios[0]} (pedía {tier_min}) — aceptable en no-crítica")}
        if critico:
            r["recomendacion_modo"] = r.get("recomendacion_modo") or \
                "director/subir flota — una silla crítica pide su modelo bueno"
    if talla == "grande" and MODELOS.get(bocas[0]["modelo"], {}).get("tier") not in ("grande", "ultra"):
        r["recomendacion_modo"] = ("director — la talla pide un grande y ninguno tiene boca "
                                   "(./router.py --cambiar-modo director)")
    if critico:                                             # 5️⃣ — el PLAN del duelo, no su ejecución
        a = bocas[0]["modelo"]
        b = next((x["modelo"] for x in bocas[1:] if x["modelo"] != a), None)
        if b is None:                                       # rival DISTINTO de otro oficio afín, vivo si puede
            otras, _ = capa_breaker(_candidatos(["razonamiento", "general"], "mediano"), oficios[0])
            b = next((x["modelo"] for x in otras if x["modelo"] != a), None)
        arbitro = "qwen3-30b-a3b-thinking" if "qwen3-30b-a3b-thinking" in MODELOS else "qwen3-14b"
        if arbitro == a or arbitro == b:
            arbitro = next(n for n in ("qwen3-30b-a3b-thinking", "qwen3-14b", "deepseek-r1-distill-14b")
                           if n in MODELOS and n not in (a, b))
        r["duelo"] = ({"a": a, "b": b, "arbitro": arbitro,
                       "nota": "ejecutar el duelo es del llamante (2 llamadas + árbitro juzga cuál responde mejor)"}
                      if b else {"sin_rival": "no hay 2º modelo DISTINTO con boca — el duelo no aporta; va la elección simple"})
    return r


# ── MODOS ────────────────────────────────────────────────────────────
def _roster_vivo(nombre_modo):
    filas = []
    for f in MODOS[nombre_modo].get("roster", []):
        m = MODELOS.get(f["modelo"], {})
        host = HOSTS.get(m.get("maquina", "macbook"), "127.0.0.1")
        filas.append({**f, "gb": m.get("gb", 0), "host": host, "vivo": vivo(host, f["puerto"])})
    return filas


def modo_actual():
    puntuaciones = {}
    for nombre in MODOS:
        filas = _roster_vivo(nombre)
        arriba = sum(1 for f in filas if f["vivo"])
        puntuaciones[nombre] = {"arriba": arriba, "de": len(filas),
                                "pct": round(arriba / max(len(filas), 1), 2)}
    mejor = max(puntuaciones, key=lambda k: puntuaciones[k]["pct"])
    return {"detectado": mejor if puntuaciones[mejor]["pct"] > 0 else "apagado",
            "sondas": puntuaciones}


def recomendar_modo(texto=""):
    """Recomienda modo por la DEMANDA (talla/contenido del trabajo que viene)."""
    if not texto:
        return {"recomendado": "orquesta", "motivo": "sin señal de demanda → el modo de serie"}
    t = _tokens(texto)
    c, _ = capa_contenido(texto)
    if t > 60000:
        return {"recomendado": "nuclear", "motivo": f"{t} tokens — solo el 70B lo piensa entero",
                "aviso": "☢️ MANUAL: exige sello off-loop + gesto de Gustavo. El router NO lo enciende."}
    if t > 2000 or c == "razonamiento":
        return {"recomendado": "director", "motivo": f"talla {t} tok / contenido {c} → grande de reduce + apoyos"}
    if c == "codigo":
        return {"recomendado": "orquesta", "motivo": "código de talla normal — la orquesta tiene boca de código"}
    return {"recomendado": "orquesta", "motivo": "trabajo de pleno normal"}


def _plan_cambio(destino):
    if destino not in MODOS:
        sys.exit(f"🧭 modo desconocido: {destino} (hay: {', '.join(MODOS)})")
    filas = _roster_vivo(destino)
    # guardia del hierro: Σgb por máquina ≤ presupuesto — calculada AQUÍ, no en una carta
    por_maq = {}
    for f in filas:
        maq = MODELOS[f["modelo"]].get("maquina", "macbook")
        por_maq[maq] = por_maq.get(maq, 0) + f["gb"]
    for maq, gb in por_maq.items():
        if gb > PRESUPUESTO.get(maq, 0):
            sys.exit(f"🧭 GUARDIA: {destino} pide {gb}GB en {maq} > presupuesto {PRESUPUESTO.get(maq)}GB — NI PLAN")
    plan = {"modo": destino, "ram_por_maquina": por_maq, "bajar": [], "subir": []}
    maqs_del_modo = set(por_maq)                            # el cambio SOLO toca SUS máquinas
    for (maq, pto), patron in _asignacion_conf().items():   # lo vivo que NO está en el roster → baja
        if maq not in maqs_del_modo:
            continue                                        # el mini y sus jueces no son de este modo
        host = HOSTS.get(maq, maq)
        if vivo(host, pto) and not any(str(f["puerto"]) == pto and f["host"] == host for f in filas):
            plan["bajar"].append(f"# bajar {patron}@{pto} ({maq}) — vía lanzar_cluster/kill del pid")
    for f in filas:
        if not f["vivo"]:
            m = MODELOS[f["modelo"]]
            plan["subir"].append(
                f"llama-server -m {m['gguf']} --port {f['puerto']} -ngl 99 --ctx-size {f['ctx']} {f.get('flags','')}".strip()
                + f"   # {f['modelo']} · {m['gb']}GB · {m.get('maquina')}")
    return plan


def cambiar_modo(destino, rumbo=""):
    if destino == "nuclear":
        if not SELLO_OFFLOOP.exists():
            return {"ok": False, "motivo": "☢️ nuclear SIN el sello off-loop de la mesa "
                    "(data/senales/OFFLOOP_SELLADO no existe). El protocolo flota↓→70B↑→resolver→70B↓→flota↑ "
                    "debe sellarse ANTES (decisión #3 Opus 21:30). El router JAMÁS lo enciende solo."}
        return {"ok": False, "motivo": "☢️ sello presente, pero nuclear = GESTO HUMANO igualmente: "
                "el router entrega el plan y Gustavo aprieta.", "plan": _plan_cambio("nuclear")}
    plan = _plan_cambio(destino)
    if os.environ.get("ROUTER_MANOS", "0") != "1":
        return {"ok": True, "modo": destino, "manos": False, "rumbo": rumbo,
                "plan": plan, "nota": "ROUTER_MANOS=0 → SOLO PLAN (nace apagado). ROUTER_MANOS=1 ejecutaría."}
    # ROUTER_MANOS=1 — ejecutar es COSA SERIA: aquí solo lo dejamos preparado y acotado.
    return {"ok": False, "motivo": "ROUTER_MANOS=1 aún no cablea la ejecución: el subir/bajar real "
            "lo hace lanzar_cluster en el Mac — conexión pendiente de la lupa de Opus (decisión de mesa).",
            "plan": plan}


def self_test():
    fallos = []
    orden_tier = ["micro", "pequeno", "mediano", "grande", "ultra"]
    for n, m in MODELOS.items():
        if m.get("tier") not in orden_tier:
            fallos.append(f"{n}: tier raro {m.get('tier')}")
    for nombre, modo in MODOS.items():
        vistos, por_maq = set(), {}
        for f in modo.get("roster", []):
            if f["modelo"] not in MODELOS:
                fallos.append(f"{nombre}: modelo fantasma {f['modelo']}")
                continue
            if f["modelo"] in vistos:
                fallos.append(f"{nombre}: modelo duplicado {f['modelo']} (regla 2 FLOTA_RAM)")
            vistos.add(f["modelo"])
            maq = MODELOS[f["modelo"]].get("maquina", "macbook")
            por_maq[maq] = por_maq.get(maq, 0) + MODELOS[f["modelo"]].get("gb", 0)
        for maq, gb in por_maq.items():
            if gb > PRESUPUESTO.get(maq, 0):
                fallos.append(f"{nombre}: {gb}GB > presupuesto {maq} {PRESUPUESTO.get(maq)}GB (regla 1)")
    d = decidir("auditor", "resume el estado del pleno")
    if not d.get("ok"):
        fallos.append(f"decidir básico falló: {d.get('motivo')}")
    print(json.dumps({"ok": not fallos, "modelos": len(MODELOS), "modos": list(MODOS), "fallos": fallos},
                     ensure_ascii=False))
    return 0 if not fallos else 1


def revalidar():
    """D3 (Opus 14:20): la HIJA re-valida el mapeo HEREDADO contra SU inventario real — FALLO
    ALTO si la plantilla apunta a un modelo/oficio que esta máquina NO tiene. «Heredas la
    plantilla, verificas que tu flota la sostiene.» Determinista, sin red (mira el catálogo)."""
    fallos, avisos = [], []
    # 1 · cada rol con silla debe tener AL MENOS un modelo que sirva su oficio en el catálogo
    turnos = BASE / "roles" / "turnos"
    sillas = sorted(p.stem for p in turnos.glob("*.yaml")) if turnos.is_dir() else []
    for rol in sillas:
        oficio = ROL_A_OFICIO.get(rol, "general")
        sirve = [n for n, m in MODELOS.items() if oficio in m.get("oficios", []) and m.get("api") == "chat"]
        if not sirve:
            fallos.append(f"rol «{rol}» (oficio {oficio}): NINGÚN modelo del catálogo lo sirve")
    # 2 · cada modo referencia SOLO modelos que existen, y cabe en el presupuesto de SU máquina
    for nombre, modo in MODOS.items():
        for f in modo.get("roster", []):
            if f["modelo"] not in MODELOS:
                fallos.append(f"modo «{nombre}»: referencia el modelo inexistente «{f['modelo']}»")
    # 3 · cada modelo declara una máquina con presupuesto conocido
    for n, m in MODELOS.items():
        maq = m.get("maquina", "?")
        if maq not in PRESUPUESTO:
            avisos.append(f"modelo «{n}»: máquina «{maq}» sin presupuesto declarado")
    r = {"ok": not fallos, "sillas": len(sillas), "modelos": len(MODELOS),
         "fallos": fallos, "avisos": avisos,
         "nota": "heredas la plantilla, verificas que TU flota la sostiene (D3, Opus 14:20)"}
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if not fallos else 1


def main():
    a = sys.argv[1:]

    def arg(f, d=None):
        return a[a.index(f) + 1] if f in a and a.index(f) + 1 < len(a) else d
    if "--self-test" in a:
        sys.exit(self_test())
    if "--revalidar" in a:
        sys.exit(revalidar())
    if "--tabla" in a:
        for nombre, modo in MODOS.items():
            gb = sum(MODELOS.get(f["modelo"], {}).get("gb", 0) for f in modo.get("roster", []))
            print(f"{nombre:<12} {gb:>5.1f}GB · {len(modo.get('roster', []))} bocas · {modo.get('descripcion','')}")
        return
    if "--modo" in a:
        print(json.dumps({"actual": modo_actual(), "recomendacion": recomendar_modo(
            Path(arg("--prompt-file")).read_text(encoding="utf-8", errors="replace") if arg("--prompt-file") else "")},
            ensure_ascii=False))
        return
    if "--cambiar-modo" in a:
        print(json.dumps(cambiar_modo(arg("--cambiar-modo"), arg("--rumbo", "")), ensure_ascii=False, indent=1))
        return
    if "--decidir" in a:
        rol = arg("--rol", "auditor")
        texto = Path(arg("--prompt-file")).read_text(encoding="utf-8", errors="replace") if arg("--prompt-file") else ""
        r = decidir(rol, texto, critico="--critico" in a)
        if "--plano" in a and r.get("ok"):                  # bash 3.2-safe: una línea
            e = r["eleccion"]
            deg = r.get("degradado")
            print(f"puerto={e['puerto']} host={e['host']} modelo={e['modelo']} vivo={1 if e['vivo'] else 0} "
                  f"talla={r['talla']} contenido={r['contenido']} razonador={1 if e.get('razonador') else 0} "
                  f"critico={1 if r.get('critico') else 0} degradado={1 if deg else 0} "
                  f"servido={e.get('tier','?')}")
        else:
            print(json.dumps(r, ensure_ascii=False))
        return
    print("uso: --decidir --rol R [--prompt-file F] [--critico] [--plano] | --modo | "
          "--cambiar-modo M [--rumbo TXT] | --tabla | --self-test", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
