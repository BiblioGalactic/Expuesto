# 📅 Calendario Mental

Un visor hermoso y potente de **todas tus conversaciones con IA** (Claude, ChatGPT, Gemini, Deepseek, Perplexity, etc.) con calendario, búsqueda y la posibilidad de **continuar cualquier chat con tu modelo local**.

![Vista previa](https://via.placeholder.com/800x400?text=Captura+de+pantalla)

## ✨ Características

- 📆 Calendario mensual interactivo
- 🔍 Búsqueda global (títulos + contenido de mensajes)
- 🎯 Filtros por fuente (Claude, ChatGPT, etc.)
- 🖼️ Visualización de imágenes y audios adjuntos
- 🚀 **Fork**: Continúa cualquier conversación antigua con tu LLM local (llama.cpp)
- 💬 Chat en tiempo real con modelos `.gguf`
- 📦 Todo en un solo archivo HTML + servidor Node.js

## 📦 Requisitos

- Node.js **v18 o superior**
- (Opcional) [llama.cpp](https://github.com/ggerganov/llama.cpp) compilado
- Modelos `.gguf` (p.ej., Mistral, LLaMA, etc.)

## 🚀 Instalación y uso

```bash
# Clonar el repositorio
git clone https://github.com/tuusuario/calendario-mental.git
cd calendario-mental

# Instalar (no hay dependencias externas, solo Node.js nativo)
npm install  # opcional, solo para tener package.json

# Colocar tus archivos de conversaciones (JSON) en la carpeta raíz
# Por ejemplo: claude_conversations.json, chatgpt_conversations.json, etc.

# (Opcional) Crear carpeta para modelos y colocar .gguf
mkdir modelos
# Copia tu modelo.gguf a modelos/

# Iniciar el servidor
npm start
# o
node servidor_ia.js

Abre tu navegador en http://127.0.0.1:8787

⚙️ Configuración avanzada

Puedes usar variables de entorno para personalizar rutas:

bash
export IA_MODELS_DIR=/ruta/a/tus/modelos
export IA_MAIN_BINARY=/ruta/a/llama-cli
export PORT=8787
node servidor_ia.js
🧠 Funcionamiento del chat local

El servidor incluye una API que permite:

Listar modelos .gguf disponibles en IA_MODELS_DIR.
Iniciar una sesión de chat (con historial opcional).
Enviar mensajes y recibir respuestas usando llama-cli.
Cerrar sesión y guardar el historial en local_<modelo>.json.
El prompt se construye en formato Mistral Instruct ([INST] ... [/INST]). Si usas otro modelo, ajusta buildPrompt en servidor_ia.js.

📁 Estructura de archivos

calendario_mental.html – Interfaz web.
servidor_ia.js – Servidor HTTP + API de IA.
local_*.json – Historial de chats locales (se generan automáticamente).
llama_errors.log – Log de errores de llama-cli.
🛠️ Personalización

Colores: Edita FIXED_COLORS y DYNAMIC_PALETTE en el HTML.
Agentes: Añade o quita entradas en AGENTS en el HTML y en el servidor (para detección automática).
Parámetros de generación: Modifica runLlama en servidor_ia.js (-c, -n, --temp, etc.).
🤝 Contribuciones

Las contribuciones son bienvenidas. Abre un issue o pull request.

📄 Licencia

MIT
