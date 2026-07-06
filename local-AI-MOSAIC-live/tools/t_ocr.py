#!/usr/bin/env python3
# 🧰 ocr (nivel 2 · lectura): un fichero DEL ÁRBOL → texto. Mismas herramientas que
#    silo_extractor (tesseract spa+eng · pdftotext · pdftoppm) — adaptación por-fichero.
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _contrato import ok, fail, payload, dentro_de_base

P = payload()
ruta = str(P.get("ruta", "")).strip()
real = dentro_de_base(ruta) if ruta else None
if not real or not os.path.isfile(real):
    fail(f"ocr: el fichero debe existir DENTRO del árbol: «{ruta}»")
ext = os.path.splitext(real)[1].lower()
lang = os.environ.get("OCR_LANG", "spa+eng")

def corre(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=120, **kw)

texto = ""
if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic"):
    r = corre(["tesseract", real, "stdout", "-l", lang])
    texto = r.stdout
elif ext == ".pdf":
    r = corre(["pdftotext", "-l", "8", real, "-"])
    texto = r.stdout
    if len(texto.strip()) < 40:                          # escaneado → rasteriza y lee (patrón #76)
        with tempfile.TemporaryDirectory() as td:
            corre(["pdftoppm", "-r", "200", "-l", "5", "-png", real, f"{td}/p"])
            trozos = []
            for f in sorted(os.listdir(td)):
                trozos.append(corre(["tesseract", os.path.join(td, f), "stdout", "-l", lang]).stdout)
            texto = "\n".join(trozos)
elif ext in (".txt", ".md"):
    texto = open(real, encoding="utf-8", errors="replace").read()
else:
    fail(f"ocr: extensión no soportada aún: {ext} (png/jpg/heic/pdf/txt)")
texto = texto.strip()
if not texto:
    fail("ocr: el fichero no soltó texto (¿imagen vacía? ¿faltan binarios?)")
ok({"ruta": ruta, "caracteres": len(texto), "texto": texto[: int(P.get("max", 8000))]})
