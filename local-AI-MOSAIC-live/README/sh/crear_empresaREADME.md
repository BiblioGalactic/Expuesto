# crear_empresa.sh

> 🏙️ CREAR_EMPRESA — funda una empresa nueva del GRUPO (decisiones firmadas 5-jul).

## Qué hace

🏙️ CREAR_EMPRESA — funda una empresa nueva del GRUPO (decisiones firmadas 5-jul).
🏙️   El principio (Opus): «el motor se comparte y es genérico; la inteligencia
🏙️   es privada y se cultiva». En código:
🏙️     · N BASES: la empresa = ÁRBOL DE DATOS en ~/Empresas/<nombre>; el MOTOR
🏙️       no se copia — se SYMLINKA desde la sede (una sola fuente de verdad;
🏙️       un fix en la sede arregla a todas).
🏙️     · CARTA NUEVA (hallazgo de Gustavo): epistolar virgen con ACTA FUNDACIONAL,
🏙️       su libro de sellos, sus actas, su historia. La fundación deja además una
🏙️       Decisión en la carta de la mesa FUNDADORA.
🏙️     · ANDAMIO: arranca con las sillas default de roles/turnos (voto de Opus:
🏙️       "equipo funcional el día 1") — luego se customiza con [E].
🏙️     · MÁSCARA SIEMPRE VACÍA (decisión 4, razón de Gustavo: una semilla podría
🏙️       corromper el CRAG): capabilities/ nace vacía; la inteligencia se cultiva.
🏙️     · FLOTA: hereda servidores.conf de la sede (mismo hierro del grupo); el
🏙️       candado global (~/.mosaic/flota_de) impone UNA empresa a la vez.
🏙️ Uso:  ./crear_empresa.sh <nombre>            (DRY-RUN: el plan de fundación)
🏙️       ./crear_empresa.sh <nombre> --aplicar
🏙️   Operar la empresa: MOSAIC_BASE=~/Empresas/<nombre> ./monitor.py  (o cualquier script)

## Piezas clave

- `ejecutar`
- `err`
- `log`
- `validar`

---
_Auto-documentado desde la cabecera de `crear_empresa.sh`. Parte de MOSAIC._
