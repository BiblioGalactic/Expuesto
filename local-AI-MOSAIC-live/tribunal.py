#!/usr/bin/env python3
"""
TRIBUNAL — un juez ADVERSARIAL en vez de uno solo (la rama para mejorar el juez).

Por cada respuesta: FISCAL (ataca) · ABOGADO (defiende) · ACUSACIÓN PARTICULAR (la voz
del usuario) -> JUEZ dicta veredicto leyendo los alegatos -> SALA DE APELACIÓN verifica
que el juez no fue negligente Y puntúa a cada actor. Los ROLES ROTAN entre los modelos
del pool. Los prompts de rol son CAPACIDADES MOSAIC (roles/juicio.yaml): editarlas/curarlas
las mejora, y su desempeño (data/juicio_scores.json) las ESPECIALIZA con el uso.

Todo se imprime EN TERMINAL (nada en segundo plano). Stdlib only (urllib).

Uso:
  ./tribunal.py "petición" "respuesta"                 # un juicio
  ./tribunal.py --ab "petición" "resp A" "resp B"      # dos juicios -> comparación
  ./tribunal.py --especializar                         # agrega recompensas -> scores
  ./tribunal.py --offline ...                          # sin red (mock, prueba el flujo)
"""
import json
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.request

POOL = os.getenv("TRIBUNAL_POOL",
                 "Qwen3-14B|http://127.0.0.1:8092/v1 "   # ⚔️ 3-jul: el 24B JAMÁS
                 
                 "Unholy-13B|http://127.0.0.1:8091/v1 "
                 "Ministral-8B|http://localhost:8090/v1").split()
POOL = [p.split("|", 1) for p in POOL if "|" in p]
OFFLINE = "--offline" in sys.argv
ROLES_LOG = Path(os.getenv("TRIBUNAL_ROLES", "data/tribunal_roles.jsonl"))
SCORES = Path(os.getenv("TRIBUNAL_SCORES", "data/juicio_scores.json"))
JUICIO_YAML = Path(os.getenv("TRIBUNAL_CAPS", "roles/juicio.yaml"))


def _escribir_atomico(path, texto):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.tmp{os.getpid()}")
    tmp.write_text(texto, encoding="utf-8"); os.replace(tmp, p)


def llm(url, prompt, max_tokens=400, temperature=0.4):
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


# Fallback por si no existe roles/juicio.yaml (mismas plantillas que el YAML).
DEFAULT_ROLES = {
    "fiscal": "Eres el FISCAL. Ataca la respuesta: errores, omisiones, lo que NO resuelve. 3-5 cargos.\nPETICIÓN: {req}\nRESPUESTA: {ans}\nCARGOS:",
    "abogado": "Eres el ABOGADO DEFENSOR. Defiende la respuesta, honesto, 3-5 puntos.\nPETICIÓN: {req}\nRESPUESTA: {ans}\nDEFENSA:",
    "acusacion": "Eres la ACUSACIÓN PARTICULAR (la voz del usuario). ¿Resuelve EN LA PRÁCTICA lo pedido?\nPETICIÓN: {req}\nRESPUESTA: {ans}\nRECLAMACIÓN:",
    "juez": "Eres el JUEZ. Veredicto justo leyendo los alegatos.\nPETICIÓN: {req}\nRESPUESTA: {ans}\nFISCAL:\n{fiscal}\nDEFENSA:\n{abogado}\nACUSACIÓN:\n{acusacion}\nSOLO JSON: {{\"nota\": <0-10>, \"razon\": \"<breve>\"}}",
    "apelacion": "Eres la APELACIÓN. ¿El juez fue negligente? Corrige si toca y puntúa a cada actor 0-1.\nPETICIÓN: {req}\nRESPUESTA: {ans}\n{fiscal}\n{acusacion}\nVEREDICTO: {veredicto}\nSOLO JSON: {{\"nota_final\": <0-10>, \"negligente\": true|false, \"motivo\": \"<breve>\", \"roles\": {{\"fiscal\": <0-1>, \"abogado\": <0-1>, \"acusacion\": <0-1>}}}}",
}


def cargar_roles():
    """Roles como capacidades MOSAIC (roles/juicio.yaml); si falta, plantillas internas."""
    roles = dict(DEFAULT_ROLES)
    try:
        import yaml
        if JUICIO_YAML.exists():
            for c in (yaml.safe_load(JUICIO_YAML.read_text()) or {}).get("capabilities", []):
                rid, pat = str(c.get("id", "")), c.get("behavioral_pattern", "")
                for rol in roles:
                    if rid.endswith(rol) and pat:
                        roles[rol] = pat
    except Exception:
        pass
    return roles


ROLES = cargar_roles()


def _reparto(trial_idx):
    roles = ["fiscal", "abogado", "acusacion", "juez", "apelacion"]
    n = len(POOL) or 1
    return {rol: POOL[(trial_idx + i) % n] for i, rol in enumerate(roles)}


def juicio(req, ans, trial_idx=0, etiqueta=""):
    rep = _reparto(trial_idx)
    print("=" * 72)
    print(f"⚖️  JUICIO {etiqueta}  ·  petición: {req[:60]}")
    for rol, (nom, _) in rep.items():
        print(f"    {rol:10}-> {nom}")
    print("-" * 72)

    # Los 3 alegatos son INDEPENDIENTES -> en PARALELO (cada uno en su modelo/máquina).
    # Pasa de 5 llamadas en serie a 3 etapas: [fiscal|abogado|acusacion] -> juez -> apelación.
    with ThreadPoolExecutor(max_workers=3) as ex:
        fut = {r: ex.submit(lambda rr: llm(rep[rr][1], ROLES[rr].format(req=req, ans=ans)), r)
               for r in ("fiscal", "abogado", "acusacion")}
        fiscal = fut["fiscal"].result()
        abogado = fut["abogado"].result()
        acusacion = fut["acusacion"].result()
    print(f"🔴 FISCAL ({rep['fiscal'][0]}):\n{fiscal.strip()[:500]}\n")
    print(f"🟢 DEFENSA ({rep['abogado'][0]}):\n{abogado.strip()[:500]}\n")
    print(f"🟠 ACUSACIÓN PARTICULAR ({rep['acusacion'][0]}):\n{acusacion.strip()[:500]}\n")

    v = _json(llm(rep["juez"][1], ROLES["juez"].format(req=req, ans=ans, fiscal=fiscal,
                  abogado=abogado, acusacion=acusacion)), {"nota": 5, "razon": "(sin veredicto)"})
    print(f"👨‍⚖️ JUEZ ({rep['juez'][0]}): nota {v.get('nota')}/10 — {v.get('razon','')[:200]}\n")

    ap = _json(llm(rep["apelacion"][1], ROLES["apelacion"].format(req=req, ans=ans, fiscal=fiscal,
                   acusacion=acusacion, veredicto=json.dumps(v, ensure_ascii=False))),
               {"nota_final": v.get("nota", 5), "negligente": False, "motivo": "(sin apelación)", "roles": {}})
    neg = "⚠️ NEGLIGENTE" if ap.get("negligente") else "✅ confirmado"
    print(f"🏛️  APELACIÓN ({rep['apelacion'][0]}): {neg} — nota firme {ap.get('nota_final')}/10 — {ap.get('motivo','')[:200]}")
    print("=" * 72)

    _registrar(rep, v, ap)
    return {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "peticion": req,
            "nota_juez": v.get("nota"), "nota_final": ap.get("nota_final"),
            "negligente": bool(ap.get("negligente")), "reparto": {r: n for r, (n, _) in rep.items()}}


def _registrar(rep, veredicto, apelacion):
    """Recompensa/castigo a TODOS los actores -> data para que se especialicen."""
    ROLES_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    notas = apelacion.get("roles") or {}
    filas = [{"rol": "juez", "modelo": rep["juez"][0],
              "score": 0.0 if apelacion.get("negligente") else 1.0, "ts": ts},
             {"rol": "apelacion", "modelo": rep["apelacion"][0], "score": 1.0, "ts": ts}]
    for rol in ("fiscal", "abogado", "acusacion"):
        s = notas.get(rol)
        if isinstance(s, (int, float)):
            filas.append({"rol": rol, "modelo": rep[rol][0], "score": float(s), "ts": ts})
    with open(ROLES_LOG, "a", encoding="utf-8") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def especializar():
    """Agrega el registro de actores (EMA por rol+modelo) -> data/juicio_scores.json.
    Así, con horas, ves qué modelo es mejor en cada rol (base de la especialización)."""
    if not ROLES_LOG.exists() or not ROLES_LOG.read_text().strip():
        print("Sin juicios registrados todavía."); return
    sc = {}
    try:
        sc = json.loads(SCORES.read_text()) if SCORES.exists() else {}
    except Exception:
        sc = {}
    n = 0
    for ln in ROLES_LOG.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        k = f"{r.get('rol')}|{r.get('modelo')}"
        prev = sc.get(k, {}).get("score", 0.5)
        sc[k] = {"score": round(0.8 * prev + 0.2 * float(r.get("score", 0.5)), 3),
                 "n": sc.get(k, {}).get("n", 0) + 1}
        n += 1
    _escribir_atomico(SCORES, json.dumps(sc, ensure_ascii=False, indent=2))
    arch = ROLES_LOG.with_name(ROLES_LOG.stem + ".consolidado" + ROLES_LOG.suffix)
    with open(arch, "a", encoding="utf-8") as f:
        f.write(ROLES_LOG.read_text())
    ROLES_LOG.write_text("")
    print(f"Especialización: {n} marcas agregadas -> {SCORES}")
    print("Mejores por rol:")
    for rol in ("fiscal", "abogado", "acusacion", "juez", "apelacion"):
        cand = [(k.split("|")[1], v["score"], v["n"]) for k, v in sc.items() if k.startswith(rol + "|")]
        if cand:
            cand.sort(key=lambda x: -x[1])
            print("  " + rol + ": " + " · ".join(f"{m}={s:.2f}(n{c})" for m, s, c in cand))


def _alegato(rep, rol, req, ans):
    return llm(rep[rol][1], ROLES[rol].format(req=req, ans=ans))


def juicio_lote(items, trial_base=0, etiqueta=""):
    """BATCH por rol (escala): primero TODOS los alegatos (fiscal/abogado/acusacion) de
    todos los casos, luego TODOS los jueces, luego TODAS las apelaciones. Cada modelo
    recibe su rol en ráfaga -> mejor uso de los servidores (sobre todo con --parallel).
    Concurrencia acotada por TRIBUNAL_CONCURRENCIA para no saturar slots (evita timeouts)."""
    n = len(items)
    if n == 0:
        return []
    cc = max(1, int(os.getenv("TRIBUNAL_CONCURRENCIA", "6")))
    reps = [_reparto(trial_base + k) for k in range(n)]
    print("=" * 72)
    print(f"⚖️  JUICIO EN LOTE {etiqueta} · {n} casos · batch por rol (concurrencia {cc})")
    print("-" * 72)
    # Etapa 1 · alegatos (3·n) en paralelo acotado
    aleg = {}
    with ThreadPoolExecutor(max_workers=cc) as ex:
        fut = {(k, rol): ex.submit(_alegato, reps[k], rol, items[k][0], items[k][1])
               for k in range(n) for rol in ("fiscal", "abogado", "acusacion")}
        for key, f in fut.items():
            aleg[key] = f.result()
    # Etapa 2 · jueces (n)
    vers = {}
    with ThreadPoolExecutor(max_workers=cc) as ex:
        fut = {k: ex.submit(lambda kk: _json(llm(reps[kk]["juez"][1], ROLES["juez"].format(
                   req=items[kk][0], ans=items[kk][1], fiscal=aleg[(kk, "fiscal")],
                   abogado=aleg[(kk, "abogado")], acusacion=aleg[(kk, "acusacion")])),
                   {"nota": 5, "razon": "(sin veredicto)"}), k) for k in range(n)}
        for k, f in fut.items():
            vers[k] = f.result()
    # Etapa 3 · apelaciones (n)
    apes = {}
    with ThreadPoolExecutor(max_workers=cc) as ex:
        fut = {k: ex.submit(lambda kk: _json(llm(reps[kk]["apelacion"][1], ROLES["apelacion"].format(
                   req=items[kk][0], ans=items[kk][1], fiscal=aleg[(kk, "fiscal")],
                   acusacion=aleg[(kk, "acusacion")], veredicto=json.dumps(vers[kk], ensure_ascii=False))),
                   {"nota_final": vers[kk].get("nota", 5), "negligente": False, "motivo": "(sin apelación)", "roles": {}}), k)
               for k in range(n)}
        for k, f in fut.items():
            apes[k] = f.result()
    # Imprimir + registrar (recompensa a los actores) + recolectar
    out = []
    for k in range(n):
        req, ans = items[k]; rep = reps[k]; v = vers[k]; ap = apes[k]
        neg = "⚠️NEG" if ap.get("negligente") else "✅"
        print(f"  [{k+1}/{n}] juez({rep['juez'][0]}) {v.get('nota')}/10 · "
              f"apel({rep['apelacion'][0]}) {neg} {ap.get('nota_final')}/10 :: {req[:42]}")
        _registrar(rep, v, ap)
        out.append({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "peticion": req,
                    "nota_juez": v.get("nota"), "nota_final": ap.get("nota_final"),
                    "negligente": bool(ap.get("negligente")), "reparto": {r: nm for r, (nm, _) in rep.items()}})
    print("=" * 72)
    return out


def main():
    if "--especializar" in sys.argv:
        especializar(); return
    if "--lote" in sys.argv:
        idx = sys.argv.index("--lote")
        path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        items = []
        if path and os.path.exists(path):
            for ln in open(path, encoding="utf-8"):
                ln = ln.rstrip("\n")
                if "\t" in ln:
                    req, ans = ln.split("\t", 1)
                    if req.strip():
                        items.append((req, ans))
        juicio_lote(items, 0, f"({len(items)})")
        return
    args = [a for a in sys.argv[1:] if a not in ("--offline",)]
    if args and args[0] == "--ab":
        _, req, ansA, ansB = (args + ["", "", ""])[:4]
        sA = juicio(req, ansA, 0, "A (composición)")
        sB = juicio(req, ansB, 1, "B (crudo)")
        gana = "A" if (sA["nota_final"] or 0) >= (sB["nota_final"] or 0) else "B"
        print(f"\n🏆 SENTENCIA A/B: gana {gana}  (A={sA['nota_final']} vs B={sB['nota_final']})")
    elif len(args) >= 2:
        juicio(args[0], args[1], 0)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
