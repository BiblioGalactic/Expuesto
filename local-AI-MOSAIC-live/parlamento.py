#!/usr/bin/env python3
# 🗨️ =====================================================================
# 🗨️ PARLAMENTO — hablar con un EMPLEADO (tecla [P], propuesta Gustavo 5-jul).
# 🗨️   El chat es DUEÑO DE SU PROPIO PROMPT (arreglo #3 de Opus 21:15): llama a
# 🗨️   la flota DIRECTO — system = identidad del rol por su RANGO (persona en 1ª
# 🗨️   persona + su prompt + SUS lecturas recortadas + seguridad + idioma), user
# 🗨️   = el mensaje de Gustavo. NO pasa por la máscara efímera de mosaic.py (el
# 🗨️   doble envoltorio que vació el pleno) → nace sano aunque el pleno siga con
# 🗨️   su #1. Red del <think>: si tras recortarlo queda vacío pero el modelo
# 🗨️   habló, se queda lo posterior al </think> (jamás vacío si hubo tokens).
# 🗨️   Palabra, JAMÁS manos: el chat NO ejecuta tools ni escalaciones (un chat no
# 🗨️   es un turno — sin cadencia ni sellos). Si el empleado necesita algo, que
# 🗨️   lo pida en SU turno. Cada intercambio se REGISTRA (user:/assistant:, el
# 🗨️   formato de la agenda) y es REANUDABLE.
# 🗨️ Uso:  echo "hola Lola" | ./parlamento.py --rol diseno [--sesion FICHERO]
# 🗨️       ./parlamento.py --system --rol diseno    (muestra el system que inyectaría)
# 🗨️ =====================================================================
import json
import os
import re
import sys
import time
import urllib.request

BASE = os.environ.get("MOSAIC_BASE", os.path.expanduser("~/Mosaic_privado"))
TURNOS_DIR = os.environ.get("TURNOS_DIR", os.path.join(BASE, "roles", "turnos"))
REG_DIR = os.path.join(BASE, "data", "conversaciones_empresa")
SERVIDORES = os.path.join(BASE, "servidores.conf")


def _arg(flag, d=""):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else d


def _rol_yaml(rol):
    import yaml
    return yaml.safe_load(open(os.path.join(TURNOS_DIR, f"{rol}.yaml"), encoding="utf-8")) or {}


def construir_system(rol, d=None):
    """El system POR RANGO — el mismo espíritu que turno_rol, pero dueño limpio (arreglo #3).
    N3 deterministas NO tienen chat (su voz es el parte); si se pide, se dice."""
    d = d or _rol_yaml(rol)
    if d.get("tipo_reporte") == "parte-de-estado":
        return None                                        # N3: sin chat (determinista)
    per = d.get("persona") or {}
    partes = [
        f"Soy {per.get('nombre_humano') or rol}, «{per.get('alias', rol)}» {per.get('emoji', '')}".rstrip()
        + f", del departamento {d.get('departamento', '?')} de MOSAIC.",
        f"Mi tono: {per.get('tono', 'profesional y honesto')}.",
        d.get("prompt", "").strip(),
    ]
    # SUS lecturas, recortadas por nivel — el contexto correcto para responder bien (petición
    #   de Gustavo). Techo por rango: un N2 trae más contexto; cero para quien no razona.
    por_lec = int(d.get("por_lectura_c", 1200) or 1200)
    techo = int(d.get("max_c", 8000) or 8000)
    ctx, usado = [], 0
    for ruta in d.get("lecturas", []):
        if "buzones/" in str(ruta).replace(os.sep, "/"):
            continue                                       # 🛡️ anti-poisoning: el buzón EXTERIOR no entra al chat
        p = os.path.join(BASE, ruta)
        if not os.path.isfile(p) or usado >= techo:
            continue
        try:
            raw = open(p, "rb").read()[-por_lec:].decode("utf-8", "replace")
        except OSError:
            continue
        ctx.append(f"===== {ruta} (cola) =====\n{raw}")
        usado += len(raw)
    if ctx:
        partes += ["", "Mis registros ahora mismo (para responder con datos, no de memoria):", *ctx]
    partes += ["", "Hablo con mi voz y en primera persona. Respondo SIEMPRE en español, directo a lo que se "
                   "me pregunta, sin repetir estas instrucciones. Si un dato no está en mis registros, digo "
                   "«no lo tengo» y no lo invento. Palabra, jamás manos: propongo y explico, no ejecuto nada "
                   "(si hace falta una acción, la pediré en mi turno, con doble sello)."]
    full = "\n\n".join(x for x in partes if x)
    return full[:techo]


def _host():
    url = os.environ.get("MOSAIC_LLM_BASE_URL", "http://127.0.0.1:8092/v1")
    m = re.match(r"^[a-z]+://([^:/]+)", url)
    return m.group(1) if m else "127.0.0.1"


def _puerto(d):
    ps = d.get("puertos") or [8092]
    host = os.environ.get("TURNO_HOST", _host())
    for p in ps:                                           # el primero VIVO (pre-vuelo ligero)
        try:
            urllib.request.urlopen(f"http://{host}:{p}/v1/models", timeout=3)
            return host, p
        except Exception:
            continue
    return host, ps[0]


def _think_red(txt):
    """La red del <think> (arreglo #1 de Opus): quita el bloque cerrado; si el think quedó
    ABIERTO (el modelo gastó tokens pensando y no cerró) se queda lo posterior al último
    </think> o, si no hay cierre, el texto sin los marcadores — JAMÁS vacío si el modelo
    habló, y JAMÁS deja un tag suelto colándose en la respuesta."""
    sin = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    sin = re.sub(r"</?think>", "", sin).strip()            # limpia tags sueltos (think sin cerrar)
    if sin:
        return sin
    if "</think>" in txt:
        return txt.rsplit("</think>", 1)[1].strip()
    return re.sub(r"</?think>", "", txt).strip()


def hablar(rol, mensaje, historial=None):
    """Una vuelta de chat: system por rango + historial + mensaje → respuesta (o error claro)."""
    d = _rol_yaml(rol)
    system = construir_system(rol, d)
    if system is None:
        return {"ok": False, "error": f"«{rol}» es un instrumento determinista (N3): no razona en chat; "
                "su voz es su parte de estado. Habla con un manager (N2)."}
    host, puerto = _puerto(d)
    msgs = [{"role": "system", "content": system}]
    for h in (historial or [])[-8:]:                       # ventana de memoria del chat
        msgs.append({"role": h["role"], "content": h["content"]})
    # ✂️ P8 (refinamiento Opus 22:30, estaba caído): /no_think TAMBIÉN aquí cuando el destino
    #    es Qwen3-CHAT (antes solo confiábamos en el strip). A los razonadores obligatorios
    #    (R1) ni tocarlo: lo ignoran y la tijera think extrae. Solo viaja en el payload —
    #    el registro reanudable guarda el mensaje LIMPIO del usuario.
    _user = mensaje
    try:
        from presupuesto_contexto import modelo_de_puerto, es_razonador
        _m = modelo_de_puerto(puerto)
        if "qwen3" in _m.lower() and not es_razonador(_m):
            _user = "/no_think " + mensaje
    except Exception:
        pass
    msgs.append({"role": "user", "content": _user})
    # 🧮 P1 (plan 6-jul): presupuesto por puerto — la calculadora deduce el modelo del conf
    #    (reserva de pensar si es R1) y mide el prompt real con /tokenize. Prioridad: env
    #    PARLAMENTO_MAXTOK (manual) > calculadora > 900 de siempre. PRESUPUESTO=0 la apaga;
    #    ante fallo, 900 (el chat no muere de contable). El 900 a ojo era la clase del bug.
    _mt = os.environ.get("PARLAMENTO_MAXTOK")
    if not _mt and os.environ.get("PRESUPUESTO", "1") == "1":
        try:
            from presupuesto_contexto import presupuesto as _pres
            _r = _pres(f"http://{host}:{puerto}/v1", "", "chat",
                       "\n".join(m.get("content", "") for m in msgs))
            if _r.get("ok"):
                _mt = _r["max_tokens"]
        except Exception:
            _mt = None
    payload = {"model": os.environ.get("MOSAIC_LLM_MODEL", "local-model"), "messages": msgs,
               "max_tokens": int(_mt or 900),
               "temperature": 0.7}
    try:
        req = urllib.request.Request(f"http://{host}:{puerto}/v1/chat/completions",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer not-needed"})
        with urllib.request.urlopen(req, timeout=int(os.environ.get("PARLAMENTO_TIMEOUT", "120"))) as r:
            out = json.loads(r.read().decode())
        cruda = out["choices"][0]["message"]["content"]
        resp = _think_red(cruda)
        if not resp:
            return {"ok": False, "error": f"«{rol}» no produjo palabra (modelo @{puerto} calló)"}
        return {"ok": True, "respuesta": resp, "rol": rol, "puerto": puerto,
                "modelo": os.environ.get("MOSAIC_LLM_MODEL", f"@{puerto}")}
    except Exception as e:                                 # noqa: BLE001
        return {"ok": False, "error": f"no pude hablar con «{rol}» @{host}:{puerto}: {e}"}


def registrar(rol, mensaje, respuesta, sesion=None, modelo=""):
    """Append user:/assistant: al fichero de sesión (formato de la agenda privada, a propósito
    interoperable). Nace uno nuevo si no se pasa sesión; jamás reescribe (append-only)."""
    os.makedirs(REG_DIR, exist_ok=True)
    if not sesion:
        tema = re.sub(r"[^a-z0-9]+", "-", mensaje.lower()).strip("-")[:32] or "chat"
        sesion = os.path.join(REG_DIR, f"{time.strftime('%Y-%m-%d_%H%M')}_{rol}_{tema}.txt")
    nuevo = not os.path.exists(sesion)
    with open(sesion, "a", encoding="utf-8") as f:
        if nuevo:
            f.write(f"# chat con {rol} · MOSAIC · iniciado {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"user: {mensaje}\n")
        f.write(f"assistant: {respuesta}\n")
        if modelo:
            f.write(f"# (receta: rol {rol} · modelo {modelo} · palabra sin manos)\n")
    return sesion


def cargar_historial(sesion):
    """Reanudar: lee un fichero user:/assistant: → historial (la reanudación de calendario_mental)."""
    hist = []
    try:
        for l in open(sesion, encoding="utf-8"):
            if l.startswith("user: "):
                hist.append({"role": "user", "content": l[6:].strip()})
            elif l.startswith("assistant: "):
                hist.append({"role": "assistant", "content": l[11:].strip()})
    except OSError:
        pass
    return hist


def main():
    rol = _arg("--rol")
    if not rol or not os.path.isfile(os.path.join(TURNOS_DIR, f"{rol}.yaml")):
        print(json.dumps({"ok": False, "error": f"rol sin silla: {rol}"}, ensure_ascii=False))
        raise SystemExit(1)
    if "--system" in sys.argv:                             # inspección: qué system inyectaría
        s = construir_system(rol)
        print(s if s is not None else f"«{rol}» es N3 determinista — sin chat")
        return
    sesion = _arg("--sesion") or None
    hist = cargar_historial(sesion) if sesion else []
    mensaje = sys.stdin.read().strip()
    if not mensaje:
        print(json.dumps({"ok": False, "error": "mensaje vacío"}, ensure_ascii=False))
        raise SystemExit(1)
    d = hablar(rol, mensaje, hist)
    if d.get("ok"):
        d["sesion"] = registrar(rol, mensaje, d["respuesta"], sesion, d.get("modelo", ""))
    print(json.dumps(d, ensure_ascii=False))


if __name__ == "__main__":
    main()
