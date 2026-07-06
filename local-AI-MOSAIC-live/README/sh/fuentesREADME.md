# fuentes.sh

> FUENTES — CASCADA de ingesta con CESIÓN y SUELO (nunca cero).

## Qué hace

FUENTES — CASCADA de ingesta con CESIÓN y SUELO (nunca cero).
Orden fijo de lectura cada ciclo · unidades 1 + primos (2,3,5,7,11) = 29:
  1º 📚 libro(1) · 2º 🔭 conversación(2) · 3º 🔮 oráculo(3)
  4º 🛡️ cuarentena(5) · 5º 📰 noticias(7) · 6º 🏭 fábrica(11)
Cada fuente recibe base+arrastre; lo que NO aporta lo CEDE a la siguiente.
Si nadie real produce, la fábrica hereda hasta 29 (un día de suerte).
SUELO≥1: la cadena nunca cae a cero (invariante Collatz del teorema de memoria).
Antes de la fábrica se DRENA el silo (PDFs/libros/noticias REALES) y actúa la capa
RIEMANN (recuperación): sobre las unidades cedidas rescata HUECOS reales de la memoria.
El humo (fábrica) es el último cartucho: solo si no hay nada real ni que rescatar.
REPOSICIÓN: la fuente que aporta 0 (almacén vacío) dispara su RECOLECTOR aguas-arriba
en 2º plano al terminar la pasada (oráculo/cuarentena → oraculo_auto.sh), con
enfriamiento, para llegar llena al próximo ciclo. Ceder = pedir restock.
Uso:  ./fuentes.sh pull

## Piezas clave

- `cola_n`
- `drenar_silo`
- `fuente_conversacion`
- `fuente_cuarentena`
- `fuente_fabrica`
- `fuente_libro`
- `fuente_noticias`
- `fuente_oraculo`
- `fuente_recuperacion`
- `lanzar_recolector`
- `log`
- `notas_n`
- `pull`
- `recolector_de`
- `reponer_agotadas`
- `silo_n`

---
_Auto-documentado desde la cabecera de `fuentes.sh`. Parte de MOSAIC._
