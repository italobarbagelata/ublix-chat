# 🚀 Prompt para Crear Frontend con Chat Streaming

## Contexto
Necesito crear un frontend para un sistema de chat que tiene dos endpoints:
1. **Chat Normal**: `/api/chat/message` (respuesta JSON tradicional)  
2. **Chat Streaming**: `/api/chat/stream` (respuesta en tiempo real con Server-Sent Events)

## 📋 Especificaciones de los Endpoints

### ✅ Chat Normal - `/api/chat/message`
**Método**: POST  
**Content-Type**: application/json

**Request Body**:
```json
{
    "message": "Hola, ¿cómo estás?",
    "project_id": "12345",
    "user_id": "user123",
    "name": "Juan Pérez",
    "number_phone_agent": "+1234567890",
    "source": "web",
    "source_name": "web_app"
}
```

**Response** (JSON):
```json
{
    "response": "¡Hola! Estoy muy bien, gracias por preguntar. ¿En qué puedo ayudarte hoy?",
    "message_id": "msg_12345",
    "user_id": "user123"
}
```

### ⚡ Chat Streaming - `/api/chat/stream`
**Método**: POST  
**Content-Type**: application/json  
**Response**: text/event-stream (Server-Sent Events)

**Request Body**: (Igual que el endpoint normal)

**Response Stream** (múltiples eventos):
```javascript
// Chunk de contenido (se reciben múltiples)
{
    "type": "content_chunk",
    "content": "¡Hola! Estoy muy bien",
    "conversation_id": "conv_123",
    "user_id": "user123",
    "is_complete": false
}

// Actualización de estado
{
    "type": "status_update", 
    "status": "processing",
    "node": "agent",
    "conversation_id": "conv_123",
    "user_id": "user123",
    "is_complete": false
}

// Estados posibles: "processing", "using_tools", "thinking", "writing"

// Finalización
{
    "type": "completion",
    "response": "¡Hola! Estoy muy bien, gracias por preguntar. ¿En qué puedo ayudarte hoy?",
    "conversation_id": "conv_123", 
    "user_id": "user123",
    "is_complete": true
}

// Error (si ocurre)
{
    "type": "error",
    "error": "Descripción del error",
    "conversation_id": "conv_123",
    "user_id": "user123", 
    "is_complete": true
}

// Fin del stream
{
    "type": "stream_end"
}
```

## 🎯 Requerimientos del Frontend

### 📱 Funcionalidades Principales:
1. **Chat Interface**: Input para mensajes + área de conversación
2. **Modo Dual**: Botón para elegir entre "Normal" vs "Streaming"
3. **Indicadores Visuales**: 
   - Loading states
   - Typing indicators
   - Status updates ("Procesando...", "Usando herramientas...")
4. **Real-time Response**: Para streaming, mostrar texto mientras se escribe
5. **Error Handling**: Manejo graceful de errores
6. **UX Optimizada**: 
   - Auto-scroll
   - Botones disabled durante procesamiento
   - Timestamps
   - Diferenciación visual entre mensajes usuario/AI

### 🎨 Experiencia de Usuario Deseada:

#### Chat Normal:
```
Usuario: [Escribe mensaje] → [Enviar] → [Loading 3-5s] → [Respuesta completa]
```

#### Chat Streaming:
```
Usuario: [Escribe mensaje] → [Enviar] → [200ms] Primeras palabras... 
→ [500ms] más palabras... → [800ms] respuesta completa
```

### 📊 Métricas a Mostrar (opcional):
- Tiempo hasta primera respuesta
- Tiempo total
- Modo utilizado (Normal/Streaming)

## 💻 Ejemplo de Implementación JavaScript

### Chat Normal:
```javascript
async function sendNormalMessage(message) {
    const response = await fetch('/api/chat/message', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            message,
            project_id: "12345",
            user_id: "user123",
            name: "Usuario",
            number_phone_agent: "",
            source: "web", 
            source_name: "frontend"
        })
    });
    
    const data = await response.json();
    return data.response;
}
```

### Chat Streaming:
```javascript
async function sendStreamingMessage(message) {
    const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            message,
            project_id: "12345", 
            user_id: "user123",
            name: "Usuario",
            number_phone_agent: "",
            source: "web",
            source_name: "frontend"
        })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                
                if (data.type === 'content_chunk') {
                    // Agregar chunk al mensaje en tiempo real
                    appendToCurrentMessage(data.content);
                }
                else if (data.type === 'status_update') {
                    // Mostrar status como "Escribiendo..."
                    showStatus(data.status);
                }
                else if (data.type === 'completion') {
                    // Finalizar y limpiar
                    finalizeMessage(data.response);
                    hideStatus();
                }
                else if (data.type === 'error') {
                    showError(data.error);
                }
            }
        }
    }
}
```

## 🎨 Consideraciones de UI/UX

### Estados Visuales:
- **Escribiendo usuario**: Input activo
- **Enviando**: Botón disabled, loading spinner  
- **AI procesando**: "🤔 Procesando tu mensaje..."
- **AI usando herramientas**: "🔧 Usando herramientas..."
- **AI escribiendo**: Texto apareciendo en tiempo real
- **Completado**: Estado normal

### Indicadores de Status:
- "🤔 Procesando tu mensaje..."
- "🔧 Usando herramientas..."  
- "💭 Pensando..."
- "✍️ Escribiendo respuesta..."

### Responsive Design:
- Mobile-first
- Touch-friendly
- Accesibilidad (ARIA labels)

## 🔧 Configuración Recomendada

```javascript
const CONFIG = {
    API_BASE_URL: 'http://localhost:8000', // Ajustar según entorno
    DEFAULT_PROJECT_ID: '12345',
    DEFAULT_USER_ID: 'user123',
    STREAMING_ENABLED: true,
    AUTO_SCROLL: true,
    SHOW_TIMESTAMPS: true,
    SHOW_METRICS: true // opcional
};
```

## 📋 Tareas Específicas

Por favor, crea un frontend que:

1. **✅ Implemente ambos endpoints** (normal + streaming)
2. **⚡ Priorice la experiencia de streaming** como modo principal
3. **🎨 Tenga una UI moderna y responsiva**
4. **🔄 Maneje todos los estados y errores** apropiadamente  
5. **📱 Funcione bien en mobile y desktop**
6. **♿ Sea accesible** (buenas prácticas web)
7. **🚀 Demuestre claramente** la diferencia de velocidad entre ambos modos

**Framework preferido**: [React/Vue/Angular/Vanilla - especifica tu preferencia]

**Estilo**: [Material UI/Tailwind/Bootstrap/Custom - especifica tu preferencia]

---

**¿Podrías crear este frontend con todas estas especificaciones?** 