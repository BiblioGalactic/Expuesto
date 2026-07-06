# chequeo_mini.sh

> CHEQUEO MINI — ¿puede el mini REPONER en paralelo mientras el MacBook

## Qué hace

CHEQUEO MINI — ¿puede el mini REPONER en paralelo mientras el MacBook
hace FASE 1? Comprueba 3 cosas y no cambia NADA (solo lee y prueba):
  1) SSH sin contraseña al mini
  2) recolector + dependencias (crawler, venv, token, OCR) EN el mini
  3) si el silo es disco COMPARTIDO (lo ve el mini en la misma ruta)
Ejecuta EN EL MACBOOK:   bash chequeo_mini.sh
Si el usuario del mini difiere:   MINI="usuario@localhost" bash chequeo_mini.sh
(a propósito SIN 'set -e': un chequeo debe seguir aunque una prueba dé "no")

---
_Auto-documentado desde la cabecera de `chequeo_mini.sh`. Parte de MOSAIC._
