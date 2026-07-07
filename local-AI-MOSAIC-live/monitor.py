#!/usr/bin/env python3
# 🖥️ =====================================================================
# 🖥️ MONITOR — Consola de Operaciones Epistolar (RONDA 2 · esqueleto TUI).
# 🖥️   Zona A (izq. 70%): visor Markdown — debrief del ciclo o cola de CARTAS.
# 🖥️   Zona B (der. 30%): dashboard en vivo de data/estado_sistema.json.
# 🖥️   Footer: [D]ebrief · [C]artas · [V]ivo · [R]eportar · [A]rchivar · [L]anzar ·
# 🖥️           [S] compartir (packs por ADUANA) · [E] empleados (plantilla de agentes) · [Q] salir.
# 🖥️ El VISOR solo lee; las acciones escriben SIEMPRE por sus motores (reportar/archivado/
# 🖥️ empaquetar/importar.sh), jamás a mano desde aquí.
# 🖥️ Refresco REACTIVO barato: un stat/s por fichero (mtime); re-render solo si cambió.
# 🖥️ Requiere: pip install textual   (dependencia de TOOLING humano, bendecida en Ronda 2)
# 🖥️ Uso:  ./monitor.py     (q para salir · Ctrl+C también vale)
# 🖥️ =====================================================================
import json
import os
import subprocess          # [G] topología (gateway) — antes solo se importaba local en cada acción
import sys
import time

BASE = os.environ.get("MOSAIC_BASE", os.path.dirname(os.path.abspath(__file__)))

# 🖥️ MODO de la TUI (debate Sombra 11:32 · «una TUI, dos caras» — opción d/c): en el mini,
#    arranca en modo WORKER = solo-lo-suyo y READ-ONLY (línea roja #4: el mini JAMÁS escribe
#    en el epistolar — se deposita siempre en el cerebro, el MacBook). Detección por hostname
#    (decisión #5, mi voto: hostname con override por env). NO decide worker-vs-instancia (#1,
#    de Gustavo): es el suelo seguro común a ambas ramas — nace conservador.
def _detectar_modo():
    m = os.environ.get("MOSAIC_TUI_MODO", "").strip().lower()
    if m in ("mini", "macbook"):
        return m
    try:
        import socket
        h = socket.gethostname().lower()
    except Exception:                                      # noqa: BLE001
        h = ""
    return "mini" if ("mac-mini" in h or "macmini" in h or "mac mini" in h) else "macbook"


TUI_MODO = _detectar_modo()
ES_MINI = TUI_MODO == "mini"

ESTADO = os.path.join(BASE, "data", "estado_sistema.json")
DEBRIEF_MD = os.path.join(BASE, "data", "debrief_ultimo.md")
CARTAS = os.path.join(BASE, "info", "CARTAS.md")
CICLO_LOG = os.path.join(BASE, "logs", "ciclo_vivo.log")   # lo escribe mosaic.sh ciclo (script -q)
REPORTAR = os.path.join(BASE, "reportar.sh")               # R3: EL escritor seguro del epistolar
ARCHIVADO = os.path.join(BASE, "archivado.sh")             # R4: la rotación del epistolar (motor de Opus)
MOSAIC_SH = os.path.join(BASE, "mosaic.sh")                # R4-L: el motor (ya existe; el menú solo lo invoca)
AUTODIAGNOSIS = os.path.join(BASE, "autodiagnosis.sh")     # el TURNO de MOSAIC (propone-texto, permiso acotado)
TURNO_ROL = os.path.join(BASE, "turno_rol.sh")             # el motor de sillas (orquesta 5-jul)
PLENO_SH = os.path.join(BASE, "pleno.sh")                  # la orquesta entera de una orden
TURNOS_DIR = os.path.join(BASE, "roles", "turnos")         # los yamls = LA fuente de agentes ([E])
EMPAQUETAR = os.path.join(BASE, "empaquetar.sh")           # [S]: exporta la máscara (curada+saneada) a packs/
IMPORTAR = os.path.join(BASE, "importar.sh")               # [S]: recibe un pack ajeno (ADUANA defensa.py)
ESCALACIONES = os.path.join(BASE, "data", "escalaciones.json")          # [T]: el libro de escalado (Opus 13:56)
ESC_ARCHIVO = os.path.join(BASE, "data", "escalaciones_archivo.jsonl")  # lo caducado/viejo duerme aquí
CALENDARIO_DIR = os.environ.get("CALENDARIO_DIR",          # [A]💬: la agenda PRIVADA de Gustavo (F1 firmada
                                os.path.expanduser("~/proyecto/calendario_mental"))  # por Opus 21:45 — SOLO índice)
FICHA_SH = os.path.join(BASE, "ficha.sh")                  # [P]: la ficha DERIVADA (motor de Opus — solo se invoca)
BAUTIZAR_SH = os.path.join(BASE, "bautizar.sh")            # [P]: 🎲 nombres humanos (motor de Opus)
FICHAS_MD = os.path.join(BASE, "data", "fichas_ultimo.md")  # [P]: las fichas renderizadas para el visor
SERVIDORES = os.path.join(BASE, "servidores.conf")        # roster para el selector de modelo (no hardcodear)
GATEWAY = os.path.join(BASE, "gateway.py")                 # [G] fusión intención+router+flota (topología)
LANZADOR_PID = os.path.join(BASE, "data", ".lanzador.pid")  # guard de UN lanzamiento a la vez
LANZAR_CLUSTER = os.environ.get("LLAMA_LAUNCH",             # [Q]: el apagado ordenado YA existe — se reusa
                                os.path.expanduser("~/cluster/lanzar_cluster.sh"))
CARTAS_MAX_KB = int(os.environ.get("CARTAS_MAX_KB", "450"))  # mismo umbral que archivado.sh

# nombre legible del modelo desde su ruta gguf (para el selector — sin inventar, del fichero)
def _nombre_modelo(ruta):
    base = os.path.basename(ruta).replace("*", "").replace(".gguf", "")
    for tok in ("Qwen3-14B", "Unholy-v2-13B", "qwen2.5-coder-14b", "DeepSeek-R1"):
        if tok.lower() in base.lower():
            return tok
    return base[:24] or "modelo"


def _roster_base():
    """Candidatos a modelo BASE de la máscara: LEÍDOS de servidores.conf — macbook·fijo, sin el
    juez pequeño del mini y (⚔️) SIN el 24B jamás. Devuelve [(etiqueta, endpoint, modelo)]."""
    out = []
    try:
        for ln in open(SERVIDORES, encoding="utf-8"):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            p = ln.split("|")
            if len(p) < 5 or p[0] != "macbook" or p[3] != "fijo":
                continue
            if "juez" in p[2].lower() or "24b" in ln.lower():
                continue
            puerto, rol, ruta = p[1], p[2], p[4]
            nom = _nombre_modelo(ruta)
            out.append((f"{nom} · {rol} (@{puerto})", f"http://127.0.0.1:{puerto}/v1", nom))
    except OSError:
        pass
    return out or [("Qwen3-14B · principal (@8092)", "http://127.0.0.1:8092/v1", "qwen3-14b")]


def _dominios():
    """Dominios exportables LEÍDOS de capabilities/ (stems de fichero válidos) — sin hardcodear.
    Los importado_* se filtran del radio (re-compartir lo ajeno se teclea a mano, a conciencia)."""
    out = []
    try:
        for nom in sorted(os.listdir(os.path.join(BASE, "capabilities"))):
            if not (nom.endswith(".yaml") or nom.endswith(".yml")):
                continue
            stem = nom.rsplit(".", 1)[0]
            if stem.startswith("importado_") or not all(ch.isalnum() or ch in "_-" for ch in stem):
                continue
            out.append(stem)
    except OSError:
        pass
    return out


def _turnos_roles():
    """Las sillas registradas (roles/turnos/*.yaml — LA fuente única de agentes, sin
    agentes.json paralelo: doctrina firmada por Opus). Devuelve lista de dicts con
    rol · firma · tipo · activo · cadencia · departamento · nivel."""
    out = []
    try:
        import yaml
        for nom in sorted(os.listdir(TURNOS_DIR)):
            if not nom.endswith(".yaml"):
                continue
            try:
                y = yaml.safe_load(open(os.path.join(TURNOS_DIR, nom), encoding="utf-8")) or {}
            except Exception:                              # noqa: BLE001 — un yaml roto no tumba la lista
                continue
            rol = str(y.get("rol", nom[:-5]))
            out.append({"rol": rol, "firma": str(y.get("firma", f"MOSAIC-{rol}")),
                        "tipo": str(y.get("tipo_reporte", "Informe")),
                        "activo": bool(y.get("activo", 1)),
                        "cadencia": int(y.get("cadencia_s", 0) or 0),
                        "departamento": str(y.get("departamento", "sin-departamento")),
                        "nivel": str(y.get("nivel", "N2")),
                        "nivel_acceso": int(y.get("nivel_acceso", 1) or 1)})
    except Exception:                                      # noqa: BLE001 — sin yaml/sin dir → sin sillas
        pass
    return out
CARTAS_COLA_BYTES = 30000        # del epistolar solo la COLA (6000+ líneas enteras = visor lento)
CICLO_TAIL_BYTES = 8000          # al abrir: la cola reciente del log; luego, incremental

try:
    from rich.text import Text
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import (Button, Checkbox, Footer, Header, Input, Label, Markdown,
                                 RadioButton, RadioSet, RichLog, Static, TextArea)
except ImportError:
    sys.stderr.write(
        "🖥️  monitor: falta Textual (la única pieza externa de la consola).\n"
        "    Instálala en tu venv:  pip install textual\n"
        "    (o source ~/wikirag/venv/bin/activate && pip install textual)\n")
    sys.exit(1)

COLOR = {"verde": "green", "amarillo": "yellow", "rojo": "red"}
MARCA = {"ok": "[green]✓[/]", "incidencia": "[red]✗[/]",
         "no_alcanzada": "[yellow]⊘[/]", "sin_rastro": "[dim]·[/]"}


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _leer_md(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return f"*(aún no existe `{os.path.basename(path)}` — corre `./mosaic.sh ciclo` o `./debrief.sh`)*"


def _leer_cartas_cola(path):
    try:
        tam = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, tam - CARTAS_COLA_BYTES))
            texto = f.read().decode("utf-8", errors="ignore")
        # arranca en la primera cabecera completa para no partir una carta a la mitad
        corte = texto.find("\n## ")
        if corte > 0:
            texto = texto[corte + 1:]
        return f"*(cola del epistolar — las últimas cartas de {tam // 1024} KB totales)*\n\n" + texto
    except OSError:
        return "*(sin CARTAS.md a la vista)*"


_SPARK_CACHE = {"clave": None, "serie": []}


def _spark(vals, ancho=36):
    """▁▂▃▄▅▆▇█ — la foto hecha PELÍCULA (auditoría TUI 10:47, probada sobre los 36 CRAG).
    Pura y testeable; normaliza al min-max de la serie; vacío = vacío (nada se inventa)."""
    vs = [v for v in vals if isinstance(v, (int, float))][-ancho:]
    if not vs:
        return ""
    lo, hi = min(vs), max(vs)
    bloques = "▁▂▃▄▅▆▇█"
    if hi - lo < 1e-9:
        return bloques[3] * len(vs)
    return "".join(bloques[min(7, int((v - lo) / (hi - lo) * 7.999))] for v in vs)


def _serie_crag():
    """Los CRAG de todas las actas, CACHEADOS por (nº, mtime del último) — releer 36 json
    cada segundo sería caro; mitigación declarada en la auditoría."""
    import glob as _g
    try:
        actas = sorted(_g.glob(os.path.join(BASE, "data", "actas", "acta_*.json")))
        if not actas:
            return []
        clave = (len(actas), os.path.getmtime(actas[-1]))
        if _SPARK_CACHE["clave"] == clave:
            return _SPARK_CACHE["serie"]
        serie = []
        for p in actas:
            try:
                serie.append((json.load(open(p, encoding="utf-8")).get("tanda_resumen") or {})
                             .get("crag_medio"))
            except (OSError, ValueError):
                continue
        _SPARK_CACHE.update(clave=clave, serie=serie)
        return serie
    except OSError:
        return []


def _canales_ingesta(n=4):
    """El panel RX del mockup, HONESTO: la cola pendiente POR FUENTE (cola.db, solo-lectura)."""
    try:
        import sqlite3
        db = sqlite3.connect(f"file:{os.path.join(BASE, 'data', 'cola.db')}?mode=ro", uri=True)
        filas = db.execute("SELECT fuente, COUNT(*) FROM cola WHERE estado=0 "
                           "GROUP BY fuente ORDER BY 2 DESC").fetchall()
        db.close()
        tot = sum(c for _, c in filas) or 1
        return [(str(f or "?")[:14], c, c / tot) for f, c in filas[:n]]
    except Exception:                                      # noqa: BLE001
        return []


def _dignidad_lentes(n=4):
    """Salud del blue team (dignidad_modelos.json) — hoy solo visible abriendo cartas."""
    try:
        d = json.load(open(os.path.join(BASE, "data", "dignidad_modelos.json"), encoding="utf-8")) or {}
        filas = [(k.split("|")[0][:12], float(v["dignidad"]))
                 for k, v in d.items() if isinstance(v, dict) and "dignidad" in v]
        filas.sort(key=lambda x: x[1])
        return filas[:n]
    except Exception:                                      # noqa: BLE001
        return []


def _modelos_mini():
    """Los modelos del MINI declarados en servidores.conf (su parte del hierro — sin red)."""
    filas = []
    try:
        for ln in open(os.path.join(BASE, "servidores.conf"), encoding="utf-8"):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            c = ln.split("|")
            if len(c) >= 5 and c[0] == "mini":
                nom = c[4].split("/")[-1].replace("*", "").replace(".gguf", "")[:26]
                filas.append((c[1], c[2][:20], c[3], nom))
    except OSError:
        pass
    return filas


def _dashboard_mini():
    """🖥️ La cara-MINI (Sombra opción c): solo LO SUYO, read-only. Su hierro, sus modelos,
    la dignidad de las lentes que hospeda, la salud del enlace. JAMÁS el epistolar del cerebro
    (eso vive en el MacBook). Todo de ficheros locales — cero escritura, cero SSH desde aquí."""
    L = ["[bold yellow]🖥️ MODO MINI · worker (solo-lectura)[/]",
         "[dim]el cerebro documental es el MacBook · desde aquí NO se escribe[/dim]", ""]
    L.append("[bold]┌─ mi hierro ─┐[/] [dim]Mac mini · 16GB[/]")
    modelos = _modelos_mini()
    if modelos:
        L.append("[bold]┌─ mis modelos ─┐[/] [dim](servidores.conf)[/]")
        for pto, rol, modo, nom in modelos:
            mc = "green" if modo == "fijo" else "cyan"
            L.append(f" [{mc}]@{pto}[/] {rol} [dim]{modo}[/] · {nom}")
    lentes = _dignidad_lentes(6)
    if lentes:
        L += ["", "[bold]┌─ dignidad (lo que juzgo aquí) ─┐[/]"]
        for nom, dig in lentes:
            ll = max(0, min(8, round(8 * dig)))
            lc = "green" if dig >= 0.7 else "yellow" if dig >= 0.3 else "red"
            L.append(f" [{lc}]{'█' * ll}{'░' * (8 - ll)}[/] {nom} {dig:.2f}")
    L += ["", "[bold]┌─ enlace con el cerebro ─┐[/]",
          " [dim]estado del epistolar/sellos/actas: en el MacBook.[/dim]",
          " [dim]recoger lo mío: recoger_del_mini.sh (rsync, desde el cerebro).[/dim]"]
    L += ["", "[dim]teclas de escritura ([R][A][O][L]…) DESACTIVADAS en modo mini.",
          "solo lectura: [C]artas·[G]mapa·[A]genda·[T]ickets. · [Q] salir[/dim]"]
    return "\n".join(L)


def _dashboard(path):
    """El estado del sistema como markup de Rich — colores intuitivos (regla de Gustavo)."""
    if ES_MINI:
        return _dashboard_mini()
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return "[dim]sin estado_sistema.json todavía\n(corre ./debrief.sh o un ciclo)[/]"
    g = d.get("estado_general", "?")
    c = COLOR.get(g, "white")
    edad = int(time.time()) - int(d.get("generado_ts", 0) or 0)
    edad_txt = f"{edad}s" if edad < 120 else f"{edad // 60}min"
    L = [f"[bold {c}]● {g.upper()}[/]  [dim](hace {edad_txt} · {d.get('modo','?')})[/]",
         f"[dim]{d.get('acta','')}[/]", ""]
    L.append("[bold]fases[/]")
    for f_ in d.get("fases", []):
        L.append(f" {MARCA.get(f_.get('estado'), '·')} {f_.get('id')} {f_.get('nombre','')}")
    m = d.get("metricas", {})
    delta = m.get("crag_delta")
    flecha = "[green]↑[/]" if (delta or 0) > 0 else "[red]↓[/]" if (delta or 0) < 0 else "="
    L += ["", "[bold]┌─ métricas ─┐[/] [dim](espejo del acta)[/]",
          f" CRAG [bold]{m.get('crag','?')}[/] {flecha}{abs(delta) if delta else ''}"]
    serie = _serie_crag()
    if serie:                                              # 🎞️ la meseta EN UNA LÍNEA (mejora A)
        L.append(f" [cyan]{_spark(serie)}[/] [dim]{len([v for v in serie if v is not None])} actas[/]")
    L += [f" resueltos {m.get('resueltos','?')}/{m.get('ejecuciones','?')} · A/B "
          f"{(m.get('ab') or {}).get('a','?')}-{(m.get('ab') or {}).get('b','?')}-{(m.get('ab') or {}).get('empates','?')}",
          f" huecos +{m.get('huecos_nuevos','?')} ({m.get('huecos_total','?')} hist)"]
    canales = _canales_ingesta()
    if canales:                                            # 📡 mejora B: los canales RX, honestos
        L += ["", "[bold]┌─ canales de ingesta ─┐[/]"]
        for fte, cnt, frac in canales:
            ll = max(0, min(8, round(8 * frac)))
            L.append(f" [yellow]{'█' * ll}{'░' * (8 - ll)}[/] {fte} {cnt}")
    lentes = _dignidad_lentes()
    if lentes:                                             # 🛡️ mejora C: salud del blue team
        L += ["", "[bold]┌─ blue team ─┐[/] [dim](dignidad)[/]"]
        for nom, dig in lentes:
            ll = max(0, min(8, round(8 * dig)))
            lc = "green" if dig >= 0.7 else "yellow" if dig >= 0.3 else "red"
            L.append(f" [{lc}]{'█' * ll}{'░' * (8 - ll)}[/] {nom} {dig:.2f}")
    b = d.get("banco", {})
    pend, tope = int(b.get("pendientes", 0) or 0), int(b.get("tope", 60) or 60)
    lleno = max(0, min(10, round(10 * pend / tope))) if tope else 0
    barra = "█" * lleno + "░" * (10 - lleno)
    bcolor = "green" if pend >= 20 else "yellow" if pend >= 10 else "red"
    L += ["", f"[bold]banco[/] [{bcolor}]{barra}[/] {pend}/{tope}"]
    L += [f" [dim]{k} {v}[/]" for k, v in (b.get("fuentes") or {}).items()]
    L.append(f" [dim]fábrica saltada {b.get('fabrica_saltos_seguidos', 0)}×[/]")
    s = d.get("salud", {})
    L += ["", "[bold]salud[/]",
          f" bucle acta→gob {'[green]✓[/]' if s.get('bucle_acta_gobernador') else '[red]✗[/]'}",
          f" fail-closed    {'[green]✓[/]' if s.get('fail_closed') else '[red]✗ SIN CANDADO[/]'}"]
    L += ["", "[bold]subsistemas[/]"]
    for sub in d.get("subsistemas", []):
        e = sub.get("estado", "?")
        sc = "green" if e in ("ok", "on") else "dim" if e == "off" else "red"
        L.append(f" [{sc}]{e:>3}[/] {sub.get('id')}")
    fl = d.get("flags", {})
    L += ["", "[bold]flags[/] [dim]" + " ".join(f"{k}={v}" for k, v in fl.items()) + "[/]"]
    incs = d.get("incidencias", [])
    if incs:
        L += ["", "[bold red]incidencias[/]"] + [f" [red]⚠ {i.get('texto','')[:46]}[/]" for i in incs]
    reps = d.get("ultimos_reportes", [])
    if reps:
        L += ["", "[bold]última carta[/]", f" [dim]{reps[-1].get('cabecera','')[:48]}[/]"]
    # R4 · alarma del peso del epistolar (recomendación del Nuevo): que Gustavo no tenga que acordarse
    try:
        kb = os.path.getsize(CARTAS) // 1024
        if kb > CARTAS_MAX_KB:
            L += ["", f"[bold red]⚠ CARTAS {kb}KB > {CARTAS_MAX_KB}KB — toca archivar: pulsa [A][/]"]
        else:
            L += ["", f"[dim]CARTAS {kb}KB (umbral {CARTAS_MAX_KB}KB)[/]"]
    except OSError:
        pass
    return "\n".join(L)


class PantallaReporte(ModalScreen):
    """R3 · el formulario [R]: Tipo · Título · Cuerpo · Etiquetas → reportar.sh (lock+append)."""

    CSS = """
    PantallaReporte { align: center middle; }
    #caja { width: 76; height: auto; max-height: 90%; border: thick $accent;
            background: $surface; padding: 1 2; }
    #cuerpo_ta { height: 10; margin: 1 0; }
    #botones { height: auto; align-horizontal: right; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def compose(self) -> ComposeResult:
        with Vertical(id="caja"):
            yield Label("[b]📋 Nuevo reporte a la mesa[/b]  [dim](se firma y fecha solo · Esc cancela)[/dim]")
            with RadioSet(id="tipo"):
                yield RadioButton("Informe", value=True)
                yield RadioButton("Decisión")
                yield RadioButton("Incidente")
            yield Input(placeholder="Título (breve)", id="titulo")
            yield TextArea(id="cuerpo_ta")
            yield Input(placeholder="Etiquetas (opcional: panel ronda3 …)", id="etiquetas")
            with Horizontal(id="botones"):
                yield Button("Cancelar", id="cancelar")
                yield Button("Depositar en la mesa", id="guardar", variant="success")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "cancelar":
            self.dismiss(None)
            return
        tipo_rs = self.query_one("#tipo", RadioSet)
        tipo = str(tipo_rs.pressed_button.label) if tipo_rs.pressed_button else "Informe"
        titulo = self.query_one("#titulo", Input).value.strip()
        cuerpo = self.query_one("#cuerpo_ta", TextArea).text.strip()
        etiquetas = self.query_one("#etiquetas", Input).value.strip()
        if not titulo or not cuerpo:
            self.notify("Título y cuerpo son obligatorios.", severity="warning")
            return
        self.dismiss({"tipo": tipo, "titulo": titulo, "cuerpo": cuerpo, "etiquetas": etiquetas})


class PantallaArchivado(ModalScreen):
    """R4 · [A]: enseña el PLAN real (dry-run del motor de Opus) y pide confirmación.
    Devuelve 'aplicar' | 'forzar' | None. El motor guarda backup y usa el mismo cerrojo."""

    CSS = """
    PantallaArchivado { align: center middle; }
    #caja_a { width: 84; height: auto; max-height: 90%; border: thick $warning;
              background: $surface; padding: 1 2; }
    #plan { height: 14; border: solid $accent; padding: 0 1; margin: 1 0; }
    #botones_a { height: auto; align-horizontal: right; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, plan_txt: str, kb: int):
        super().__init__()
        self._plan = plan_txt
        self._kb = kb

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_a"):
            yield Label(f"[b]🗄️ Archivar el epistolar[/b]  [dim]· CARTAS pesa {self._kb}KB (umbral {CARTAS_MAX_KB}KB) · Esc = atrás[/dim]")
            with VerticalScroll(id="plan"):
                yield Static(self._plan or "(el motor no devolvió plan)")
            yield Label("[dim]Backup automático a trash/backups · lo viejo → info/historico/ · mismo cerrojo que [R][/dim]")
            with Horizontal(id="botones_a"):
                yield Button("Cancelar", id="a_cancelar")
                yield Button("Forzar (sin criterio)", id="a_forzar", variant="error")
                yield Button("Archivar", id="a_aplicar", variant="warning")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "a_aplicar":
            self.dismiss("aplicar")
        elif ev.button.id == "a_forzar":
            self.dismiss("forzar")
        else:
            self.dismiss(None)


class PantallaLanzar(ModalScreen):
    """R4 · [L]: el PUENTE DE MANDO. Rama A = lanzar un modo de mosaic.sh (ciclo/aprender/…)
    con flags; Rama B = la MÁSCARA de competencia sobre el modelo que elijas, a una consulta.
    Devuelve dict con la orden, o None. El lanzamiento real (Popen) lo hace la App."""

    CSS = """
    PantallaLanzar { align: center middle; }
    #caja_l { width: 88; height: auto; max-height: 92%; border: thick $success;
              background: $surface; padding: 1 2; }
    #scroll_l { height: auto; max-height: 32; }
    #consulta_ta { height: 6; margin: 1 0; }
    RadioSet { height: auto; }
    #botones_l { height: auto; align-horizontal: right; margin-top: 1; }
    Button { margin-left: 2; }
    .titulo { text-style: bold; margin-top: 1; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_l"):
            yield Label("[b]🚀 Puente de mando[/b]  [dim]· lanza sin salir de la consola · Esc cancela · ⇕ scroll[/dim]")
            with VerticalScroll(id="scroll_l"):
                yield from self._formulario()
            with Horizontal(id="botones_l"):
                yield Button("Cancelar", id="l_cancelar")
                yield Button("🪑 Turno / Pleno", id="l_mosaic", variant="primary")
                yield Button("Lanzar", id="l_lanzar", variant="success")

    def _formulario(self) -> ComposeResult:
            yield Label("Rama A · lanzar un modo", classes="titulo")
            with RadioSet(id="modo"):
                yield RadioButton("Ciclo", value=True)
                yield RadioButton("Aprender")
                yield RadioButton("Consolidar")
                yield RadioButton("Generar")
            yield Input(placeholder="nº de tandas (Ciclo/Aprender · def. 1)", id="tandas", value="1")
            with Horizontal():
                yield RadioSet(
                    RadioButton("pool 4 bocas", value=True, id="w4"),
                    RadioButton("secuencial (1)"), id="workers")
                yield Input(placeholder="jueces (2)", id="jueces", value="2")
            # flags de conducta (los del spec de Opus 17:04, con SU default real — lista cerrada)
            with Horizontal():
                yield Checkbox("cascada 2º plano", value=True, id="f_cascada")
                yield Checkbox("escalada", value=True, id="f_escalada")
                yield Checkbox("pipeline auto", value=True, id="f_pipeline")
                yield Checkbox("debrief", value=True, id="f_debrief")
            with Horizontal():
                yield Checkbox("gobernador", value=True, id="f_gob")
                yield Checkbox("bajar al acabar", value=True, id="f_bajar")
                yield Checkbox("FNC firmado", value=False, id="f_fnc")
            yield Static("[dim]defaults = conducta de siempre · FNC sigue gated (A/B) · pipeline solo se APAGA[/dim]")
            yield Label("Rama B · la MÁSCARA sobre un modelo (deja la consulta vacía para usar la Rama A)", classes="titulo")
            yield TextArea(id="consulta_ta")
            yield Label("[dim]modelo base de la máscara (de servidores.conf):[/dim]")
            with RadioSet(id="modelo"):
                for i, (etq, _url, _nom) in enumerate(_roster_base()):
                    yield RadioButton(etq, value=(i == 0))
            yield Label("Rama C · 🪑 turnos de la ORQUESTA (cada silla lee SU estado y postea a la mesa)", classes="titulo")
            with RadioSet(id="turno_c"):
                yield RadioButton("portavoz (autodiagnóstico global)", value=True)
                for _s in _turnos_roles():
                    yield RadioButton(f"{_s['rol']} · {_s['firma']} · {_s['tipo']}"
                                      f"{'' if _s['activo'] else ' · INACTIVO'}")
                yield RadioButton("🏛️ PLENO — todas las sillas + portavoz")
            yield Static("[dim]palabra, jamás manos — proponen; Opus audita; tú sellas. Sus cartas, en [C].[/dim]")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def _flags(self):
        """Los flags del formulario, con validación (jueces solo dígitos>0)."""
        val = lambda sel: self.query_one(sel, Checkbox).value                       # noqa: E731
        j = self.query_one("#jueces", Input).value.strip()
        return {"cascada": val("#f_cascada"), "escalada": val("#f_escalada"),
                "pipeline": val("#f_pipeline"), "debrief": val("#f_debrief"),
                "gobernador": val("#f_gob"), "bajar": val("#f_bajar"), "fnc": val("#f_fnc"),
                "jueces": j if (j.isdigit() and j != "0") else "2"}

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "l_mosaic":                     # Rama C · turnos de la orquesta
            try:
                rs = self.query_one("#turno_c", RadioSet)
                sel = str(rs.pressed_button.label) if rs.pressed_button else "portavoz"
            except Exception:                              # noqa: BLE001
                sel = "portavoz"
            self.dismiss({"rama": "C", "turno": sel})
            return
        if ev.button.id != "l_lanzar":
            self.dismiss(None)
            return
        consulta = self.query_one("#consulta_ta", TextArea).text.strip()
        w4 = self.query_one("#workers", RadioSet).pressed_index == 0
        if consulta:                                       # Rama B — la joya: máscara sobre modelo elegido
            roster = _roster_base()
            idx = self.query_one("#modelo", RadioSet).pressed_index or 0
            _etq, url, nom = roster[idx]
            self.dismiss({"rama": "B", "consulta": consulta, "url": url, "modelo": nom,
                          "workers": 4 if w4 else 1, **self._flags()})
        else:                                              # Rama A — lanzar un modo
            modo_rs = self.query_one("#modo", RadioSet)
            modo = str(modo_rs.pressed_button.label).lower() if modo_rs.pressed_button else "ciclo"
            _t = self.query_one("#tandas", Input).value.strip(); tandas = _t if (_t.isdigit() and _t != "0") else "1"
            self.dismiss({"rama": "A", "modo": modo, "tandas": tandas,
                          "workers": 4 if w4 else 1, **self._flags()})


class PantallaPlan(ModalScreen):
    """Genérica [S]: enseña el PLAN real (dry-run del motor, solo lee) y pide confirmación
    explícita — el mismo rito del [A]. Devuelve True | None."""

    CSS = """
    PantallaPlan { align: center middle; }
    #caja_p { width: 92; height: auto; max-height: 92%; border: thick $warning;
              background: $surface; padding: 1 2; }
    #plan_p { height: 14; border: solid $accent; padding: 0 1; margin: 1 0; }
    #botones_p { height: auto; align-horizontal: right; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, titulo: str, plan_txt: str, boton: str, pie: str = ""):
        super().__init__()
        self._titulo, self._plan, self._boton, self._pie = titulo, plan_txt, boton, pie

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_p"):
            yield Label(f"[b]{self._titulo}[/b]  [dim]· Esc cancela[/dim]")
            with VerticalScroll(id="plan_p"):
                yield Static(self._plan or "(el motor no devolvió plan)")
            if self._pie:
                yield Label(f"[dim]{self._pie}[/dim]")
            with Horizontal(id="botones_p"):
                yield Button("Cancelar", id="p_cancelar")
                yield Button(self._boton, id="p_confirmar", variant="warning")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(True if ev.button.id == "p_confirmar" else None)


class PantallaCompartir(ModalScreen):
    """[S]: COMPARTIR la máscara (VISIÓN Opus 17:16). Rama E = exportar un dominio como pack
    (empaquetar.sh cura+sanea); Rama I = importar un pack ajeno (importar.sh: ADUANA defensa).
    Devuelve {'rama':'E','dominio':..} | {'rama':'I','ruta':..} | None. Los motores ya existen."""

    CSS = """
    PantallaCompartir { align: center middle; }
    #caja_s { width: 88; height: auto; max-height: 92%; border: thick $primary;
              background: $surface; padding: 1 2; }
    RadioSet { height: auto; }
    #botones_s { height: auto; align-horizontal: right; margin-top: 1; }
    Button { margin-left: 2; }
    .titulo { text-style: bold; margin-top: 1; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def compose(self) -> ComposeResult:
        doms = _dominios()
        with Vertical(id="caja_s"):
            yield Label("[b]📦 Compartir la máscara[/b]  [dim]· packs curados+saneados · Esc cancela[/dim]")
            yield Label("Rama E · EXPORTAR un dominio (de capabilities/):", classes="titulo")
            if doms:
                with RadioSet(id="dominio_rs"):
                    for i, d in enumerate(doms):
                        yield RadioButton(d, value=(i == 0))
            else:
                yield Static("[dim](sin ficheros en capabilities/)[/dim]")
            yield Input(placeholder="…u otro dominio por etiqueta/expertise (ej. python) — manda sobre el radio",
                        id="dominio_in")
            yield Label("Rama I · IMPORTAR un pack recibido (pasa la ADUANA antes de entrar):", classes="titulo")
            yield Input(placeholder="ruta al .mosaic (ej. packs/python_poc_v1.mosaic o /Users/…/recibido.mosaic)",
                        id="ruta_in")
            yield Static("[dim]el dry-run enseña el PLAN antes de tocar nada · lo ajeno JAMÁS entra sin veredicto SEGURO[/dim]")
            with Horizontal(id="botones_s"):
                yield Button("Cancelar", id="s_cancelar")
                yield Button("🛃 Importar…", id="s_importar", variant="error")
                yield Button("📦 Exportar…", id="s_exportar", variant="primary")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "s_exportar":
            dominio = self.query_one("#dominio_in", Input).value.strip()
            if not dominio:
                try:
                    rs = self.query_one("#dominio_rs", RadioSet)
                    dominio = str(rs.pressed_button.label) if rs.pressed_button else ""
                except Exception:                              # noqa: BLE001 — sin radio (capabilities/ vacío)
                    dominio = ""
            if not dominio or not all(ch.isalnum() or ch in "_-" for ch in dominio):
                self.app.notify("dominio inválido (solo letras/números/_/-)", severity="warning", timeout=6)
                return
            self.dismiss({"rama": "E", "dominio": dominio})
        elif ev.button.id == "s_importar":
            ruta = os.path.expanduser(self.query_one("#ruta_in", Input).value.strip())
            if ruta and not os.path.isabs(ruta):
                ruta = os.path.join(BASE, ruta)
            if not ruta.endswith(".mosaic") or not os.path.isfile(ruta):
                self.app.notify("eso no es un .mosaic legible — revisa la ruta", severity="warning", timeout=6)
                return
            self.dismiss({"rama": "I", "ruta": ruta})
        else:
            self.dismiss(None)


class PantallaEnviar(ModalScreen):
    """[S] post-export: el pack ya existe — ¿cómo lo compartimos? Finder (arrastrar/AirDrop)
    o Mail (borrador nuevo con el pack ADJUNTO). Devuelve 'finder' | 'mail' | None."""

    CSS = """
    PantallaEnviar { align: center middle; }
    #caja_e { width: 70; height: auto; border: thick $success; background: $surface; padding: 1 2; }
    #botones_e { height: auto; align-horizontal: right; margin-top: 1; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, nombre: str):
        super().__init__()
        self._nombre = nombre

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_e"):
            yield Label(f"[b]✅ {self._nombre} creado en packs/[/b]  [dim]· Esc = atrás[/dim]")
            yield Static("[dim]compartir = enviar ESE fichero a mano (packs/ jamás va con el repo)[/dim]")
            with Horizontal(id="botones_e"):
                yield Button("Cerrar", id="e_cerrar")
                yield Button("📂 Revelar en Finder", id="e_finder")
                yield Button("✉️ Enviar por Mail", id="e_mail", variant="success")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss({"e_finder": "finder", "e_mail": "mail"}.get(ev.button.id))


class PantallaSalir(ModalScreen):
    """[Q] inteligente (spec Opus 18:37 + matiz de Gustavo): el monitor es un VISOR — cerrarlo
    JAMÁS mata el trabajo salvo que el humano lo pida. DEFAULT = solo salir (el ciclo y la
    flota sobreviven; al reabrir, el monitor los 'reanuda' solo). Devuelve
    'solo' | 'matar' | 'bajar' | None."""

    CSS = """
    PantallaSalir { align: center middle; }
    #caja_q { width: 76; height: auto; border: thick $accent; background: $surface; padding: 1 2; }
    #botones_q { height: auto; align-horizontal: right; margin-top: 1; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, pid, flota):
        super().__init__()
        self._pid, self._flota = pid, flota

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_q"):
            yield Label("[b]🚪 Salir del monitor[/b]  [dim]· hay trabajo vivo — tú decides qué pasa con él · Esc = atrás[/dim]")
            if self._pid:
                yield Static(f"🚀 lanzamiento VIVO (PID {self._pid}) — si «solo sales», sigue y se reanuda al reabrir")
            if self._flota:
                yield Static(f"🔌 flota ARRIBA ({len(self._flota)}): " + " · ".join(self._flota[:4]))
            yield Static("[dim]el monitor es un visor: cerrar no mata nada salvo que lo pidas[/dim]")
            with Horizontal(id="botones_q"):
                yield Button("Cancelar", id="q_cancelar")
                if self._flota:
                    yield Button("Bajar flota y salir", id="q_bajar", variant="warning")
                if self._pid:
                    yield Button("Matar lanzamiento y salir", id="q_matar", variant="error")
                yield Button("Solo salir", id="q_solo", variant="success")

    def on_mount(self) -> None:
        self.query_one("#q_solo", Button).focus()          # el DEFAULT es el que preserva (Gustavo)

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss({"q_solo": "solo", "q_matar": "matar", "q_bajar": "bajar"}.get(ev.button.id))


class PantallaEmpleados(ModalScreen):
    """[E] · la PLANTILLA de agentes (idea del Nuevo, 5-jul): lista las sillas registradas
    (roles/turnos/*.yaml — fuente ÚNICA, sin agentes.json paralelo) y da de alta nuevas.
    Devuelve 'nuevo' | None."""

    CSS = """
    PantallaEmpleados { align: center middle; }
    #caja_emp { width: 96; height: auto; max-height: 92%; border: thick $primary;
                background: $surface; padding: 1 2; }
    #lista_emp { height: auto; max-height: 18; border: solid $accent; padding: 0 1; margin: 1 0; }
    #botones_emp { height: auto; align-horizontal: right; }
    #e_num { width: 8; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def _fila(self, n, s):
        ult = "nunca"
        try:
            t = int(open(os.path.join(BASE, "data", "turnos", f"{s['rol']}.ultimo")).read().split()[0])
            mins = (int(time.time()) - t) // 60
            ult = f"hace {mins}min" if mins < 120 else f"hace {mins // 60}h"
        except (OSError, ValueError, IndexError):
            pass
        estado = "[green]ACTIVO[/]" if s["activo"] else "[red]inactivo[/]"
        return (f"  [{n}] [b]{s['rol']}[/b] · {s['firma']} · {s['tipo']} · {estado} · "
                f"🔑acceso {s.get('nivel_acceso', 1)}/5 · "
                f"cad {s['cadencia'] if s['cadencia'] else 'ciclo+1h'} · último: {ult}")

    @staticmethod
    def _grupo():
        """El GRUPO (N0): empresa activa + hermanas en ~/Empresas + claim de la flota."""
        empresa = os.path.basename(BASE.rstrip("/")) or "MOSAIC"
        otras = []
        try:
            edir = os.path.expanduser("~/Empresas")
            otras = sorted(d for d in os.listdir(edir) if os.path.isdir(os.path.join(edir, d)))
        except OSError:
            pass
        try:
            duena = open(os.path.expanduser("~/.mosaic/flota_de"), encoding="utf-8").read().split()[0]
            flota = f"flota: {os.path.basename(duena)}"
        except (OSError, IndexError):
            flota = "flota: LIBRE"
        return empresa, otras, flota

    def compose(self) -> ComposeResult:
        self._indice = {}                                  # nº visible → rol (para Editar)
        empresa, otras, flota = self._grupo()
        with Vertical(id="caja_emp"):
            yield Label(f"[b]🧑‍💼 Empleados — organigrama de 3 niveles[/b]  "
                        f"[b]🏙️ Empresa: {empresa}[/b] [dim]· {flota} · Esc cierra[/dim]")
            with VerticalScroll(id="lista_emp"):
                yield Static("[b]🏙️ N0 · el GRUPO[/b] [dim](multi-empresa: motor compartido, inteligencia privada)[/dim]\n"
                             f"  🏢 activa: [b]{empresa}[/b]" +
                             (f" · hermanas: {', '.join(otras)}" if otras else " · sin hermanas aún") +
                             "\n  [dim]fundar: ./crear_empresa.sh <nombre> --aplicar · "
                             "cambiar: reabrir con MOSAIC_BASE=~/Empresas/<nombre>[/dim]")
                yield Static("[b]🏢 N1 · Dirección/Ops[/b] [dim](grandes off-loop — GESTIONAN)[/dim]\n"
                             "  👑 Gustavo · Dirección General · sello\n"
                             "  [dim]⏳ aspiracional: «El Comisario» (24B off-loop, Seguridad) — entra con tier grande-offloop[/dim]")
                sillas = _turnos_roles()
                if not sillas:
                    yield Static("[dim](sin sillas — da de alta la primera)[/dim]")
                n = 0
                for dep in sorted({s["departamento"] for s in sillas}):
                    filas = [f"[b]── {dep.upper()} ──[/b]"]
                    for niv, titulo in (("N2", "Managers/Leads 🟡"), ("N3", "Trabajadores 🟢 (parte-de-estado)")):
                        grupo = [s for s in sillas if s["departamento"] == dep and s["nivel"] == niv]
                        if grupo:
                            filas.append(f" [dim]{titulo}[/dim]")
                            for s in grupo:
                                n += 1
                                self._indice[str(n)] = s["rol"]
                                filas.append(self._fila(n, s))
                    yield Static("\n".join(filas))
            yield Static("[dim]lanzar turno = [L] Rama C · baja = activo: 0 (nunca borrar) · "
                         "tipo Acción vetado desde el panel (se gana) · "
                         "[E] = el TRABAJO · quién es (nombre/cara/tono) = [P][/dim]")
            with Horizontal(id="botones_emp"):
                yield Button("Cerrar", id="e_cerrar")
                yield Input(placeholder="nº", id="e_num")
                yield Button("✏️ Editar nº", id="e_editar", variant="warning")
                yield Button("➕ Nuevo", id="e_nuevo", variant="primary")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "e_editar":
            num = self.query_one("#e_num", Input).value.strip()
            rol = self._indice.get(num)
            if not rol:
                self.app.notify(f"nº inválido: «{num}» (1-{len(self._indice)})", severity="warning", timeout=5)
                return
            self.dismiss(("editar", rol))
            return
        self.dismiss("nuevo" if ev.button.id == "e_nuevo" else None)


class PantallaAltaEmpleado(ModalScreen):
    """[E] · FICHA de empleado: ALTA (editar_rol=None) o EDICIÓN (editar_rol='x', prefill).
    Editable: prompt, lecturas, departamento, puertos, contexto, activo, cadencia.
    INMUTABLE desde el panel: rol, firma, tipo (la Acción se gana), nivel (doctrina).
    Devuelve el dict o None; el yaml lo escribe la App (backup si es edición)."""

    CSS = """
    PantallaAltaEmpleado { align: center middle; }
    #caja_alta { width: 96; height: auto; max-height: 96%; border: thick $success;
                 background: $surface; padding: 1 2; }
    #prompt_ta { height: 7; margin: 1 0; }
    RadioSet { height: auto; }
    #botones_alta { height: auto; align-horizontal: right; margin-top: 1; }
    Button { margin-left: 2; }
    Checkbox { margin-right: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, editar_rol=None):
        super().__init__()
        self._editar = editar_rol
        self._orig = {}
        if editar_rol:
            try:
                import yaml
                self._orig = yaml.safe_load(open(os.path.join(TURNOS_DIR, f"{editar_rol}.yaml"),
                                                 encoding="utf-8")) or {}
            except Exception:                              # noqa: BLE001
                self._orig = {}

    def compose(self) -> ComposeResult:
        o = self._orig
        with Vertical(id="caja_alta"):
            if self._editar:
                yield Label(f"[b]✏️ Editar a {o.get('firma', self._editar)}[/b] [dim]· Esc = atrás[/dim] "
                            f"[dim]· nivel {o.get('nivel','N2')} · tipo {o.get('tipo_reporte','Informe')} "
                            f"(rol/firma/tipo/nivel: inmutables desde el panel)[/dim]")
            else:
                yield Label("[b]➕ Alta de empleado[/b]  [dim]· palabra JAMÁS manos · su firma será MOSAIC-<rol> · Esc = atrás[/dim]")
            with Horizontal():
                yield Input(placeholder="rol (ej: fnc, oraculo)", id="alta_rol",
                            value=self._editar or "", disabled=bool(self._editar))
                yield Input(placeholder="departamento (ej: seguridad)", id="alta_dep",
                            value=str(o.get("departamento", "")))
            if not self._editar:
                with RadioSet(id="alta_nivel"):
                    yield RadioButton("N2 · Manager/Lead (razona con modelo → Informe)", value=True)
                    yield RadioButton("N3 · Trabajador (parte-de-estado, SIN modelo)")
                # 🪪 PASO 3 (handoff Opus 14:39): un empleado nuevo nace CON CARA, no anónimo
                yield Label("[dim]🪪 su persona (quién es — luego se afina en [P]; nombre vacío = 🎲 bautizo auto):[/dim]")
                with Horizontal():
                    yield Input(placeholder="nombre humano (🎲 si vacío)", id="alta_pnombre")
                    yield Input(placeholder="alias (ej: El Vigía)", id="alta_palias")
                    yield Input(placeholder="tono", id="alta_ptono")
            yield Label("[dim]prompt de sistema (su alma: QUÉ mirar y QUÉ reportar — los N3 no lo usan):[/dim]")
            yield TextArea(str(o.get("prompt", "")), id="prompt_ta")
            yield Input(placeholder="lecturas (rutas relativas por comas · ej: data/META.md, servidores.conf)",
                        id="alta_lecturas", value=", ".join(o.get("lecturas", [])))
            with Horizontal():
                yield Checkbox("activo", value=bool(o.get("activo", 1)), id="alta_activo")
                yield Input(placeholder="cadencia h (1)", id="alta_cad",
                            value=str(round(o["cadencia_s"] / 3600, 2)) if o.get("cadencia_s") else "")
                yield Input(placeholder="contexto max_c (8000)", id="alta_maxc",
                            value=str(o.get("max_c", "")) if o.get("max_c") else "")
                yield Input(placeholder=f"🔑acceso ≤{o.get('nivel_acceso', 1)}", id="alta_niv_acc",
                            value=str(o.get("nivel_acceso", 1)) if self._editar else "1")
            yield Static("[dim]tipo Acción VETADO desde el panel — se gana con el circuito de sellos (hoy solo el auditor)[/dim]")
            yield Label("[dim]modelo(s) candidatos — el pre-vuelo usa el primero VIVO (los N3 no necesitan):[/dim]")
            with Horizontal():
                for i, (etq, url, _nom) in enumerate(_roster_base()):
                    try:
                        p = int(url.rsplit(":", 1)[1].split("/")[0])
                    except Exception:                      # noqa: BLE001
                        p = 0
                    marcado = (p in o.get("puertos", [])) if self._editar else (i == 0)
                    yield Checkbox(etq, value=marcado, id=f"alta_p{i}")
            with Horizontal(id="botones_alta"):
                yield Button("Cancelar", id="alta_cancelar")
                yield Button("Guardar" + ("" if self._editar else " (nace el yaml)"),
                             id="alta_guardar", variant="success")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id != "alta_guardar":
            self.dismiss(None)
            return
        import re
        rol = (self._editar or self.query_one("#alta_rol", Input).value.strip().lower())
        if not re.fullmatch(r"[a-z0-9_-]{2,32}", rol or ""):
            self.app.notify("rol inválido (minúsculas/números/-/_ · 2-32)", severity="warning", timeout=6)
            return
        if not self._editar and os.path.exists(os.path.join(TURNOS_DIR, f"{rol}.yaml")):
            self.app.notify(f"«{rol}» ya existe — usa ✏️ Editar", severity="warning", timeout=6)
            return
        nivel = str(self._orig.get("nivel", "N2")) if self._editar else \
            ("N3" if (self.query_one("#alta_nivel", RadioSet).pressed_index or 0) == 1 else "N2")
        prompt = self.query_one("#prompt_ta", TextArea).text.strip()
        if nivel == "N2" and len(prompt) < 40:
            self.app.notify("el prompt es el ALMA del agente — dale al menos unas frases", severity="warning", timeout=6)
            return
        roster = _roster_base()
        puertos = []
        for i, (_etq, url, _nom) in enumerate(roster):
            try:
                if self.query_one(f"#alta_p{i}", Checkbox).value:
                    puertos.append(int(url.rsplit(":", 1)[1].split("/")[0]))
            except Exception:                              # noqa: BLE001
                continue
        if nivel == "N2" and not puertos:
            self.app.notify("un N2 razona: elige al menos un modelo candidato", severity="warning", timeout=6)
            return
        lecturas = [x.strip() for x in self.query_one("#alta_lecturas", Input).value.split(",") if x.strip()]
        if nivel == "N3" and not lecturas:
            self.app.notify("un N3 ES sus lecturas — dale al menos un registro", severity="warning", timeout=6)
            return
        cad = self.query_one("#alta_cad", Input).value.strip()
        maxc = self.query_one("#alta_maxc", Input).value.strip()
        # 🔑 nivel_acceso: desde el panel SOLO HACIA ABAJO (subir = decisión de rango, no autoservicio)
        na_txt = self.query_one("#alta_niv_acc", Input).value.strip()
        na_orig = int(self._orig.get("nivel_acceso", 1) or 1) if self._editar else 1
        na = int(na_txt) if na_txt.isdigit() and 1 <= int(na_txt) <= 5 else na_orig
        if na > na_orig:
            self.app.notify(f"🔑 subir el acceso ({na_orig}→{na}) NO es autoservicio — decisión de rango "
                            "(yaml a mano o Gustavo). Lo dejo en su nivel.", severity="warning", timeout=8)
            na = na_orig
        # tipo: N2→Informe · N3→parte-de-estado · edición→el que ya tenía (Acción se gana, jamás desde aquí)
        tipo = str(self._orig.get("tipo_reporte", "Informe")) if self._editar else \
            ("parte-de-estado" if nivel == "N3" else "Informe")
        persona = {}
        if not self._editar:                               # 🪪 PASO 3: nace con cara ([P] la afina después)
            persona = {"nombre_humano": self.query_one("#alta_pnombre", Input).value.strip(),
                       "alias": self.query_one("#alta_palias", Input).value.strip(),
                       "tono": self.query_one("#alta_ptono", Input).value.strip()}
        self.dismiss({"rol": rol, "editar": bool(self._editar), "nivel": nivel, "tipo": tipo,
                      "nivel_acceso": na, "persona": persona,
                      "departamento": self.query_one("#alta_dep", Input).value.strip().lower() or "sin-departamento",
                      "prompt": prompt, "lecturas": lecturas, "puertos": puertos,
                      "activo": self.query_one("#alta_activo", Checkbox).value,
                      "cadencia_s": int(float(cad) * 3600) if cad.replace(".", "", 1).isdigit() else 3600,
                      "max_c": int(maxc) if maxc.isdigit() else 8000})


def _barra(val, maxv, ancho=10):
    """▓▓▓░░ noventera de texto — val sobre maxv en `ancho` celdas (clamp seguro)."""
    try:
        f = 0.0 if maxv <= 0 else max(0.0, min(1.0, float(val) / float(maxv)))
    except (TypeError, ValueError):
        f = 0.0
    llenas = int(round(f * ancho))
    return "█" * llenas + "░" * (ancho - llenas)


def _stats_agente(rol):
    """[E] · los STATS de la ficha noventera — DERIVADOS y HONESTOS (nada de ELO inventado,
    ni salud por-agente que no medimos): acceso (yaml) · actividad (sus cartas contadas de
    verdad) · último turno (data/turnos) · tickets (escalaciones vivas suyas). Puro/testeable."""
    import yaml
    st = {"nivel": "N2", "nivel_acceso": 1, "tipo": "Informe", "depto": "?",
          "cartas": 0, "ultimo": "nunca", "tickets": 0, "activo": True}
    try:
        d = yaml.safe_load(open(os.path.join(TURNOS_DIR, f"{rol}.yaml"), encoding="utf-8")) or {}
        st.update(nivel=str(d.get("nivel", "N2")), nivel_acceso=int(d.get("nivel_acceso", 1) or 1),
                  tipo=str(d.get("tipo_reporte", "Informe")), depto=str(d.get("departamento", "?")),
                  activo=bool(d.get("activo", 1)), firma=str(d.get("firma", f"MOSAIC-{rol}")))
    except Exception:                                      # noqa: BLE001
        st["firma"] = f"MOSAIC-{rol}"
    # actividad: cuántas veces habló en CARTAS (su firma en una cabecera ##) — real, no inventado
    try:
        firma = st["firma"]
        st["cartas"] = sum(1 for l in open(CARTAS, encoding="utf-8", errors="replace")
                           if l.startswith("## ") and firma in l)
    except OSError:
        pass
    # último turno (data/turnos/<rol>.ultimo: epoch acta)
    try:
        t = int(open(os.path.join(BASE, "data", "turnos", f"{rol}.ultimo"), encoding="utf-8").read().split()[0])
        mins = (int(time.time()) - t) // 60
        st["ultimo"] = f"hace {mins}min" if mins < 120 else f"hace {mins // 60}h"
    except (OSError, ValueError, IndexError):
        pass
    # tickets vivos suyos (escalaciones.json)
    try:
        ts = (json.load(open(ESCALACIONES, encoding="utf-8")) or {}).get("tickets") or []
        st["tickets"] = sum(1 for t in ts if t.get("agente_origen") == rol
                            and t.get("estado") in ("abierto", "escalado", "en_revision"))
    except Exception:                                      # noqa: BLE001
        pass
    # 💰 el bolsillo (F2 economía): gasto REAL medido — si el ledger aún no existe, se dice
    try:
        a = (json.load(open(os.path.join(BASE, "data", "economia.json"), encoding="utf-8"))
             .get("agentes") or {}).get(rol)
        st["gasto"] = (f"{a['tokens_entrada'] + a['tokens_salida']} tok en {a['turnos']} turnos"
                       if a else "0 (sin turnos medidos)")
    except Exception:                                      # noqa: BLE001
        st["gasto"] = "contador ⏸ (arranca tras el debut, ECONOMIA=1)"
    return st


def _ficha_noventera(rol):
    """[E] · la FICHA DEL EMPLEADO estilo pantalla-de-creación-de-personaje 90s (mockup de
    Gustavo → campos REALES). Rich-markup lista de líneas. PUESTO 🔒 = núcleo inmutable; los
    'stats' son DERIVADOS honestos (los que sé medir); herramientas por su nivel; rutina real."""
    p = _persona_de(rol)
    s = _stats_agente(rol)
    tools_mias = []
    try:
        reg = (__import__("yaml").safe_load(open(os.path.join(BASE, "data", "herramientas.yaml"),
               encoding="utf-8")) or {})
        techo = int(reg.get("techo_f1", 3) or 3)
        for t in reg.get("tools", []):
            nr = int(t.get("nivel_requerido", 5) or 5)
            if not t.get("cmd") or nr > techo:
                continue
            marca = "▣" if nr <= s["nivel_acceso"] else "☐"
            tools_mias.append(f"{marca} {t['nombre']}({nr})")
    except Exception:                                      # noqa: BLE001
        tools_mias = ["(registro de tools no disponible)"]
    nom = p.get("nombre_humano") or rol
    est = "[b green]🟢 ACTIVO[/]" if s["activo"] else "[b red]💤 inactivo[/]"
    N = "[b cyan]"                                          # helpers de color CRT
    return [
        f"[b]╔═══════════ FICHA DEL EMPLEADO · {nom} ═══════════╗[/b]",
        f" {N}IDENTIDAD[/]                    {N}DEPARTAMENTO[/]",
        f" ► Nombre:  [b]{nom}[/b]            ▓▓ {s['depto']}",
        f"   Alias:   «{p.get('alias','—')}» {p.get('emoji','')}",
        f"   Tono:    ‹ {str(p.get('tono','—'))[:34]} ›",
        "",
        f" {N}PUESTO · fijo 🔒[/]             {N}ESTADO · derivado (real)[/]",
        f"  Nivel:   {s['nivel']}              Actividad: {_barra(s['cartas'],20)} [{s['cartas']} 🗨]",
        f"  Acceso:  {_barra(s['nivel_acceso'],5,5)} [{s['nivel_acceso']}/5]   Tickets:   {s['tickets']} 🎫 vivos",
        f"  Emite:   {s['tipo']}         Últ. turno: {s['ultimo']}",
        f"           {est}          💰 Gasto: {s.get('gasto', 'sin contador aún')}",
        "",
        f" {N}HERRAMIENTAS · por su nivel[/]",
        "  " + "  ".join(tools_mias),
        "",
        f" {N}RUTINA · cuándo actúa[/]",
        f"  🗨 Habla en el pleno    ⏱ Parte por cadencia    📮 Lee su buzón",
        "[b]╚══════════════════════════════════════════════════════╝[/b]",
        "[dim](ELO/salud por-agente NO se pintan: aún no los medimos — honestidad de la casa)[/dim]",
    ]


# ═══════════════ [A] AGENDA — el eje del TIEMPO (Opus 18:40: mapeo HONESTO, read-only) ═══════════════

def _agenda_eventos():
    """Todos los eventos FECHADOS que ya existen — cada glifo traza a un fichero real
    (línea roja: cero telemetría falsa). Devuelve [{ts:'YYYY-MM-DD HH:MM', glifo, txt}].
    Fuentes: actas · acciones.json · escalaciones(+archivo) · cabeceras de CARTAS(+histórico)."""
    ev = []
    import glob as _g
    import re as _re
    for p in sorted(_g.glob(os.path.join(BASE, "data", "actas", "acta_*.json"))):
        m = _re.search(r"acta_(\d{8})_(\d{6})", os.path.basename(p))
        if not m:
            continue
        d, h = m.group(1), m.group(2)
        try:
            crag = (json.load(open(p, encoding="utf-8")).get("tanda_resumen") or {}).get("crag_medio", "?")
        except Exception:                                  # noqa: BLE001
            crag = "?"
        ev.append({"ts": f"{d[:4]}-{d[4:6]}-{d[6:]} {h[:2]}:{h[2:4]}", "glifo": "🔄",
                   "txt": f"acta de ciclo (CRAG {crag})"})
    try:
        for a in (json.load(open(os.path.join(BASE, "data", "acciones.json"), encoding="utf-8"))
                  .get("acciones")) or []:
            sellada = bool(a.get("sellos"))
            ev.append({"ts": str(a.get("ts", ""))[:16], "glifo": "✅" if sellada else "📋",
                       "txt": f"{a.get('id','ACC-?')} {'SELLADA' if sellada else a.get('estado','propuesta')} "
                              f"· {a.get('autor','?')} · {str(a.get('titulo',''))[:48]}"})
    except Exception:                                      # noqa: BLE001
        pass
    try:
        vivos = (json.load(open(ESCALACIONES, encoding="utf-8")) or {}).get("tickets") or []
    except Exception:                                      # noqa: BLE001
        vivos = []
    arch = []
    try:
        with open(ESC_ARCHIVO, encoding="utf-8") as f:
            arch = [json.loads(l) for l in f if l.strip()]
    except (OSError, ValueError):
        pass
    for t in vivos + arch:
        ev.append({"ts": str(t.get("ts", ""))[:16], "glifo": "⚠️",
                   "txt": f"{t.get('id','ESC-?')} {t.get('agente_origen','?')} pide "
                          f"{t.get('herramienta','?')} ({t.get('estado','?')})"})
    # 💬📝 LA AGENDA PRIVADA (F1, firmada Opus 21:45): SOLO ÍNDICE — fecha y tema salen del
    #    NOMBRE del fichero; el contenido JAMÁS se lee aquí, jamás entra a un modelo desde
    #    la agenda, jamás viaja (conversaciones_txt está fuera del árbol y del export).
    def _fecha_sana(s):
        """Un filename con '9999-99-99' NO es un evento — la agenda no traga fechas imposibles."""
        try:
            time.strptime(s, "%Y-%m-%d")
            return 2000 <= int(s[:4]) <= 2100
        except ValueError:
            return False

    try:
        cdir = os.path.join(CALENDARIO_DIR, "conversaciones_txt")
        for f in os.listdir(cdir):
            m = _re.match(r"(\d{4}-\d{2}-\d{2})_(.+)\.txt$", f)
            if m and _fecha_sana(m.group(1)):
                ev.append({"ts": m.group(1) + " 00:00", "glifo": "💬",
                           "txt": f"conversación IA: {m.group(2).replace('-', ' ')[:56]}"})
    except OSError:
        pass                                               # sin calendario montado → sin capa privada
    try:                                                   # 📝 capa-detalle: las notas CLASIFICADAS (resúmenes
        for raiz, _dirs, fs in os.walk(os.path.join(CALENDARIO_DIR, "notas_clasificadas")):
            for f in fs:                                   #    nuestros — recomendación #4 de Opus)
                m = _re.match(r"(\d{4}-\d{2}-\d{2})_.*\.txt$", f)
                if m and _fecha_sana(m.group(1)):
                    tema = os.path.basename(raiz).split("--")[-1].replace("-", " ")[:36]
                    ev.append({"ts": m.group(1) + " 00:00", "glifo": "📝",
                               "txt": f"nota clasificada [{tema}]: {f[11:-4][:44]}"})
    except OSError:
        pass
    try:                                                   # 🗨️ los CHATS con empleados ([P] Parlamento) —
        cdir = os.path.join(BASE, "data", "conversaciones_empresa")   # empresarial: cuenta como 🏢
        for f in os.listdir(cdir):
            m = _re.match(r"(\d{4}-\d{2}-\d{2})_(\d{4})_([a-z0-9_-]+)_(.+)\.txt$", f)
            if m and _fecha_sana(m.group(1)):
                ev.append({"ts": f"{m.group(1)} {m.group(2)[:2]}:{m.group(2)[2:]}", "glifo": "🗨️",
                           "txt": f"chat con {m.group(3)}: {m.group(4).replace('-', ' ')[:48]}"})
    except OSError:
        pass                                               # sin chats aún → sin capa (nada se rompe)
    try:                                                   # 💹 la cotización en el calendario (mejora #3 Opus)
        with open(os.path.join(BASE, "data", "ticker_historia.jsonl"), encoding="utf-8") as f:
            for l in f:
                if not l.strip():
                    continue
                h = json.loads(l)
                d = h.get("delta_pct")
                ev.append({"ts": str(h.get("ts", ""))[:16], "glifo": "💹",
                           "txt": f"cotización {h.get('empresa','?')}: {h.get('valor','?')}"
                                  + (f" ({'▲' if d >= 0 else '▼'}{abs(d)}%)" if isinstance(d, (int, float)) else "")})
    except (OSError, ValueError):
        pass
    pat = _re.compile(r"^## .*?([A-Za-zÁ-ú°𝘢-𝘻\-]*\S*)?.*· (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*$")
    for ruta in (CARTAS, os.path.join(BASE, "info", "historico", "CARTAS_2026-07.md")):
        try:
            for l in open(ruta, encoding="utf-8", errors="replace"):
                if not l.startswith("## "):
                    continue
                m = _re.search(r"· (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*$", l)
                if not m:
                    continue
                turno = "Turno de" in l or "Parte de estado" in l
                ev.append({"ts": m.group(1), "glifo": "🗣" if turno else "✉️",
                           "txt": l[3:].strip()[:64]})
        except OSError:
            continue
    return sorted((e for e in ev if len(e.get("ts", "")) >= 10), key=lambda e: e["ts"])


def _agenda_filtrar(ev, modo):
    """El filtro DUAL (F1 firmada): 'todo' · 'empresa' (actas/turnos/sellos/tickets/cartas/
    cotización) · 'privada' (💬 conversaciones IA + 📝 notas — la vida de Gustavo). Puro."""
    PRIVADOS = ("💬", "📝")
    if modo == "privada":
        return [e for e in ev if e["glifo"] in PRIVADOS]
    if modo == "empresa":
        return [e for e in ev if e["glifo"] not in PRIVADOS]
    return ev


def _agenda_prospectivo():
    """Lo PROSPECTIVO honesto: SOLO lo que un motor ya programó (perpetuo, gobernador) —
    el futuro no se inventa (línea roja de Opus)."""
    out = []
    try:
        pid = int(open(os.path.join(BASE, "data", ".perpetuo.pid"), encoding="utf-8").read().strip())
        os.kill(pid, 0)
        out.append(f"♾️ perpetuo ENCENDIDO (PID {pid}) · pleno cada {os.environ.get('PLENO_CADA_MIN', '60')} min")
    except (OSError, ValueError):
        out.append("♾️ perpetuo apagado — sin plenos programados")
    try:
        p = json.load(open(os.path.join(BASE, "data", "perfil_lanzamiento.json"), encoding="utf-8"))
        mandos = p.get("mandos") or {}
        out.append("🧭 próximo ciclo (gobernador): "
                   + " · ".join(f"{k}={v}" for k, v in list(mandos.items())[:6]))
        cr = (p.get("seniales") or {}).get("tendencia_crag") or (p.get("seniales") or {}).get("crag")
        if cr is not None:
            out.append(f"   señal CRAG: {cr}")
    except Exception:                                      # noqa: BLE001
        out.append("🧭 sin perfil del gobernador aún")
    return out


def _agenda_anio(ev, anio):
    """Capa AÑO: heatmap de actividad por mes (cuenta real de eventos)."""
    lineas = [f"[b]📅 {anio} — actividad por mes[/b] [dim](cuenta de eventos reales)[/dim]", ""]
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    for i, nom in enumerate(meses, 1):
        n = sum(1 for e in ev if e["ts"].startswith(f"{anio}-{i:02d}"))
        lineas.append(f"  {nom} {_barra(n, 200, 14)} {n if n else '[dim]—[/dim]'}")
    lineas += ["", "[dim]mes vacío = vacío (nada se inventa) · entra a MES con: {:>7}[/dim]".format(f"{anio}-MM")]
    return lineas


def _agenda_mes(ev, ym):
    """Capa MES: rejilla de días con GLIFOS de lo que pasó (🔄 acta · 🗣 turno · ✅ sellada ·
    📋 propuesta · ⚠️ escalación · ✉️ carta). Día sin datos = casilla vacía."""
    import calendar
    try:
        a, m = int(ym[:4]), int(ym[5:7])
    except ValueError:
        return [f"[red]mes raro: {ym} (espero YYYY-MM)[/red]"]
    lineas = [f"[b]📅 {calendar.month_name[m]} {a}[/b] [dim]· glifos: 🔄acta 🗣turno ✅sellada "
              f"📋propuesta ⚠️ticket ✉️carta[/dim]", ""]
    for dia in range(1, calendar.monthrange(a, m)[1] + 1):
        pref = f"{a}-{m:02d}-{dia:02d}"
        dev = [e for e in ev if e["ts"].startswith(pref)]
        if not dev:
            lineas.append(f"  {dia:2d} [dim]·[/dim]")
            continue
        cuenta = {}
        for e in dev:
            cuenta[e["glifo"]] = cuenta.get(e["glifo"], 0) + 1
        resumen = " ".join(f"{g}×{n}" if n > 1 else g for g, n in
                           sorted(cuenta.items(), key=lambda x: -x[1]))
        lineas.append(f"  {dia:2d} {resumen}  [dim]({len(dev)} eventos)[/dim]")
    lineas += ["", f"[dim]entra a un DÍA con: {ym}-DD[/dim]"]
    return lineas


def _agenda_dia(ev, fecha):
    """Capa DÍA: la agenda HORARIA por ts real + quién actuó (los `ts` exactos, Opus 18:40)."""
    dev = [e for e in ev if e["ts"].startswith(fecha)]
    lineas = [f"[b]📅 {fecha} — {len(dev)} eventos[/b]", ""]
    if not dev:
        lineas.append("[dim](día sin eventos — vacío de verdad, nada se pinta)[/dim]")
        return lineas
    for e in dev:
        lineas.append(f"  {e['ts'][11:16]}  {e['glifo']}  {e['txt']}")
    actores = sorted({e["txt"].split("→")[0].split("·")[0].replace("## ", "").strip()
                      for e in dev if e["glifo"] in ("🗣", "✉️")})[:10]
    if actores:
        lineas += ["", "[dim]actuaron: " + " · ".join(a[:24] for a in actores) + "[/dim]"]
    return lineas


class PantallaAgenda(ModalScreen):
    """[A] AGENDA · el eje del TIEMPO (Opus 18:40) — 3 capas (Año·Mes·Día) sobre eventos
    REALES fechados. READ-ONLY estricto: la agenda LEE ts; programar = solo el motor
    (perpetuo.sh la cadencia, sellar.sh las acciones). Ninguna casilla dispara nada."""

    CSS = """
    PantallaAgenda { align: center middle; }
    #caja_ag { width: 96; height: auto; max-height: 94%; border: double $accent;
               background: $surface; padding: 1 2; }
    #vista_ag { height: auto; max-height: 24; border: round $accent; padding: 0 1; margin: 1 0; }
    #botones_ag { height: auto; align-horizontal: right; }
    #ag_sel { width: 16; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self):
        super().__init__()
        self._ev = _agenda_eventos()
        self._hoy = time.strftime("%Y-%m-%d")
        self._capa = "mes"
        self._filtro = "todo"                              # todo · empresa · privada (F1 dual)

    def _pintar(self, sel):
        ev = _agenda_filtrar(self._ev, self._filtro)
        if self._capa == "año":
            return _agenda_anio(ev, sel[:4])
        if self._capa == "mes":
            return _agenda_mes(ev, sel[:7])
        return _agenda_dia(ev, sel[:10])

    def compose(self) -> ComposeResult:
        n_priv = len(_agenda_filtrar(self._ev, "privada"))
        with Vertical(id="caja_ag"):
            yield Label("[b]📅 AGENDA — propiocepción en el eje del tiempo[/b] [dim]· read-only: "
                        "programar es del motor (perpetuo/sellos) · Esc cierra[/dim]")
            with VerticalScroll(id="vista_ag"):
                yield Static("\n".join(self._pintar(self._hoy)), id="ag_cuerpo")
            yield Static("[b]PROSPECTIVO[/b] [dim](solo lo ya programado — el futuro no se inventa)[/dim]\n"
                         + "\n".join("  " + l for l in _agenda_prospectivo()), id="ag_pros")
            yield Static(f"[dim]💬/📝 agenda PRIVADA ({n_priv} eventos, 2023→hoy): SOLO ÍNDICE del nombre "
                         "de fichero — el contenido jamás se lee aquí, jamás viaja, jamás entra a un "
                         "modelo sin tu acto explícito (línea sellada por Opus 21:45)[/dim]", id="ag_priv")
            with Horizontal(id="botones_ag"):
                yield Button("Cerrar", id="ag_cerrar")
                yield Input(placeholder=self._hoy, id="ag_sel")
                yield Button("📆 Año", id="ag_anio")
                yield Button("🗓 Mes", id="ag_mes", variant="primary")
                yield Button("📋 Día", id="ag_dia", variant="success")
                yield Button("Σ Todo", id="ag_f_todo")
                yield Button("🏢", id="ag_f_empresa")
                yield Button("💬", id="ag_f_privada", variant="warning")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        bid = ev.button.id or ""
        if bid in ("ag_anio", "ag_mes", "ag_dia"):
            self._capa = {"ag_anio": "año", "ag_mes": "mes", "ag_dia": "día"}[bid]
        elif bid.startswith("ag_f_"):
            self._filtro = bid[5:]
        else:
            self.dismiss(None)
            return
        sel = (self.query_one("#ag_sel", Input).value.strip() or self._hoy)
        self.query_one("#ag_cuerpo", Static).update("\n".join(self._pintar(sel)))


class PantallaParlamento(ModalScreen):
    """[P] PARLAMENTO (propuesta Gustavo 5-jul): hablar con un EMPLEADO. Elige silla →
    chat. El motor (parlamento.py) es DUEÑO de su prompt (arreglo #3 Opus): system por
    RANGO, llamada directa a la flota — no hereda el vacío del pleno. Registra y reanuda.
    Palabra jamás manos: el chat no ejecuta nada. Los N3 deterministas no tienen chat."""

    CSS = """
    PantallaParlamento { align: center middle; }
    #caja_par { width: 100; height: 90%; border: double $accent; background: $surface; padding: 1 2; }
    #hist_par { height: 1fr; border: round $accent; padding: 0 1; margin: 1 0; }
    #fila_par { height: auto; }
    #par_msg { width: 1fr; }
    Button { margin-left: 1; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self):
        super().__init__()
        import yaml
        self._sillas = []
        try:
            for f in sorted(os.listdir(TURNOS_DIR)):
                if not f.endswith(".yaml"):
                    continue
                d = yaml.safe_load(open(os.path.join(TURNOS_DIR, f), encoding="utf-8")) or {}
                if d.get("tipo_reporte") != "parte-de-estado":     # N3 fuera: no razonan en chat
                    per = d.get("persona") or {}
                    self._sillas.append((f[:-5], per.get("nombre_humano") or f[:-5],
                                         per.get("emoji", "🎭"), str(d.get("departamento", "?"))))
        except OSError:
            pass
        self._rol = self._sillas[0][0] if self._sillas else None
        self._hist = []                                    # [{role, content}]
        self._sesion = None

    def compose(self) -> ComposeResult:
        cat = " · ".join(f"[{i + 1}]{n}{e}" for i, (r, n, e, d) in enumerate(self._sillas))
        with Vertical(id="caja_par"):
            yield Label("[b]🗨️ PARLAMENTO — habla con tu gente[/b] [dim]· cada charla se registra en la "
                        "AGENDA (🏢) y es reanudable · palabra, jamás manos · Esc cierra[/dim]")
            yield Static(cat or "[dim](sin sillas razonadoras)[/dim]")
            with VerticalScroll(id="hist_par"):
                yield Static(self._saludo(), id="par_cuerpo")
            with Horizontal(id="fila_par"):
                yield Input(placeholder="nº para cambiar de empleado · o escribe tu mensaje…", id="par_msg")
                yield Button("Enviar", id="par_enviar", variant="primary")
                yield Button("Cerrar", id="par_cerrar")

    def _saludo(self):
        if not self._rol:
            return "[dim](no hay empleados razonadores — da de alta un N2 en [E])[/dim]"
        nom = next((n for r, n, e, d in self._sillas if r == self._rol), self._rol)
        return (f"[b]Hablas con {nom}[/b] ([i]{self._rol}[/i]). Escribe un mensaje y pulsa Enviar.\n"
                "[dim]Te contesta con SU rango: su persona, su prompt y sus registros — el contexto "
                "correcto para responderte bien. Cambia de empleado escribiendo su número.[/dim]")

    def _pinta(self, extra=""):
        cuerpo = [self._saludo(), ""]
        for h in self._hist[-12:]:
            quien = "[b cyan]Tú[/]" if h["role"] == "user" else "[b yellow]" + self._rol + "[/]"
            cuerpo.append(f"{quien}: {h['content']}")
        if extra:
            cuerpo.append(extra)
        self.query_one("#par_cuerpo", Static).update("\n\n".join(cuerpo))

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "par_cerrar":
            self.dismiss(None)
            return
        val = self.query_one("#par_msg", Input).value.strip()
        if not val:
            return
        if val.isdigit() and 1 <= int(val) <= len(self._sillas):   # cambiar de empleado
            self._rol = self._sillas[int(val) - 1][0]
            self._hist, self._sesion = [], None
            self.query_one("#par_msg", Input).value = ""
            self._pinta()
            return
        if not self._rol:
            return
        self.query_one("#par_msg", Input).value = ""
        self._hist.append({"role": "user", "content": val})
        self._pinta("[dim]… pensando (su rango se inyecta; puede tardar con la flota)…[/dim]")
        self._responder(val)

    def _responder(self, mensaje) -> None:
        import subprocess
        try:
            args = ["python3", os.path.join(BASE, "parlamento.py"), "--rol", self._rol]
            if self._sesion:
                args += ["--sesion", self._sesion]
            r = subprocess.run(args, input=mensaje, capture_output=True, text=True,
                               errors="replace", timeout=180, cwd=BASE,
                               env={**os.environ, "MOSAIC_BASE": BASE})
            d = json.loads(r.stdout or "{}")
        except Exception as e:                             # noqa: BLE001
            d = {"ok": False, "error": f"no pude invocar el parlamento: {e}"}
        if d.get("ok"):
            self._hist.append({"role": "assistant", "content": d["respuesta"]})
            self._sesion = d.get("sesion", self._sesion)
            self._pinta()
        else:
            self._pinta(f"[red]⚠️ {d.get('error', 'sin respuesta')}[/red]")


def _bolsa_abierta():
    """🔔 LA CAMPANA DE APERTURA (auditoría Opus 18:20 — «primero el latido; luego el
    mercado»): la bolsa abre SOLA cuando el circuito ha latido de verdad — la PRIMERA
    Acción SELLADA (el debut). Override explícito: MOSAIC_BOLSA=1. Puro/testeable."""
    if os.environ.get("MOSAIC_BOLSA", "") == "1":
        return True
    try:
        acc = (json.load(open(os.path.join(BASE, "data", "acciones.json"), encoding="utf-8"))
               .get("acciones")) or []
        return any(a.get("sellos") for a in acc)
    except Exception:                                      # noqa: BLE001
        return False


def _bolsa_lineas():
    """[E]→💹 · las CARDS del ranking (data/ranking.json — lo escribe valorar_empresa.py,
    N3 determinista). Builder PURO testeable. Solo lectura: el ranking PROPONE, jamás
    ejecuta — la flota/fundar/jubilar los decide Gustavo (línea roja de la ronda)."""
    try:
        rk = json.load(open(os.path.join(BASE, "data", "ranking.json"), encoding="utf-8")) or {}
    except Exception:                                      # noqa: BLE001
        return ["[dim](sin ranking aún — se genera al abrir esta pestaña)[/dim]"], ""
    lineas = []
    ico_est = {"sede": "🏛️", "neutral": "🤝", "quiebra": "📉", "sin cotizar": "⏳"}
    for t in rk.get("empresas", []):
        v = t.get("valor")
        d = t.get("delta_pct")
        delta = "" if d is None else (f" [green]▲{d}%[/]" if d >= 0 else f" [red]▼{abs(d)}%[/]")
        cab = (f"[b]{ico_est.get(t.get('estado'), '·')} {t.get('empresa', '?')}[/b] · "
               + (f"[b yellow]{v}[/b yellow]{delta}" if v is not None else "[dim]— sin cotizar —[/dim]"))
        lineas.append(cab)
        det = t.get("madurez_detalle") or {}
        lineas.append(f"   Madurez {_barra(t.get('madurez_pct', 0), 100)} [{t.get('madurez_pct', 0)}%] "
                      f"[dim](sillas {det.get('sillas', '?')} · sellos {det.get('sellos', '?')} · "
                      f"tools {det.get('tools', '?')})[/dim]")
        if v is not None:
            lineas.append(f"   CRAG {t.get('crag', '?')} · {t.get('capacidades', 0)} caps · "
                          f"{t.get('actas', 0)} actas · estado {t.get('estado', '?')}")
        else:
            lineas.append(f"   [dim]{t.get('nota', '')}[/dim]")
        lineas.append("")
    return (lineas or ["[dim](ranking vacío)[/dim]"]), str(rk.get("generado", ""))


class PantallaBolsa(ModalScreen):
    """[E]→💹 BOLSA · el ranking del grupo, tipo tickers CRT (ronda bursátil 5-jul).
    Al abrir REGENERA el ranking (valorar_empresa.py --grupo: determinista, sin LLM,
    subsegundo) y lo pinta. SOLO LECTURA — cuadro de mando, no mercado autónomo."""

    CSS = """
    PantallaBolsa { align: center middle; }
    #caja_bolsa { width: 96; height: auto; max-height: 92%; border: double $warning;
                  background: $surface; padding: 1 2; }
    #cards_bolsa { height: auto; max-height: 22; border: round $accent; padding: 0 1; margin: 1 0; }
    #botones_bolsa { height: auto; align-horizontal: right; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def compose(self) -> ComposeResult:
        # 🔔 la campana (auditoría Opus 18:20): SIN primer sello, la bolsa está CERRADA —
        #    ni se regenera el ranking ni se pinta cotización. El debut es la apertura.
        if not _bolsa_abierta():
            with Vertical(id="caja_bolsa"):
                yield Label("[b]💹 BOLSA DEL GRUPO[/b] [dim]· Esc cierra[/dim]")
                yield Static("\n[b yellow]🔔 CERRADA — abre con el DEBUT.[/b yellow]\n\n"
                             "«Primero el latido; luego el mercado» (Opus, 18:20). La bolsa suena\n"
                             "sola con la PRIMERA Acción sellada:\n"
                             "  1. ./pleno.sh              (¿se leen limpias las cartas?)\n"
                             "  2. ./sellar.sh ACC-20260705-01 auditor \"veredicto\"   (Opus)\n"
                             "  3. ./sellar.sh ACC-20260705-01 humano \"ok\"           (Gustavo)\n"
                             "\n[dim](override a conciencia: MOSAIC_BOLSA=1 ./monitor.py — pero el\n"
                             "orden firmado es pleno limpio → debut → mercado)[/dim]")
                with Horizontal(id="botones_bolsa"):
                    yield Button("Cerrar", id="bolsa_cerrar", variant="primary")
            return
        import subprocess
        try:                                               # regenerar = leer y pesar (N3, rápido)
            subprocess.run(["python3", os.path.join(BASE, "valorar_empresa.py"), "--grupo"],
                           capture_output=True, text=True, timeout=30,
                           env={**os.environ, "MOSAIC_BASE": BASE}, cwd=BASE)
        except Exception:                                  # noqa: BLE001
            pass                                           # si falla, se pinta el último ranking
        lineas, gen = _bolsa_lineas()
        with Vertical(id="caja_bolsa"):
            yield Label("[b]💹 BOLSA DEL GRUPO[/b] [dim]· valor DERIVADO (fórmula abierta: "
                        "data/formula_valor.yaml) · el ranking PROPONE, tú decides · Esc cierra[/dim]")
            with VerticalScroll(id="cards_bolsa"):
                yield Static("\n".join(lineas))
            yield Static(f"[dim]generado {gen} · sin actas = «sin cotizar» (jamás cero inventado) · "
                         "quiebra = CRAG bajo suelo 2 actas · fundar: ./crear_empresa.sh[/dim]")
            with Horizontal(id="botones_bolsa"):
                yield Button("Cerrar", id="bolsa_cerrar", variant="primary")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(None)


def _persona_de(rol):
    """[P] · el bloque persona del yaml de un rol (dict, {} si no hay)."""
    try:
        import yaml
        d = yaml.safe_load(open(os.path.join(TURNOS_DIR, f"{rol}.yaml"), encoding="utf-8")) or {}
        return d.get("persona") or {}
    except Exception:                                      # noqa: BLE001
        return {}


def _persona_guardar(rol, campos):
    """[P] · escribe SOLO el bloque `persona:` — CIRUGÍA DE TEXTO (handoff Opus 14:39):
    comentarios y NÚCLEO intactos, sin sed -i. Guardia EN el código: backup previo →
    recorta/inserta el bloque → tmp+replace → VERIFICA (parsea Y el núcleo no cambió:
    rol/firma/tipo_reporte/nivel/nivel_acceso); si la verificación falla, RESTAURA el
    backup. Devuelve (ok, mensaje). Helper puro: testeable sin TUI."""
    import re
    import shutil
    import yaml
    ruta = os.path.join(TURNOS_DIR, f"{rol}.yaml")
    if not os.path.isfile(ruta):
        return False, f"no existe la silla: {rol}"
    try:
        antes = yaml.safe_load(open(ruta, encoding="utf-8")) or {}
    except Exception as e:                                 # noqa: BLE001
        return False, f"el yaml de {rol} ya no parsea ({e}) — no toco nada"
    nucleo = {k: antes.get(k) for k in ("rol", "firma", "tipo_reporte", "nivel", "nivel_acceso")}
    bkdir = os.path.join(BASE, "trash", "backups")
    os.makedirs(bkdir, exist_ok=True)
    bak = os.path.join(bkdir, f"{rol}.yaml.{time.strftime('%Y%m%d_%H%M%S')}.panelP.bak")
    shutil.copy2(ruta, bak)
    lines = open(ruta, encoding="utf-8").read().splitlines(keepends=True)
    ini = next((i for i, l in enumerate(lines) if re.match(r"^persona:\s*$", l)), None)
    if ini is not None:                                    # recortar el bloque viejo (solo él)
        fin = ini + 1
        while fin < len(lines) and (not lines[fin].strip() or lines[fin][0] in " \t"):
            fin += 1
        del lines[ini:fin]
    else:
        ini = len(lines)
        if lines and lines[-1].strip():
            lines.append("\n")
    bloque = ["persona:\n"]
    for k in ("nombre_humano", "alias", "emoji", "tono", "bio"):
        v = str(campos.get(k) or "").strip()
        if v:                                              # json.dumps = escalar entrecomillado yaml-válido
            bloque.append(f"  {k}: {json.dumps(v, ensure_ascii=False)}\n")
    if len(bloque) > 1:
        lines[ini:ini] = bloque
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.replace(tmp, ruta)
    try:
        despues = yaml.safe_load(open(ruta, encoding="utf-8")) or {}
        assert {k: despues.get(k) for k in nucleo} == nucleo, "el NÚCLEO cambió"
    except Exception as e:                                 # noqa: BLE001
        shutil.copy2(bak, ruta)
        return False, f"verificación falló ({e}) — backup RESTAURADO, nada cambió"
    return True, f"persona de {rol} guardada (backup {os.path.basename(bak)})"


class PantallaPersona(ModalScreen):
    """[P] · QUIÉN ES cada uno (handoff Opus 14:39): la plantilla con su carácter.
    [E] = el TRABAJO (qué hace) · [P] = la PERSONA (nombre, cara, tono, bio).
    Devuelve ('editar', rol) | None. Las fichas completas quedan en el visor de atrás."""

    CSS = """
    PantallaPersona { align: center middle; }
    #caja_per { width: 96; height: auto; max-height: 92%; border: thick $accent;
                background: $surface; padding: 1 2; }
    #lista_per { height: auto; max-height: 16; border: solid $accent; padding: 0 1; margin: 1 0; }
    #botones_per { height: auto; align-horizontal: right; }
    #p_num { width: 8; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def compose(self) -> ComposeResult:
        self._indice = {}
        with Vertical(id="caja_per"):
            yield Label("[b]🪪 Persona — quién es cada uno[/b]  [dim]· el trabajo se edita en [E]; "
                        "aquí SOLO el carácter (núcleo inmutable) · Esc cierra[/dim]")
            with VerticalScroll(id="lista_per"):
                filas, n = [], 0
                try:
                    roles = sorted(f[:-5] for f in os.listdir(TURNOS_DIR) if f.endswith(".yaml"))
                except OSError:
                    roles = []
                for rol in roles:
                    per = _persona_de(rol)
                    n += 1
                    self._indice[str(n)] = rol
                    filas.append(f"  [{n}] {per.get('emoji', '🎭')} [b]{per.get('nombre_humano', '(sin nombre)')}[/b] "
                                 f"«{per.get('alias', '?')}» · {rol} · [dim]{str(per.get('tono', ''))[:46]}[/dim]")
                yield Static("\n".join(filas) or "[dim](sin sillas)[/dim]")
            yield Static("[dim]la ficha COMPLETA (trayectoria·credenciales·salud·red) está en el visor de atrás — "
                         "derivada por ficha.sh, cero segunda fuente de verdad[/dim]")
            with Horizontal(id="botones_per"):
                yield Button("Cerrar", id="p_cerrar")
                yield Input(placeholder="nº", id="p_num")
                yield Button("✏️ Personalizar nº", id="p_editar", variant="primary")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "p_editar":
            num = self.query_one("#p_num", Input).value.strip()
            rol = self._indice.get(num)
            if not rol:
                self.app.notify(f"nº inválido: «{num}» (1-{len(self._indice)})", severity="warning", timeout=5)
                return
            self.dismiss(("editar", rol))
            return
        self.dismiss(None)


class PantallaEditarPersona(ModalScreen):
    """[P] · editor del CARÁCTER de un rol: nombre_humano · alias · emoji · tono · bio.
    INMUTABLE desde aquí: rol · firma · tipo_reporte · nivel · nivel_acceso (el núcleo —
    misma salvaguarda que [E]; además _persona_guardar lo VERIFICA tras escribir).
    Devuelve ('guardar', rol, campos) | ('azar', rol) | None."""

    CSS = """
    PantallaEditarPersona { align: center middle; }
    #caja_ep { width: 92; height: auto; max-height: 92%; border: thick $success;
               background: $surface; padding: 1 2; }
    #botones_ep { height: auto; align-horizontal: right; margin-top: 1; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, rol):
        super().__init__()
        self._rol = rol
        self._per = _persona_de(rol)

    def compose(self) -> ComposeResult:
        p = self._per
        with Vertical(id="caja_ep"):
            yield Label(f"[b]🪪 Personalizar a «{self._rol}»[/b]  [dim]· Esc = atrás · núcleo INMUTABLE "
                        "(rol·firma·tipo·nivel·acceso) — solo cambia QUIÉN ES[/dim]")
            with Horizontal():
                yield Input(placeholder="nombre humano (ej: Mari José)", id="ep_nombre",
                            value=str(p.get("nombre_humano", "")))
                yield Input(placeholder="alias (ej: El Vigía)", id="ep_alias",
                            value=str(p.get("alias", "")))
                yield Input(placeholder="emoji", id="ep_emoji", value=str(p.get("emoji", "")))
            yield Input(placeholder="tono (ej: alerta; reporta salud y preocupación)", id="ep_tono",
                        value=str(p.get("tono", "")))
            yield Input(placeholder="bio (una frase)", id="ep_bio", value=str(p.get("bio", "")))
            yield Static("[dim]el carácter se ANTEPONE a su prompt en cada turno; su coletilla de "
                         "seguridad queda intacta (capa PERSONA 🎨 sobre NÚCLEO 🔒)[/dim]")
            with Horizontal(id="botones_ep"):
                yield Button("Cancelar", id="ep_cancelar")
                yield Button("🎲 Nombre al azar", id="ep_azar", variant="warning")
                yield Button("Guardar", id="ep_guardar", variant="success")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "ep_azar":
            self.dismiss(("azar", self._rol))
            return
        if ev.button.id != "ep_guardar":
            self.dismiss(None)
            return
        self.dismiss(("guardar", self._rol,
                      {"nombre_humano": self.query_one("#ep_nombre", Input).value,
                       "alias": self.query_one("#ep_alias", Input).value,
                       "emoji": self.query_one("#ep_emoji", Input).value,
                       "tono": self.query_one("#ep_tono", Input).value,
                       "bio": self.query_one("#ep_bio", Input).value}))


class PantallaFichaNoventera(ModalScreen):
    """[E]→🪪 · la FICHA estilo pantalla-de-creación-de-personaje 90s (mockup de Gustavo,
    campos REALES). Elegir agente → su ficha boxeada (PUESTO 🔒 + stats derivados honestos)
    → Personalizar (rutea al editor de persona que YA existe). Re-skin, no rebuild."""

    CSS = """
    PantallaFichaNoventera { align: center middle; }
    #caja_fn { width: 100; height: auto; max-height: 94%; border: double $accent;
               background: $surface; padding: 1 2; }
    #ficha_fn { height: auto; max-height: 22; border: round $accent; padding: 0 1; margin: 1 0; }
    #botones_fn { height: auto; align-horizontal: right; }
    #fn_num { width: 8; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, rol=None):
        super().__init__()
        try:
            self._roles = sorted(f[:-5] for f in os.listdir(TURNOS_DIR) if f.endswith(".yaml"))
        except OSError:
            self._roles = []
        self._rol = rol or (self._roles[0] if self._roles else None)

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_fn"):
            yield Label("[b]🪪 FICHA DEL EMPLEADO[/b] [dim]· estilo 90s · el PUESTO no se toca aquí "
                        "(cambiar de puesto = decisión de rango) · Esc cierra[/dim]")
            catalogo = " · ".join(f"[{i + 1}]{r}" for i, r in enumerate(self._roles))
            yield Static(catalogo or "[dim](sin sillas)[/dim]")
            with VerticalScroll(id="ficha_fn"):
                yield Static("\n".join(_ficha_noventera(self._rol)) if self._rol
                             else "[dim](sin sillas)[/dim]", id="fn_cuerpo")
            with Horizontal(id="botones_fn"):
                yield Button("Cerrar", id="fn_cerrar")
                yield Input(placeholder="nº ver", id="fn_num")
                yield Button("👁 Ver nº", id="fn_ver")
                yield Button("✏️ Personalizar", id="fn_editar", variant="primary")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "fn_ver":
            num = self.query_one("#fn_num", Input).value.strip()
            if num.isdigit() and 1 <= int(num) <= len(self._roles):
                self._rol = self._roles[int(num) - 1]
                self.query_one("#fn_cuerpo", Static).update("\n".join(_ficha_noventera(self._rol)))
            else:
                self.app.notify(f"nº inválido (1-{len(self._roles)})", severity="warning", timeout=5)
            return
        if ev.button.id == "fn_editar" and self._rol:
            self.dismiss(("editar", self._rol))
            return
        self.dismiss(None)


class PantallaHub(ModalScreen):
    """El PANEL noventero de pestañas MANUALES (fila de botones): consolida varias teclas en
    UNA (debate 5-jul: 12→8). No reconstruye nada — cada botón RUTEA a la pantalla que ya
    existe. Devuelve el id del destino elegido | None. Textual-mínimo: Button + Label."""

    CSS = """
    PantallaHub { align: center middle; }
    #caja_hub { width: 78; height: auto; border: double $accent; background: $surface; padding: 1 2; }
    #pestanas_hub { height: auto; align-horizontal: center; margin: 1 0; }
    Button { margin: 0 1; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, titulo, subtitulo, pestanas):
        super().__init__()
        self._titulo = titulo
        self._subtitulo = subtitulo
        self._pestanas = pestanas                          # [(id, etiqueta, variante), …]

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_hub"):
            yield Label(f"[b]{self._titulo}[/b]")
            yield Static(f"[dim]{self._subtitulo} · Esc = atrás[/dim]")
            with Horizontal(id="pestanas_hub"):
                for pid, etq, var in self._pestanas:
                    yield Button(etq, id=f"hub_{pid}", variant=var)
                # 🚪 SIEMPRE una salida visible (petición Gustavo 7-jul: «me quedo atrapado») —
                #    el Esc ya funcionaba, pero la puerta se tiene que VER.
                yield Button("← Atrás", id="hub__atras")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        bid = ev.button.id or ""
        if bid == "hub__atras":
            self.dismiss(None)
            return
        self.dismiss(bid[4:] if bid.startswith("hub_") else None)


class PantallaPerpetuo(ModalScreen):
    """[L]→♾️ · estado del PERPETUO + su encendido (con el prerrequisito de Opus a la vista) y
    el freno de mano (señal PARAR). El monitor no corre el bucle: lo LANZA (como [L]/[F]) y
    enseña el pid; matar/parar es por la SEÑAL, jamás kill desde aquí."""

    CSS = """
    PantallaPerpetuo { align: center middle; }
    #caja_pp { width: 84; height: auto; border: double $warning; background: $surface; padding: 1 2; }
    #botones_pp { height: auto; align-horizontal: right; margin-top: 1; }
    #pp_min { width: 16; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    @staticmethod
    def _estado():
        pidf = os.path.join(BASE, "data", ".perpetuo.pid")
        try:
            pid = int(open(pidf, encoding="utf-8").read().strip())
            os.kill(pid, 0)
            return f"[b green]♾️ ENCENDIDO[/] (PID {pid})"
        except (OSError, ValueError):
            return "[dim]apagado[/]"

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_pp"):
            yield Label("[b]♾️ PERPETUO — plenos «cada X» sin fin[/b]  [dim]· Esc = atrás[/dim]")
            yield Static(f"Estado: {self._estado()}")
            yield Static("[b yellow]⚠ Prerrequisito de Opus:[/] NO encender hasta que un pleno se lea "
                         "LIMPIO tras el fix del eco. Si no, es ruido perpetuo.")
            yield Static("[dim]freno de mano: touch data/senales/PARAR_PERPETUO (se consume con sello "
                         "de hora) · respeta pausa.flag del vigía · Ctrl+C también[/dim]")
            with Horizontal():
                yield Input(placeholder="cada N min (60)", id="pp_min")
                yield Static("[dim]arranca en 2º plano; míralo en [V]. Un pleno primero, ¿ya se lee bien?[/dim]")
            with Horizontal(id="botones_pp"):
                yield Button("Cerrar", id="pp_cerrar")
                yield Button("🛑 Frenar", id="pp_frenar", variant="error")
                yield Button("♾️ Encender", id="pp_encender", variant="warning")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "pp_encender":
            m = self.query_one("#pp_min", Input).value.strip()
            self.dismiss(("encender", m if m.isdigit() and m != "0" else ""))
        elif ev.button.id == "pp_frenar":
            self.dismiss(("frenar", ""))
        else:
            self.dismiss(None)


def _esc_lineas():
    """[T] · el libro de escalaciones, líneas legibles (helper puro: testeable sin TUI).
    SOLO LECTURA — el visor jamás resuelve: los agentes deciden en su turno, el humano
    con ./escalado.sh. Orden de cola: prioridad (urgente→baja) y antigüedad."""
    orden = {"urgente": 0, "alta": 1, "normal": 2, "baja": 3}
    icono = {"abierto": "🆕", "escalado": "📤", "en_revision": "👀", "resuelto": "✅",
             "denegado": "⛔", "esperando_sello": "🔏", "caducado": "🗄️"}
    try:
        ts = (json.load(open(ESCALACIONES, encoding="utf-8")) or {}).get("tickets") or []
    except Exception:
        ts = []
    ts.sort(key=lambda t: (orden.get(t.get("prioridad"), 9), t.get("ts", "")))
    lineas = []
    for t in ts:
        lineas.append(f"{icono.get(t.get('estado'), '·')} {t.get('id','?')} · {t.get('prioridad','?'):7} · "
                      f"{t.get('estado','?'):15} · en «{t.get('rango_actual','?')}» · "
                      f"{t.get('agente_origen','?')}(niv{t.get('nivel_agente','?')}) pide "
                      f"{t.get('herramienta','?')}(niv{t.get('nivel_requerido','?')}) · {t.get('ts','')[5:16]}")
    n_arch = 0
    try:
        with open(ESC_ARCHIVO, encoding="utf-8") as f:
            n_arch = sum(1 for l in f if l.strip())
    except OSError:
        pass
    return lineas, n_arch


class PantallaEscalaciones(ModalScreen):
    """[T] · la escalera de permisos EN VIVO (plan Opus 13:56): quién pide qué, en qué
    rango va, prioridad, estado. Igual que el libro de sellos: el TUI enseña, no toca."""

    CSS = """
    PantallaEscalaciones { align: center middle; }
    #caja_t { width: 100; height: auto; max-height: 90%; border: thick $accent;
              background: $surface; padding: 1 2; }
    #lista_t { height: auto; max-height: 24; border: solid $accent; padding: 0 1; margin: 1 0; }
    #botones_t { height: auto; align-horizontal: right; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def compose(self) -> ComposeResult:
        lineas, n_arch = _esc_lineas()
        with Vertical(id="caja_t"):
            yield Label("[b]🎫 Escalaciones[/b] · la escalera del organigrama: lead → manager → N1 → humano  "
                        "[dim]· Esc cierra[/dim]")
            with VerticalScroll(id="lista_t"):
                yield Static("\n".join(lineas) if lineas
                             else "[dim](libro vacío — nadie pide por encima de su rango)[/dim]")
            yield Static(f"[dim]archivo (caducados/viejos): {n_arch} · TTL {os.environ.get('MOSAIC_ESC_TTL_H', '48')}h · "
                         "resolver: los agentes EN SU TURNO · humano: ./escalado.sh conceder|denegar|escalar <id> · "
                         "nivel 5 → 🔏 esperando_sello (el doble sello es el último peldaño)[/dim]")
            with Horizontal(id="botones_t"):
                yield Button("Cerrar", id="t_cerrar", variant="primary")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(None)


class PantallaFlota(ModalScreen):
    """[F] · la FLOTA del grupo (spec Opus 11:55, luz verde 12:01): las 4 operaciones de
    lanzar_cluster (estado · subir · bajar · arrancar+supervisar), parametrizables
    (CLUSTER_ESPERA / SUPERVISA_CADA). El hierro es COMPARTIDO entre empresas: se muestra
    el claim global. Doctrina: NO 24B en la flota concurrente (off-loop es N1, otro carril).
    Devuelve {'op':…, 'espera':…, 'supervisa':…} o None. El Popen lo hace la App."""

    CSS = """
    PantallaFlota { align: center middle; }
    #caja_f { width: 88; height: auto; max-height: 92%; border: thick $warning;
              background: $surface; padding: 1 2; }
    #roster_f { height: auto; max-height: 12; border: solid $accent; padding: 0 1; margin: 1 0; }
    RadioSet { height: auto; }
    #botones_f { height: auto; align-horizontal: right; margin-top: 1; }
    #f_espera, #f_supervisa { width: 14; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    @staticmethod
    def _claim():
        try:
            partes = open(os.path.expanduser("~/.mosaic/flota_de"), encoding="utf-8").read().split()
            return partes[0] if partes else ""
        except OSError:
            return ""

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_f"):
            duena = self._claim()
            estado_claim = (f"[red]reclamada por {os.path.basename(duena)}[/]" if duena and duena != BASE
                            else "[green]de esta empresa[/]" if duena else "[dim]LIBRE[/]")
            yield Label(f"[b]🚀 Flota del grupo[/b]  · claim: {estado_claim}  "
                        f"[dim]· una empresa a la vez, las 2 máquinas JUNTAS · Esc cancela[/dim]")
            with VerticalScroll(id="roster_f"):
                try:
                    filas = []
                    for ln in open(SERVIDORES, encoding="utf-8"):
                        ln = ln.strip()
                        if not ln or ln.startswith("#"):
                            continue
                        p = ln.split("|")
                        if len(p) >= 5:
                            filas.append(f"  {p[0]:8} :{p[1]}  {p[2]:22} [{p[3]}]  {os.path.basename(p[4])[:34]}")
                    yield Static("\n".join(filas) or "(servidores.conf vacío)")
                except OSError:
                    yield Static("[dim](sin servidores.conf — hereda o crea uno)[/dim]")
            with RadioSet(id="f_op"):
                yield RadioButton("estado — ¿qué hay arriba? (sonda el roster)", value=True)
                yield RadioButton("subir — levanta los FIJOS en orden (reclama la flota)")
                yield RadioButton("bajar — apagado ordenado mini→MacBook (libera la flota)")
                yield RadioButton("arrancar + supervisar — subir y quedarse vigilando (cortafuegos OOM)")
            with Horizontal():
                yield Input(placeholder="espera s (10)", id="f_espera")
                yield Input(placeholder="supervisa s (30)", id="f_supervisa")
                yield Static("[dim]⚔️ el 24B JAMÁS en la flota concurrente — off-loop = N1, otro carril[/dim]")
            with Horizontal(id="botones_f"):
                yield Button("Cancelar", id="f_cancelar")
                yield Button("Ejecutar", id="f_ejecutar", variant="warning")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id != "f_ejecutar":
            self.dismiss(None)
            return
        ops = ["estado", "subir", "bajar", "arrancar"]
        idx = self.query_one("#f_op", RadioSet).pressed_index or 0
        esp = self.query_one("#f_espera", Input).value.strip()
        sup = self.query_one("#f_supervisa", Input).value.strip()
        self.dismiss({"op": ops[idx],
                      "espera": esp if esp.isdigit() and esp != "0" else "",
                      "supervisa": sup if sup.isdigit() and sup != "0" else ""})


def _topologia_datos():
    """Lee gateway.py --topologia (JSON) — el mapa HONESTO de servidores. Sin flota arriba
    devuelve lo declarado con todo ⚫. Nunca peta la TUI: ante fallo, dict con 'error'."""
    try:
        r = subprocess.run(["python3", GATEWAY, "--topologia", "--json"],
                           capture_output=True, text=True, timeout=20, cwd=BASE,
                           env={**os.environ, "MOSAIC_BASE": BASE,
                                "ROUTER_SONDA_TIMEOUT": os.environ.get("ROUTER_SONDA_TIMEOUT", "0.6")})
        return json.loads(r.stdout or "{}") if r.returncode == 0 else {"error": (r.stderr or "gateway falló")[:300]}
    except Exception as e:                                  # noqa: BLE001
        return {"error": str(e)}


def _barra(usado, total, ancho=10):
    """Barra de carga honesta (RAM residente / presupuesto) — no un '% hack' inventado."""
    if not total:
        return "░" * ancho
    lleno = max(0, min(ancho, round(ancho * usado / total)))
    return "█" * lleno + "░" * (ancho - lleno)


def _mapa_topologia(d):
    """Compone el mapa noventero con caracteres de caja pesada — DATOS REALES (anti-humo):
    máquinas, modelos con sonda 🟢/⚫, tier/GB/oficio, carga = RAM residente/presupuesto."""
    if d.get("error"):
        return f"[red]⚠️ no pude leer la topología:[/red] {d['error']}\n[dim](¿existe gateway.py? ¿router.py + inventario?)[/dim]"
    lin = []
    lin.append("[b]🗺️  MAPA DE SERVIDORES · TOPOLOGÍA (fusión GATEWAY+ROUTER)[/b]")
    lin.append("[dim]─────────────────────────────────────────────────────────────[/dim]")
    modo = d.get("modo_actual", "?")
    lin.append(f" 🚪 [b]GATEWAY-ROUTER[/b] ─── modo ACTUAL: [b yellow]{modo}[/b yellow] "
               f"─── [dim]una boca: intención→modelo→flota[/dim]")
    lin.append(" [dim]│[/dim]")
    nodos = d.get("nodos", {})
    maqs = list(nodos)
    for mi, (maq, n) in enumerate(nodos.items()):
        rama = "└──" if mi == len(maqs) - 1 else "├──"
        emoji = "💻" if maq == "macbook" else "⚙️"
        usado, pres = n.get("usado_gb", 0), n.get("presupuesto_gb", 0)
        lin.append(f" [dim]{rama}[/dim] {emoji} [b]{maq.upper()}[/b]  [dim]{n.get('host','?')}[/dim]  "
                   f"RAM [green]{_barra(usado, pres)}[/green] {usado:.0f}/{pres}GB")
        pad = "      " if mi == len(maqs) - 1 else " [dim]│[/dim]    "
        modelos = n.get("modelos", [])
        for si, m in enumerate(modelos):
            sub = "┗━" if si == len(modelos) - 1 else "┣━"
            punto = "[green]🟢[/green]" if m.get("vivo") else "[dim]⚫[/dim]"
            ofi = ",".join(m.get("oficios", [])[:2]) or "?"
            estilo = "" if m.get("vivo") else "dim"
            texto = (f"{sub} {punto} :{m.get('puerto','?'):<5} {m.get('modelo','?'):<24} "
                     f"[{m.get('tier','?')} {m.get('gb',0)}GB] · {ofi}")
            lin.append(pad + (f"[{estilo}]{texto}[/{estilo}]" if estilo else texto))
        lin.append(" [dim]│[/dim]" if mi < len(maqs) - 1 else "")
    lin.append("[dim]─────────────────────────────────────────────────────────────[/dim]")
    modos = d.get("modos_disponibles", {})
    lin.append(" [b]MODOS[/b] (Σ RAM · bocas):")
    for k, v in modos.items():
        marca = "[b yellow]▶[/b yellow]" if k == modo else " "
        lin.append(f"  {marca} [b]{k:<12}[/b] {v.get('gb',0):>5}GB · {v.get('bocas',0)} bocas · [dim]{v.get('descripcion','')[:44]}[/dim]")
    return "\n".join(lin)


def _sellos_lineas():
    """[O] · el libro de acciones, legible (helper puro). Estados con color: propuesta=ámbar
    (espera triaje) · auditada=cian · lista=verde · ejecutada=verde-b · vetada=roja."""
    col = {"propuesta": "yellow", "auditada": "cyan", "lista": "green",
           "ejecutada": "bold green", "vetada": "red"}
    try:
        libro = json.load(open(os.path.join(BASE, "data", "acciones.json"), encoding="utf-8")) or {}
    except Exception:                                      # noqa: BLE001
        return [], []
    lineas, ids = [], []
    for i, a in enumerate(libro.get("acciones", []), 1):
        ids.append(a.get("id", "?"))
        sellos = ",".join(s.get("rol", "?") for s in a.get("sellos", [])) or "—"
        c = col.get(a.get("estado"), "white")
        lineas.append(f" [{i}] [{c}]{a.get('estado','?'):9}[/] {a.get('id','?')} · sellos[{sellos}] · "
                      f"{str(a.get('titulo',''))[:44]}")
    return lineas, ids


class PantallaSellos(ModalScreen):
    """[O] · EL DESPACHO DE SELLOS (encargo Gustavo 7-jul, tras la auditoría de higiene):
    ver las peticiones del libro de acciones y ESTAMPAR desde el monitor — sellar (humano),
    vetar con motivo, o archivar la propuesta huérfana. TODO pasa por sellar.sh (el único
    escritor del libro): este panel es la ventanilla, jamás la pluma. El sello del AUDITOR
    no se estampa aquí: es de la sesión de Opus (doctrina: el humano firma DESPUÉS)."""

    CSS = """
    PantallaSellos { align: center middle; }
    #caja_o { width: 96; height: auto; max-height: 92%; border: double $warning;
              background: $surface; padding: 1 2; }
    #libro_o { height: auto; max-height: 14; border: solid $accent; padding: 0 1; margin: 1 0; }
    #salida_o { height: auto; max-height: 8; border: solid $accent; padding: 0 1; margin: 1 0; }
    #botones_o { height: auto; align-horizontal: right; }
    #o_num { width: 8; }
    #o_motivo { width: 42; }
    Button { margin-left: 1; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def compose(self) -> ComposeResult:
        lineas, self._ids = _sellos_lineas()
        with Vertical(id="caja_o"):
            yield Label("[b]🖋️ Despacho de sellos[/b] [dim]· el libro de acciones · humano firma "
                        "DESPUÉS del auditor · Esc = atrás[/dim]")
            with VerticalScroll(id="libro_o"):
                yield Static("\n".join(lineas) or "[dim](libro vacío — ninguna Acción registrada)[/dim]",
                             id="o_libro")
            with VerticalScroll(id="salida_o"):
                yield Static("[dim](elige nº y una acción: el resultado de sellar.sh sale aquí)[/dim]",
                             id="o_salida")
            with Horizontal():
                yield Input(placeholder="nº", id="o_num")
                yield Input(placeholder="motivo (para vetar/archivar)", id="o_motivo")
            with Horizontal(id="botones_o"):
                yield Button("← Atrás", id="o_cerrar")
                yield Button("👁 Ver", id="o_ver")
                yield Button("🗄️ Archivar", id="o_archivar")
                yield Button("⛔ Vetar", id="o_vetar", variant="error")
                yield Button("✅ Sellar (humano)", id="o_sellar", variant="success")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def _run_sellar(self, args):
        import subprocess
        try:
            r = subprocess.run(["bash", os.path.join(BASE, "sellar.sh"), *args],
                               capture_output=True, text=True, errors="replace",
                               timeout=30, cwd=BASE, env={**os.environ, "MOSAIC_BASE": BASE})
            return (r.stdout + r.stderr).strip() or "(sin salida)"
        except Exception as e:                             # noqa: BLE001
            return f"⚠️ no pude invocar sellar.sh: {e}"

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        bid = ev.button.id or ""
        if bid in ("o_cerrar", ""):
            self.dismiss(None)
            return
        num = self.query_one("#o_num", Input).value.strip()
        if not (num.isdigit() and 1 <= int(num) <= len(self._ids)):
            self.app.notify(f"nº inválido (1-{len(self._ids)})", severity="warning", timeout=5)
            return
        acc = self._ids[int(num) - 1]
        motivo = self.query_one("#o_motivo", Input).value.strip()
        if bid == "o_ver":
            out = self._run_sellar(["ver", acc])
        elif bid == "o_sellar":
            out = self._run_sellar([acc, "humano", motivo or "ok desde [O]"])
        elif bid == "o_vetar":
            if not motivo:
                self.app.notify("vetar exige MOTIVO (escríbelo en el campo)", severity="warning", timeout=6)
                return
            out = self._run_sellar([acc, "humano", "--veto", motivo])
        elif bid == "o_archivar":
            out = self._run_sellar(["archivar", acc, motivo or "archivada desde [O]"])
        else:
            return
        self.query_one("#o_salida", Static).update(out[:1200])
        lineas, self._ids = _sellos_lineas()               # el libro, repintado tras el gesto
        self.query_one("#o_libro", Static).update("\n".join(lineas) or "[dim](libro vacío)[/dim]")


class PantallaTopologia(ModalScreen):
    """[G] · el MAPA DE SERVIDORES (fusión GATEWAY+ROUTER · encargo Gustavo 7-jul). Datos
    HONESTOS de gateway.py --topologia: las 2 máquinas, sus modelos con sonda viva, tier/GB/
    oficio, carga real (RAM residente/presupuesto) y el modo actual + los modos disponibles.
    Levantar un modo → enseña el PLAN (nace apagado: router/gateway planifican, no ejecutan).
    Ejecutar el cambio es del [F] Flota / gesto humano. Devuelve None (solo-lectura + plan)."""

    CSS = """
    PantallaTopologia { align: center middle; }
    #caja_g { width: 92; height: auto; max-height: 94%; border: thick $accent;
              background: $surface; padding: 1 2; }
    #mapa_g { height: auto; max-height: 14; border: solid $accent; padding: 0 1; margin: 1 0; }
    #plan_g { height: auto; max-height: 8; border: solid $warning; padding: 0 1; margin: 1 0; }
    #modos_g { height: auto; max-height: 8; border: solid $accent; padding: 0 1; }
    RadioSet { height: auto; }
    #botones_g { height: auto; align-horizontal: right; margin-top: 1; }
    Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar"), ("r", "refrescar", "Refrescar")]

    def compose(self) -> ComposeResult:
        self._datos = _topologia_datos()
        with Vertical(id="caja_g"):
            yield Label("[b]🗺️ Mapa de servidores[/b]  [dim]· fusión gateway+router · R refresca · Esc cierra[/dim]")
            with VerticalScroll(id="mapa_g"):
                yield Static(_mapa_topologia(self._datos), id="mapa_static")
            yield Label("[dim]Ver el PLAN de un modo (bajar/subir exactos · NO ejecuta — el cambio es [F]/gesto humano):[/dim]")
            # 🎛️ los 6 modos SIEMPRE alcanzables (fix Gustavo 7-jul: el mapa a 26 líneas
            #    RECORTABA los 2 últimos — orquesta_v5 y nuclear quedaban fuera de pantalla).
            #    Scroll propio + mapa compactado: en terminales bajas se llega a todo.
            modos = list(self._datos.get("modos_disponibles", {})) or ["orquesta"]
            with VerticalScroll(id="modos_g"):
                with RadioSet(id="g_modo"):
                    for i, k in enumerate(modos):
                        yield RadioButton(k, value=(i == 0))
            with VerticalScroll(id="plan_g"):
                yield Static("[dim](elige un modo y pulsa «Ver plan»)[/dim]", id="plan_static")
            with Horizontal(id="botones_g"):
                yield Button("Cerrar", id="g_cerrar")
                yield Button("Ver plan", id="g_plan", variant="primary")

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def action_refrescar(self) -> None:
        self._datos = _topologia_datos()
        self.query_one("#mapa_static", Static).update(_mapa_topologia(self._datos))

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id != "g_plan":
            self.dismiss(None)
            return
        try:
            rs = self.query_one("#g_modo", RadioSet)
            modo = str(rs.pressed_button.label) if rs.pressed_button else "orquesta"
        except Exception:                                  # noqa: BLE001
            modo = "orquesta"
        try:
            r = subprocess.run(["python3", GATEWAY, "--levantar", modo],
                               capture_output=True, text=True, timeout=25,
                               cwd=BASE, env={**os.environ, "MOSAIC_BASE": BASE})
            d = json.loads(r.stdout or "{}")
        except Exception as e:                             # noqa: BLE001
            d = {"ok": False, "motivo": str(e)}
        if not d.get("ok"):
            txt = f"[red]☢️/guardia:[/red] {d.get('motivo','?')}"
        else:
            p = d.get("plan", {})
            ram = " · ".join(f"{k} {v}GB" for k, v in p.get("ram_por_maquina", {}).items())
            bajar = "\n".join(f"  [red]↓[/red] {b}" for b in p.get("bajar", [])) or "  [dim](nada que bajar)[/dim]"
            subir = "\n".join(f"  [green]↑[/green] {s}" for s in p.get("subir", [])) or "  [dim](ya residente)[/dim]"
            txt = (f"[b]{modo}[/b] · RAM: {ram}  [dim](nace apagado: PLAN, no manos)[/dim]\n{bajar}\n{subir}")
        self.query_one("#plan_static", Static).update(txt)


class Consola(App):
    """Consola de la mesa: visor epistolar + dashboard + [R] reporte + [A] archivar + [L] lanzar
    + [S] compartir (packs de máscara: exportar/importar) + [E] empleados (plantilla de agentes)
    + [F] flota del grupo + [Q] cierre inteligente."""

    TITLE = "MOSAIC · Consola de Operaciones Epistolar"
    # 🖥️ tema CRT noventero (debate 5-jul): fósforo verde sobre negro + ámbar de acento.
    #    Es SOLO piel — colores; ni un motor tocado. Se apaga con env MOSAIC_TUI_CRT=0.
    _CRT = os.environ.get("MOSAIC_TUI_CRT", "1") != "0"
    CSS = ("""
    $accent: #00cc66; $surface: #001a0d; $panel: #002814;
    Screen { background: #001108; color: #33ff88; }
    Header, Footer { background: #002814; color: #ffb000; }
    """ if _CRT else "") + """
    #cuerpo { height: 1fr; }
    #visor { width: 70%; padding: 0 1; }
    #dash  { width: 30%; border-left: solid $accent; padding: 0 1; }
    #consola { height: 14; border-top: solid $accent; padding: 0 1; }
    .expandida #cuerpo  { display: none; }
    .expandida #consola { height: 1fr; }
    """
    # 🕹️ consolidación noventera FASE 2 (DISEÑO_TUI de Opus + carta 18:40): los WORKSPACES.
    #    [M] MESA absorbe Cartas+Debrief+Reportar+Archivar · [E] EMPRESA (plantilla/ficha/
    #    tickets/bolsa) · [L] MOTOR (lanzar/flota/perpetuo) · [A] AGENDA (el eje del tiempo,
    #    read-only) · [V] vivo · [S] compartir · [Q]. Las teclas viejas (c/d/r/p/t/f) siguen
    #    VIVAS como alias ocultos — ⚠️ la única que CAMBIA de dueño es [A]: era Archivar,
    #    ahora Agenda (Archivar vive en [M], como manda el diseño).
    BINDINGS = [
        ("m", "mesa", "Mesa"),
        ("e", "empresa", "Empresa"),
        ("l", "motor", "Motor"),
        ("p", "parlamento", "Parlamento"),
        ("a", "agenda", "Agenda"),
        ("v", "ciclo_vivo", "Vivo ⇕"),
        ("g", "topologia", "🗺️ Mapa"),
        ("o", "sellos", "🖋️ Sellos"),
        ("s", "compartir", "Compartir"),
        ("q", "quit", "Salir"),
        Binding("c", "ver_cartas", "Cartas", show=False),
        Binding("d", "ver_debrief", "Debrief", show=False),
        Binding("r", "reportar", "Reportar", show=False),
        Binding("t", "escalaciones", "Tickets", show=False),
        Binding("f", "flota", "Flota", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.fuente_md = DEBRIEF_MD          # qué enseña la zona A
        self._mt = {}                        # mtimes vistos (refresco reactivo barato)
        self._log_off = 0                    # hasta dónde leímos el log vivo (cola incremental)
        self._proc_lanzado = None            # el Popen vivo de [L]/[S] — para poder COSECHARLO (zombi)
        self._proc_flota = None              # el Popen vivo de [F] — mismo patrón poll-primero

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="raiz"):
            with Horizontal(id="cuerpo"):
                with VerticalScroll(id="visor"):
                    yield Markdown(_leer_md(self.fuente_md), id="md")
                with VerticalScroll(id="dash"):
                    yield Static(_dashboard(ESTADO), id="estado")
            # R2-extra (Gustavo): consola plegable del CICLO EN VIVO — [V] la expande a pantalla
            yield RichLog(id="consola", wrap=False, max_lines=3000, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        self._mt = {ESTADO: _mtime(ESTADO), self.fuente_md: _mtime(self.fuente_md)}
        rl = self.query_one("#consola", RichLog)
        rl.write(Text.from_markup("[dim]— ciclo en vivo · [b]V[/b] expande/pliega · esperando logs/ciclo_vivo.log —[/]"))
        self._regar_log(inicial=True)
        self.set_interval(1.0, self.refrescar)   # 1 stat/s por fichero; re-render SOLO si cambió

    def refrescar(self) -> None:
        me = _mtime(ESTADO)
        if me != self._mt.get(ESTADO):
            self._mt[ESTADO] = me
            self.query_one("#estado", Static).update(_dashboard(ESTADO))
        mm = _mtime(self.fuente_md)
        if mm != self._mt.get(self.fuente_md):
            self._mt[self.fuente_md] = mm
            self._pintar_md()
        self._regar_log()

    def _regar_log(self, inicial=False) -> None:
        """Cola INCREMENTAL del log vivo: lee solo lo nuevo desde el offset; si el fichero
        encogió (mosaic.sh lo trunca al arrancar un ciclo), reinicia — 'el ciclo ACTUAL'."""
        try:
            tam = os.path.getsize(CICLO_LOG)
        except OSError:
            return
        rl = self.query_one("#consola", RichLog)
        if tam < self._log_off:                       # truncado → ciclo nuevo
            rl.clear()
            rl.write(Text.from_markup("[dim]— ciclo NUEVO detectado —[/]"))
            self._log_off = 0
        if inicial and self._log_off == 0 and tam > CICLO_TAIL_BYTES:
            self._log_off = tam - CICLO_TAIL_BYTES    # al abrir: solo la cola reciente
        if tam == self._log_off:
            return
        try:
            with open(CICLO_LOG, "rb") as f:
                f.seek(self._log_off)
                trozo = f.read(tam - self._log_off)
            self._log_off = tam
        except OSError:
            return
        for ln in trozo.decode("utf-8", errors="ignore").splitlines():
            ln = ln.replace("\r", "")
            if ln.strip():
                rl.write(Text.from_ansi(ln))          # respeta los COLORES del ciclo (script -q los guarda)

    def _pintar_md(self) -> None:
        contenido = (_leer_cartas_cola(CARTAS) if self.fuente_md == CARTAS
                     else _leer_md(self.fuente_md))
        self.query_one("#md", Markdown).update(contenido)

    def _bloqueo_mini(self, que="Esa acción") -> bool:
        """🖥️ Línea roja del debate (Sombra 11:32, decisión #4): el MINI JAMÁS escribe en el
        epistolar/sellos/máscara — se deposita SIEMPRE en el cerebro (el MacBook). En modo
        mini toda tecla de escritura avisa y no hace nada. True = bloqueada (el llamante corta)."""
        if ES_MINI:
            self.notify(f"{que} escribe en el epistolar — DESACTIVADA en el mini (worker de solo "
                        "lectura). Deposita desde el MacBook (el cerebro documental).",
                        title="🖥️ modo mini · read-only", severity="warning", timeout=8)
            return True
        return False

    def action_ver_debrief(self) -> None:
        self.fuente_md = DEBRIEF_MD
        self._mt[self.fuente_md] = _mtime(self.fuente_md)
        self._pintar_md()

    def action_ver_cartas(self) -> None:
        self.fuente_md = CARTAS
        self._mt[self.fuente_md] = _mtime(self.fuente_md)
        self._pintar_md()

    def action_ciclo_vivo(self) -> None:
        """[V]: la consola del ciclo pasa de plegada (14 líneas) a pantalla completa, y vuelta."""
        self.query_one("#raiz", Vertical).toggle_class("expandida")

    def action_reportar(self) -> None:
        """R3 · [R]: formulario → reportar.sh (cerrojo + append íntegro) → el visor se
        refresca SOLO (ya vigila el mtime de CARTAS). El humano jamás toca el fichero."""
        if self._bloqueo_mini("Reportar"):
            return
        def al_cerrar(datos) -> None:
            if not datos:
                return
            import subprocess
            r = subprocess.run(
                ["bash", REPORTAR, datos["tipo"], datos["titulo"], datos["cuerpo"],
                 datos["etiquetas"], os.environ.get("REPORTAR_AUTOR", "Gustavo")],
                capture_output=True, text=True, errors="replace", timeout=15,
                env={**os.environ, "MOSAIC_BASE": BASE, "CARTAS_MD": CARTAS})
            if r.returncode == 0:
                self.notify(f"📋 {datos['tipo']} «{datos['titulo']}» depositado en la mesa.",
                            severity="information")
                self.action_ver_cartas()          # salta al epistolar: tu carta, ya dentro
            else:
                self.notify(f"reportar.sh falló: {(r.stderr or r.stdout).strip()[:120]}",
                            title="Reporte NO depositado", severity="error", timeout=10)
        self.push_screen(PantallaReporte(), al_cerrar)

    def action_archivar(self) -> None:
        """R4 · [A]: dry-run del motor (seguro, solo lee) → modal con el plan → confirmación
        explícita → --aplicar (o --forzar). El motor de Opus pone backup, cerrojo y atomicidad."""
        if self._bloqueo_mini("Archivar"):
            return
        import subprocess
        entorno = {**os.environ, "MOSAIC_BASE": BASE, "CARTAS_MD": CARTAS}
        try:
            dry = subprocess.run(["bash", ARCHIVADO], capture_output=True, text=True,
                                 errors="replace", timeout=30, env=entorno)
            plan = (dry.stdout + dry.stderr).strip()
        except Exception as e:                                    # noqa: BLE001 — el plan nunca rompe la consola
            plan = f"(no pude pedir el plan: {e})"
        try:
            kb = os.path.getsize(CARTAS) // 1024
        except OSError:
            kb = 0

        def al_cerrar(decision) -> None:
            if not decision:
                return
            args = ["bash", ARCHIVADO, "--aplicar"] + (["--forzar"] if decision == "forzar" else [])
            r = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=60, env=entorno)
            cola_out = (r.stdout + r.stderr).strip().splitlines()
            ultima = cola_out[-1] if cola_out else "(sin salida)"
            if r.returncode == 0:
                self.notify(f"🗄️ {ultima[:140]}", title="Archivado", severity="information", timeout=8)
                self.action_ver_cartas()          # el CARTAS nuevo (con resumen ejecutivo), a la vista
            else:
                self.notify(f"archivado falló: {ultima[:140]}", title="Archivado NO aplicado",
                            severity="error", timeout=10)
        self.push_screen(PantallaArchivado(plan, kb), al_cerrar)

    def _lanzamiento_vivo(self):
        """¿Hay ya un lanzamiento nuestro corriendo? Devuelve el PID o None.
        🧟 LECCIÓN (Gustavo, 4-jul): el hijo terminado queda ZOMBI hasta que el padre (este
        monitor) lo cosecha — y os.kill(zombi, 0) responde 'vivo' → el guard se congelaba para
        SIEMPRE tras acabar un turno. Por eso: si tenemos el objeto Popen, poll() (que además
        COSECHA al zombi) es la verdad; el pidfile+kill queda para monitor REABIERTO (ahí el
        hijo se reparenta a init, que sí lo cosecha — cero zombis posibles)."""
        if self._proc_lanzado is not None:
            if self._proc_lanzado.poll() is None:          # sigue corriendo de verdad
                return self._proc_lanzado.pid
            self._proc_lanzado = None                      # terminó: cosechado por poll()
            try:
                os.remove(LANZADOR_PID)
            except OSError:
                pass
            return None
        try:
            pid = int(open(LANZADOR_PID).read().strip())
            os.kill(pid, 0)                    # señal 0 = ¿existe? (no mata)
            return pid
        except (OSError, ValueError):
            return None

    def action_lanzar(self) -> None:
        """R4 · [L]: puente de mando. Guard de UN lanzamiento (pidfile) → formulario →
        Popen FIRE-AND-FORGET a ciclo_vivo.log (la Vista 3 lo tailea). Args de LISTA, jamás
        shell=True (la lección de reportar.sh). El monitor no espera: sigue reactivo."""
        if self._bloqueo_mini("Lanzar"):
            return
        vivo = self._lanzamiento_vivo()
        if vivo:
            self.notify(f"Ya hay un lanzamiento corriendo (PID {vivo}). Espera o mátalo antes de otro.",
                        title="Un lanzamiento a la vez", severity="warning", timeout=8)
            return

        def al_cerrar(orden) -> None:
            if not orden:
                return
            import subprocess
            env = {**os.environ, "MOSAIC_BASE": BASE, "MOSAIC_WORKERS": str(orden.get("workers", 4))}
            if orden["rama"] in ("A", "B"):                # flags del formulario → env (lista CERRADA, defaults reales)
                env["CASCADA_BG"] = "1" if orden.get("cascada", True) else "0"
                env["MOSAIC_ESCALADA"] = "1" if orden.get("escalada", True) else "0"
                env["DEBRIEF"] = "1" if orden.get("debrief", True) else "0"
                env["MOSAIC_GOBERNADOR"] = "1" if orden.get("gobernador", True) else "0"
                env["MOSAIC_BAJAR_AL_ACABAR"] = "1" if orden.get("bajar", True) else "0"
                env["MOSAIC_FNC"] = "1" if orden.get("fnc", False) else "0"
                env["MOSAIC_JUECES"] = orden.get("jueces", "2")
                if not orden.get("pipeline", True):
                    env["PIPELINE"] = "0"                  # auto por defecto; el checkbox solo lo APAGA
            if orden["rama"] == "C":                       # 🪑 turnos de la ORQUESTA — rutas acotadas
                sel = orden.get("turno", "portavoz")
                if "PLENO" in sel:
                    args = ["bash", PLENO_SH]              # todas las sillas, mismo motor, cadencia intacta
                    desc = "🏛️ PLENO de la orquesta"
                elif sel.startswith("portavoz"):
                    args = ["bash", AUTODIAGNOSIS]         # SOLO mosaic.sh→reportar.sh dentro (permiso acotado)
                    desc = "🪑 turno de MOSAIC (portavoz)"
                else:
                    rol = sel.split(" ")[0].strip()        # la etiqueta empieza por el rol (validado en el motor)
                    args = ["bash", TURNO_ROL, rol]
                    desc = f"🎭 turno de {rol}"
            elif orden["rama"] == "B":                     # la MÁSCARA sobre el modelo elegido
                env["MOSAIC_LLM_BASE_URL"] = orden["url"]
                env["MOSAIC_LLM_MODEL"] = orden["modelo"]
                args = ["bash", MOSAIC_SH, orden["consulta"]]     # consulta como ARGUMENTO de lista
                desc = f"máscara · {orden['modelo']} · «{orden['consulta'][:40]}»"
            else:                                          # Rama A · un modo
                args = ["bash", MOSAIC_SH, orden["modo"]]
                if orden["modo"] in ("ciclo", "aprender"):
                    args.append(orden["tandas"])
                desc = f"{orden['modo']} {orden.get('tandas','') if orden['modo'] in ('ciclo','aprender') else ''}".strip()
            try:
                logf = open(CICLO_LOG, "ab")              # la Vista 3 ([V]) ya tailea este fichero
                proc = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, cwd=BASE, env=env,
                                        start_new_session=True)   # fire-and-forget: no cuelga la TUI
                logf.close()                      # el hijo tiene su dup; cerramos el nuestro (no fugar fd)
                self._proc_lanzado = proc         # guardamos el objeto: poll() cosechará al zombi
                with open(LANZADOR_PID, "w") as f:
                    f.write(str(proc.pid))
                self.notify(f"🚀 lanzado: {desc} (PID {proc.pid}) → míralo abajo con [V]",
                            title="Puente de mando", severity="information", timeout=8)
                if not self.query_one("#raiz", Vertical).has_class("expandida"):
                    self.query_one("#raiz", Vertical).add_class("expandida")   # expande el ciclo en vivo
            except Exception as e:                          # noqa: BLE001
                self.notify(f"no pude lanzar: {e}", title="Lanzamiento fallido",
                            severity="error", timeout=10)
        self.push_screen(PantallaLanzar(), al_cerrar)

    def action_compartir(self) -> None:
        """[S] COMPARTIR (rework 7-jul · ANDAMIO): hub «la puerta hacia fuera y al grupo».
        Pestañas: Máscara (packs, YA vive) · Máquinas (la federación) · Público (repo a GitHub) ·
        Blueprint (la estructura). Las 3 nuevas en «próximamente» honesto — el motor de cada una YA
        existe (empaquetar/exportar_publico/servidores.conf), falta cablearlo aquí en pasos siguientes.
        RE-SKIN: no toca motores, yaml ni sellos. Nada aquí añade MANOS."""
        def tras_hub(dest) -> None:
            if dest == "mascara":
                self._compartir_mascara()
            else:
                nombre = {"maquinas": "🖧 Máquinas (federación · el grupo)",
                          "publico": "🌐 Repo público (a GitHub, saneado)",
                          "blueprint": "📐 Blueprint (organigrama sin máscara)"}.get(dest, dest)
                self.notify(f"{nombre} — próximamente. El rework de [S] está en curso (andamio hoy); "
                            "el motor ya existe, falta cablearlo a esta pestaña.",
                            title="🚧 en construcción", severity="information", timeout=7)
        self.push_screen(PantallaHub(
            "📡 COMPARTIR — la puerta hacia fuera y al grupo",
            "Máscara (packs curados+saneados) · Máquinas (el grupo) · Público (repo a GitHub) · Blueprint (la estructura)",
            [("mascara", "📦 Máscara", "primary"),
             ("maquinas", "🖧 Máquinas", "default"),
             ("publico", "🌐 Público", "default"),
             ("blueprint", "📐 Blueprint", "default")]), tras_hub)

    def _compartir_mascara(self) -> None:
        """[S]▸Máscara: compartir la máscara. EXPORTAR = empaquetar.sh (dry → PLAN con redacciones PII →
        --aplicar, rápido y local) y ofrecer Finder/Mail (`open -a Mail` = borrador con adjunto).
        IMPORTAR = importar.sh (dry → PLAN → la ADUANA con --aplicar va LENTA porque piensa la
        defensa → Popen fire-and-forget a ciclo_vivo.log, como [L], con el mismo guard pidfile).
        Las lecciones de siempre: args de LISTA jamás shell=True · errors=replace · DEVNULL."""
        if self._bloqueo_mini("Compartir la máscara"):     # la máscara/packs viven en el cerebro
            return
        import subprocess
        entorno = {**os.environ, "MOSAIC_BASE": BASE}

        def exportar(dominio) -> None:
            try:
                dry = subprocess.run(["bash", EMPAQUETAR, dominio], capture_output=True, text=True,
                                     errors="replace", timeout=30, env=entorno)
                plan = (dry.stdout + dry.stderr).strip()
            except Exception as e:                            # noqa: BLE001 — el plan nunca rompe la consola
                plan = f"(no pude pedir el plan: {e})"

            def al_confirmar(ok) -> None:
                if not ok:
                    return
                r = subprocess.run(["bash", EMPAQUETAR, dominio, "--aplicar"], capture_output=True,
                                   text=True, errors="replace", timeout=60, env=entorno)
                salida = (r.stdout + r.stderr).strip()
                rel = next((ln.split("pack creado: ", 1)[1].split(" ")[0]
                            for ln in salida.splitlines() if "pack creado: " in ln), "")
                if r.returncode == 0 and rel:
                    ruta = rel if os.path.isabs(rel) else os.path.join(BASE, rel)

                    def al_enviar(via) -> None:
                        if not via:
                            return
                        args = ["open", "-R", ruta] if via == "finder" else ["open", "-a", "Mail", ruta]
                        try:                                   # `open` es de macOS: instantáneo, no bloquea
                            subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, start_new_session=True)
                        except Exception as e:                 # noqa: BLE001
                            self.notify(f"no pude abrir {via}: {e}", severity="error", timeout=8)
                    self.push_screen(PantallaEnviar(os.path.basename(ruta)), al_enviar)
                else:
                    ultima = salida.splitlines()[-1] if salida else "(sin salida)"
                    self.notify(f"empaquetar falló: {ultima[:140]}", title="NO exportado",
                                severity="error", timeout=10)
            self.push_screen(PantallaPlan(f"📦 Exportar máscara «{dominio}»", plan, "Empaquetar",
                                          "curada+saneada · PII redactada arriba · packs/ queda fuera del repo"),
                             al_confirmar)

        def importar(ruta) -> None:
            try:
                dry = subprocess.run(["bash", IMPORTAR, ruta], capture_output=True, text=True,
                                     errors="replace", timeout=30, env=entorno)
                plan = (dry.stdout + dry.stderr).strip()
            except Exception as e:                            # noqa: BLE001
                plan = f"(no pude pedir el plan: {e})"

            def al_confirmar(ok) -> None:
                if not ok:
                    return
                vivo = self._lanzamiento_vivo()
                if vivo:                                       # la aduana usa la flota: una cosa gorda a la vez
                    self.notify(f"Ya hay un lanzamiento corriendo (PID {vivo}). La aduana espera su turno.",
                                title="Un lanzamiento a la vez", severity="warning", timeout=8)
                    return
                try:
                    logf = open(CICLO_LOG, "ab")               # la Vista 3 ([V]) ya tailea este fichero
                    proc = subprocess.Popen(["bash", IMPORTAR, ruta, "--aplicar"], stdout=logf,
                                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                            cwd=BASE, env=entorno, start_new_session=True)
                    logf.close()                               # el hijo tiene su dup (no fugar fd)
                    self._proc_lanzado = proc                  # para cosechar al zombi (poll)
                    with open(LANZADOR_PID, "w") as f:
                        f.write(str(proc.pid))
                    self.notify(f"🛃 aduana en marcha: {os.path.basename(ruta)} (PID {proc.pid}) → míralo con [V]. "
                                "SEGURO=entra con prior · DUDOSO/TRAMPA=se queda fuera.",
                                title="Importando", severity="information", timeout=10)
                    if not self.query_one("#raiz", Vertical).has_class("expandida"):
                        self.query_one("#raiz", Vertical).add_class("expandida")
                except Exception as e:                          # noqa: BLE001
                    self.notify(f"no pude lanzar la aduana: {e}", title="Import fallido",
                                severity="error", timeout=10)
            self.push_screen(PantallaPlan(f"🛃 Importar «{os.path.basename(ruta)}»", plan, "Importar (ADUANA)",
                                          "defensa.py dicta: solo SEGURO entra · fichero aparte · prior ≤0.60 · sin pisar nada"),
                             al_confirmar)

        def al_cerrar(orden) -> None:
            if not orden:
                return
            if orden["rama"] == "E":
                exportar(orden["dominio"])
            else:
                importar(orden["ruta"])
        self.push_screen(PantallaCompartir(), al_cerrar)

    def _flota_arriba(self):
        """¿Servidores del roster respondiendo? Sonda barata a <url>/models (timeout 3s).
        Un 4xx también cuenta como VIVO: respondió = está arriba."""
        import urllib.error
        import urllib.request
        vivos = []
        for etq, url, _n in _roster_base():
            try:
                urllib.request.urlopen(url.rstrip("/") + "/models", timeout=3)
                vivos.append(etq)
            except urllib.error.HTTPError:
                vivos.append(etq)
            except Exception:                              # noqa: BLE001 — caído/inalcanzable: no está
                continue
        return vivos

    def action_quit(self) -> None:
        """[Q] inteligente (spec Opus 18:37): sin nada vivo → sal directo. Con lanzamiento o
        flota arriba → modal; DEFAULT «solo salir» preserva TODO (el resume que le gusta a
        Gustavo). Matar = killpg del grupo propio (start_new_session). Bajar = reusa el
        apagado ordenado de lanzar_cluster.sh (mini verificado → MacBook). Args de LISTA."""
        pid = self._lanzamiento_vivo()
        flota = self._flota_arriba()
        if not pid and not flota:
            self.exit()
            return

        def al_cerrar(decision) -> None:
            if not decision:
                return
            if decision == "matar" and pid:
                import signal
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)  # grupo PROPIO (start_new_session)
                except OSError as e:
                    self.notify(f"no pude matar el PID {pid}: {e}", severity="error", timeout=8)
                if self._proc_lanzado is not None:              # cosechar: que no quede ni el zombi
                    try:
                        self._proc_lanzado.wait(timeout=5)
                    except Exception:                           # noqa: BLE001 — salir jamás se cuelga
                        pass
                    self._proc_lanzado = None
                try:
                    os.remove(LANZADOR_PID)
                except OSError:
                    pass
            elif decision == "bajar":
                import subprocess
                try:                                       # bloquea unos s AL SALIR (aceptable): apagado en orden
                    subprocess.run(["bash", LANZAR_CLUSTER, "bajar"], capture_output=True,
                                   text=True, errors="replace", timeout=180)
                except Exception as e:                     # noqa: BLE001 — salir jamás se queda colgado
                    self.notify(f"el bajar falló: {e}", severity="error", timeout=8)
            self.exit()
        self.push_screen(PantallaSalir(pid, flota), al_cerrar)

    def action_empleados(self) -> None:
        """[E] · plantilla de agentes (idea del Nuevo): lista de sillas + ALTA. El alta
        escribe roles/turnos/<rol>.yaml — LA fuente única — y con el yaml nace la
        identidad (reportar.sh acepta las firmas de los yamls). El monitor no lanza
        nada desde aquí: los turnos se lanzan desde [L]."""
        if self._bloqueo_mini("Alta/edición de empleados"):
            return
        def tras_alta(datos) -> None:
            if not datos:
                self.push_screen(PantallaEmpleados(), tras_lista)
                return
            try:
                import shutil
                import yaml
                ruta = os.path.join(TURNOS_DIR, f"{datos['rol']}.yaml")
                if datos.get("editar"):
                    # EDICIÓN: backup obligatorio + preservar claves que el panel no toca
                    bkdir = os.path.join(BASE, "trash", "backups")
                    os.makedirs(bkdir, exist_ok=True)
                    shutil.copy2(ruta, os.path.join(
                        bkdir, f"{datos['rol']}.yaml.{time.strftime('%Y%m%d_%H%M%S')}.panelE.bak"))
                    d = yaml.safe_load(open(ruta, encoding="utf-8")) or {}
                    d.update({"departamento": datos["departamento"], "puertos": datos["puertos"],
                              "max_c": datos["max_c"], "activo": 1 if datos["activo"] else 0,
                              "cadencia_s": datos["cadencia_s"], "prompt": datos["prompt"],
                              "nivel_acceso": datos.get("nivel_acceso", 1),
                              "lecturas": datos["lecturas"]})
                    accion_txt = "editado (backup en trash/backups)"
                else:
                    d = {"rol": datos["rol"], "firma": f"MOSAIC-{datos['rol']}",
                         "departamento": datos["departamento"], "nivel": datos["nivel"],
                         "nivel_acceso": datos.get("nivel_acceso", 1),
                         "tipo_reporte": datos["tipo"], "etiquetas": f"turno {datos['rol']}",
                         "puertos": datos["puertos"], "max_c": datos["max_c"], "por_lectura_c": 2000,
                         "activo": 1 if datos["activo"] else 0, "cadencia_s": datos["cadencia_s"],
                         "prompt": datos["prompt"] + "\nPalabra, JAMÁS manos: solo describes y "
                                   "propones; no ejecutas nada. Si un registro está vacío o no se ve, "
                                   "dilo sin inventar. Máximo ~250 palabras.",
                         "lecturas": datos["lecturas"]}
                    # 🪪 PASO 3 (handoff Opus 14:39): nace CON CARA — [P] la afina, bautizar la nombra
                    per = datos.get("persona") or {}
                    d["persona"] = {k: v for k, v in {
                        "nombre_humano": per.get("nombre_humano", ""),
                        "alias": per.get("alias") or f"El {datos['rol']}",
                        "emoji": "🎭",
                        "tono": per.get("tono") or "profesional y honesto",
                        "bio": f"Silla {datos['nivel']} del departamento {datos['departamento']}."}.items() if v}
                    accion_txt = "dado de alta"
                os.makedirs(TURNOS_DIR, exist_ok=True)
                tmp = ruta + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write("# 🎭 ROL gestionado desde [E] (monitor) — palabra, jamás manos.\n")
                    yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)
                os.replace(tmp, ruta)
                if not datos.get("editar") and not (datos.get("persona") or {}).get("nombre_humano"):
                    # nombre vacío → 🎲 bautizo automático (el MISMO motor de Opus, cero duplicar pool)
                    import subprocess
                    try:
                        subprocess.run(["bash", BAUTIZAR_SH, datos["rol"]], cwd=BASE,
                                       env={**os.environ, "MOSAIC_BASE": BASE},
                                       capture_output=True, text=True, timeout=30)
                    except Exception:                      # noqa: BLE001
                        pass                               # sin bautizo no se cae un alta
                faltan = [l for l in datos["lecturas"] if not os.path.isfile(os.path.join(BASE, l))]
                aviso = f" · ⚠️ lecturas que hoy NO existen (se saltarán): {', '.join(faltan)}" if faltan else ""
                self.notify(f"🧑‍💼 {d.get('firma', datos['rol'])} {accion_txt}{aviso}",
                            title="Plantilla", severity="information", timeout=10)
            except Exception as e:                          # noqa: BLE001
                self.notify(f"no pude escribir el yaml: {e}", title="Guardado fallido", severity="error", timeout=10)
            self.push_screen(PantallaEmpleados(), tras_lista)

        def tras_lista(decision) -> None:
            if decision == "nuevo":
                self.push_screen(PantallaAltaEmpleado(), tras_alta)
            elif isinstance(decision, tuple) and decision[0] == "editar":
                self.push_screen(PantallaAltaEmpleado(editar_rol=decision[1]), tras_alta)
        self.push_screen(PantallaEmpleados(), tras_lista)

    def action_flota(self) -> None:
        """[F] · la flota del grupo (spec Opus): 4 operaciones de lanzar_cluster, knobs por env,
        fire-and-forget a ciclo_vivo.log (la [V] lo tailea), guard de UNA operación a la vez
        (objeto Popen + poll-primero, la lección del zombi; entre sesiones guarda el CLAIM
        global, no este monitor). El monitor jamás toca procesos: lanzar_cluster.sh es el
        único con manos sobre la flota."""
        if self._bloqueo_mini("Operar la flota"):          # el mini no orquesta el hierro del cerebro
            return
        vivo = None
        if self._proc_flota is not None:
            if self._proc_flota.poll() is None:
                vivo = self._proc_flota.pid
            else:
                self._proc_flota = None
        if vivo:
            self.notify(f"Ya hay una operación de flota corriendo (PID {vivo}) — mírala con [V].",
                        title="Una operación a la vez", severity="warning", timeout=8)
            return

        def al_cerrar(orden) -> None:
            if not orden:
                return
            import subprocess
            env = {**os.environ, "MOSAIC_BASE": BASE, "MOSAIC_DIR": BASE}
            if orden["espera"]:
                env["CLUSTER_ESPERA"] = orden["espera"]
            if orden["supervisa"]:
                env["SUPERVISA_CADA"] = orden["supervisa"]
            args = ["bash", LANZAR_CLUSTER] + ([] if orden["op"] == "arrancar" else [orden["op"]])
            try:
                logf = open(CICLO_LOG, "ab")
                proc = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, cwd=BASE, env=env,
                                        start_new_session=True)
                logf.close()
                self._proc_flota = proc
                self.notify(f"🚀 flota · {orden['op']} (PID {proc.pid}) → míralo abajo con [V]",
                            title="Flota del grupo", severity="information", timeout=8)
                if not self.query_one("#raiz", Vertical).has_class("expandida"):
                    self.query_one("#raiz", Vertical).add_class("expandida")
            except Exception as e:                          # noqa: BLE001
                self.notify(f"no pude operar la flota: {e}", title="Flota", severity="error", timeout=10)
        self.push_screen(PantallaFlota(), al_cerrar)

    def action_escalaciones(self) -> None:
        """[T] · el libro de escalaciones (plan Opus 13:56) — SOLO LECTURA, como el resto
        del visor: los agentes resuelven en su turno; el humano, con ./escalado.sh."""
        self.push_screen(PantallaEscalaciones())

    def _fichas_al_visor(self) -> None:
        """[P] · hook de Opus (14:27): ficha.sh --todos → data/fichas_ultimo.md → visor."""
        import subprocess
        try:
            out = subprocess.run(["bash", FICHA_SH, "--todos"], cwd=BASE,
                                 env={**os.environ, "MOSAIC_BASE": BASE},
                                 capture_output=True, text=True, errors="replace", timeout=30).stdout
            with open(FICHAS_MD, "w", encoding="utf-8") as f:
                f.write("# 🪪 Fichas de identidad de la plantilla\n\n```\n" + (out or "(sin fichas)") + "\n```\n")
            self.fuente_md = FICHAS_MD
            self._mt[self.fuente_md] = _mtime(self.fuente_md)
            self._pintar_md()
        except Exception as e:                             # noqa: BLE001
            self.notify(f"no pude generar las fichas: {e}", severity="error", timeout=8)

    def action_persona(self) -> None:
        """[P] · PERSONA (handoff Opus 14:39): fichas DERIVADAS al visor + PERSONALIZAR
        el carácter. División: [E] = el TRABAJO (qué hace) · [P] = QUIÉN ES (nombre, cara,
        tono, bio). El guardado es cirugía SOLO del bloque persona (núcleo verificado)."""
        if self._bloqueo_mini("Personalizar"):
            return
        self._fichas_al_visor()

        def tras_editor(res) -> None:
            if not res:
                self.push_screen(PantallaPersona(), tras_lista)
                return
            if res[0] == "azar":
                import subprocess
                try:
                    r = subprocess.run(["bash", BAUTIZAR_SH, res[1]], cwd=BASE,
                                       env={**os.environ, "MOSAIC_BASE": BASE},
                                       capture_output=True, text=True, errors="replace", timeout=30)
                    self.notify("🎲 " + ((r.stdout or r.stderr or "bautizado").strip().splitlines()[-1][:110]),
                                title="Bautizo", severity="information", timeout=6)
                except Exception as e:                     # noqa: BLE001
                    self.notify(f"no pude bautizar: {e}", severity="error", timeout=8)
                self._fichas_al_visor()
                self.push_screen(PantallaEditarPersona(res[1]), tras_editor)
                return
            ok, msg = _persona_guardar(res[1], res[2])
            self.notify(("🪪 " if ok else "⚠️ ") + msg,
                        severity="information" if ok else "error", timeout=8)
            self._fichas_al_visor()
            self.push_screen(PantallaPersona(), tras_lista)

        def tras_lista(res) -> None:
            if isinstance(res, tuple) and res[0] == "editar":
                self.push_screen(PantallaEditarPersona(res[1]), tras_editor)
        self.push_screen(PantallaPersona(), tras_lista)

    def _abrir_editor_persona(self, rol, al_volver=None) -> None:
        """Editor de persona REUSABLE (lo llaman [P] y la ficha noventera): 🎲 bautiza o
        guarda por cirugía verificada, refresca las fichas del visor, y al cerrar llama a
        `al_volver` (para volver a la ficha desde donde se abrió). Cero lógica nueva."""
        def tras_editor(res) -> None:
            if not res:
                if al_volver:
                    al_volver()
                return
            if res[0] == "azar":
                import subprocess
                try:
                    r = subprocess.run(["bash", BAUTIZAR_SH, res[1]], cwd=BASE,
                                       env={**os.environ, "MOSAIC_BASE": BASE},
                                       capture_output=True, text=True, errors="replace", timeout=30)
                    self.notify("🎲 " + ((r.stdout or r.stderr or "bautizado").strip().splitlines()[-1][:110]),
                                title="Bautizo", severity="information", timeout=6)
                except Exception as e:                     # noqa: BLE001
                    self.notify(f"no pude bautizar: {e}", severity="error", timeout=8)
                self._fichas_al_visor()
                self.push_screen(PantallaEditarPersona(res[1]), tras_editor)
                return
            ok, msg = _persona_guardar(res[1], res[2])
            self.notify(("🪪 " if ok else "⚠️ ") + msg,
                        severity="information" if ok else "error", timeout=8)
            self._fichas_al_visor()
            if al_volver:
                al_volver()
        self.push_screen(PantallaEditarPersona(rol), tras_editor)

    def action_empresa(self) -> None:
        """[E] EMPRESA (debate 5-jul, 12→8): panel de pestañas que consolida Empleados +
        Persona + Tickets. Re-skin: cada pestaña RUTEA a la pantalla que YA existe."""
        def tras_ficha(res) -> None:
            if isinstance(res, tuple) and res[0] == "editar":
                self._abrir_editor_persona(res[1], al_volver=abrir_ficha)
            else:
                self.action_empresa()                      # volver al hub

        def abrir_ficha() -> None:
            self._fichas_al_visor()
            self.push_screen(PantallaFichaNoventera(), tras_ficha)

        def tras_hub(dest) -> None:
            if dest == "plantilla":
                self.action_empleados()
            elif dest == "ficha":
                abrir_ficha()
            elif dest == "solicitudes":
                self.action_escalaciones()
            elif dest == "bolsa":
                self.push_screen(PantallaBolsa())
        self.push_screen(PantallaHub(
            "🏙️ EMPRESA — la plantilla y su gente",
            "Plantilla (el TRABAJO) · Ficha 90s (QUIÉN ES) · Solicitudes (tickets) · Bolsa (el grupo)",
            [("plantilla", "👥 Plantilla", "primary"),
             ("ficha", "🪪 Ficha 90s", "success"),
             ("solicitudes", "🎫 Solicitudes", "default"),
             ("bolsa", "💹 Bolsa", "warning")]), tras_hub)

    def action_motor(self) -> None:
        """[L] MOTOR (debate 5-jul, 12→8): panel que consolida Lanzar + Flota + Perpetuo.
        Re-skin: cada pestaña RUTEA al motor que YA existe (o al perpetuo, apagado)."""
        def tras_hub(dest) -> None:
            if dest == "lanzar":
                self.action_lanzar()
            elif dest == "flota":
                self.action_flota()
            elif dest == "perpetuo":
                self.action_perpetuo()
            elif dest == "mapa":
                self.action_topologia()
        self.push_screen(PantallaHub(
            "⚙️ MOTOR — arrancar, flota, mapa y perpetuo",
            "Lanzar (un modo/squad) · Flota (subir/bajar) · 🗺️ Mapa (topología+modos) · ♾️ Perpetuo",
            [("lanzar", "🚀 Lanzar", "primary"),
             ("flota", "🛰️ Flota", "warning"),
             ("mapa", "🗺️ Mapa", "primary"),
             ("perpetuo", "♾️ Perpetuo", "default")]), tras_hub)

    def action_topologia(self) -> None:
        """[G] MAPA (fusión gateway+router · 7-jul): la topología de servidores con datos
        reales (modelos vivos, carga, modo actual) + el plan de cada modo. Solo-lectura."""
        self.push_screen(PantallaTopologia())

    def action_mesa(self) -> None:
        """[M] MESA (DISEÑO_TUI · workspace leer/escribir): Cartas · Debrief · Reportar ·
        Archivar · Vivo. Hub que RUTEA a las acciones que ya existían — cero rebuild."""
        def tras_hub(dest) -> None:
            if dest == "cartas":
                self.action_ver_cartas()
            elif dest == "debrief":
                self.action_ver_debrief()
            elif dest == "reportar":
                self.action_reportar()
            elif dest == "archivar":
                self.action_archivar()
            elif dest == "vivo":
                self.action_ciclo_vivo()
        self.push_screen(PantallaHub(
            "📬 MESA — leer y escribir el epistolar",
            "Cartas (la cola) · Debrief (el mapa del ciclo) · Reportar (escribir) · Archivar (rotar) · Vivo",
            [("cartas", "📬 Cartas", "primary"),
             ("debrief", "🧭 Debrief", "default"),
             ("reportar", "✍️ Reportar", "success"),
             ("archivar", "🗄️ Archivar", "warning"),
             ("vivo", "📟 Vivo", "default")]), tras_hub)

    def action_agenda(self) -> None:
        """[A] AGENDA (carta Opus 18:40) — el eje del TIEMPO, read-only: 3 capas sobre
        eventos reales fechados + lo prospectivo YA programado. Programar = el motor."""
        self.push_screen(PantallaAgenda())

    def action_sellos(self) -> None:
        """[O] · el DESPACHO DE SELLOS (encargo Gustavo 7-jul): ver el libro de acciones y
        estampar — sellar/vetar/archivar — por la ventanilla de sellar.sh (el único escritor)."""
        if self._bloqueo_mini("Sellar"):
            return
        self.push_screen(PantallaSellos())

    def action_parlamento(self) -> None:
        """[P] PARLAMENTO (propuesta Gustavo 5-jul) — chat con un empleado: su rango se
        inyecta (persona+prompt+lecturas, arreglo #3 de Opus: dueño del prompt), se registra
        en la agenda 🏢 y es reanudable. La persona se edita en [E]→Ficha; aquí se HABLA."""
        if self._bloqueo_mini("Hablar con un empleado"):
            return
        self.push_screen(PantallaParlamento())

    def action_perpetuo(self) -> None:
        """[L]→♾️ · encender/frenar el perpetuo (lo LANZA en 2º plano, como [L]; parar = SEÑAL)."""
        if self._bloqueo_mini("Encender el perpetuo"):
            return
        def al_cerrar(res) -> None:
            if not res:
                return
            import subprocess
            if res[0] == "encender":
                env = {**os.environ, "MOSAIC_BASE": BASE}
                if res[1]:
                    env["PLENO_CADA_MIN"] = res[1]
                try:
                    logf = open(CICLO_LOG, "ab")
                    subprocess.Popen(["bash", os.path.join(BASE, "perpetuo.sh"), "--si"],
                                     stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     cwd=BASE, env=env, start_new_session=True)
                    logf.close()
                    self.notify("♾️ perpetuo ENCENDIDO en 2º plano — míralo en [V] · freno: 🛑 Frenar",
                                title="Perpetuo", severity="warning", timeout=8)
                    if not self.query_one("#raiz", Vertical).has_class("expandida"):
                        self.query_one("#raiz", Vertical).add_class("expandida")
                except Exception as e:                     # noqa: BLE001
                    self.notify(f"no pude encender el perpetuo: {e}", severity="error", timeout=8)
            elif res[0] == "frenar":
                try:
                    os.makedirs(os.path.join(BASE, "data", "senales"), exist_ok=True)
                    open(os.path.join(BASE, "data", "senales", "PARAR_PERPETUO"), "w").write("frenar desde [L]\n")
                    self.notify("🛑 señal PARAR_PERPETUO puesta — parará tras el pleno en curso",
                                title="Perpetuo", severity="information", timeout=8)
                except OSError as e:
                    self.notify(f"no pude poner el freno: {e}", severity="error", timeout=8)
        self.push_screen(PantallaPerpetuo(), al_cerrar)


if __name__ == "__main__":
    Consola().run()
