# memoria.sh

> MEMORIA — "¿ya lo he visto?" UNIFICADO y reanudable para TODAS las fuentes.

## Qué hace

MEMORIA — "¿ya lo he visto?" UNIFICADO y reanudable para TODAS las fuentes.
Un solo registro: data/vistos.jsonl  (sustituye a .noticias_vistos,
.libros_vistos, cuarentena/.clonados, data/oraculo_vistos). La planta ya
rota data/vistos*.jsonl. Identidad EXACTA por (ambito|clave) con hash →
a prueba de rutas/URLs con caracteres raros.
Uso:
  memoria.sh nuevo  <ambito> <clave>   # 0 = NUEVO (y lo marca) · 1 = ya estaba
  memoria.sh visto  <ambito> <clave>   # 0 = ya estaba · 1 = nuevo (no marca)
  memoria.sh marcar <ambito> <clave>   # lo registra (idempotente)
  memoria.sh migrar                    # importa los registros viejos (NO borra)
  memoria.sh estado                    # cuántos por ámbito

## Piezas clave

- `_hash`
- `_importar`
- `_marcar`
- `_visto`

---
_Auto-documentado desde la cabecera de `memoria.sh`. Parte de MOSAIC._
