#!/usr/bin/env python3
# 🗂 =====================================================================
# 🗂 MOSAIC EXTRAER CONVERSACIONES (Paso B) — lee exports de IA y saca UNA conversación
# 🗂 por .txt con FECHA en el nombre, para que luego silo_conversaciones.sh las observe
# 🗂 de la MÁS ANTIGUA a hoy. Detecta el esquema como tu analize_json.py:
# 🗂   · ChatGPT  → 'mapping' (árbol de mensajes por uuid; fecha = create_time)
# 🗂   · Claude   → 'chat_messages' (lista sender/text; fecha = created_at)
# 🗂   · Gemini   → 'messages' (role/content)
# 🗂 RAM acotada: procesa UN export a la vez (el JSON grande se libera al pasar al siguiente).
# 🗂 Uso:  python3 mosaic_extraer_conversaciones.py export1.json [export2.json ...]
# 🗂       (destino: CONV_TXT_DIR, def. calendario_mental/conversaciones_txt)
# 🗂 =====================================================================
import os, re, sys, json
from datetime import datetime, timezone
from pathlib import Path

DEST = os.getenv("CONV_TXT_DIR", os.path.expanduser("~/proyecto/calendario_mental/conversaciones_txt"))


def _slug(s):
    return (re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:50]) or "sin-titulo"


def _fecha(conv):
    for k in ("create_time", "created_at", "date", "update_time"):
        v = conv.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return datetime.fromtimestamp(v, timezone.utc).strftime("%Y-%m-%d")
        if isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v):
            return v[:10]
    return "9999-99-99"                      # sin fecha → al final del orden cronológico


def _txt_mapping(mapping):                   # ChatGPT: árbol {uuid: {message, parent, children}}
    msgs = []
    for node in (mapping or {}).values():
        m = (node or {}).get("message")
        if not m:
            continue
        role = ((m.get("author") or {}).get("role")) or ""
        parts = ((m.get("content") or {}).get("parts")) or []
        txt = " ".join(p for p in parts if isinstance(p, str)).strip()
        if txt and role in ("user", "assistant"):
            msgs.append((m.get("create_time") or 0, role, txt))
            continue
        # Deepseek (hallazgo de Opus, 2-jul): mapping con 'fragments'
        # [{type: REQUEST|RESPONSE, content}] en vez de content.parts — un msg por fragmento.
        for fr in (m.get("fragments") or []):
            if not isinstance(fr, dict):
                continue
            c, t = fr.get("content"), (fr.get("type") or "").upper()
            r = "user" if t == "REQUEST" else ("assistant" if t == "RESPONSE" else role)
            if isinstance(c, str) and c.strip() and r in ("user", "assistant"):
                msgs.append((m.get("create_time") or 0, r, c.strip()))
    msgs.sort(key=lambda x: x[0] or 0)
    return "\n".join(f"{r}: {t}" for _, r, t in msgs)


def _txt_lista(lista):                        # Claude/notas (chat_messages) o Gemini (messages)
    out = []
    for m in (lista or []):
        if not isinstance(m, dict):
            continue
        r = m.get("role") or m.get("sender") or ""
        t = m.get("text") or m.get("content") or ""
        if isinstance(t, list):
            t = " ".join(x for x in t if isinstance(x, str))
        if isinstance(t, str) and t.strip():
            out.append(f"{r}: {t.strip()}")
    return "\n".join(out)


def conversaciones(export_path):
    """(fecha, titulo, texto) por conversación; auto-detecta el esquema."""
    try:
        data = json.load(open(export_path, encoding="utf-8", errors="ignore"))
    except Exception as e:
        print(f"⚠️  no pude leer {export_path}: {e}", file=sys.stderr); return
    # Log LOCAL estilo OpenAI (lista de mensajes sueltos role/content, p. ej. local_*.json):
    # todo el fichero = UNA conversación; fecha = mtime del fichero (mejor que 9999).
    if isinstance(data, list) and data and all(isinstance(m, dict) for m in data) \
       and any(("role" in m or "sender" in m) and ("content" in m or "text" in m) for m in data) \
       and not any(k in m for m in data for k in ("mapping", "chat_messages", "messages")):
        texto = _txt_lista(data)
        if texto.strip():
            try:
                f = datetime.fromtimestamp(os.path.getmtime(export_path), timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                f = "9999-99-99"
            yield (f, Path(export_path).stem, texto)
        return
    lista = data if isinstance(data, list) else (data.get("conversations") or [data])
    for conv in lista:
        if not isinstance(conv, dict):
            continue
        if "mapping" in conv:
            texto = _txt_mapping(conv["mapping"])
        elif "chat_messages" in conv:
            texto = _txt_lista(conv["chat_messages"])
        elif "messages" in conv:
            texto = _txt_lista(conv["messages"])
        else:
            texto = ""
        if not texto.strip():
            continue
        titulo = conv.get("title") or conv.get("name") or "sin-titulo"
        yield (_fecha(conv), titulo, texto)


def main():
    exports = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not exports:
        print("uso: mosaic_extraer_conversaciones.py export.json [...]", file=sys.stderr); sys.exit(2)
    dest = Path(DEST); dest.mkdir(parents=True, exist_ok=True)
    total = 0
    for ex in exports:                        # UN export a la vez → RAM acotada
        n = dups = 0
        for fecha, titulo, texto in conversaciones(ex):
            nombre = f"{fecha}_{_slug(titulo)}"
            out = dest / f"{nombre}.txt"; i = 1; dup = False
            while out.exists():              # re-lanzamiento SEGURO: idéntica ya extraída → no duplicar
                if out.read_text(encoding="utf-8", errors="ignore") == texto:
                    dup = True; break
                out = dest / f"{nombre}-{i}.txt"; i += 1
            if dup:
                dups += 1; continue
            out.write_text(texto, encoding="utf-8"); n += 1; total += 1
        if n == 0 and dups > 0:
            aviso = f"   (las {dups} ya estaban extraídas — re-lanzamiento seguro)"
        elif n == 0:
            aviso = "   ← 0: ¿esquema desconocido? pásale una muestra a Fable"
        else:
            aviso = f" (+{dups} ya extraídas)" if dups else ""
        print(f"  📤 {Path(ex).name}: {n} conversaciones → {dest.name}/{aviso}")
    print(f"🗂 total {total} .txt con fecha en {dest}")
    print("   ahora:  CHATS_DIR=" + str(dest) + "  ./silo_conversaciones.sh idle   (las observa viejo→hoy)")


if __name__ == "__main__":
    main()
