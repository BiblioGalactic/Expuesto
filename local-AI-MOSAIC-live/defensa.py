#!/usr/bin/env python3
"""
DEFENSA — analiza código/repos EXTERNOS con 3 LENTES repartidas por FUERZA del modelo:
  intención  -> Mythos (lee la trama: cebo, doble propósito, ingeniería social)
  código     -> Dolphin (pasada técnica: red, eval/exec, exfiltración, ofuscación)
  adversarial-> Unholy (red-team profundo; puede pedir PROBAR en sandbox)
Un JUEZ DE SEGURIDAD funde las tres -> veredicto TRAMPA/SEGURO/DUDOSO + riesgo, y destila
un 'patron_defensa' -> PROPUESTA de capacidad de 'seguridad' (a revisar, no entra sola).
Objetivo DEFENSIVO: reconocer y resistir, no fabricar. El código se prueba SIEMPRE en
sandbox.sh (#64). Stdlib only (urllib). Roles desde roles/defensa.yaml.

Uso:
  ./defensa.py --repo u/r --readme README.md --codigo code.py
  ./defensa.py --repo u/r --readme-text "..." --codigo-text "..."
  ./defensa.py ... --offline       # sin red (mock, prueba el flujo)
  ./defensa.py --mapa              # arranque en seco: mapa lente→modelo y sale (ACC-20260706-01)
Asignación lente→modelo: asignacion_lentes.conf (LA FUENTE ÚNICA, compartida con lentes.sh).
"""
import json
import os
import sys
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.request

# lente -> (nombre_modelo, url)  · reparto por FUERZA (no rotación ciega); el Elo lo confirma
# 🎯 ACC-20260706-01 (1ª Acción con doble sello · 6-jul 04:03): la asignación vive en LA FUENTE
#    ÚNICA (asignacion_lentes.conf, compartida con lentes.sh) — aquí ya NO hay valores a mano.
#    Prioridad: env DEFENSA_MODELO_*/DEFENSA_URL_* (data/.lentes_env vía cuarentena.sh SIGUE
#    mandando) > conf. Sin ninguna de las dos → fallar ALTO (jamás una lente a ciegas — D0).
ASIGNACION_CONF = Path(os.getenv("ASIGNACION_CONF",
                                 str(Path(__file__).resolve().parent / "asignacion_lentes.conf")))

def _conf_lentes():
    m = {}
    try:
        for ln in ASIGNACION_CONF.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            c = [x.strip() for x in ln.split("|")]
            if len(c) >= 5 and c[0]:
                m[c[0]] = (c[1], c[4])          # lente -> (nombre_modelo, url_defecto)
    except OSError:
        pass
    return m

def _asig():
    conf, asig, faltan = _conf_lentes(), {}, []
    for lente in ("intencion", "codigo", "adversarial", "juez"):
        mod = os.getenv(f"DEFENSA_MODELO_{lente.upper()}") or conf.get(lente, ("", ""))[0]
        url = os.getenv(f"DEFENSA_URL_{lente.upper()}") or conf.get(lente, ("", ""))[1]
        if mod and url:
            asig[lente] = (mod, url)
        else:
            faltan.append(lente)
    if faltan:
        sys.exit(f"defensa.py: SIN asignación para {faltan} — ni {ASIGNACION_CONF} ni env "
                 f"DEFENSA_MODELO_*/DEFENSA_URL_*. Arranque en seco: python3 defensa.py --mapa")
    return asig

ASIG = _asig()

if "--mapa" in sys.argv:   # 🗺️ arranque en seco (Riesgos de ACC-20260706-01): mapa y fuera
    for _l, (_m, _u) in ASIG.items():
        print(f"{_l:<12} → {_m:<15} {_u}")
    sys.exit(0)
OFFLINE = "--offline" in sys.argv
ROLES_YAML = Path(os.getenv("DEFENSA_CAPS", "roles/defensa.yaml"))
PROPUESTAS = Path(os.getenv("DEFENSA_PROPUESTAS", "data/seguridad_propuestas.yaml"))
ROLES_LOG = Path(os.getenv("DEFENSA_LOG", "data/defensa_roles.jsonl"))
DIGNIDAD = Path(os.getenv("DIGNIDAD_SCORES", "data/dignidad_modelos.json"))   # tasa de buenas por modelo (compartida)
TRAZA = Path(os.getenv("DEFENSA_TRAZA", "data/defensa_traza.jsonl"))          # trazabilidad: intercambio pegado
SANDBOX = os.getenv("DEFENSA_SANDBOX", str(Path(__file__).resolve().parent / "sandbox.sh"))

DEFAULT_ROLES = {
    "intencion": ("Eres la LENTE DE INTENCIÓN. ¿Qué quiere el autor de quien ejecute esto? "
                  "Busca cebo, doble propósito, ingeniería social.\nREPO: {repo}\nREADME: {readme}\n"
                  'SOLO JSON: {{"intencion":"benigna|sospechosa|maliciosa","senales":["..."],"razon":"<breve>"}}'),
    # Prompts endurecidos 3-jul (biblia de Gustavo): nada de manuales genéricos ni riesgo 0 de compromiso —
    # cada afirmación anclada a ESTE código, con cita textual o descarte explícito.
    "codigo": ("Eres la LENTE DE CÓDIGO. Analiza EXCLUSIVAMENTE el código de abajo, línea a línea. "
               "PROHIBIDO dar guías genéricas o listas de buenas prácticas: cada hallazgo debe CITAR "
               "el fragmento textual de ESTE código (función o línea). Vigila: red/exfiltración, "
               "eval/exec/descarga-y-ejecuta, borrado de ficheros, credenciales, ofuscación, "
               "dependencias sospechosas. Si está limpio, di QUÉ revisaste y por qué lo descartas.\n"
               "CÓDIGO:\n{codigo}\n"
               'SOLO JSON: {{"riesgo_tecnico":<0-10>,"hallazgos":[{{"cita":"<fragmento textual de este código>","por_que":"<el riesgo>"}}],'
               '"limpio_porque":"<si no hay hallazgos: qué revisaste y por qué está limpio>","razon":"<breve>"}}'),
    "adversarial": ("Eres la LENTE ADVERSARIAL (red-team defensivo). Piensa como el ATACANTE que escribió "
                    "este código: ¿dónde esconderías TÚ la maldad? OBLIGATORIO elegir una de dos: "
                    "(a) nombra AL MENOS UN vector plausible con su punto exacto en el código, o "
                    "(b) declara limpio LISTANDO los 3 sitios que revisaste y por qué quedan descartados. "
                    "Prohibido el riesgo 0 sin descartes explícitos y las respuestas de compromiso. "
                    "Si pides sandbox, entrega en 'snippet' un trozo AUTOCONTENIDO y mínimo que dispare "
                    "el vector (sin imports del repo) y su 'lenguaje' — se prueba ESE trozo, no el módulo.\n"
                    "CÓDIGO:\n{codigo}\n"
                    'SOLO JSON: {{"riesgo_oculto":<0-10>,"vectores":[{{"donde":"<punto exacto en el código>","como":"<el truco>"}}],'
                    '"descartados":["<sitio revisado y por qué no es vector>"],"probar_en_sandbox":true|false,'
                    '"snippet":"<trozo autocontenido o vacío>","lenguaje":"python|bash|js|ts|go|ruby",'
                    '"que_observar":"<señal CONCRETA a vigilar al ejecutarlo>"}}'),
    "juez": ("Eres el JUEZ DE SEGURIDAD. Funde intención+código+adversarial.\nREPO: {repo}\n"
             "INTENCIÓN:\n{intencion}\nCÓDIGO:\n{codigo_scan}\nADVERSARIAL:\n{adversarial}\n"
             'SOLO JSON: {{"veredicto":"TRAMPA|SEGURO|DUDOSO","riesgo":<0-10>,"razon":"<breve>","patron_defensa":"<regla general>"}}'),
}


def cargar_roles():
    roles = dict(DEFAULT_ROLES)
    try:
        import yaml
        if ROLES_YAML.exists():
            for c in (yaml.safe_load(ROLES_YAML.read_text()) or {}).get("capabilities", []):
                rid, pat = str(c.get("id", "")), c.get("behavioral_pattern", "")
                for rol in roles:
                    if rid.endswith(rol) and pat:
                        roles[rol] = pat
    except Exception:
        pass
    return roles


def llm(url, prompt, max_tokens=400, temperature=0.3):
    if OFFLINE or url == "mock":
        return ""
    body = json.dumps({"model": "local", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": temperature}).encode("utf-8")
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[error LLM: {e}]"


def _json(texto, default):
    try:
        return json.loads(texto[texto.find("{"):texto.rfind("}") + 1])
    except Exception:
        return default


def _ciega(txt):
    """¿Esta lente NO analizó de verdad? (caída, vacía o error). Fail-closed D0 (Opus, 2-jul):
    una lente ciega jamás puede contar como análisis — y sin análisis no se firma SEGURO."""
    t = (txt or "").strip()
    return (not t) or t.startswith("[error LLM")


def _oxigeno(lente, prompt):
    """P-L1 (3-jul, probado a mano): Qwen3 RAZONA por defecto y el pensamiento se come los
    max_tokens cortos → content vacío (120/120 tokens en reasoning_content) → la lente parece
    ciega sin estarlo. /no_think es su interruptor suave oficial: piensa vacío y contesta.
    SOLO se añade si el modelo destino es Qwen3; a los demás no se les toca el prompt."""
    return ("/no_think " + prompt) if "qwen3" in (ASIG[lente][0] or "").lower() else prompt


def _escribir_atomico(path, texto):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.tmp{os.getpid()}")
    tmp.write_text(texto, encoding="utf-8"); os.replace(tmp, p)


_EXT_SNIPPET = {"python": ".py", "py": ".py", "bash": ".sh", "sh": ".sh", "shell": ".sh",
                "js": ".js", "javascript": ".js", "node": ".js", "ruby": ".rb", "rb": ".rb",
                "ts": ".ts", "typescript": ".ts", "go": ".go", "golang": ".go"}


def _en_sandbox(codigo_file, snippet=None, lenguaje=None):
    """Ejecuta código CONTENIDO en sandbox.sh y devuelve lo observado (acotado).
    Pieza 2 (Opus 4-jul): si la adversarial entregó un SNIPPET autocontenido + lenguaje,
    se prueba ESE trozo (tmp con su extensión) — no el módulo entero con imports que peta
    en el primer import. Sin snippet (o lenguaje desconocido): el fichero de siempre, y el
    techo D0.2 retiene si no se pudo observar."""
    objetivo, tmp = codigo_file, None
    ext = _EXT_SNIPPET.get((lenguaje or "").strip().lower())
    if (snippet or "").strip() and ext:
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=ext, prefix="defensa_snippet_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(snippet)
        objetivo = tmp
    try:
        if not (objetivo and os.path.exists(objetivo) and os.path.exists(SANDBOX)):
            return "(sin fichero de código o sandbox para probar)"
        try:
            r = subprocess.run(["bash", SANDBOX, "--script", objetivo],
                               capture_output=True, text=True, timeout=90)
            return ((r.stdout or "") + (r.stderr or ""))[:1200]
        except Exception as e:
            return f"[sandbox error: {e}]"
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _slug(s):
    s = "".join(ch if ch.isalnum() else "-" for ch in s.lower())
    return "-".join(p for p in s.split("-") if p)[:40] or "repo"


def _proponer_capacidad(repo, ver):
    """Si hay patrón y el veredicto no es SEGURO, propone una capacidad de 'seguridad'
    (a un fichero de PROPUESTAS; NO entra sola en la biblioteca: gobernanza #65/#67)."""
    patron = (ver.get("patron_defensa") or "").strip()
    if not patron or ver.get("veredicto") == "SEGURO":
        return None
    cid = "seguridad-" + _slug(repo)
    existentes = ""
    if PROPUESTAS.exists():
        existentes = PROPUESTAS.read_text(encoding="utf-8")
        if cid in existentes:
            return None
    bloque = (f"  - id: {cid}\n    role: constraint\n    domain_expertise: [seguridad, defensa]\n"
              f"    behavioral_pattern: >\n      {patron}\n"
              f"    tags: [seguridad, propuesta, auto]\n    origen: {repo}\n    veredicto: {ver.get('veredicto')}\n")
    cab = "" if existentes.strip().startswith("capabilities:") else "capabilities:\n"
    _escribir_atomico(PROPUESTAS, (existentes if existentes else cab) + bloque)
    return cid


def _registrar(repo, ver):
    ROLES_LOG.parent.mkdir(parents=True, exist_ok=True)
    fila = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "repo": repo,
            "veredicto": ver.get("veredicto"), "riesgo": ver.get("riesgo"),
            "lentes": {k: v[0] for k, v in ASIG.items()}}
    with open(ROLES_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def juzgar(que, contenido):
    """Juez BUENO/FALLIDO sobre un texto (mismo gate que las respuestas de ingesta). VISIBLE.
    D0 (Opus, 2-jul): si el juez es INALCANZABLE devuelve buena=None — ni premia ni castiga
    la dignidad del modelo (el ledger no se corrompe con culpas ajenas)."""
    if OFFLINE or not (contenido or "").strip():
        return {"buena": True, "razon": "(offline/sin contenido)"}
    p = (f"¿Es esto un {que} de buena calidad (útil, sólido, no basura ni mentira)? Sé honesto.\n"
         f"TEXTO:\n{contenido[:1500]}\nDevuelve SOLO JSON: {{\"buena\": true|false, \"razon\": \"<breve>\"}}")
    resp = llm(ASIG["juez"][1], _oxigeno("juez", p), max_tokens=300, temperature=0.1)
    if _ciega(resp):
        return {"buena": None, "razon": "(juez inalcanzable → no puntúa dignidad)"}
    return _json(resp, {"buena": None, "razon": "(juez ilegible → no puntúa dignidad)"})


def _dignidad(modelo, rol, buena):
    """Dignidad por modelo = su tasa de 'buenas' en el juez (ledger compartido con trampa.py)."""
    d = {}
    try:
        d = json.loads(DIGNIDAD.read_text()) if DIGNIDAD.exists() else {}
    except Exception:
        d = {}
    k = f"{modelo}|{rol}"
    e = d.get(k, {"buenas": 0, "fallidas": 0})
    e["buenas" if buena else "fallidas"] += 1
    tot = e["buenas"] + e["fallidas"]
    e["dignidad"] = round(e["buenas"] / tot, 3) if tot else 0.0
    d[k] = e
    _escribir_atomico(DIGNIDAD, json.dumps(d, ensure_ascii=False, indent=2))
    return e["dignidad"]


def _trazar(record):
    """Trazabilidad: PEGA todo el intercambio (entradas+salidas de las 3 lentes) a un log auditable."""
    TRAZA.parent.mkdir(parents=True, exist_ok=True)
    record["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(TRAZA, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def analizar(repo, readme, codigo, codigo_file=None):
    R = cargar_roles()
    print("=" * 72)
    print(f"🛡️  DEFENSA · {repo}")
    for lente, (nom, _) in ASIG.items():
        print(f"    {lente:11}-> {nom}")
    print("-" * 72)
    tiene_codigo = bool((codigo or "").strip())
    # Las lentes en PARALELO (cada una a su modelo)
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_int = ex.submit(llm, ASIG["intencion"][1], _oxigeno("intencion", R["intencion"].format(repo=repo, readme=(readme or "")[:2000])))
        if tiene_codigo:
            f_cod = ex.submit(llm, ASIG["codigo"][1], R["codigo"].format(codigo=codigo[:4000]))
            f_adv = ex.submit(llm, ASIG["adversarial"][1], R["adversarial"].format(codigo=codigo[:4000]))
        intencion = f_int.result()
        codigo_scan = f_cod.result() if tiene_codigo else "(sin código disponible; solo intención)"
        adversarial = f_adv.result() if tiene_codigo else "(sin código disponible; solo intención)"
    # TRANSPARENCIA: imprime ENTERO lo que generó cada lente (Mythos/Dolphin/Unholy), sin truncar
    print(f"🔮 INTENCIÓN — la generó {ASIG['intencion'][0]}:\n{(intencion or '').strip()}\n")
    print(f"🔧 CÓDIGO — la generó {ASIG['codigo'][0]}:\n{(codigo_scan or '').strip()}\n")
    print(f"🗡️  ADVERSARIAL — la generó {ASIG['adversarial'][0]}:\n{(adversarial or '').strip()}\n")
    # ¿probar en sandbox? (lo decide la lente adversarial) · Pieza 2 (Opus 4-jul): si entregó
    # snippet AUTOCONTENIDO + lenguaje, se prueba ESE trozo; si no, el fichero (y D0.2 retiene).
    obs = ""
    adv_j = _json(adversarial, {})
    if adv_j.get("probar_en_sandbox") and not OFFLINE and (codigo_file or (adv_j.get("snippet") or "").strip()):
        obs = _en_sandbox(codigo_file, snippet=adv_j.get("snippet"), lenguaje=adv_j.get("lenguaje"))
        etiq_sbx = "snippet de la adversarial" if (adv_j.get("snippet") or "").strip() else "fichero entero (sin snippet)"
        print(f"🧪 SANDBOX (contenido, sin red · {etiq_sbx}):\n{obs}\n")
        adversarial += f"\nOBSERVADO EN SANDBOX:\n{obs}"
    # JUEZ bueno/fallido por LENTE (VISIBLE) -> dignidad de cada modelo (Mythos/Dolphin/Unholy)
    jueces = {}
    for lente, txt, etiq in (("intencion", intencion, "análisis de intención"),
                             ("codigo", codigo_scan, "análisis de código"),
                             ("adversarial", adversarial, "análisis adversarial")):
        if not (tiene_codigo or lente == "intencion"):
            continue
        modelo = ASIG[lente][0]
        if _ciega(txt):   # D0: lente ciega → no se juzga ni puntúa (la culpa no es del modelo)
            jueces[lente] = {"buena": None, "razon": "(lente ciega: caída o error)"}
            print(f"    🛑 juez({modelo}@{lente}): LENTE CIEGA — no analizó, no puntúa")
            continue
        j = juzgar(etiq, txt); jueces[lente] = j
        if j.get("buena") is None:
            print(f"    ◽ juez({modelo}@{lente}): sin veredicto — {j.get('razon','')}")
            continue
        dg = _dignidad(modelo, lente, bool(j.get("buena")))
        print(f"    🔎 juez({modelo}@{lente}): {'BUENA' if j.get('buena') else 'FALLIDA'} — {j.get('razon','')}  · dignidad {dg:.2f}")
    # Juez de seguridad (veredicto global)
    ver = _json(llm(ASIG["juez"][1], _oxigeno("juez", R["juez"].format(repo=repo, intencion=intencion,
                    codigo_scan=codigo_scan, adversarial=adversarial)), max_tokens=700),
                {"veredicto": "DUDOSO", "riesgo": 5, "razon": "(sin veredicto)", "patron_defensa": ""})
    # 🛑 D0 · FAIL-CLOSED (Opus, 2-jul): con lentes ciegas NADIE analizó de verdad →
    # el veredicto JAMÁS puede ser SEGURO. Degradar es retener, nunca aprobar.
    lentes_ciegas = [n for n, t in (("intencion", intencion), ("codigo", codigo_scan),
                                    ("adversarial", adversarial))
                     if (tiene_codigo or n == "intencion") and _ciega(t)]
    if lentes_ciegas:
        print(f"🛑 fail-closed: lente(s) CIEGA(s) → {', '.join(lentes_ciegas)}")
        if ver.get("veredicto") == "SEGURO":
            ver = {"veredicto": "DUDOSO",
                   "riesgo": max(5, int(ver.get("riesgo") or 5)),
                   "razon": f"fail-closed: lentes ciegas ({', '.join(lentes_ciegas)}) — nadie analizó de verdad",
                   "patron_defensa": ver.get("patron_defensa", "")}
    # 🔒 D0.2 · TECHO del candado (Opus, 4-jul): si la adversarial PIDIÓ probar en sandbox
    #    pero NO se pudo OBSERVAR (extensión/módulo no ejecutable, o error), NO es "limpio":
    #    es un NO-análisis dinámico. No observar ≠ seguro → jamás SEGURO sobre lo no observado.
    _sbx_ciego = (bool(_json(adversarial, {}).get("probar_en_sandbox")) and bool(codigo_file)
                  and any(m in (obs or "") for m in
                          ("no soportada", "no sé ejecutar", "[sandbox error", "sin fichero")))
    if _sbx_ciego and ver.get("veredicto") == "SEGURO":
        print("🛑 fail-closed: la adversarial pidió sandbox y NO se pudo OBSERVAR → no observar ≠ limpio")
        ver = {"veredicto": "DUDOSO", "riesgo": max(5, int(ver.get("riesgo") or 5)),
               "razon": "fail-closed: sandbox no pudo observar (extensión/módulo no ejecutable) — no observar ≠ seguro",
               "patron_defensa": ver.get("patron_defensa", "")}
    print(f"⚖️  JUEZ ({ASIG['juez'][0]}): {ver.get('veredicto')} · riesgo {ver.get('riesgo')}/10 — {ver.get('razon','')[:200]}")
    prop = _proponer_capacidad(repo, ver)
    if prop:
        print(f"🧩 propuesta de capacidad de seguridad: {prop}  (en {PROPUESTAS}, a revisar)")
    print("=" * 72)
    _registrar(repo, ver)
    # TRAZABILIDAD: pega TODO el intercambio (las 3 lentes + sandbox + veredicto)
    _trazar({"repo": repo,
             "lentes": {"intencion": {"modelo": ASIG["intencion"][0], "salida": intencion},
                        "codigo": {"modelo": ASIG["codigo"][0], "salida": codigo_scan},
                        "adversarial": {"modelo": ASIG["adversarial"][0], "salida": adversarial}},
             "sandbox": obs, "jueces_lente": jueces, "lentes_ciegas": lentes_ciegas,
             "veredicto": ver, "propuesta": prop})
    return ver


def _arg(flag, default=""):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else default


def main():
    repo = _arg("--repo", "repo/desconocido")
    readme = _arg("--readme-text") or (Path(_arg("--readme")).read_text(encoding="utf-8", errors="ignore")
                                       if _arg("--readme") and os.path.exists(_arg("--readme")) else "")
    cfile = _arg("--codigo")
    codigo = _arg("--codigo-text") or (Path(cfile).read_text(encoding="utf-8", errors="ignore")
                                       if cfile and os.path.exists(cfile) else "")
    if not (readme or codigo):
        print(__doc__); return
    analizar(repo, readme, codigo, codigo_file=cfile if cfile and os.path.exists(cfile) else None)


if __name__ == "__main__":
    main()
