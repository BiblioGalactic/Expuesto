#!/usr/bin/env python3
# 📤 =====================================================================
# 📤 EL CARTERO — router de correo de SALIDA (P3 del plan 6-jul · espejo del estafeta).
# 📤   N3 DETERMINISTA: reglas, cero LLM. NACE EN MODO PLUMA: mueve ficheros DENTRO
# 📤   de data/ y JAMÁS envía nada fuera. El envío real es un GESTO DE GUSTAVO.
# 📤   El flujo:
# 📤     data/buzones/<rol>/salida/carta_*.txt   ← un rol deja aquí su carta
# 📤        cabeceras en las primeras líneas:  PARA: <rol|dirección>  ·  ASUNTO: <texto>
# 📤     → cartero.py --procesar:
# 📤        1) PARA = rol CONOCIDO (roles/turnos/*.yaml) → INTERNO: se entrega a
# 📤           data/buzones/<destino>/entrada/ etiquetada [PROCEDENCIA: INTERIOR — de
# 📤           <origen>] (pluma-con-registro dentro de buzones: D22). El anti-poisoning
# 📤           del turno NO se dispara (interior verificado ≠ buzón exterior).
# 📤        2) PARA = dirección EXTERNA (email/tel/lo-no-conocido) → JAMÁS SE ENVÍA:
# 📤           queda en data/salida_pendiente/ con su metadato, esperando el DOBLE
# 📤           SELLO + el gesto humano (mensaje_externo es nivel 5: SIEMPRE humano).
# 📤        3) FILTRO DE FUGAS: toda carta pasa por los patrones `gate` de
# 📤           saneado_patrones.conf (la fuente única) — si contiene un secreto/PII de
# 📤           la casa se RETIENE (data/salida_pendiente/retenidas/) y se avisa. Un
# 📤           agente jamás saca secretos por correo, ni por error.
# 📤     Todo movimiento queda en data/buzones/libro.jsonl (el mismo libro del estafeta).
# 📤   Kill-switch: CARTERO=0 (no procesa nada). Sin --procesar = DRY (enseña el plan).
# 📤   Lo que NO hace (a conciencia): enviar (SMTP/SMS/lo-que-sea), tocar fuera de
# 📤   data/, decidir por el humano. La conexión como tool (correo_interno, nivel 4)
# 📤   espera la ratificación de D22 por la mesa.
# 📤 Uso:  ./cartero.py             (dry: qué haría)
# 📤       ./cartero.py --procesar
# 📤 =====================================================================
import datetime
import json
import os
import re
import shutil
import sys

BASE = os.environ.get("MOSAIC_BASE", os.path.expanduser("~/Mosaic_privado"))
BUZONES = os.path.join(BASE, "data", "buzones")
PENDIENTE = os.path.join(BASE, "data", "salida_pendiente")
RETENIDAS = os.path.join(PENDIENTE, "retenidas")
LIBRO = os.path.join(BUZONES, "libro.jsonl")
TURNOS_DIR = os.path.join(BASE, "roles", "turnos")
SANEADO = os.environ.get("SANEADO_CONF", os.path.join(BASE, "saneado_patrones.conf"))
APLICAR = "--procesar" in sys.argv

# 🪶 PLUMA-CON-CUOTA (resolución Opus 14:55): correo_interno deja de ser manos-doble-sello y
#    pasa a pluma con RATE-LIMIT — un humano no sella cada carta entre agentes (mataría la
#    autonomía) y el anti-poisoning ya defusa el mensaje EN RECEPCIÓN («material, no mandato»).
#    La cuota es la salvaguarda: un agente no puede INUNDAR a otro. Y el TRIPWIRE: si un origen
#    revienta N× su cuota (coordinación/spam), se ESCALA a sello-auditor (la excepción se sella).
CUOTA_INTERNA = int(os.environ.get("CARTERO_CUOTA", "3") or "3")        # cartas internas / origen / corrida
TRIPWIRE_X = int(os.environ.get("CARTERO_TRIPWIRE_X", "3") or "3")      # ×cuota que dispara el escalado


def log(msg):
    print(f"[{datetime.datetime.now():%H:%M:%S}] 📤 {msg}")


def anotar(evento, **kv):
    if not APLICAR:
        return
    os.makedirs(os.path.dirname(LIBRO), exist_ok=True)
    with open(LIBRO, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
                            "evento": evento, **kv}, ensure_ascii=False) + "\n")


def roles_conocidos():
    try:
        return {f[:-5] for f in os.listdir(TURNOS_DIR) if f.endswith(".yaml")}
    except OSError:
        return set()


def patrones_fuga():
    """Los `gate` de la fuente única — si el conf falta, FALLAR ALTO (jamás colar fugas)."""
    pats = []
    try:
        for ln in open(SANEADO, encoding="utf-8"):
            ln = ln.rstrip("\n")
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            c = ln.split("\t")
            if len(c) >= 3 and c[0] == "gate" and c[2]:
                try:
                    pats.append(re.compile(c[2], re.I))
                except re.error:
                    pass
    except OSError:
        pass
    if not pats:
        sys.exit(f"🛑 cartero: sin patrones anti-fuga ({SANEADO}) — no muevo NADA a ciegas")
    return pats


def cabeceras(texto):
    para, asunto = "", ""
    for ln in texto.splitlines()[:6]:
        m = re.match(r"\s*PARA:\s*(.+)", ln, re.I)
        if m:
            para = m.group(1).strip()
        m = re.match(r"\s*ASUNTO:\s*(.+)", ln, re.I)
        if m:
            asunto = m.group(1).strip()
    return para, asunto


def main():
    if os.environ.get("CARTERO", "1") != "1":
        log("CARTERO=0 → apagado, no proceso nada")
        return
    conocidos = roles_conocidos()
    fugas = patrones_fuga()
    total = 0
    enviadas_por = {}                                       # 🪶 la cuota: cuántas internas lleva cada origen
    for rol in sorted(os.listdir(BUZONES)) if os.path.isdir(BUZONES) else []:
        salida = os.path.join(BUZONES, rol, "salida")
        if rol.startswith("_") or not os.path.isdir(salida):
            continue
        for f in sorted(os.listdir(salida)):
            if not (f.startswith("carta_") and f.endswith(".txt")):
                continue                                    # reruta_* es del estafeta; no lo toco
            total += 1
            ruta = os.path.join(salida, f)
            try:
                texto = open(ruta, encoding="utf-8", errors="replace").read()
            except OSError as e:
                log(f"⚠️ ilegible {rol}/salida/{f}: {e}")
                continue
            para, asunto = cabeceras(texto)
            sello_id = f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{rol}_{f}"
            if not para:
                log(f"⚠️ {rol}/salida/{f}: sin cabecera PARA: — la dejo donde está (que el rol la corrija)")
                continue
            # ── 1) INTERNO: destinatario conocido → su buzón de entrada (PLUMA-CON-CUOTA) ──
            if para in conocidos:
                enviadas_por[rol] = enviadas_por.get(rol, 0) + 1
                n = enviadas_por[rol]
                # 🚨 TRIPWIRE: un origen que revienta N× su cuota huele a coordinación/spam →
                #    la carta NO se entrega en pluma: se RETIENE para sello-auditor (excepción sellada).
                if n > CUOTA_INTERNA * TRIPWIRE_X:
                    destino_d = os.path.join(PENDIENTE, "tripwire")
                    log(f"🚨 TRIPWIRE {rol}→{para}: {n} internas (>{CUOTA_INTERNA}×{TRIPWIRE_X}) → a sello-auditor")
                    if APLICAR:
                        os.makedirs(destino_d, exist_ok=True)
                        shutil.move(ruta, os.path.join(destino_d, f"tripwire_{sello_id}"))
                        anotar("cartero_tripwire", origen=rol, destino=para, n=n, fichero=f)
                    continue
                # 🪶 CUOTA: pasada la cuota, la carta ESPERA a la próxima corrida (no se pierde,
                #    no se entrega: el rate-limit acota el caudal sin sellar cada mensaje).
                if n > CUOTA_INTERNA:
                    log(f"🪶 cuota {rol}: {n}>{CUOTA_INTERNA} internas — «{asunto or f}» ESPERA a la próxima corrida")
                    anotar("cartero_cuota_diferida", origen=rol, destino=para, n=n, fichero=f)
                    continue
                destino_d = os.path.join(BUZONES, para, "entrada")
                destino = os.path.join(destino_d, f"interior_{sello_id}")
                log(f"📬 interno {rol} → {para} ({n}/{CUOTA_INTERNA}): «{asunto or f}»" + ("" if APLICAR else "  [dry]"))
                if APLICAR:
                    os.makedirs(destino_d, exist_ok=True)
                    etiqueta = (f"[PROCEDENCIA: INTERIOR — de {rol} · {datetime.datetime.now():%Y-%m-%d %H:%M}]\n"
                                f"DE: {rol}\nASUNTO: {asunto or '(sin asunto)'}\n\n")
                    open(destino, "w", encoding="utf-8").write(etiqueta + texto)
                    os.remove(ruta)
                    anotar("cartero_entrega_interna", origen=rol, destino=para, asunto=asunto, fichero=f, cuota=f"{n}/{CUOTA_INTERNA}")
                continue
            # ── 3) filtro de FUGAS — SOLO en la frontera (lo interno se queda en casa y
            #    menciona IPs/hosts propios con toda legitimidad; la exfiltración es lo
            #    que se caza: un secreto de la casa JAMÁS cruza hacia fuera, ni por error) ──
            toca = [p.pattern[:40] for p in fugas if p.search(texto)]
            if toca:
                destino = os.path.join(RETENIDAS, sello_id)
                log(f"🛑 RETENIDA {rol}/salida/{f} (externa → «{para}») → patrón sensible ({len(toca)}): {toca[0]}…")
                if APLICAR:
                    os.makedirs(RETENIDAS, exist_ok=True)
                    shutil.move(ruta, destino)
                    anotar("cartero_retenida", origen=rol, para=para, fichero=f, motivo=toca[:3])
                continue
            # ── 2) EXTERNO: JAMÁS enviar — a la bandeja del humano con su metadato ──
            destino = os.path.join(PENDIENTE, f"externa_{sello_id}")
            log(f"🕊️ externa {rol} → «{para}»: RETENIDA en salida_pendiente/ (el envío es gesto humano"
                + (", nivel 5)" if "@" in para or re.search(r"\+?\d{9,}", para) else " — destino desconocido)")
                + ("" if APLICAR else "  [dry]"))
            if APLICAR:
                os.makedirs(PENDIENTE, exist_ok=True)
                meta = (f"[SALIDA EXTERNA — esperando DOBLE SELLO + envío humano · de {rol} · "
                        f"{datetime.datetime.now():%Y-%m-%d %H:%M}]\nPARA: {para}\nASUNTO: {asunto or '(sin asunto)'}\n\n")
                open(destino, "w", encoding="utf-8").write(meta + texto)
                os.remove(ruta)
                anotar("cartero_pendiente_externa", origen=rol, para=para, asunto=asunto, fichero=f)
    log(f"{'procesadas' if APLICAR else 'plan (dry — nada movido)'}: {total} carta(s)"
        + ("" if total else " — ninguna carta_*.txt en los buzones de salida"))


if __name__ == "__main__":
    main()
