#!/usr/bin/env python3
# 🧰 web (nivel 2 · lectura externa): trae UNA url como texto plano. Traer, no tocar.
#    Adaptación fina del /web del gateway (idea, no código): GET + strip de HTML + tope.
import re, sys, os, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _contrato import ok, fail, payload

P = payload()
url = str(P.get("url", "")).strip()
if not re.match(r"^https?://", url):
    fail("web: solo http(s):// — y una URL, no un deseo")
req = urllib.request.Request(url, headers={"User-Agent": "MOSAIC/1.0 (lectura; local-first)"})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read(512 * 1024).decode("utf-8", errors="replace")
except Exception as e:
    fail(f"web: no pude traer {url}: {e}")
txt = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
txt = re.sub(r"(?s)<[^>]+>", " ", txt)
txt = re.sub(r"\s+", " ", txt).strip()
tope = int(P.get("max", 6000))
ok({"url": url, "texto": txt[:tope], "recortado": len(txt) > tope})
