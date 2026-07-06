#!/usr/bin/env python3
# 🧰 buscar (nivel 2 · lectura externa): búsqueda web sin clave (DuckDuckGo HTML).
#    Traer, no tocar. Si el buscador no responde, lo dice honesto — no inventa.
import re, sys, os, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _contrato import ok, fail, payload

P = payload()
q = str(P.get("q", "")).strip()
if not q:
    fail("buscar: sin consulta")
n = max(1, min(int(P.get("n", 5)), 8))
url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MOSAIC lectura)"})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read(512 * 1024).decode("utf-8", errors="replace")
except Exception as e:
    fail(f"buscar: el buscador no respondió: {e}")
res = []
for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html):
    href, tit = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
    mm = re.search(r"uddg=([^&]+)", href)
    if mm:
        href = urllib.parse.unquote(mm.group(1))
    res.append({"titulo": tit, "url": href})
    if len(res) >= n:
        break
if not res:
    fail("buscar: 0 resultados parseables (¿bloqueado o cambió el HTML?) — no invento")
ok({"q": q, "resultados": res})
