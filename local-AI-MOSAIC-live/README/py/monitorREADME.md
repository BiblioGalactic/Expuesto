# monitor.py

> 🖥️ MONITOR — Consola de Operaciones Epistolar (RONDA 2 · esqueleto TUI).

## Qué hace

🖥️ MONITOR — Consola de Operaciones Epistolar (RONDA 2 · esqueleto TUI).
🖥️   Zona A (izq. 70%): visor Markdown — debrief del ciclo o cola de CARTAS.
🖥️   Zona B (der. 30%): dashboard en vivo de data/estado_sistema.json.
🖥️   Footer: [D]ebrief · [C]artas · [V]ivo · [R]eportar · [A]rchivar · [L]anzar ·
🖥️           [S] compartir (packs por ADUANA) · [E] empleados (plantilla de agentes) · [Q] salir.
🖥️ El VISOR solo lee; las acciones escriben SIEMPRE por sus motores (reportar/archivado/
🖥️ empaquetar/importar.sh), jamás a mano desde aquí.
🖥️ Refresco REACTIVO barato: un stat/s por fichero (mtime); re-render solo si cambió.
🖥️ Requiere: pip install textual   (dependencia de TOOLING humano, bendecida en Ronda 2)
🖥️ Uso:  ./monitor.py     (q para salir · Ctrl+C también vale)

## Piezas clave

- `_agenda_anio`
- `_agenda_dia`
- `_agenda_eventos`
- `_agenda_filtrar`
- `_agenda_mes`
- `_agenda_prospectivo`
- `_barra`
- `_bolsa_abierta`
- `_bolsa_lineas`
- `_canales_ingesta`
- `_dashboard`
- `_dashboard_mini`
- `_detectar_modo`
- `_dignidad_lentes`
- `_dominios`
- `_esc_lineas`
- `_ficha_noventera`
- `_leer_cartas_cola`
- `_leer_md`
- `_mapa_topologia`
- `_modelos_mini`
- `_mtime`
- `_nombre_modelo`
- `_persona_de`
- `_persona_guardar`
- `_roster_base`
- `_sellos_lineas`
- `_serie_crag`
- `_spark`
- `_stats_agente`
- `_topologia_datos`
- `_turnos_roles`

---
_Auto-documentado desde la cabecera de `monitor.py`. Parte de MOSAIC._
