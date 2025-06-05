import logging
import asyncio
from typing import AsyncGenerator, Dict, Any
from langchain_core.messages import AIMessage, HumanMessage
from app.controler.chat.core.llm_adapter import LLMAdapter

class StreamingService:
    """Servicio para manejar streaming de respuestas en tiempo real"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def stream_graph_response_with_memory(
        self, 
        graph, 
        initial_state: Dict[str, Any], 
        config: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        🚀 STREAMING REAL del GRAFO COMPLETO (con memoria y herramientas)
        Usa el streaming nativo de LangGraph en lugar de llamar directamente al modelo
        """
        try:
            self.logger.info("Iniciando streaming del grafo completo con memoria")
            
            # Enviar status inicial
            yield {
                "type": "status_update",
                "status": "processing",
                "node": "agent"
            }
            
            # 🎯 USAR STREAMING NATIVO DE LANGGRAPH
            # Esto mantiene toda la funcionalidad: memoria, herramientas, edges, etc.
            try:
                if hasattr(graph, 'astream'):
                    # Streaming asíncrono del grafo completo
                    self.logger.info("Usando graph.astream() para streaming con memoria")
                    
                    full_response = ""
                    chunks_processed = 0
                    final_ai_message = None
                    
                    async for chunk in graph.astream(initial_state, config):
                        chunks_processed += 1
                        self.logger.debug(f"Procesando chunk #{chunks_processed}: {type(chunk)}")
                        
                        # Procesar cada chunk del grafo
                        if isinstance(chunk, dict):
                            # Buscar mensajes AI en el chunk
                            for node_name, node_state in chunk.items():
                                self.logger.debug(f"Procesando nodo: {node_name}")
                                
                                if "messages" in node_state:
                                    messages = node_state["messages"]
                                    if isinstance(messages, list):
                                        for message in messages:
                                            if isinstance(message, AIMessage) and hasattr(message, 'content'):
                                                content = message.content
                                                if content:
                                                    final_ai_message = message
                                                    
                                                    # Si el contenido es diferente al acumulado, enviar chunk
                                                    if content != full_response:
                                                        new_content = content[len(full_response):] if len(content) > len(full_response) else content
                                                        
                                                        if new_content and new_content.strip():
                                                            full_response = content
                                                            
                                                            yield {
                                                                "type": "content_chunk",
                                                                "content": new_content,
                                                                "message_id": getattr(message, 'id', None),
                                                                "is_complete": False
                                                            }
                    
                    # 🚀 FINALIZACIÓN GARANTIZADA
                    self.logger.info(f"Stream terminado. Chunks procesados: {chunks_processed}, Respuesta final: {len(full_response)} chars")
                    
                    yield {
                        "type": "completion",
                        "response": full_response,
                        "is_complete": True,
                        "status": "finished",
                        "message_id": getattr(final_ai_message, 'id', None) if final_ai_message else None
                    }
                    
                elif hasattr(graph, 'stream'):
                    # Streaming síncrono (convertir a asíncrono)
                    self.logger.info("Usando graph.stream() para streaming con memoria")
                    
                    full_response = ""
                    final_ai_message = None
                    
                    # Ejecutar stream en hilo separado
                    def _stream_graph():
                        return list(graph.stream(initial_state, config))
                    
                    chunks = await asyncio.to_thread(_stream_graph)
                    self.logger.info(f"Obtenidos {len(chunks)} chunks del grafo")
                    
                    for chunk in chunks:
                        if isinstance(chunk, dict):
                            for node_name, node_state in chunk.items():
                                if "messages" in node_state:
                                    messages = node_state["messages"]
                                    if isinstance(messages, list):
                                        for message in messages:
                                            if isinstance(message, AIMessage) and hasattr(message, 'content'):
                                                content = message.content
                                                if content:
                                                    final_ai_message = message
                                                    
                                                    if content != full_response:
                                                        # Simular streaming dividiendo en chunks
                                                        new_content = content[len(full_response):]
                                                        full_response = content
                                                        
                                                        if new_content:
                                                            words = new_content.split()
                                                            chunk_size = 3
                                                            
                                                            for i in range(0, len(words), chunk_size):
                                                                chunk_words = words[i:i + chunk_size]
                                                                chunk_content = " ".join(chunk_words)
                                                                
                                                                if i + chunk_size < len(words):
                                                                    chunk_content += " "
                                                                
                                                                yield {
                                                                    "type": "content_chunk",
                                                                    "content": chunk_content,
                                                                    "message_id": getattr(message, 'id', None),
                                                                    "is_complete": False
                                                                }
                                                                
                                                                await asyncio.sleep(0.03)
                    
                    # 🚀 FINALIZACIÓN GARANTIZADA
                    self.logger.info(f"Stream síncrono terminado. Respuesta final: {len(full_response)} chars")
                    
                    yield {
                        "type": "completion",
                        "response": full_response,
                        "is_complete": True,
                        "status": "finished",
                        "message_id": getattr(final_ai_message, 'id', None) if final_ai_message else None
                    }
                
                else:
                    raise Exception("El grafo no soporta streaming (ni astream ni stream)")
                    
            except Exception as stream_error:
                self.logger.error(f"Error en streaming del grafo: {stream_error}")
                raise stream_error
                    
        except Exception as e:
            self.logger.error(f"Error en streaming con memoria: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": f"Error en streaming: {str(e)}",
                "is_complete": True
            }
    
    async def stream_llm_response_real(
        self,
        model_name: str,
        messages: list,
        tools: list = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        🚀 STREAMING REAL del modelo LLM usando el adapter
        ⚠️  NOTA: Este método NO tiene memoria - solo para casos específicos
        """
        try:
            # Obtener modelo con streaming habilitado
            model = LLMAdapter.get_llm(model_name, 0)
            
            # Verificar y habilitar streaming
            if hasattr(model, 'streaming'):
                model.streaming = True
            
            # Vincular herramientas si las hay
            if tools:
                model = model.bind_tools(tools)
            
            # Verificar si el modelo soporta stream
            if hasattr(model, 'astream'):
                self.logger.info(f"Usando streaming real para modelo {model_name}")
                
                # 🎯 STREAMING REAL
                async for chunk in model.astream(messages):
                    if hasattr(chunk, 'content') and chunk.content:
                        yield {
                            "type": "content_chunk",
                            "content": chunk.content,
                            "message_id": getattr(chunk, 'id', None),
                            "is_complete": False
                        }
                
                yield {
                    "type": "completion",
                    "is_complete": True,
                    "status": "finished"
                }
            else:
                raise Exception(f"Modelo {model_name} no soporta streaming real (astream)")
                
        except Exception as e:
            self.logger.error(f"Error in real LLM streaming: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "is_complete": True
            }
    
    async def stream_graph_response_hybrid(
        self, 
        graph, 
        initial_state: Dict[str, Any], 
        config: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        🚀 STREAMING CON MEMORIA - Usa el grafo completo para mantener memoria
        """
        # 🎯 USAR GRAFO COMPLETO PARA MANTENER MEMORIA
        async for chunk in self.stream_graph_response_with_memory(graph, initial_state, config):
            yield chunk
    
    async def stream_with_token_counting(
        self,
        graph,
        initial_state: Dict[str, Any],
        config: Dict[str, Any],
        token_service
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming con conteo de tokens en paralelo
        """
        try:
            token_count = 0
            content_buffer = ""
            
            async for chunk in self.stream_graph_response_hybrid(graph, initial_state, config):
                
                if chunk["type"] == "content_chunk":
                    content_buffer += chunk["content"]
                    
                    # Contar tokens incrementalmente (aproximado)
                    token_count += len(chunk["content"].split()) * 1.3  # Aproximación rápida
                    
                    # Agregar info de tokens al chunk
                    chunk["estimated_tokens"] = int(token_count)
                
                yield chunk
                
        except Exception as e:
            self.logger.error(f"Error in streaming with tokens: {e}", exc_info=True)
            yield {"type": "error", "error": str(e), "is_complete": True} 