#!/usr/bin/env python3
# 🌐 =====================================================================
# 🌐 FNC — Composición Funcional Neopolilingüe como ARMA de FIRMEZA para MOSAIC.
# 🌐 Convierte una REGLA/PROHIBICIÓN en claro → versión FNC (EN estructura ·
# 🌐 DE técnico · ES intención · [JA imperativo opcional]) con un modelo FUERTE,
# 🌐 y la VALIDA con tu propio validate_prompt.py (portero de calidad, 0-100).
# 🌐 GATED: solo firma si MOSAIC_FNC=1 y la salida pasa el validador. Si no,
# 🌐 devuelve el texto EN CLARO (degradación elegante: NUNCA rompe el pipeline).
# 🌐 Cache: las reglas FIJAS se firman UNA vez (data/fnc_cache.json).
# 🌐 Uso:  echo "regla" | fnc.py firmar      ·      echo "texto" | fnc.py validar
# 🌐 =====================================================================
import os, sys, json, hashlib, urllib.request
from pathlib import Path

FNC_DIR = os.getenv("FNC_DIR", os.path.expanduser("~/Expuesto/volumen_linguistic_composition"))
CACHE = Path(os.getenv("FNC_CACHE", "data/fnc_cache.json"))
LLM_URL = os.getenv("FNC_LLM_URL") or os.getenv("MOSAIC_LLM_BASE_URL", "http://127.0.0.1:8092/v1")  # F9 (4-jul): la firma FNC exige modelo FUERTE (Qwen3-14B@8092), no el juez pequeño del mini (8090)
MIN_VALID = float(os.getenv("FNC_MIN_VALID", "60"))     # score mínimo del validador para aceptar la FNC
ON = os.getenv("MOSAIC_FNC", "0") == "1"                # interruptor maestro (default OFF: no cambia conducta)
USA_JA = os.getenv("FNC_JA", "0") == "1"                # imperativos en JA (R2 del BNF; sube la firmeza)
JA_URL = os.getenv("FNC_JA_URL", "")                    # modelo JA dedicado (japanese-stablelm); vacío = lo hace el principal


# --- validador: REUSA tu validate_prompt.py (portero de calidad) ------------
def _validador():
    try:
        sys.path.insert(0, str(Path(FNC_DIR) / "tools"))
        import validate_prompt as vp
        return vp
    except Exception:
        return None


def validar(texto):
    """(valido, score, idiomas) según TU validador FNC; respaldo mínimo si no está."""
    vp = _validador()
    if vp:
        r = vp.validate(texto)
        return bool(r.valid), float(r.score), sorted(r.languages_detected - {"UNKNOWN"})
    import re
    langs = set()
    if re.search(r"[A-Za-z]", texto): langs.add("LATN")
    if re.search(r"[぀-ヿ一-鿿]", texto): langs.add("JA")
    if re.search(r"[ÄÖÜäöüß]", texto): langs.add("DE")
    if re.search(r"[áéíóúñ¿¡]", texto): langs.add("ES")
    return (len(langs) >= 2), 50.0, sorted(langs)


# --- meta-prompt: pide la composición FNC a un modelo fuerte ----------------
def _meta_prompt(regla, con_ja_inline):
    ja = ("- Los IMPERATIVOS/PROHIBICIONES van en japonés formal "
          "(してはならない=prohibido · しなければならない=obligatorio).\n" if con_ja_inline else
          "- Los IMPERATIVOS/PROHIBICIONES van en alemán rotundo o inglés tajante "
          "(muss / darf nicht · must / shall not).\n")
    return (
        "Eres un compositor de NEOPOLILENGUA FUNCIONAL. Reescribe la REGLA como UN texto "
        "fusionado donde cada idioma cumple un ROL (no es traducción):\n"
        "- EN → estructura lógica y conectores.\n"
        "- DE → términos técnicos y precisión.\n"
        "- ES → intención y énfasis.\n"
        f"{ja}"
        "Restricciones: mínimo 3 idiomas; PROHIBIDAS las traducciones paralelas (cada fragmento "
        "aporta algo distinto); debe leerse como un solo idioma emergente, no fragmentos pegados. "
        "Devuelve SOLO el texto fusionado, sin comillas ni explicación.\n\n"
        f"REGLA EN CLARO:\n{regla}\n\nVERSIÓN NEOPOLILINGÜE:"
    )


def _llm(prompt, url=None, timeout=120):
    body = json.dumps({"model": "local", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 300, "temperature": 0.3}).encode("utf-8")
    req = urllib.request.Request((url or LLM_URL).rstrip("/") + "/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def _ja_imperativo(regla, url):
    """SOLO el imperativo/prohibición en japonés formal, por un modelo JA-capaz (japanese-stablelm)."""
    p = ("Convierte esta REGLA en UNA prohibición o imperativo BREVE en japonés formal "
         "(してはならない = prohibido · しなければならない = obligatorio). "
         "Devuelve SOLO el japonés, sin romaji ni explicación.\n\n"
         f"REGLA: {regla}\nJAPONÉS:")
    return _llm(p, url=url, timeout=120)


# --- cache (reglas fijas: firmar una vez) -----------------------------------
def _cache_load():
    try: return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception: return {}

def _cache_save(d):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".tmp"); tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, CACHE)

def _key(regla): return hashlib.sha1(f"{regla}|ja={int(USA_JA)}|{JA_URL}".encode("utf-8")).hexdigest()[:16]


def firmar(regla, url=None, forzar=False):
    """Versión FNC de una regla. GATED: si MOSAIC_FNC!=1 y no forzar → claro tal cual.
    Cachea reglas fijas. Valida la salida con tu validador; si no pasa → claro (no rompe)."""
    if not (ON or forzar):
        return regla
    cache = _cache_load(); k = _key(regla)
    if k in cache:
        return cache[k]["fnc"]
    try:
        ja_dedicado = bool(USA_JA and JA_URL)
        cuerpo = _llm(_meta_prompt(regla, con_ja_inline=(USA_JA and not ja_dedicado)), url=url)
        fnc = cuerpo
        if ja_dedicado:                      # capa JA enriquecedora (BNF §4) por el modelo japonés
            ja = _ja_imperativo(regla, JA_URL)
            if ja.strip() and "[error" not in ja:
                fnc = cuerpo.rstrip(" .。") + " — " + ja.strip()
    except Exception:
        return regla                         # sin modelo accesible → degrada a claro
    ok, score, langs = validar(fnc)
    if not ok or score < MIN_VALID:
        return regla                         # FNC mal formada → mejor el claro
    cache[k] = {"regla": regla[:120], "fnc": fnc, "score": score, "langs": langs}
    _cache_save(cache)
    return fnc


# --- CLI --------------------------------------------------------------------
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    entrada = (sys.stdin.read().strip() if not sys.stdin.isatty() else " ".join(sys.argv[2:]))
    if cmd == "firmar":
        print(firmar(entrada, forzar=True))
    elif cmd == "validar":
        ok, score, langs = validar(entrada)
        print(json.dumps({"valido": ok, "score": score, "idiomas": langs}, ensure_ascii=False))
    else:
        print("uso: fnc.py firmar <regla> | fnc.py validar <texto>   (admite stdin)", file=sys.stderr)
        sys.exit(2)
