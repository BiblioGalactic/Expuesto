# sellar.sh

> 🖋️ SELLAR — el ÚNICO escritor de sellos del libro de acciones (P2 orquesta).

## Qué hace

🖋️ SELLAR — el ÚNICO escritor de sellos del libro de acciones (P2 orquesta).
🖋️   Doctrina (Opus 22:21 · espec Fable 23:36): un "✅" en el TEXTO de una carta
🖋️   vale CERO — un agente alucinado se auto-aprobaría. Los sellos viven en
🖋️   data/acciones.json, los escribe SOLO esta herramienta, invocada por la mano
🖋️   de confianza (Gustavo, o la sesión del auditor). El futuro ejecutor (F2)
🖋️   verificará: DOBLE sello (auditor+humano) + hash del cuerpo intacto.
🖋️   Estados: propuesta → auditada (sello auditor) → LISTA (ambos sellos).
🖋️   Rechazar también es sellar: --veto deja el porqué y cierra la Acción.
🖋️ Uso:  ./sellar.sh <ACC-id> <auditor|humano> ["veredicto/nota"]
🖋️       ./sellar.sh <ACC-id> <auditor|humano> --veto "porqué"
🖋️       ./sellar.sh listar [estado]     ·      ./sellar.sh ver <ACC-id>
🖋️       ./sellar.sh archivar <ACC-id> ["motivo"]   (higiene 7-jul: propuesta de
🖋️         pleno-de-prueba → trash/propuestas_archivadas/<id>.json — JAMÁS se borra,
🖋️         sale del libro vivo con su motivo y su fecha; solo estados sin sellos)

## Piezas clave

- `cleanup`
- `ejecutar`
- `err`
- `log`
- `validar`

---
_Auto-documentado desde la cabecera de `sellar.sh`. Parte de MOSAIC._
