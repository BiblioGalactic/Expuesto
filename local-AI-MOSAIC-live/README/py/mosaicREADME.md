# mosaic.py

> MOSAIC — versión privada monolítica (todo en un archivo).

## Qué hace

MOSAIC — versión privada monolítica (todo en un archivo).

Composición de agentes efímeros a partir de capacidades reutilizables que se
recuperan, componen, ejecutan y evolucionan. Implementa el whitepaper completo
(intent -> recuperación híbrida -> contextualización -> grafo de compatibilidad
-> orquestación -> evolución) en un solo fichero, sin frameworks.

Dependencia obligatoria: numpy.  Opcionales: pyyaml (capacidades externas),
sentence-transformers (embeddings neuronales).  El HTTP al cluster va por
urllib (stdlib), así que no hace falta httpx.

Config por variables de entorno (las exporta mosaic.sh):
  MOSAIC_LLM_BASE_URL   endpoint OpenAI-compatible (llama-server)  [principal · Qwen3-14B]
  MOSAIC_LLM_FAST_URL   endpoint rápido                            [13B]
  MOSAIC_LLM_MODEL      nombre de modelo (llama-server lo ignora)
  MOSAIC_EMBEDDER       hashing | sentence-transformers
  MOSAIC_CAPS_DIR       carpeta de capacidades .yaml (opcional)
  MOSAIC_STATE          ruta del estado aprendido (scores/sinergias)
  MOSAIC_CONTEXTUALIZE  1 para activar §2.2 (por defecto 1 online)

Uso:
  python3 mosaic.py "escribe un fetcher async con tests"
  python3 mosaic.py "..." --fast --no-exec
  python3 mosaic.py "..." --offline           # sin red (mock + hashing)
  python3 mosaic.py --selftest

## Piezas clave

- `_a_trash`
- `_bocas_pool`
- `_ctx_text`
- `_curar_capacidad`
- `_ejecutar_con_boca`
- `_ensure_wikirag_on_path`
- `_escribir_atomico`
- `_judge`
- `_leer_registros`
- `_log_historial`
- `_norm`
- `_nt`
- `_recuperar_huerfanos`
- `_run_ab`
- `_safe_exec`
- `ab_test`
- `analizar`
- `aprender`
- `build_embedder`
- `build_judge_llm`
- `build_knowledge`
- `build_light_llm`
- `build_llm`
- `build_predictor`
- `build_prefilter`
- `build_reranker_bridge`
- `consolidar`
- `curar_existentes`
- `endpoint_for`
- `entrenar_predictor`
- `entrenar_reward`
- `estimate_tokens`
- `evaluar`
- `generar_capacidades`
- `judge_endpoint`
- `light_endpoint`
- `load_capabilities`
- `log`
- `main`
- `make_engine`
- `selftest`
- `servidor`
- `tokenize`

---
_Auto-documentado desde la cabecera de `mosaic.py`. Parte de MOSAIC._
