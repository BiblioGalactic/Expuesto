# dedup.py

> DEDUP — servicio COMÚN de similitud semántica (MiniLM → léxica de respaldo).

## Qué hace

DEDUP — servicio COMÚN de similitud semántica (MiniLM → léxica de respaldo).
Extraído de gobernanza (#60) para que lo usen TODAS las fuentes y no se
reprocesen entradas equivalentes entre sí. Bajo consumo: carga el modelo
UNA vez por llamada (pensado para LOTES); índice persistente y acotado.
API:   from dedup import make_sim
CLI:   echo "texto" | dedup.py parecido --indice data/dedup_index.jsonl --umbral 0.82
          -> exit 0 = ya hay algo parecido (DUP) · exit 1 = NUEVO (lo registra)
        dedup.py nuevos --indice ... --umbral 0.82 f1.txt f2.txt ...
          -> imprime "NUEVO<TAB>fichero" / "DUP<TAB>fichero" (UNA carga de modelo,
             deduplica contra el índice Y dentro del propio lote)

## Piezas clave

- `_anadir`
- `_arg`
- `_cargar`
- `_embedder`
- `_ficheros`
- `_sim`
- `main`
- `make_sim`

---
_Auto-documentado desde la cabecera de `dedup.py`. Parte de MOSAIC._
