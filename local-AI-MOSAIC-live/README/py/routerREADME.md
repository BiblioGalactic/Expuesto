# router.py

> 🧭 ROUTER — el router INTELIGENTE de la casa (encargo Gustavo 7-jul: «las 5 propuestas,

## Qué hace

🧭 ROUTER — el router INTELIGENTE de la casa (encargo Gustavo 7-jul: «las 5 propuestas,
5 modos, y que también decida cambios de modo»). Reimplementación mosaic-nativa del
model_router.py de /Expuesto (decisión #2 del dossier de Sombra) + FLOTA_RAM §6.

LAS 5 CAPAS (las 5 propuestas de Gustavo, apiladas — no compiten, se refinan):
  1️⃣ OFICIO   (P1): rol → oficio → modelo, tabla fija. La base determinista.
  2️⃣ TALLA    (P2): tokens del prompt → tier (micro/mediano/grande) — sube o baja la apuesta.
  3️⃣ CONTENIDO(P3): heurística determinista (código/razonamiento/visión/general) SIN latencia;
      el clasificador micro (@8095) SOLO si la heurística duda Y está vivo (latencia solo si aporta).
  4️⃣ BREAKER  (P4): dignidad (data/dignidad_modelos.json) + sonda de vivos + fallback ordenado.
      Dignidad < 0.5 en ese oficio → el modelo se salta (el ledger manda).
  5️⃣ DUELO    (P5): SOLO con --critico: 2 modelos en paralelo + árbitro. El router DEVUELVE EL
      PLAN del duelo (quién vs quién, árbitro) — ejecutarlo es del llamante (palabra, no manos).

LOS MODOS (data/inventario_modelos.yaml — la fuente única): 🏛️ orquesta(+v5) · 🎩 director ·
🐝 enjambre · 🔬 micro_masa · ☢️ nuclear. El router los CONOCE, detecta el actual (sondas),
RECOMIENDA cambio y prepara el PLAN de cambio (comandos exactos).

DOCTRINA (nace apagado · regla del hierro):
  · ROUTER_MANOS=0 (default): cambiar-modo IMPRIME el plan (bajar/subir), no toca nada.
  · ROUTER_MANOS=1: ejecuta el plan CON guardias (Σgb ≤ presupuesto verificado EN código).
  · ☢️ NUCLEAR: JAMÁS se ejecuta desde aquí — exige el sello off-loop de la mesa
    (data/senales/OFFLOOP_SELLADO) Y el gesto humano. Sin sello, ni el plan se da entero.
  · El enchufe en turno_rol es OPT-IN (ROUTER=1); sin él, todo sigue como siempre.

CLI:
  ./router.py --decidir --rol auditor [--prompt-file F] [--critico] [--plano]
  ./router.py --modo            (detecta el actual + recomienda)
  ./router.py --cambiar-modo director [--rumbo "por qué"]
  ./router.py --tabla | --self-test | --revalidar   (--revalidar: la hija verifica su herencia)

## Piezas clave

- `_asignacion_conf`
- `_candidatos`
- `_carga_inventario`
- `_conf_sirve`
- `_dignidad`
- `_flag_si`
- `_plan_cambio`
- `_roster_vivo`
- `_tokens`
- `cambiar_modo`
- `capa_breaker`
- `capa_contenido`
- `capa_talla`
- `decidir`
- `main`
- `modo_actual`
- `recomendar_modo`
- `revalidar`
- `self_test`
- `vivo`

---
_Auto-documentado desde la cabecera de `router.py`. Parte de MOSAIC._
