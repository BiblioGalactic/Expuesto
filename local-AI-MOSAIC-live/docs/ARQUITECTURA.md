# 🏗️ ARQUITECTURA — las 7 fases, la defensa y los packs

Los diagramas grandes viven en esta carpeta (`docs/`): el flujo de datos completo
(`mosaic_flujo_datos.svg`), la cascada de ingesta (`ingesta_despensa_y_cocina.svg` y
`arquitectura_inputs_unificada.svg`), la rama de seguridad (`rama_seguridad.svg`), el
ciclo por fases (`ciclo_completo_fases.svg`) y el ciclo de vida del dato
(`ciclo_vida_del_dato_reciclaje.svg`).

## Las fases, una a una

**FASE 0 · Flota.** El lanzador lee `servidores.conf`, presupuesta RAM por máquina,
levanta en orden SOLO lo caído y espera a que cada endpoint infiera. Al acabar el
ciclo, la flota se acuesta sola (el bucle continuo la mantiene entre vueltas).

**FASE 1 · Cascada anti-humo.** Las fuentes tienen prioridad y presupuesto: libro →
conversación → oráculo (crawler de código) → cuarentena → noticias → recuperación
(rescata los huecos peor puntuados: nada muere sin segunda oportunidad) → y SOLO al
final la fábrica de preguntas sintéticas (con contador de saltos y "ciclo de humo"
forzado si nunca dispara). Puerta común: memoria de vistos + dedup semántico (o léxico
si no hay torch). Invariantes heredados de un teorema-heurística propio: lotes primos,
suelo "nunca cero", cesión entre fuentes.

**FASE 2 · Banco → ejecución ‖ juicio.** Cola SQLite atómica; un discriminador arma el
lote (cupos por fuente + diversidad + envejecimiento). Pool de bocas first-to-finish
entre las dos máquinas; cada respuesta la puntúa el juez pequeño de la 2ª máquina EN
PARALELO (pipeline). La nota alimenta el CRAG (0-1), la señal honesta del sistema.

**FASE 3 · Tribunal adversarial.** Una muestra del lote pasa por fiscal/abogado/juez
(modelos distintos) en 2º plano. Detecta la complacencia del juez único.

**FASE 4 · Aprender.** Cada hueco (lo que el sistema no supo hacer) puede parir una
capacidad nueva: se genera, se cura (juez + poda + gobernanza), y entra a la biblioteca
con score que vivirá del uso. El A/B composición-vs-crudo mide si la máscara aporta.

**FASE 5 · Panel.** Tendencia (CRAG, resueltos, huecos nuevos, banco). La nota del juez
saturó — el panel lo dice en vez de maquillarlo.

**FASE 6 · Acta.** El ciclo se destila a sí mismo: JSON para la máquina + MD para
humanos. Solo tandas completas.

**FASE 7 · Gobernador (propiocepción).** Lee las N últimas actas y ajusta los mandos
del PRÓXIMO lanzamiento — valores acotados, con histéresis, y el porqué escrito. Firma
qué acta digirió (acuse de recibo verificable). `MOSAIC_GOBERNADOR=0` lo apaga.

## La defensa (código ajeno = no confiable)

Todo lo que viene de fuera (repos del oráculo, packs de máscara) pasa por la aduana:

- **4 lentes = 4 modelos distintos**: intención (¿cebo? ¿doble propósito?), código
  (red, eval/exec, exfiltración), adversarial (red-team profundo, puede pedir sandbox),
  y un juez de seguridad que funde veredictos: TRAMPA / SEGURO / DUDOSO.
- **Sandbox** de snippets autocontenidos (aislado, sin red, con timeout) — y el candado:
  si la adversarial pidió probar y NO se pudo observar, **jamás SEGURO** ("no observar
  ≠ limpio"). Fail-closed en todo el camino: sin veredicto = DUDOSO = no entra.
- Lo DUDOSO/TRAMPA no se tira: genera una propuesta de capacidad de *seguridad*
  (reconocer el patrón), que pasa por gobernanza humana.

## Los packs (máscara portátil)

`empaquetar.sh` exporta un dominio de la biblioteca como `packs/<dominio>_vN.mosaic`
(tar.gz: `manifest.json` con schema_version y roles requeridos · `capabilities.yaml`
con whitelist de 8 campos y PII redactada · `graph.json` con las sinergias aprendidas
intra-pack). `importar.sh` valida el schema con degradación elegante, pasa TODO por la
defensa, y funde sin pisar: fichero aparte, namespace de autor, prior indulgente.

El contrato es agnóstico de flota: el pack declara ROLES (no modelos); el importador
los mapea a su propia flota. La máscara viaja; los modelos y el corpus, jamás.

## El epistolar y la consola

El proyecto se gobierna por cartas (privadas) con escritor único (`reportar.sh`:
cerrojo + append atómico), archivado por rotación (`archivado.sh`) y una consola TUI
(`monitor.py`) que es visor + puente de mando. MOSAIC mismo tiene un turno de palabra
(`autodiagnosis.sh`): lee su estado compacto, opina y propone — con exactamente dos
rutas permitidas (componer texto, depositar UNA carta) y transparencia de receta
(con qué modelo y qué capacidades habló).

## La orquesta (agentes con silla, 5-jul)

Sobre ese molde de "turno de palabra" crece una plantilla entera. Cada silla es un yaml
declarativo (`roles/turnos/<rol>.yaml`: qué lee, qué reporta, con qué modelo candidato)
y `turno_rol.sh` es el motor GENÉRICO que la ejecuta: N sillas = N yamls, UNA fuente de
salvaguardas. Tres niveles según el organigrama (`roles/organigrama.yaml`): N1 dirección
(hoy, el humano) · N2 managers que razonan con modelo · N3 funcionarios deterministas
que dan *parte-de-estado* sin modelo (funcionan hasta con la flota abajo). `pleno.sh`
hace hablar a toda la orquesta de una orden.

Lo que la hace segura, por capas y todas EN el código:

- **Palabra, jamás manos:** toda silla propone; ejecutar exige el circuito de sellos
  (`reportar.sh` tipo Acción → `data/acciones.json` → `sellar.sh`, doble firma con el
  humano). Un ✅ en el texto vale cero.
- **Herramientas por contrato:** las tools (`tools/*.py`, registro `data/herramientas.yaml`)
  hablan JSON stdin→stdout y las despacha UN dispatcher (`herramientas.py`) — F1 es solo
  LECTURA (niveles 1-3); las manos (correo/mensajería, 4-5) están declaradas sin cmd.
- **Escalera de permisos:** pedir por encima de tu nivel no es un "no" — nace un ticket
  (`data/escalaciones.json`) con prioridad del agente y CADENA derivada del organigrama;
  sube solo hasta el primer rango capaz, que lo resuelve EN SU TURNO (conceder ejecuta,
  denegar con motivo, escalar sube otro peldaño); el nivel 5 termina siempre en sello
  humano y lo caducado se archiva, no se pierde. `escalado.sh` es el CLI; la tecla `[T]`
  del monitor, el visor.
- **Correo de entrada:** un router N3 determinista (`estafeta.py`) reparte a buzones por
  rol (`data/buzones/`), etiqueta TODO lo exterior como no-verificado, y rige el
  anti-poisoning: un turno que tragó buzón no ejecuta herramientas ni concede permisos.
  La salida (enviar) es fase-manos: espera el doble sello.
- **Persona ≠ núcleo:** cada agente tiene carácter editable (nombre, alias, tono — capa
  PERSONA, en el hub `[E]` Empresa, `ficha.sh`/`bautizar.sh`) separado del núcleo inmutable
  (rol, firma, nivel, acceso). El carácter se antepone a su prompt; su coletilla de seguridad
  queda intacta y el guardado verifica que el núcleo no cambió.

Todo el estado de la orquesta son ficheros json/yaml con lock — sin demonios, sin base
de datos nueva, legible con `cat` y auditable con `git diff`.

## La empresa: multi-instancia y economía

Sobre la orquesta crece una **empresa**, con dos capas más:

- **Multi-empresa:** `crear_empresa.sh` funda una instancia nueva — **N bases sobre UN motor** (el
  código se comparte por symlink: un fix mejora a todas), **una empresa a la vez** sobre la flota
  (candado global), **organigrama de andamio** (sillas por defecto) y **máscara SIEMPRE vacía** — una
  semilla ajena corrompería su CRAG: cada casa cultiva su propia tierra. Se opera con su `MOSAIC_BASE`
  propio y reusa la maquinaria del export (misma separación motor-vs-privado).

- **La empresa cotiza y acuña** (dos piezas N3 deterministas, cero LLM y cero red). `valorar_empresa.py`
  es un **ticker DERIVADO**: lee actas/capacidades/acciones/escalaciones y pesa con `data/formula_valor.yaml`
  (fórmula abierta, auditable con `cat`) — valor = CRAG × [capacidades + resueltos] + madurez (sillas
  debutadas, acciones selladas, tools conectadas). Sin actas **no cotiza** (jamás un cero inventado) y el
  ranking PROPONE, nadie ejecuta por cotización (anti-Goodhart). `banco_central.py` es una **casa de moneda
  respaldada por cómputo**: mide la capacidad de la flota y la acuña en un libro `data/tesoreria.jsonl`
  **append-only con hash encadenado** (alterar una línea rompe la cadena; un `verificar` fiscaliza). Ancla
  anti-fiat: no se emite más de lo que las dos máquinas computan. El banco propone, jamás mueve solo (asignar
  = Acción + doble sello) y no acuña hasta la primera Acción sellada.

- **Trato y vida diaria:** `parlamento.py` deja **hablar con un empleado por su rango** (tecla `[P]`; llamada
  directa a la flota con su identidad como system, sin el doble envoltorio del motor; anti-poisoning: el buzón
  exterior no entra al contexto; charla reanudable). La **agenda** (`[A]`) reúne en una vista de índice la vida
  privada y la empresarial. Y `perpetuo.sh` mantiene la casa despierta con plenos "cada X" — nace apagado, con
  freno de mano (`data/senales/PARAR_PERPETUO`) y respeto al vigía de RAM.

Todas estas capas — organigrama, tickets, ticker, tesorería, personas — son ficheros json/yaml con lock:
sin demonios, sin base de datos nueva, auditable con `git diff`.

## El router, el gateway y la federación

Sobre la flota crece la capa que lo conecta todo — y la que prepara la **federación** (varias máquinas
coordinadas sin servidor central):

- **El router (`router.py`) — el modelo justo, disponible.** Cinco capas apiladas que, al invocar a un empleado,
  eligen la boca: **oficio** (rol→oficio) → **talla** (cuánto pesa la tarea) → **contenido** (código/razonamiento
  añaden reservas) → **breaker** (dignidad por rol + **sonda de vivos** `/v1/models` + fallback ordenado) →
  **duelo** (solo en modo crítico; devuelve el plan, no ejecuta). Conoce 6 **modos de flota** como rosters
  (orquesta · director · enjambre · micro-masa · nuclear) y **cruza máquinas**: si el nodo local no puede con un
  oficio, mira si el otro está libre para delegarle, y si no, **baja de talla** en local. El catálogo vive en
  `data/inventario_modelos.yaml` (verdad de disco); la disponibilidad se sondea en vivo. Nace apagado (`ROUTER=1`);
  el modelo masivo (nuclear) jamás se enciende solo.

- **El gateway (`gateway.py`) — la boca única.** Una sola puerta que acepta entradas (una petición, un buzón, un
  empleado), decide en 3 capas (**intención** → **modelo** vía el router → **flota**) y devuelve la salida por
  donde toca (respuesta · buzón vía `estafeta` · carta vía `cartero`). Nace apagado y solo-interno: la salida
  externa exige gesto humano. Es la reimplementación mosaic-nativa de un router de modelos previo del autor.

- **La federación (el grupo de máquinas).** Dos máquinas (o N) se coordinan sin coordinador central: **SSH sin
  contraseña**, `servidores.conf` declara cada nodo y sus modelos, `chequeo_mini.sh` valida el enlace (SSH · deps ·
  disco compartido), y un **candado global** (`~/.mosaic/flota_de`) reparte el hierro — **una empresa a la vez**
  sobre la flota del grupo; si una cae, otra reclama. El pool de ejecución ya trabaja cruzando las dos GPUs
  (first-to-finish). Ésa es la base sobre la que se federan instancias.

La **fábrica** de la FASE 1 evolucionó a **destilería** (`destileria.py`): cuando la cascada real se agota, en vez
de inventar preguntas de humo, destila material propio ya visto (procedencia obligatoria) para ejercitar las
capacidades — el círculo hueco→capacidad apuntado al valor, no al relleno.
