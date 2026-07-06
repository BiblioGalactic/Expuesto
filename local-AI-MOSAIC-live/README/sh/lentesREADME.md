# lentes.sh

> 👓 LENTES v2.1 — sirve las lentes del blue team BAJO DEMANDA repartidas entre

## Qué hace

👓 LENTES v2.1 — sirve las lentes del blue team BAJO DEMANDA repartidas entre
👓 las DOS máquinas (doctrina 3-jul: MacBook 48GB · mini 16GB — usar el hierro real):
👓   código    → Dolphin (8B)   : intenta MINI primero (dolphin3 vive allí) → local
👓   intención → Mythos (13B)   : intenta MINI si le queda sitio (Mythos3 vive allí) → local
👓   (remotas → data/.lentes_env exporta DEFENSA_URL_* y cuarentena.sh lo hereda)
👓 La adversarial (Unholy@8091) es del cluster: NO se toca. (El 24B: JAMÁS — orden 3-jul.)
👓 Mythos SIEMPRE con --chat-template (llama2 sin plantilla = lente ciega, Opus 3-jul).
👓 TODO-O-NADA: sin Unholy viva o sin trío completable → no levanta nada (D0 protege).
👓 Uso:  ./lentes.sh subir | bajar | estado

## Piezas clave

- `bajar`
- `escribir_env`
- `estado`
- `gb_fichero`
- `gb_libres`
- `gb_libres_mini`
- `lanzar_local`
- `lente_al_mini`
- `listo`
- `listo_local`
- `listo_remoto`
- `log`
- `subir`
- `vivo`
- `vivo_remoto`
- `warn`

---
_Auto-documentado desde la cabecera de `lentes.sh`. Parte de MOSAIC._
