# silo_traducir.sh

> SILO TRADUCIR (#78) — traduce una transcripción a un idioma destino.

## Qué hace

SILO TRADUCIR (#78) — traduce una transcripción a un idioma destino.
Intenta primero argos-translate (OFFLINE, local); si no está, usa el
cluster LLM (MOSAIC_LLM_BASE_URL). Escribe la traducción y NO toca el
original. Degrada sin romper (si no hay ninguno, sale 1 en silencio).
Uso:  ./silo_traducir.sh ARCHIVO.txt IDIOMA [salida.txt]
      IDIOMA: en · es · ja · de · fr …

---
_Auto-documentado desde la cabecera de `silo_traducir.sh`. Parte de MOSAIC._
