#!/usr/bin/env python3
# 🔭 =====================================================================
# 🔭 MOSAIC OBSERVADOR — lee UNA conversación y deposita UNA nota meta.json en el
# 🔭 formato EXACTO del calendario_mental: taxonomía de 5 niveles + calidad/confianza
# 🔭 + embedding MiniLM-384 (el MISMO que usa el dedup de MOSAIC) — y el ORO NUEVO:
# 🔭 'observacion' = qué CAPACIDAD/insight emerge para MOSAIC al leer esa conversación.
# 🔭 Normaliza la taxonomía LIMPIO (sin el bug ia→inteligencia-artificial del clasificador).
# 🔭 Degrada con elegancia: sin cluster/MiniLM produce una nota bien formada igualmente.
# 🔭 Uso:  python3 mosaic_observador.py CHAT.txt [carpeta_notas]
# 🔭 =====================================================================
import os, sys, re, json, glob, urllib.request
from datetime import datetime
from pathlib import Path

LLM_URL = os.getenv("MOSAIC_LLM_BASE_URL", "http://127.0.0.1:8090/v1")
EMB_MODEL = os.getenv("EMB_MODEL", os.path.expanduser("~/modelo/modelos_grandes/semantico/"
                      "models--sentence-transformers--all-MiniLM-L6-v2/snapshots"))
MAXTXT = int(os.getenv("OBS_MAXTXT", "6000"))
NOTAS_DIR = os.getenv("NOTAS_DIR", os.path.expanduser("~/proyecto/calendario_mental/notas"))
CLASIF_DIR = os.getenv("CLASIF_DIR", os.path.expanduser("~/proyecto/calendario_mental/notas_clasificadas"))
NIVELES = ("n1_dominio", "n2_pilar", "n3_disciplina", "n4_tema", "n5_entidad")
MODELO = re.sub(r"[^a-z0-9]+", "-", os.getenv("MOSAIC_LLM_MODEL", "24b").lower()).strip("-") or "modelo"
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_carta(dt=None):  # "martes, 30 de junio de 2026" — la marca de agua de cuándo se escribió
    dt = dt or datetime.now()
    return f"{_DIAS[dt.weekday()]}, {dt.day} de {_MESES[dt.month - 1]} de {dt.year}"


def _llm(prompt, max_tokens=400, temp=0.2):
    body = json.dumps({"model": "local", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": temp}).encode("utf-8")
    req = urllib.request.Request(LLM_URL.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def _json_de(t, defecto):
    try:
        return json.loads(t[t.find("{"):t.rfind("}") + 1])
    except Exception:
        return defecto


def _slug(s):  # normalización LIMPIA (arregla el bug ia→inteligencia-artificial)
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    return s or "sin-clasificar"


def clasificar(texto):
    p = ("Clasifica esta conversación humano-IA en 5 niveles taxonómicos y puntúala. Devuelve SOLO JSON:\n"
         '{"n1_dominio":"","n2_pilar":"","n3_disciplina":"","n4_tema":"","n5_entidad":"","calidad":8,"confianza":8}\n'
         "n1=dominio amplio · n2=pilar · n3=disciplina · n4=tema concreto · n5=entidad. calidad y confianza de 1 a 10.\n\n"
         f"CONVERSACIÓN:\n{texto[:MAXTXT]}")
    d = {}
    try:
        d = _json_de(_llm(p), {})
    except Exception:
        d = {}
    if not d:
        d = {"n1_dominio": "biblioteca", "n2_pilar": "tecnologia", "n3_disciplina": "general",
             "n4_tema": "conversaciones", "n5_entidad": "chat", "calidad": 5, "confianza": 5}
    for k in NIVELES:
        d[k] = _slug(d.get(k, ""))
    d["calidad"] = max(1, min(10, int(float(d.get("calidad", 5) or 5))))
    d["confianza"] = max(1, min(10, int(float(d.get("confianza", 5) or 5))))
    return d


def observar(texto):
    """EL ORO: qué capacidad/patrón reutilizable emerge para MOSAIC (no un resumen)."""
    p = ("Eres MOSAIC observando una conversación humano-IA para APRENDER. En 1-2 frases di qué "
         "CAPACIDAD o patrón reutilizable extraerías (no resumas el tema; di qué habilidad emerge). "
         "Devuelve solo el texto.\n\n"
         f"CONVERSACIÓN:\n{texto[:MAXTXT]}")
    try:
        return _llm(p, max_tokens=120).strip()
    except Exception:
        return ""


def embed(texto):
    try:
        cand = EMB_MODEL if os.path.isdir(EMB_MODEL) else next(iter(glob.glob(EMB_MODEL + "*")), "")
        if cand and os.path.isdir(cand):
            from sentence_transformers import SentenceTransformer
            m = SentenceTransformer(cand)
            return [float(x) for x in m.encode([texto[:MAXTXT]])[0]]
    except Exception:
        pass
    return [0.0] * 384                       # placeholder de contrato; en tu Mac será MiniLM real


def fecha_de(nombre):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", nombre)
    return m.group(1) if m else datetime.now().strftime("%Y-%m-%d")


def main():
    if len(sys.argv) < 2:
        print("uso: mosaic_observador.py TEXTO.txt [carpeta_clasificadas]", file=sys.stderr); sys.exit(2)
    ruta = sys.argv[1]
    base_out = sys.argv[2] if len(sys.argv) > 2 else CLASIF_DIR
    texto = Path(ruta).read_text(encoding="utf-8", errors="ignore").strip()
    base = Path(ruta).stem
    fecha = fecha_de(base)
    # nombre = <fecha>_<titulo> (conserva la fecha si ya la trae; si no, la antepone)
    nombre = base if re.match(r"^\d{4}-\d{2}-\d{2}", base) else f"{fecha}_{base}"

    clas = clasificar(texto)
    ruta_completa = "--".join(clas[k] for k in NIVELES)
    obs = observar(texto)
    titulo = re.sub(r"^\d{4}-\d{2}-\d{2}(_\d{4}-\d{2}-\d{2})?_?", "", nombre) or nombre
    nota = {
        "archivo": f"{nombre}.txt",
        "fecha_procesamiento": datetime.now().isoformat(),
        **{k: clas[k] for k in NIVELES},
        "ruta_completa": ruta_completa,
        "calidad": clas["calidad"],
        "confianza": clas["confianza"],
        "nota_final": round((clas["calidad"] + clas["confianza"]) / 2, 1),
        "observacion": obs,                       # el oro de MOSAIC (qué capacidad emerge)
        "fuente": f"mosaic_{MODELO}",             # quién la hizo: MOSAIC + modelo
        "vector_embedding": embed(texto),
    }
    # (1) registro CLASIFICADO (con embedding, para el RAG): notas_clasificadas/<ruta>/<nombre>.{txt,_meta.json}
    outdir = Path(base_out) / ruta_completa
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{nombre}.txt").write_text(texto, encoding="utf-8")
    (outdir / f"{nombre}_meta.json").write_text(json.dumps(nota, ensure_ascii=False), encoding="utf-8")
    # (2) NOTA DEL CALENDARIO en notas/ — archivada bajo la fecha de la CONVERSACIÓN (día del
    #     calendario), con cabecera de CARTA (fecha en que MOSAIC la escribió) + marca mosaic_<modelo>.
    notas = Path(NOTAS_DIR); notas.mkdir(parents=True, exist_ok=True)
    cal = notas / f"{fecha}_mosaic_{MODELO}_{_slug(titulo)}.txt"
    cal.write_text(
        f"Fecha: {fecha_carta()} · observado por mosaic_{MODELO}\n---\n"
        f"{obs or '(sin observación)'}\n\n"
        f"— sobre «{titulo}» ({fecha}) · {ruta_completa} · calidad {clas['calidad']}/confianza {clas['confianza']}\n",
        encoding="utf-8")
    print(cal)


if __name__ == "__main__":
    main()
