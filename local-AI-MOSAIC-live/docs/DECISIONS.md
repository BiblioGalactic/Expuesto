# 🧭 DECISIONS — las decisiones de diseño y las trampas que nos las enseñaron

> Destilado del registro interno del proyecto (P8 del plan de mesa). Cada decisión viene con su
> POR QUÉ — casi siempre una trampa real que nos mordió primero. Se publica para que quien monte
> su propia orquesta local no pague la misma matrícula.

## Gobernanza

**Palabra, jamás manos.** Los agentes PROPONEN por escrito; ejecutar requiere doble sello
(auditor + humano) sobre una Acción con plantilla (Motivación/Cambios/Riesgos/Ficheros/
Reversibilidad). *Trampa que lo parió:* un agente con manos directas puede deshacer en un
minuto lo que costó semanas. El primer intento de sello se vetó porque el cuerpo era un eco
del prompt — el doble sello existe exactamente para eso.

**Nunca borrar.** Todo lo que sobra se mueve a una papelera interna (`trash/`) con rotación
comprimida; toda edición importante deja un `.bak` previo. *Por qué:* la reversibilidad barata
es la diferencia entre un susto y una catástrofe.

**El papel manda.** La fuente de verdad es el registro escrito (cartas/checklist), no la
memoria de la conversación. *Trampa:* el sesgo de recencia — el último mensaje pesaba más que
la orden vigente escrita, y así se violó una spec de flota.

**Cadencia bajo presión.** Mensaje en caliente → parar, releer el registro, UNA acción mínima
verificada. *Trampa:* acelerar cuando el humano se enfada multiplica el daño (un sprint fundió
la máquina de desarrollo).

## Arquitectura

**Fuente única para toda asignación.** Dos tablas paralelas (qué modelo sirve cada rol, qué
patrones se censuran) SIEMPRE divergen en silencio. Toda asignación vive en UN fichero de
configuración que los consumidores leen; el env manda encima para overrides. *Trampa:* la
misma lente juzgaba distinto según la puerta de entrada.

**Presupuesto de contexto determinista.** `max_tokens` no se adivina: se calcula por modelo
(ctx ÷ parallel − oxígeno − reserva de pensamiento del razonador) con el tokenizador del propio
servidor (`/tokenize`), y si el prompt no cabe se recortan lecturas (las más viejas primero) ANTES
de enviar. *Trampa:* pedir 3000 tokens de salida en una ventana de 4096 con un prompt de 2500 →
rechazo instantáneo → el agente «salía vacío» y parecía un bug del prompt.

**Los razonadores obligatorios piensan aparte.** Un modelo tipo R1 quema 1-3k tokens SOLO en
`<think>`; su presupuesto lleva reserva de pensamiento además de la salida, y una tijera con red
extrae la respuesta tras el pensamiento (jamás devolver vacío si el modelo habló).

**bash portable = bash 3.2.** El shell por defecto de macOS es bash 3.2: los heredoc dentro de
`$( )` o `< <( )` ROMPEN ahí. Regla: heredoc → `cat > fichero.py` plano y la sustitución sin
heredoc. Y bajo `set -e`, un `$( test && cmd )` cuyo test falla MATA el script: `|| true`.
*Trampa:* dos parches sucesivos fallaron antes de entender que el bug era de la CLASE entera.

**Anti-poisoning en la frontera.** Texto exterior no verificado (correo entrante) jamás dispara
herramientas ni concede permisos en el turno que lo leyó; la salida externa pasa un filtro de
fugas (secretos/PII) y el envío real siempre es gesto humano. Un desconocido no da órdenes:
se lee como material, no como mandato.

**Fail-closed y fallar ALTO.** Sin juez no hay veredicto SEGURO (la aduana rechaza); sin
patrones de censura no se exporta ni se empaqueta; una lente ciega jamás cuenta como análisis.
Los errores deben ser ruidosos, jamás silencio con pinta de éxito.

## Método

**Anti-humo.** Ninguna métrica se inventa: el valor deriva de medidas reproducibles y auditables
con `cat`. Si una señal satura (una nota 4/5 eterna), se cambia de instrumento, no de relato.

**Todo nace APAGADO.** Los bucles autónomos (perpetuo, vigilia productiva, envío de correo)
nacen con kill-switch y OFF por defecto; se encienden con un criterio firmado (N plenos limpios
seguidos), no con entusiasmo.

**El circuito entero, una vez, antes de construir encima.** La deriva favorita: diseñar la
siguiente pieza con la actual sin probar. La regla: cerrar el lazo (proponer → sellar →
ejecutar) aunque sea pequeño, y SOLO entonces ampliar.

**La memoria del proponedor.** Un agente que propone mejoras debe LEER su propio libro de
propuestas antes de hablar, o re-propondrá lo ya hecho (nos pasó: la segunda propuesta de la
historia duplicaba la primera — y el molde de su prompt anclaba al mismo tema con su ejemplo).
Los ejemplos de formato deben ser de OTRO dominio que el trabajo esperado.
