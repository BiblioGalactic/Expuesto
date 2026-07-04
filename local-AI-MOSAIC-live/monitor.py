#!/usr/bin/env python3
# 🖥️ =====================================================================
# 🖥️ MONITOR — Consola de Operaciones Epistolar (RONDA 2 · esqueleto TUI).
# 🖥️   Zona A (izq. 70%): visor Markdown — debrief del ciclo o cola de CARTAS.
# 🖥️   Zona B (der. 30%): dashboard en vivo de data/estado_sistema.json.
# 🖥️   Footer: [D]ebrief · [C]artas · [V]ivo · [R]eportar · [A]rchivar · [L]anzar ·
# 🖥️           [S] compartir (packs de máscara: exportar/Finder/Mail · importar por ADUANA) · [Q] salir.
# 🖥️ El VISOR solo lee; las acciones escriben SIEMPRE por sus motores (reportar/archivado/
# 🖥️ empaquetar/importar.sh), jamás a mano desde aquí.
# 🖥️ Refresco REACTIVO barato: un stat/s por fichero (mtime); re-render solo si cambió.
# 🖥️ Requiere: pip install textual   (dependencia de TOOLING humano, bendecida en Ronda 2)
# 🖥️ Uso:  ./monitor.py     (q para salir · Ctrl+C también vale)
# 🖥️ =====================================================================
import json
import os
import sys
import time

BASE = os.environ.get("MOSAIC_BASE", os.path.dirname(os.path.abspath(__file__)))
ESTADO = os.path.join(BASE, "data", "estado_sistema.json")
DEBRIEF_MD = os.path.join(BASE, "data", "debrief_ultimo.md")
CARTAS = os.path.join(BASE, "info", "CARTAS.md")
CICLO_LOG = os.path.join(BASE, "logs", "ciclo_vivo.log")   # lo escribe mosaic.sh ciclo (script -q)
REPORTAR = os.path.join(BASE, "reportar.sh")               # R3: EL escritor seguro del epistolar
ARCHIVADO = os.path.join(BASE, "archivado.sh")             # R4: la rotación del epistolar (motor de Opus)
MOSAIC_SH = os.path.join(BASE, "mosaic.sh")                # R4-L: el motor (ya existe; el menú solo lo invoca)
AUTODIAGNOSIS = os.path.join(BASE, "autodiagnosis.sh")     # el TURNO de MOSAIC (propone-texto, permiso acotado)
EMPAQUETAR = os.path.join(BASE, "empaquetar.sh")           # [S]: exporta la máscara (curada+saneada) a packs/
IMPORTAR = os.path.join(BASE, "importar.sh")               # [S]: recibe un pack ajeno (ADUANA defensa.py)
SERVIDORES = os.path.join(BASE, "servidores.conf")        # roster para el selector de modelo (no hardcodear)
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
CARTAS_COLA_BYTES = 30000        # del epistolar solo la COLA (6000+ líneas enteras = visor lento)
CICLO_TAIL_BYTES = 8000          # al abrir: la cola reciente del log; luego, incremental

try:
    from rich.text import Text
    from textual.app import App, ComposeResult
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


def _dashboard(path):
    """El estado del sistema como markup de Rich — colores intuitivos (regla de Gustavo)."""
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
    L += ["", "[bold]métricas[/] [dim](espejo del acta)[/]",
          f" CRAG [bold]{m.get('crag','?')}[/] {flecha}{abs(delta) if delta else ''}",
          f" resueltos {m.get('resueltos','?')}/{m.get('ejecuciones','?')} · A/B "
          f"{(m.get('ab') or {}).get('a','?')}-{(m.get('ab') or {}).get('b','?')}-{(m.get('ab') or {}).get('empates','?')}",
          f" huecos +{m.get('huecos_nuevos','?')} ({m.get('huecos_total','?')} hist)"]
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
            yield Label(f"[b]🗄️ Archivar el epistolar[/b]  [dim]· CARTAS pesa {self._kb}KB (umbral {CARTAS_MAX_KB}KB)[/dim]")
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
    #consulta_ta { height: 6; margin: 1 0; }
    RadioSet { height: auto; }
    #botones_l { height: auto; align-horizontal: right; margin-top: 1; }
    Button { margin-left: 2; }
    .titulo { text-style: bold; margin-top: 1; }
    """
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def compose(self) -> ComposeResult:
        with Vertical(id="caja_l"):
            yield Label("[b]🚀 Puente de mando[/b]  [dim]· lanza sin salir de la consola · Esc cancela[/dim]")
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
            yield Label("Rama C · 🪑 el turno de MOSAIC (se autodiagnostica y postea a la mesa)", classes="titulo")
            yield Static("[dim]MOSAIC observa su estado y OPINA — propone-texto, no aplica. Su carta aparece en [C].[/dim]")
            with Horizontal(id="botones_l"):
                yield Button("Cancelar", id="l_cancelar")
                yield Button("🪑 Turno de MOSAIC", id="l_mosaic", variant="primary")
                yield Button("Lanzar", id="l_lanzar", variant="success")

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
        if ev.button.id == "l_mosaic":                     # Rama C · el turno de MOSAIC (autodiagnóstico)
            self.dismiss({"rama": "C"})
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
            yield Label(f"[b]✅ {self._nombre} creado en packs/[/b]")
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
            yield Label("[b]🚪 Salir del monitor[/b]  [dim]· hay trabajo vivo — tú decides qué pasa con él[/dim]")
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


class Consola(App):
    """Consola de la mesa: visor epistolar + dashboard + [R] reporte + [A] archivar + [L] lanzar
    + [S] compartir (packs de máscara: exportar/importar) + [Q] cierre inteligente."""

    TITLE = "MOSAIC · Consola de Operaciones Epistolar"
    CSS = """
    #cuerpo { height: 1fr; }
    #visor { width: 70%; padding: 0 1; }
    #dash  { width: 30%; border-left: solid $accent; padding: 0 1; }
    #consola { height: 14; border-top: solid $accent; padding: 0 1; }
    .expandida #cuerpo  { display: none; }
    .expandida #consola { height: 1fr; }
    """
    BINDINGS = [
        ("d", "ver_debrief", "Debrief"),
        ("c", "ver_cartas", "Cartas"),
        ("v", "ciclo_vivo", "Ciclo vivo ⇕"),
        ("r", "reportar", "Reportar"),
        ("a", "archivar", "Archivar"),
        ("l", "lanzar", "Lanzar"),
        ("s", "compartir", "Compartir"),
        ("q", "quit", "Salir"),
    ]

    def __init__(self):
        super().__init__()
        self.fuente_md = DEBRIEF_MD          # qué enseña la zona A
        self._mt = {}                        # mtimes vistos (refresco reactivo barato)
        self._log_off = 0                    # hasta dónde leímos el log vivo (cola incremental)
        self._proc_lanzado = None            # el Popen vivo de [L]/[S] — para poder COSECHARLO (zombi)

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
            if orden["rama"] == "C":                       # 🪑 el turno de MOSAIC — su propia ruta acotada
                args = ["bash", AUTODIAGNOSIS]             # SOLO mosaic.sh→reportar.sh dentro (permiso acotado)
                desc = "🪑 turno de MOSAIC (autodiagnóstico)"
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
        """[S]: compartir la máscara. EXPORTAR = empaquetar.sh (dry → PLAN con redacciones PII →
        --aplicar, rápido y local) y ofrecer Finder/Mail (`open -a Mail` = borrador con adjunto).
        IMPORTAR = importar.sh (dry → PLAN → la ADUANA con --aplicar va LENTA porque piensa la
        defensa → Popen fire-and-forget a ciclo_vivo.log, como [L], con el mismo guard pidfile).
        Las lecciones de siempre: args de LISTA jamás shell=True · errors=replace · DEVNULL."""
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


if __name__ == "__main__":
    Consola().run()
