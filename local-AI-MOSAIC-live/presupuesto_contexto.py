#!/usr/bin/env python3
"""
🧮 PRESUPUESTO_CONTEXTO — la calculadora determinista de la ventana (P1 · plan 6-jul).
Nace del estudio de Opus 03:55 + D10-D13/D23 del PLAN_MESA: no adivinar max_tokens,
PRESUPUESTARLO por modelo con margen de oxígeno, ANTES de enviar. Es la cura del
«salió vacío» (2500 prompt + 3000 salida > 4096 ctx → rechazo instantáneo).

La llaman: turno_rol.sh::generar_directo · mosaic.py::ClusterLLM.generate · parlamento.py.
Kill-switch del llamante: PRESUPUESTO=0 → cada uno vuelve a sus defaults de siempre.

El presupuesto (D10-D13 + D23):
  n_ctx_efectivo = ctx(servidores.conf) ÷ parallel(flags)          # la trampa del bug
  oxígeno        = max(18% × n_ctx_ef, 512)                        # D10 (env OXIGENO_PCT/PISO)
  usable         = n_ctx_ef − oxígeno
  salida         = techo por tipo (accion 800 · informe 1200 · chat 800 · corto 600)  # D12*
  pensar         = reserva por MODELO (regla 3 Opus 00:45): *Thinking* 2000 · *R1*/*DeepSeek* 800 · chat 0
  cabe_prompt    = usable − salida − pensar
  t_prompt       = /tokenize del PROPIO modelo (exacto) · fallback estimador conservador
  si no cabe     → recorte determinista: las LECTURAS ceden primero, la más vieja primero
                   (bloques `===== ruta =====` desde el primero); persona+tarea y ANCLA intocables.
  si ni así cabe → FALLAR ALTO (exit 3): jamás enviar basura.
  max_tokens     = salida + pensar  (lo generado incluye el <think> del razonador)

  (*) D12 decía auditoría 600; subo accion→800 para no truncar la plantilla de 5 secciones
      a mitad (una Acción coja degrada a Informe). Desviación DECLARADA — Opus ajusta si quiere.

CLI:
  python3 presupuesto_contexto.py --url http://IP:8092/v1 --modelo Qwen3-14B \
      --tipo accion --prompt-file p.txt [--trim-out p.rec] [--plano]
  --plano  → una línea parseable en bash 3.2: «maxtok=N tprompt=N cabe=0|1 recortado=0|1 fuente=X»
  (sin --plano → JSON completo). exit: 0 ok · 3 no-cabe-ni-recortando · 2 uso.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

BASE = Path(os.environ.get("MOSAIC_BASE", Path(__file__).resolve().parent))
SERVIDORES = Path(os.environ.get("SERVIDORES_CONF", BASE / "servidores.conf"))

# ── D10/D12/D23: los números de la casa (env manda encima; a servidores.conf cuando Opus firme) ──
OXIGENO_PCT = float(os.environ.get("OXIGENO_PCT", "0.18"))
OXIGENO_PISO = int(os.environ.get("OXIGENO_PISO", "512"))
# (la reserva de pensar vive en reserva_pensar(modelo) — regla 3 Opus 00:45: 2000/800/0;
#  la constante plana de 1200 murió con el catálogo probado)
PROMPT_MINIMO = int(os.environ.get("PROMPT_MINIMO", "600"))        # persona+tarea; por debajo, ALTO
TECHOS = {"accion": int(os.environ.get("TECHO_ACCION", "800")),
          "informe": int(os.environ.get("TECHO_INFORME", "1200")),
          "chat": int(os.environ.get("TECHO_CHAT", "800")),
          "corto": int(os.environ.get("TECHO_CORTO", "600"))}
CHARS_POR_TOKEN = float(os.environ.get("CHARS_POR_TOKEN", "3.0"))  # estimador CONSERVADOR (sobreestima)


def _catalogo():
    """El catálogo (inventario_modelos.yaml) — la FUENTE ÚNICA del comportamiento (D1 Opus
    14:20). Cacheado; {} si no está (se cae a la heurística por nombre, retrocompat)."""
    if getattr(_catalogo, "_cache", None) is None:
        try:
            import yaml
            d = yaml.safe_load(open(os.path.join(BASE, "data", "inventario_modelos.yaml"),
                                    encoding="utf-8")) or {}
            _catalogo._cache = d.get("modelos") or {}
        except Exception:
            _catalogo._cache = {}
    return _catalogo._cache


def _entrada_catalogo(modelo):
    """Encuentra la entrada del catálogo por nombre (exacto o basename-gguf), tolerante."""
    cat = _catalogo()
    if modelo in cat:
        return cat[modelo]
    m = (modelo or "").lower()
    for nombre, v in cat.items():
        if nombre.lower() in m or m in nombre.lower():
            return v
        g = os.path.basename(str(v.get("gguf", ""))).lower().replace(".gguf", "")
        if g and (g in m or m in g):
            return v
    return None


def _flag_si(v):
    """Normaliza el flag razonador: YAML parsea `no`→False (bool) y `si`→'si' (str)."""
    return v in (True, "si", "sí", "yes", "true", 1)


def es_razonador(modelo):
    """D1 (Opus 14:20): del CATÁLOGO (flag `razonador`), NO del nombre. Heurística solo si
    el modelo no está catalogado (retrocompat con clones sin inventario)."""
    e = _entrada_catalogo(modelo)
    if e is not None:
        return _flag_si(e.get("razonador"))
    m = (modelo or "").lower()
    return "deepseek" in m or "-r1" in m or "_r1" in m or "thinking" in m


def reserva_pensar(modelo):
    """La reserva de pensar: del catálogo (`reserva` por razonador, D1 Opus 14:20). Si el
    modelo está catalogado como razonador sin `reserva` explícita, 800 por defecto; chat=0.
    Env RESERVA_PENSAR* siempre MANDA. Heurística por nombre solo sin catálogo."""
    e = _entrada_catalogo(modelo)
    if e is not None:
        if not _flag_si(e.get("razonador")):
            return 0
        if os.environ.get("RESERVA_PENSAR_THINK") and "thinking" in (modelo or "").lower():
            return int(os.environ["RESERVA_PENSAR_THINK"])
        if os.environ.get("RESERVA_PENSAR"):
            return int(os.environ["RESERVA_PENSAR"])
        return int(e.get("reserva", 800) or 800)
    m = (modelo or "").lower()                             # sin catálogo: la heurística de siempre
    if "thinking" in m:
        return int(os.environ.get("RESERVA_PENSAR_THINK", "2000"))
    if es_razonador(modelo):
        return int(os.environ.get("RESERVA_PENSAR", "800"))
    return 0


def ctx_efectivo(puerto):
    """ctx ÷ parallel desde servidores.conf (formato maquina|puerto|rol|modo|ruta|ctx|flags).
    Si el puerto no está declarado → 4096 conservador (mejor corto que desborde)."""
    try:
        for ln in SERVIDORES.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            c = ln.split("|")
            if len(c) >= 6 and c[1].strip() == str(puerto):
                ctx = int(c[5].strip() or 4096)
                par = re.search(r"--parallel\s+(\d+)", c[6] if len(c) > 6 else "")
                return ctx // (int(par.group(1)) if par else 1)
    except OSError:
        pass
    return 4096


def modelo_de_puerto(puerto):
    """Nombre del modelo desde servidores.conf (basename de la ruta gguf) — para llamantes
    que no lo saben (parlamento): así la reserva de pensar de R1 aplica sin hardcodes."""
    try:
        for ln in SERVIDORES.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            c = ln.split("|")
            if len(c) >= 5 and c[1].strip() == str(puerto):
                return c[4].split("/")[-1].replace("*", "").replace(".gguf", "")
    except OSError:
        pass
    return ""


def cap_max_tokens(url, modelo, texto, pedido):
    """CAP suave para llamantes que YA traen su max_tokens (mosaic.py): recorta el pedido a lo
    que de verdad cabe (usable − prompt); JAMÁS lo sube. Sin excepciones: ante fallo, el pedido."""
    try:
        puerto = (re.search(r":(\d+)", url or "") or [None, "0"])[1]
        n_ctx = ctx_efectivo(puerto)
        usable = n_ctx - max(int(n_ctx * OXIGENO_PCT), OXIGENO_PISO)
        t, _ = tokens_de(texto, url)
        return max(64, min(int(pedido), usable - t))
    except Exception:
        return int(pedido)


def tokens_de(texto, base_url):
    """/tokenize del PROPIO modelo (verdad exacta, por-modelo) · fallback estimador conservador.
    llama-server sirve /tokenize en la RAÍZ (sin /v1)."""
    raiz = re.sub(r"/v1/?$", "", (base_url or "").rstrip("/"))
    if raiz:
        try:
            req = urllib.request.Request(raiz + "/tokenize",
                                         data=json.dumps({"content": texto}).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                n = len(json.loads(r.read().decode()).get("tokens") or [])
                if n:
                    return n, "tokenize"
        except Exception:
            pass
    return int(len(texto) / CHARS_POR_TOKEN) + 1, "estimador"


def recortar(texto, chars_obj):
    """D13: las LECTURAS ceden primero, la más vieja primero. Los bloques `===== ruta =====`
    caen desde el PRIMERO (en la composición, lo más viejo va antes); la cabecera
    (persona+tarea+menús) y la cola (ANCLA) son intocables. Marcador honesto de lo caído."""
    partes = re.split("\n(?=" + re.escape("===== ") + ")", texto)   # [cabecera, bloque1, bloque2, …]
    if len(partes) < 2:
        return None                                         # sin lecturas que ceder
    cabecera, bloques = partes[0], partes[1:]
    # la ANCLA vive pegada al final del último bloque — sepárala para que sobreviva SIEMPRE
    ancla = ""
    m = re.search(r"\n\n[^\n]*$", bloques[-1])
    if m and "=====" not in m.group(0):
        ancla = m.group(0)
        bloques[-1] = bloques[-1][: m.start()]
    caidos = []
    while bloques and len(cabecera) + sum(len(b) + 1 for b in bloques) + len(ancla) > chars_obj:
        b = bloques.pop(0)                                  # la más vieja cede primero
        caidos.append((b.splitlines()[0] if b else "?").strip("= ")[:60])
    cuerpo = "\n".join([cabecera] + bloques) if bloques else cabecera
    if caidos:
        cuerpo += f"\n\n[🧮 presupuesto: {len(caidos)} lectura(s) recortada(s) por no caber: {' · '.join(caidos)}]"
    return cuerpo + ancla


def presupuesto(url, modelo, tipo, texto):
    puerto = (re.search(r":(\d+)", url or "") or [None, "0"])[1]
    if not modelo:
        modelo = modelo_de_puerto(puerto)                   # el conf sabe quién vive en el puerto
    n_ctx = ctx_efectivo(puerto)
    oxigeno = max(int(n_ctx * OXIGENO_PCT), OXIGENO_PISO)
    usable = n_ctx - oxigeno
    salida = TECHOS.get((tipo or "informe").lower(), TECHOS["informe"])
    pensar = reserva_pensar(modelo)
    gen = salida + pensar
    cabe_prompt = usable - gen
    if cabe_prompt < PROMPT_MINIMO:                         # ni la persona+tarea caben → ALTO
        return {"ok": False, "motivo": f"cabe_prompt={cabe_prompt} < mínimo {PROMPT_MINIMO} "
                                       f"(ctx_ef={n_ctx}, gen={gen}) — modelo demasiado justo para este rol"}
    t_prompt, fuente = tokens_de(texto, url)
    r = {"ok": True, "max_tokens": gen, "salida": salida, "pensar": pensar, "oxigeno": oxigeno,
         "n_ctx_efectivo": n_ctx, "usable": usable, "cabe_prompt": cabe_prompt,
         "t_prompt": t_prompt, "fuente": fuente, "cabe": t_prompt <= cabe_prompt, "recortado": False}
    if not r["cabe"]:
        ratio = len(texto) / max(t_prompt, 1)               # chars/token MEDIDO en este prompt
        objetivo = int(cabe_prompt * ratio * 0.95)          # 5% de margen sobre el recorte
        nuevo = recortar(texto, objetivo)
        if nuevo is None:
            return {"ok": False, "motivo": f"prompt {t_prompt}tok > {cabe_prompt} y sin lecturas que ceder"}
        t2, f2 = tokens_de(nuevo, url)
        if t2 > cabe_prompt:
            return {"ok": False, "motivo": f"ni recortando cabe: {t2}tok > {cabe_prompt}"}
        r.update({"texto": nuevo, "t_prompt": t2, "fuente": f2, "cabe": True, "recortado": True})
    return r


def main():
    a = sys.argv[1:]

    def arg(f, d=None):
        return a[a.index(f) + 1] if f in a and a.index(f) + 1 < len(a) else d
    url, modelo, tipo = arg("--url", ""), arg("--modelo", ""), arg("--tipo", "informe")
    pf, trim_out = arg("--prompt-file"), arg("--trim-out")
    if not pf or not Path(pf).is_file():
        print("uso: --url U --modelo M --tipo accion|informe|chat|corto --prompt-file F "
              "[--trim-out G] [--plano]", file=sys.stderr)
        sys.exit(2)
    r = presupuesto(url, modelo, tipo, Path(pf).read_text(encoding="utf-8", errors="replace"))
    if not r.get("ok"):
        print(f"🧮 FALLO ALTO: {r.get('motivo')}", file=sys.stderr)
        sys.exit(3)
    if r.get("recortado") and trim_out:
        Path(trim_out).write_text(r.pop("texto"), encoding="utf-8")
        r["trim_out"] = trim_out
    else:
        r.pop("texto", None)
    if "--plano" in a:                                      # bash 3.2-safe: una línea, sin json
        print(f"maxtok={r['max_tokens']} tprompt={r['t_prompt']} cabe=1 "
              f"recortado={1 if r['recortado'] else 0} fuente={r['fuente']}")
    else:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
