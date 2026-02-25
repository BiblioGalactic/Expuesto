# Troubleshooting rápido

## Error: `All models failed ... fetch failed`

Causa:
- `llama-server` no está arriba o URL incorrecta.

Revisar:

```bash
curl http://127.0.0.1:8080/v1/models
```

Si falla, arranca servidor.

---

## Error WhatsApp `401 loggedOut`

Causa:
- Sesión vinculada inválida/caducada.

Fix:

```bash
rm -rf data/auth
node bridge.js
```

Vincula de nuevo.

---

## No aparece código de vinculación

Revisa `.env`:

```env
WA_USE_PAIRING_CODE=true
WA_PAIRING_PHONE=<numero correcto>
```

Si sigue fallando, prueba QR:

```env
WA_USE_PAIRING_CODE=false
WA_SHOW_QR=true
```

---

## Responde dos veces

Causa:
- OpenClaw y bridge respondiendo al mismo chat.

Fix:
- apagar OpenClaw para WhatsApp, o
- restringir OpenClaw a otro chat/canal.

---

## Ignora mensajes

Revisa:

- `SELF_CHAT_ONLY=true`: solo responde en autochat.
- `ALLOW_FROM`: número permitido.
- `IGNORE_OLD_MESSAGES=true`: ignora mensajes antiguos al arrancar.

---

## Memoria “rara” o contaminada

Limpia historial:

```bash
rm -f data/history.json
```

O desde WhatsApp: `/reset`
