# EJEMPLO: Cómo agregar el endpoint de streaming a tu FastAPI

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from app.controler.chat.core.graph import Graph

app = FastAPI()

# Configurar CORS para streaming
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatController:
    """Ejemplo de controller con endpoints dual: normal + streaming"""
    
    @staticmethod
    async def chat_normal(request_data: dict, background_tasks: BackgroundTasks):
        """
        ✅ ENDPOINT ACTUAL - No se toca nada
        Mantiene toda tu funcionalidad existente
        """
        try:
            # Tu código actual aquí
            graph = Graph(
                project_id=request_data["project_id"],
                user_id=request_data["user_id"],
                username=request_data.get("username", ""),
                number_phone_agent=request_data.get("number_phone_agent", ""),
                source_id=request_data.get("source_id", ""),
                source=request_data.get("source", "")
            )
            
            # Usar el método execute normal (sin cambios)
            result = await graph.execute(
                message=request_data["message"],
                background_tasks=background_tasks
            )
            
            return result
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @staticmethod
    async def chat_stream(request_data: dict, background_tasks: BackgroundTasks):
        """
        🆕 NUEVO ENDPOINT - Para streaming
        Misma funcionalidad + respuesta en tiempo real
        """
        try:
            graph = Graph(
                project_id=request_data["project_id"],
                user_id=request_data["user_id"],
                username=request_data.get("username", ""),
                number_phone_agent=request_data.get("number_phone_agent", ""),
                source_id=request_data.get("source_id", ""),
                source=request_data.get("source", "")
            )
            
            # Generador para Server-Sent Events
            async def event_generator():
                try:
                    async for chunk in graph.execute_stream(
                        message=request_data["message"],
                        background_tasks=background_tasks
                    ):
                        # Formatear como Server-Sent Event
                        event_data = json.dumps(chunk, ensure_ascii=False)
                        yield f"data: {event_data}\n\n"
                        
                        # Pequeña pausa para no saturar
                        await asyncio.sleep(0.01)
                        
                except Exception as e:
                    # Enviar error como evento
                    error_event = {
                        "type": "error",
                        "error": str(e),
                        "is_complete": True
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                
                # Evento final de cierre
                yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
            
            # Retornar StreamingResponse con headers apropiados
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                }
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Rutas FastAPI
@app.post("/chat")
async def chat_endpoint(request: Request, background_tasks: BackgroundTasks):
    """✅ ENDPOINT ACTUAL - Sin cambios"""
    request_data = await request.json()
    return await ChatController.chat_normal(request_data, background_tasks)

@app.post("/chat/stream")
async def chat_stream_endpoint(request: Request, background_tasks: BackgroundTasks):
    """🆕 NUEVO ENDPOINT - Para streaming"""
    request_data = await request.json()
    return await ChatController.chat_stream(request_data, background_tasks)

# Ejemplo de uso desde el frontend:
"""
// ✅ USO NORMAL (tu código actual)
fetch('/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        message: "Hola",
        project_id: "123",
        user_id: "456"
    })
})
.then(response => response.json())
.then(data => {
    console.log('Respuesta completa:', data.response);
});

// 🆕 USO STREAMING (nuevo)
const eventSource = new EventSource('/chat/stream', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        message: "Hola",
        project_id: "123", 
        user_id: "456"
    })
});

eventSource.onmessage = function(event) {
    const chunk = JSON.parse(event.data);
    
    if (chunk.type === 'content_chunk') {
        // Mostrar chunk inmediatamente
        appendToChat(chunk.content);
    }
    else if (chunk.type === 'status_update') {
        // Mostrar estado (ej: "Procesando...", "Usando herramientas...")
        showStatus(chunk.status);
    }
    else if (chunk.type === 'completion') {
        // Respuesta completa
        console.log('Respuesta final:', chunk.response);
        eventSource.close();
    }
    else if (chunk.type === 'error') {
        console.error('Error:', chunk.error);
        eventSource.close();
    }
};
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 