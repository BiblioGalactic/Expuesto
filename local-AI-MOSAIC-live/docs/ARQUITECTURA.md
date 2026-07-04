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
