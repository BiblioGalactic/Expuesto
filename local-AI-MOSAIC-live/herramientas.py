#!/usr/bin/env python3
# 🧰 =====================================================================
# 🧰 HERRAMIENTAS — el DISPATCHER de tools (manifiesto Opus 13:36 · patrón del
# 🧰   dispatcher.js de wa-llama-bridge, reimplementado mosaic-nativo, cero JS).
# 🧰   (agente, tool, payload) →
# 🧰     · nivel_acceso (su yaml) ≥ nivel_requerido (data/herramientas.yaml) →
# 🧰       EJECUTA el cmd por el CONTRATO (JSON stdin → stdout {"ok":…}).
# 🧰     · si NO alcanza → EL ESCALADOR (plan Opus 13:56, modelo de mission-control
# 🧰       adaptado — json, sin sqlite, sin web): NO se deniega a secas — ticket ESC
# 🧰       en data/escalaciones.json (escritor único + lock) con PRIORIDAD QUE FIJA
# 🧰       EL AGENTE (baja|normal|alta|urgente; default normal) y CADENA derivada del
# 🧰       organigrama vivo (N2 de su depto → N1 → humano). AUTO-DISPATCH: sube al
# 🧰       primer rango capaz (nivel_acceso Y techo de su rango ≥ nivel_requerido).
# 🧰       Estados: abierto→escalado→en_revision→resuelto|denegado|esperando_sello
# 🧰       (nivel 5 → doble sello: la escalera termina en sellar.sh)|caducado (TTL,
# 🧰       se ARCHIVA en escalaciones_archivo.jsonl — no se pierde).
# 🧰       Conceder EJECUTA la tool con el payload del ticket (resuelto = concedido+ejecutado).
# 🧰     · techo F1 = solo LECTURA (nivel ≤ techo_f1): un 4-5 NI CON TICKET.
# 🧰       (el motor 4-5/esperando_sello queda CABLEADO — probado con techo alzado en jaula.)
# 🧰   Salida SIEMPRE contrato JSON (el que llama — turno_rol, pedir_tool, escalado.sh,
# 🧰   humano — parsea una sola forma). Exit: 0 ok · 1 error tool · 3 techo/ticket-mal · 4 denegado.
# 🧰 Uso:  echo '{"q":"..."}' | ./herramientas.py --agente ingesta --tool buscar
# 🧰        [--prioridad baja|normal|alta|urgente] [--ticket TCK-… legado]
# 🧰       ./herramientas.py --listar
# 🧰       ./herramientas.py --esc listar [--estado E] [--rango R] [--origen O]
# 🧰       ./herramientas.py --esc resolver --id ESC-… --como <rol|humano> \
# 🧰                          --decision conceder|denegar|escalar [--motivo "…"]
# 🧰       ./herramientas.py --esc visto --id ESC-… --como <rol>
# 🧰       ./herramientas.py --esc caducar     (el barrido TTL; abrir el libro ya barre)
# 🧰 =====================================================================
import datetime
import fcntl
import json
import os
import subprocess
import sys

BASE = os.environ.get("MOSAIC_BASE", os.path.expanduser("~/Mosaic_privado"))
REGISTRO = os.environ.get("HERRAMIENTAS_YAML", os.path.join(BASE, "data", "herramientas.yaml"))
TURNOS_DIR = os.environ.get("TURNOS_DIR", os.path.join(BASE, "roles", "turnos"))
TICKETS = os.path.join(BASE, "data", "tickets_escalado.jsonl")          # LEGADO (solo canje --ticket)

# ── el libro de ESCALACIONES (plan Opus 13:56) ──
ESCALACIONES = os.path.join(BASE, "data", "escalaciones.json")
ESC_ARCHIVO = os.path.join(BASE, "data", "escalaciones_archivo.jsonl")
ORGANIGRAMA = os.path.join(BASE, "roles", "organigrama.yaml")
PRIORIDADES = ["urgente", "alta", "normal", "baja"]                     # orden de la cola
ESTADOS_VIVOS = ("abierto", "escalado", "en_revision")
TECHOS_DEF = {"N3": 1, "N2": 3, "N1": 5, "humano": 5}                   # defaults del motor
ESC_TTL_H = int(os.environ.get("MOSAIC_ESC_TTL_H", "48") or "48")       # caducidad configurable


def emit(d, code=0):
    sys.stdout.write(json.dumps(d, ensure_ascii=False))
    sys.stdout.flush()
    raise SystemExit(code)


def arg(flag, default=""):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else default


def cargar_registro():
    import yaml
    return yaml.safe_load(open(REGISTRO, encoding="utf-8"))


# ═══════════════ EL ESCALADOR (plan Opus 13:56 — modelo mission-control, MOSAIC-nativo) ═══════════════

def _ahora():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _techos():
    """Techo por rango: hasta qué nivel RESUELVE cada rango. CONFIGURABLE (decisión de
    Gustavo): defaults del motor ← roles/organigrama.yaml (techos_rango:) ← env MOSAIC_TECHO_<RANGO>."""
    import yaml
    t = dict(TECHOS_DEF)
    try:
        og = yaml.safe_load(open(ORGANIGRAMA, encoding="utf-8")) or {}
        for k, v in (og.get("techos_rango") or {}).items():
            t[str(k)] = int(v)
    except Exception:
        pass
    for k in list(t):
        env = os.environ.get(f"MOSAIC_TECHO_{k.upper()}", "")
        if env.isdigit():
            t[k] = int(env)
    return t


def _sillas():
    """roles/turnos/*.yaml = LA fuente de agentes (misma que [E] y crear_empresa)."""
    import yaml
    out = {}
    try:
        for f in sorted(os.listdir(TURNOS_DIR)):
            if not f.endswith(".yaml"):
                continue
            try:
                d = yaml.safe_load(open(os.path.join(TURNOS_DIR, f), encoding="utf-8")) or {}
            except Exception:
                continue
            r = str(d.get("rol") or f[:-5])
            out[r] = {"nivel": str(d.get("nivel", "N2")), "departamento": str(d.get("departamento", "?")),
                      "nivel_acceso": int(d.get("nivel_acceso", 1) or 1)}
    except OSError:
        pass
    return out


def _cadena_de(agente, sillas):
    """[lead, manager, n1, humano] DERIVADA del organigrama vivo: los N2 de SU depto
    (≠ él) → los N1 de cualquier depto (hoy no hay: N1 = humano) → humano. Sin inventar."""
    mio = sillas.get(agente, {})
    cad = [r for r, d in sillas.items()
           if d["departamento"] == mio.get("departamento") and d["nivel"] == "N2" and r != agente]
    cad += [r for r, d in sillas.items() if d["nivel"] == "N1" and r != agente and r not in cad]
    cad.append("humano")
    return cad


def _capacidad(quien, sillas, techos):
    """Lo que un eslabón puede RESOLVER = min(su nivel_acceso, techo de su rango).
    El humano es el final de toda escalera: 5."""
    if quien == "humano":
        return techos.get("humano", 5)
    d = sillas.get(quien)
    return min(d["nivel_acceso"], techos.get(d["nivel"], 1)) if d else 0


class _esc_store:
    """El libro, con ESCRITOR ÚNICO: flock en sidecar .lock → leer → mutar → tmp+replace
    (mismo patrón que el libro de sellos). Abrir el libro YA barre los TTL."""

    def __enter__(self):
        os.makedirs(os.path.dirname(ESCALACIONES), exist_ok=True)
        self._lk = open(ESCALACIONES + ".lock", "a+")
        fcntl.flock(self._lk, fcntl.LOCK_EX)
        try:
            self.st = json.load(open(ESCALACIONES, encoding="utf-8"))
        except Exception:
            self.st = {"version": 1, "seq": {}, "tickets": []}
        self.st.setdefault("seq", {}); self.st.setdefault("tickets", [])
        _esc_barrer_ttl(self.st)
        return self.st

    def __exit__(self, exc, *a):
        try:
            if exc is None:
                tmp = ESCALACIONES + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.st, f, ensure_ascii=False, indent=1)
                os.replace(tmp, ESCALACIONES)
        finally:
            fcntl.flock(self._lk, fcntl.LOCK_UN)
            self._lk.close()
        return False


def _esc_barrer_ttl(st):
    """caducado (TTL): NO se pierde — se ARCHIVA. También archiva terminales viejos
    (libro vivo ligero). esperando_sello JAMÁS caduca: el sello va al paso humano."""
    ahora = datetime.datetime.now()
    limite = ahora - datetime.timedelta(hours=ESC_TTL_H)
    vivos, archivo = [], []
    for t in st["tickets"]:
        try:
            ref = datetime.datetime.strptime(t.get("resuelto_ts") or t.get("ts", ""), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            ref = ahora
        if t.get("estado") in ESTADOS_VIVOS and ref < limite:
            t["estado"] = "caducado"
            t.setdefault("historial", []).append({"rango": "motor", "ts": _ahora(), "decision": "caducado",
                                                  "motivo": f"TTL {ESC_TTL_H}h — se archiva, no se pierde"})
            archivo.append(t)
        elif t.get("estado") in ("resuelto", "denegado", "caducado") and ref < limite:
            archivo.append(t)
        else:
            vivos.append(t)
    if archivo:
        with open(ESC_ARCHIVO, "a", encoding="utf-8") as f:
            for t in archivo:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
    st["tickets"] = vivos


def _esc_dispatch(tck, sillas, techos):
    """AUTO-DISPATCH (patrón mission-control): al SIGUIENTE eslabón de la cadena capaz.
    Si es agente, lo verá EN SU TURNO; si es el humano, espera en cola (escalado.sh)."""
    ya = tck["rango_actual"]
    resto = tck["cadena"][tck["cadena"].index(ya) + 1:] if ya in tck["cadena"] else tck["cadena"]
    for esl in resto:
        if _capacidad(esl, sillas, techos) >= tck["nivel_requerido"]:
            tck["rango_actual"], tck["estado"] = esl, "escalado"
            tck["historial"].append({"rango": esl, "ts": _ahora(), "decision": "auto-dispatch",
                                     "motivo": "primer rango de la cadena con nivel suficiente"})
            return
    tck["rango_actual"], tck["estado"] = "humano", "escalado"
    tck["historial"].append({"rango": "humano", "ts": _ahora(), "decision": "auto-dispatch",
                             "motivo": "ningún agente de la cadena alcanza — a la cola humana"})


def _esc_crear(agente, rol_y, tool_n, nivel_rol, nivel_req, payload_raw, prio_txt):
    """Denegado en su nivel → NO a secas: nace el ticket (abierto) y la escalera trabaja."""
    sillas, techos = _sillas(), _techos()
    mapa_num = {"1": "baja", "2": "normal", "3": "normal", "4": "alta", "5": "urgente"}
    prio = prio_txt.strip().lower()
    prio = prio if prio in PRIORIDADES else mapa_num.get(prio, "")
    fijada = "agente" if prio else "default"
    prio = prio or "normal"
    with _esc_store() as st:
        dia = datetime.datetime.now().strftime("%Y%m%d")
        st["seq"][dia] = int(st["seq"].get(dia, 0)) + 1
        tck = {"id": f"ESC-{dia}-{st['seq'][dia]:02d}", "ts": _ahora(),
               "agente_origen": agente, "departamento": str(rol_y.get("departamento", "?")),
               "herramienta": tool_n, "payload": payload_raw[:4000],
               "nivel_requerido": nivel_req, "nivel_agente": nivel_rol,
               "prioridad": prio, "prioridad_fijada_por": fijada,
               "cadena": _cadena_de(agente, sillas), "rango_actual": agente, "estado": "abierto",
               "historial": [{"rango": agente, "ts": _ahora(), "decision": "creado",
                              "motivo": f"denegado en su nivel ({nivel_rol}<{nivel_req})"}],
               "resultado": None}
        _esc_dispatch(tck, sillas, techos)
        st["tickets"].append(tck)
    return tck


def _esc_listar(estado="", rango="", origen=""):
    with _esc_store() as st:
        ts = list(st["tickets"])
    if estado:
        ts = [t for t in ts if t.get("estado") == estado]
    if rango:
        ts = [t for t in ts if t.get("rango_actual") == rango and t.get("estado") in ("escalado", "en_revision")]
    if origen:
        ts = [t for t in ts if t.get("agente_origen") == origen]
    orden = {p: i for i, p in enumerate(PRIORIDADES)}
    ts.sort(key=lambda t: (orden.get(t.get("prioridad"), 9), t.get("ts", "")))
    return ts


def _esc_visto(tid, quien):
    """El rango MIRA el ticket en su turno → en_revision (idempotente)."""
    with _esc_store() as st:
        t = next((x for x in st["tickets"] if x.get("id") == tid), None)
        if t and t["estado"] == "escalado" and t["rango_actual"] == quien:
            t["estado"] = "en_revision"
            t["historial"].append({"rango": quien, "ts": _ahora(), "decision": "visto",
                                   "motivo": "inyectado en su turno"})
            return True
    return bool(t and t.get("rango_actual") == quien)


def _esc_resolver(tid, quien, decision, motivo):
    """conceder (EJECUTA la tool con el payload del ticket) · denegar (motivo) · escalar.
    Solo el rango_actual resuelve — salvo el humano (Dirección: final de toda cadena).
    nivel 5 → esperando_sello: el circuito de sellos (sellar.sh) es el último peldaño."""
    sillas, techos = _sillas(), _techos()
    with _esc_store() as st:
        t = next((x for x in st["tickets"] if x.get("id") == tid), None)
        if t is None:
            return {"ok": False, "error": f"no existe {tid}"}, 1
        if t["estado"] not in ESTADOS_VIVOS:
            return {"ok": False, "error": f"{tid} ya está {t['estado']} — se resuelve UNA vez"}, 1
        if quien != "humano" and t["rango_actual"] != quien:
            return {"ok": False, "error": f"{tid} está en el rango «{t['rango_actual']}», no en «{quien}»"}, 4
        t["historial"].append({"rango": quien, "ts": _ahora(), "decision": decision, "motivo": motivo or ""})
        if decision == "denegar":
            t["estado"], t["resuelto_ts"] = "denegado", _ahora()
            t["resultado"] = {"denegado_por": quien, "motivo": motivo or "(sin motivo)"}
            return {"ok": True, "result": {"id": tid, "estado": "denegado"}}, 0
        if decision == "escalar":
            antes = t["rango_actual"]
            _esc_dispatch(t, sillas, techos)
            return {"ok": True, "result": {"id": tid, "estado": t["estado"],
                                           "de": antes, "a": t["rango_actual"]}}, 0
        # ── conceder ──
        cap = _capacidad(quien, sillas, techos)
        if cap < t["nivel_requerido"]:
            return {"ok": False, "error": f"«{quien}» no alcanza el nivel {t['nivel_requerido']} "
                    f"(capacidad {cap} = min(nivel_acceso, techo de rango)) — escala o deniega"}, 4
        if t["nivel_requerido"] >= 5:
            t["estado"] = "esperando_sello"
            t["resultado"] = {"concedido_por": quien,
                              "nota": "nivel 5 = exterior: el DOBLE SELLO es el último peldaño "
                                      "(Accion + sellar.sh, fase manos) — NO se ejecuta desde aquí"}
            return {"ok": True, "result": {"id": tid, "estado": "esperando_sello"}}, 0
        t["estado"] = "en_revision"                      # marcado ANTES de ejecutar (si el tool
        payload, herr = t["payload"], t["herramienta"]   # cuelga, el TTL rescata el ticket)
    reg = cargar_registro()
    tool = next((x for x in reg.get("tools", []) if x.get("nombre") == herr), None)
    if tool is None or not tool.get("cmd"):
        d = {"ok": False, "error": f"«{herr}» sin cmd (fase siguiente) — no ejecutable"}
    else:
        d = _ejecutar_tool(tool, payload, f"escalado:{tid}:{quien}")
    with _esc_store() as st:
        t = next((x for x in st["tickets"] if x.get("id") == tid), None)
        if t is not None:
            t["estado"], t["resuelto_ts"] = "resuelto", _ahora()
            extracto = json.dumps(d.get("result") if d.get("ok") else d.get("error"), ensure_ascii=False)
            t["resultado"] = {"concedido_por": quien, "tool_ok": bool(d.get("ok")), "extracto": extracto[:1500]}
    return {"ok": True, "result": {"id": tid, "estado": "resuelto", "tool_ok": bool(d.get("ok"))}}, 0


def _ejecutar_tool(tool, payload_raw, via):
    """La ÚNICA rampa de ejecución (contrato JSON stdin→stdout) — la usan el paso directo
    por rango y la concesión del escalador. Verifica el contrato, jamás inventa."""
    env = {**os.environ, "MOSAIC_BASE": BASE, "HERR_ROL": os.environ.get("HERR_ROL", via)}
    cmd = tool.get("cmd")
    try:
        r = subprocess.run(cmd if isinstance(cmd, list) else cmd.split(),
                           input=payload_raw, capture_output=True, text=True,
                           errors="replace", timeout=int(tool.get("timeout_s", 90)),
                           cwd=BASE, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{tool.get('nombre','?')}: timeout"}
    salida = (r.stdout or "").strip()
    try:
        d = json.loads(salida)
        assert isinstance(d, dict) and "ok" in d
    except Exception:
        return {"ok": False, "error": f"{tool.get('nombre','?')} rompió el contrato (stdout no-JSON): "
                f"{salida[:200]} · stderr: {(r.stderr or '')[:200]}"}
    d.setdefault("tool", tool.get("nombre"))
    d.setdefault("via", via)
    return d


def _esc_cli():
    """Subórdenes --esc (las usan escalado.sh, turno_rol.sh y el humano). Salida = contrato."""
    orden = arg("--esc")
    if orden == "listar":
        emit({"ok": True, "result": _esc_listar(arg("--estado"), arg("--rango"), arg("--origen"))})
    if orden == "visto":
        emit({"ok": True, "result": {"id": arg("--id"), "visto": _esc_visto(arg("--id"), arg("--como"))}})
    if orden == "resolver":
        quien, dec = arg("--como"), arg("--decision")
        if not arg("--id") or not quien or dec not in ("conceder", "denegar", "escalar"):
            emit({"ok": False, "error": "uso: --esc resolver --id ESC-… --como <rol|humano> "
                  "--decision conceder|denegar|escalar [--motivo …]"}, 1)
        if quien != "humano" and not os.path.isfile(os.path.join(TURNOS_DIR, f"{quien}.yaml")):
            emit({"ok": False, "error": f"resolutor sin silla: {quien}"}, 1)
        d, rc = _esc_resolver(arg("--id"), quien, dec, arg("--motivo"))
        emit(d, rc)
    if orden == "caducar":
        with _esc_store() as st:
            n = len(st["tickets"])
        emit({"ok": True, "result": {"vivos_tras_barrido": n, "ttl_h": ESC_TTL_H}})
    emit({"ok": False, "error": "orden --esc desconocida: listar | resolver | visto | caducar"}, 1)


def main():
    import yaml
    if "--esc" in sys.argv:
        _esc_cli()
    if "--listar" in sys.argv:
        reg = cargar_registro()
        emit({"ok": True, "result": {"techo_f1": reg.get("techo_f1", 3),
              "tools": [{"nombre": t["nombre"], "nivel_requerido": t["nivel_requerido"],
                         "desc": t.get("desc", ""), "despachable": bool(t.get("cmd"))}
                        for t in reg.get("tools", [])]}})

    agente, tool_n = arg("--agente"), arg("--tool")
    if not agente or not tool_n:
        emit({"ok": False, "error": "uso: --agente <rol> --tool <nombre> [--prioridad N] [--ticket TCK]"}, 1)
    rol_f = os.path.join(TURNOS_DIR, f"{agente}.yaml")
    if not os.path.isfile(rol_f):
        emit({"ok": False, "error": f"agente sin silla: {agente}"}, 1)

    reg = cargar_registro()
    tool = next((t for t in reg.get("tools", []) if t.get("nombre") == tool_n), None)
    if tool is None:
        emit({"ok": False, "error": f"tool desconocida: {tool_n} (mira data/herramientas.yaml)"}, 1)

    rol_y = yaml.safe_load(open(rol_f, encoding="utf-8")) or {}
    nivel_rol = int(rol_y.get("nivel_acceso", 1) or 1)
    nivel_req = int(tool.get("nivel_requerido", 5) or 5)
    techo = int(reg.get("techo_f1", 3) or 3)

    # techo F1: las MANOS ni con ticket — llegan con el doble sello, en su fase
    if nivel_req > techo:
        emit({"ok": False, "error": f"«{tool_n}» (nivel {nivel_req}) está por ENCIMA del techo F1 "
              f"({techo}, solo lectura) — las manos llegan con el doble sello, ni con ticket"}, 3)

    payload_raw = sys.stdin.read().strip() or "{}"

    # _prioridad: el AGENTE fija la prioridad de su posible ticket DESDE el payload
    # (`HERRAMIENTA: x {"q":"…","_prioridad":"alta"}`) — se extrae, la tool no la ve.
    prio_payload = ""
    try:
        _p = json.loads(payload_raw)
        if isinstance(_p, dict) and "_prioridad" in _p:
            prio_payload = str(_p.pop("_prioridad"))
            payload_raw = json.dumps(_p, ensure_ascii=False)
    except Exception:
        pass

    # ── ticket LEGADO (TCK, canje --ticket): UN solo uso, se gasta bajo flock ──
    ticket_id, via = arg("--ticket"), "rango"
    if ticket_id:
        gastado = False
        try:
            with open(TICKETS, "r+", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                lineas = [json.loads(l) for l in f if l.strip()]
                for t in lineas:
                    if (t.get("id") == ticket_id and t.get("rol") == agente
                            and t.get("tool") == tool_n and t.get("estado") == "concedido"):
                        t["estado"] = "gastado"
                        t["gastado_ts"] = datetime.datetime.now().strftime("%F %T")
                        gastado = True
                if gastado:
                    f.seek(0); f.truncate()
                    f.write("\n".join(json.dumps(x, ensure_ascii=False) for x in lineas) + "\n")
        except OSError:
            pass
        if not gastado:
            emit({"ok": False, "error": f"ticket inválido/gastado/ajeno: {ticket_id}"}, 3)
        via = f"ticket:{ticket_id}"

    # ── permiso por rango, o DENEGADO → nace el ticket ESC y la ESCALERA trabaja ──
    if nivel_rol < nivel_req and via == "rango":
        tck = _esc_crear(agente, rol_y, tool_n, nivel_rol, nivel_req, payload_raw,
                         arg("--prioridad") or prio_payload)
        emit({"ok": False, "error": f"DENEGADO: {agente}(nivel {nivel_rol}) pidió {tool_n}(nivel {nivel_req}) "
              f"— ticket creado, sube solo por la cadena",
              "ticket": tck["id"], "prioridad": tck["prioridad"], "estado": tck["estado"],
              "rango_actual": tck["rango_actual"], "cadena": " → ".join(tck["cadena"]),
              "siguiente_paso": "el rango lo verá en su turno; humano: ./escalado.sh listar | conceder | denegar"}, 4)

    # ── EJECUTAR por el contrato (la rampa única) ──
    if not tool.get("cmd"):
        emit({"ok": False, "error": f"«{tool_n}» declarada pero sin cmd (fase siguiente)"}, 3)
    os.environ["HERR_ROL"] = agente
    d = _ejecutar_tool(tool, payload_raw, via)
    emit(d, 0 if d.get("ok") else 1)


if __name__ == "__main__":
    main()
