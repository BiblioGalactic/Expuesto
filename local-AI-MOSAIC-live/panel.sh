#!/bin/bash
# 📊 =====================================================================
# 📊 PANEL — metaresultados unificados de MOSAIC (un único sitio donde mirar)
# 📊 Junta: estado (cluster/mini/vigía/cola), tiempos reales por petición,
# 📊 tiempo estimado para 100, tendencia de nota por ciclos, huecos y
# 📊 capacidades. Escribe data/META.md y lo imprime.   Uso: ./panel.sh
# 📊 =====================================================================
set -euo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="$HOME_USER/Mosaic_privado"
DATA="$MOSAIC_DIR/data"
META="$DATA/META.md"
CLUSTER_URL="${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8090/v1}"
MINI="${MINI_URL:-http://localhost:8090/v1}"
mkdir -p "$DATA"

ping_srv() { curl -s -m 3 "$1/models" >/dev/null 2>&1 && echo "🟢 arriba" || echo "🔴 caído"; }
CL="$(ping_srv "$CLUSTER_URL")"; MI="$(ping_srv "$MINI")"
VIG="🟢 normal"; [ -f "$DATA/pausa.flag" ] && VIG="⏸️ PAUSA: $(cat "$DATA/pausa.flag" 2>/dev/null)"
COLA_P="$(bash "$MOSAIC_DIR/cola.sh" size 2>/dev/null || echo 0)"; COLA_P="${COLA_P:-0}"
COLA_H="$(bash "$MOSAIC_DIR/cola.sh" hechas 2>/dev/null || echo 0)"; COLA_H="${COLA_H:-0}"

python3 - "$DATA" "$META" "$MOSAIC_DIR" "$CL" "$MI" "$VIG" "${COLA_P:-0}" "${COLA_H:-0}" <<'PY'
import json, os, sys, time, csv
from collections import Counter
DATA, META, MOSAIC_DIR, CL, MI, VIG, COLA_P, COLA_H = sys.argv[1:9]

def jsonl(p):
    out=[]
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln=ln.strip()
            if ln:
                try: out.append(json.loads(ln))
                except Exception: pass
    return out

recs = jsonl(os.path.join(DATA, "historial.consolidado.jsonl"))   # procesadas + juzgadas (histórico)
pend = jsonl(os.path.join(DATA, "historial.jsonl"))               # aún sin consolidar
n = len(recs)
lat = [r["metrics"]["latency_s"] for r in recs
       if isinstance((r.get("metrics") or {}).get("latency_s"), (int, float)) and r["metrics"]["latency_s"] > 0]
ctok = []
for r in recs:
    u = (r.get("metrics") or {}).get("usage") or {}
    t = u.get("completion_tokens") or u.get("total_tokens")
    if isinstance(t, (int, float)) and t > 0: ctok.append(t)
err = sum(1 for r in recs if r.get("error"))
fuentes = Counter((r.get("fuente") or "?") for r in recs)

def cola_fuentes(db):                                 # observabilidad por fuente, en vivo (#70)
    try:
        import sqlite3
        return sqlite3.connect(db).execute(
            "SELECT COALESCE(fuente,'?'), SUM(estado=0), SUM(estado=2) FROM cola "
            "GROUP BY fuente ORDER BY 3 DESC, 2 DESC").fetchall()
    except Exception:
        return []
colf = cola_fuentes(os.path.join(DATA, "cola.db"))

filas = []
prog = os.path.join(DATA, "progreso.csv")
if os.path.exists(prog):
    with open(prog) as f:
        try: filas = list(csv.DictReader(f))
        except Exception: filas = []

def cnt_json(p):
    try: return len(json.load(open(p)))
    except Exception: return 0
def cnt_yaml(p, key):
    try:
        import yaml; return len((yaml.safe_load(open(p)) or {}).get(key, []))
    except Exception: return 0
huecos = cnt_json(os.path.join(DATA, "huecos.consolidado.json"))
caps_gen = cnt_yaml(os.path.join(MOSAIC_DIR, "capabilities", "auto_generadas.yaml"), "capabilities")
caps_rej = cnt_yaml(os.path.join(MOSAIC_DIR, "capabilities", "auto_rechazadas.yaml"), "rechazadas")

avg = lambda xs: (sum(xs) / len(xs)) if xs else 0.0
lat_avg, tok_avg = avg(lat), avg(ctok)
tps = (tok_avg / lat_avg) if lat_avg else 0.0
t100 = lat_avg * 100

L = ["# META — panel unificado de MOSAIC", f"_generado {time.strftime('%Y-%m-%d %H:%M:%S')}_\n",
     "## Estado ahora",
     f"- Cluster principal (MacBook, Qwen3-14B@8092): {CL}",
     f"- Mac mini (juez + ligeras): {MI}",
     f"- Vigía (salud MacBook): {VIG}",
     f"- Cola: {COLA_P} pendientes · {COLA_H} hechas\n",
     "## Procesamiento (histórico consolidado)"]
if n:
    L.append(f"- Peticiones procesadas y juzgadas: **{n}**" + (f"  ·  pendientes: {len(pend)}" if pend else ""))
    L.append(f"- Errores de ejecución: {err}/{n} ({100*err/n:.0f}%)")
    if lat:
        L.append(f"- ⏱️ Tiempo medio por petición: **{lat_avg:.1f} s**  (medido en {len(lat)})")
        L.append(f"- ⏱️ Estimado para **100 peticiones**: **{t100/60:.0f} min**  ({t100:.0f} s)")
    if ctok:
        L.append(f"- Tokens de salida medios: {tok_avg:.0f}  ·  velocidad ≈ {tps:.1f} tok/s")
    if fuentes:
        L += ["\n### Por fuente (qué modelo generó la pregunta)", "| Fuente | Procesadas |", "|---|---|"]
        L += [f"| {k} | {v} |" for k, v in fuentes.most_common()]
else:
    L.append("- (aún no hay nada consolidado; usa el bucle o `./aprender.sh consolidar`)")

if colf:
    L += ["\n## Cola por fuente (en vivo)", "| Fuente | Pendientes | Hechas |", "|---|---|---|"]
    L += [f"| {f} | {p or 0} | {h or 0} |" for f, p, h in colf]

if filas:
    L += ["\n## Evolución por ciclos (progreso.csv)", "| Ciclo | Nota media | Carpeta |", "|---|---|---|"]
    for r in filas[-12:]:
        L.append(f"| {r.get('ciclo','?')} | {r.get('nota_media','?')} | {r.get('carpeta','')} |")
    notas = []
    for r in filas:
        v = (r.get("nota_media") or "").strip()
        try: notas.append(float(v))
        except Exception: pass
    if len(notas) >= 2:
        d = notas[-1] - notas[0]
        flecha = "📈 subiendo" if d > 0.05 else ("📉 bajando" if d < -0.05 else "➡️ estable")
        L.append(f"\n- **Tendencia de nota:** {notas[0]:.2f} → {notas[-1]:.2f}  ({flecha}, {len(notas)} ciclos)")
    L.append("\n## ¿Suficiente? (criterio de parada)")
    if len(notas) < 5:
        L.append(f"- 🔴 Muy pronto ({len(notas)} ciclos): aún no se puede hablar de madurez (apunta a ≥10).")
    else:
        rec = notas[-5:]; banda = max(rec) - min(rec); subida = notas[-1] - notas[-5]
        meta_ok = (sum(rec) / len(rec)) >= float(os.getenv("MOSAIC_META_NOTA", "4.0"))
        if subida > 0.1:
            L.append(f"- 🟡 Progresando: la nota sube (+{subida:.2f} en 5 ciclos). Sigue alimentándolo.")
        elif banda <= 0.08 and meta_ok:
            L.append(f"- 🟢 Maduro: nota estable y alta (±{banda:.2f}, media≥4). Más datos rinden poco; puedes espaciar/parar.")
        elif banda <= 0.08:
            L.append(f"- 🟢 En meseta (±{banda:.2f}) pero por debajo de la meta de nota. Toca mejorar capacidades, no meter más datos.")
        else:
            L.append(f"- 🟡 Inestable: la nota oscila ±{banda:.2f}. Deja correr más para ver si asienta.")
    L.append("- 'Ya está' = nota en meseta alta + pocos huecos nuevos + la composición gana al crudo (A/B).")

L += ["\n## Librería que evoluciona",
      f"- Huecos detectados (histórico): {huecos}",
      f"- Capacidades auto-generadas: {caps_gen}  ·  descartadas por curación: {caps_rej}",
      "\n_Cómo leerlo: no mires un número suelto, mira la **tendencia** sobre muchos ciclos._"]

open(META, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
PY
echo
echo "📄 Guardado en: $META"
