"""
🚀 SISTEMA DE COLAS PARA MENSAJES POR USUARIO

Procesa mensajes secuencialmente por usuario para evitar colisiones
y garantizar coherencia en las conversaciones.
"""

import asyncio
import logging
from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)

class MessageStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class QueuedMessage:
    """Representa un mensaje en la cola"""
    id: str
    user_id: str
    project_id: str
    content: str
    timestamp: datetime
    status: MessageStatus
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class MessageQueue:
    """
    Sistema de colas que procesa mensajes secuencialmente por usuario.
    Cada usuario tiene su propia cola para evitar interferencias.
    """
    
    def __init__(self, max_queue_size: int = 50):
        self.max_queue_size = max_queue_size
        self.user_queues: Dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue())
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self.active_messages: Dict[str, QueuedMessage] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.stats = {
            "messages_processed": 0,
            "messages_failed": 0,
            "queues_active": 0,
            "total_wait_time": 0.0
        }
        
    def register_handler(self, message_type: str, handler: Callable):
        """Registra un handler para un tipo específico de mensaje"""
        self.message_handlers[message_type] = handler
        logger.info(f"📝 Handler registrado para tipo: {message_type}")
    
    async def enqueue_message(
        self, 
        user_id: str, 
        project_id: str, 
        content: str,
        message_type: str = "chat",
        priority: int = 0,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Encola un mensaje para procesamiento secuencial.
        
        Args:
            user_id: ID del usuario
            project_id: ID del proyecto
            content: Contenido del mensaje
            message_type: Tipo de mensaje para seleccionar handler
            priority: Prioridad del mensaje (mayor = más prioritario)
            metadata: Metadatos adicionales
            
        Returns:
            str: ID del mensaje encolado
        """
        queue_key = f"{project_id}_{user_id}"
        
        # Verificar límite de cola
        if self.user_queues[queue_key].qsize() >= self.max_queue_size:
            logger.warning(f"⚠️ Cola llena para usuario {user_id}. Rechazando mensaje.")
            raise ValueError("Cola de mensajes llena. Intenta más tarde.")
        
        # Crear mensaje
        message = QueuedMessage(
            id=f"{queue_key}_{datetime.now().timestamp()}",
            user_id=user_id,
            project_id=project_id,
            content=content,
            timestamp=datetime.now(),
            status=MessageStatus.QUEUED,
            priority=priority,
            metadata=metadata or {}
        )
        
        # Agregar tipo de mensaje a metadatos
        message.metadata["message_type"] = message_type
        
        # Encolar mensaje
        await self.user_queues[queue_key].put(message)
        
        logger.info(f"📬 Mensaje encolado para usuario {user_id}: {message.id}")
        
        # Iniciar procesador si no está activo
        if queue_key not in self.processing_tasks:
            self.processing_tasks[queue_key] = asyncio.create_task(
                self._process_user_queue(queue_key)
            )
            self.stats["queues_active"] += 1
            
        return message.id
    
    async def _process_user_queue(self, queue_key: str):
        """Procesa la cola de un usuario específico"""
        logger.info(f"🚀 Iniciando procesador para cola: {queue_key}")
        
        try:
            while True:
                try:
                    # Obtener mensaje con timeout
                    message = await asyncio.wait_for(
                        self.user_queues[queue_key].get(),
                        timeout=300.0  # 5 minutos de timeout
                    )
                    
                    await self._process_message(message)
                    
                except asyncio.TimeoutError:
                    # Cola inactiva por 5 minutos
                    logger.info(f"⏰ Cola {queue_key} inactiva. Cerrando procesador.")
                    break
                except Exception as e:
                    logger.error(f"❌ Error procesando cola {queue_key}: {str(e)}")
                    await asyncio.sleep(1)  # Pausa breve antes de continuar
                    
        finally:
            # Limpiar procesador
            if queue_key in self.processing_tasks:
                del self.processing_tasks[queue_key]
                self.stats["queues_active"] -= 1
            logger.info(f"🏁 Procesador terminado para cola: {queue_key}")
    
    async def _process_message(self, message: QueuedMessage):
        """Procesa un mensaje individual"""
        start_time = datetime.now()
        message.status = MessageStatus.PROCESSING
        self.active_messages[message.id] = message
        
        try:
            logger.info(f"🔄 Procesando mensaje {message.id}")
            
            # Obtener handler apropiado
            message_type = message.metadata.get("message_type", "chat")
            handler = self.message_handlers.get(message_type)
            
            if not handler:
                raise ValueError(f"No se encontró handler para tipo: {message_type}")
            
            # Ejecutar handler
            result = await handler(message)
            
            # Marcar como completado
            message.status = MessageStatus.COMPLETED
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ Mensaje {message.id} procesado en {processing_time:.2f}s")
            self.stats["messages_processed"] += 1
            self.stats["total_wait_time"] += processing_time
            
        except Exception as e:
            # Manejar error
            message.retry_count += 1
            
            if message.retry_count <= message.max_retries:
                logger.warning(f"⚠️ Error procesando {message.id}. Reintentando {message.retry_count}/{message.max_retries}")
                message.status = MessageStatus.QUEUED
                # Reencolar con menor prioridad
                await self.user_queues[f"{message.project_id}_{message.user_id}"].put(message)
            else:
                logger.error(f"❌ Mensaje {message.id} falló después de {message.max_retries} intentos: {str(e)}")
                message.status = MessageStatus.FAILED
                self.stats["messages_failed"] += 1
                
        finally:
            # Limpiar mensaje activo
            if message.id in self.active_messages:
                del self.active_messages[message.id]
    
    async def get_queue_status(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """Obtiene el estado de la cola de un usuario"""
        queue_key = f"{project_id}_{user_id}"
        
        return {
            "queue_size": self.user_queues[queue_key].qsize(),
            "is_processing": queue_key in self.processing_tasks,
            "active_message": self.active_messages.get(f"{queue_key}_current"),
            "estimated_wait_time": self._estimate_wait_time(queue_key)
        }
    
    def _estimate_wait_time(self, queue_key: str) -> float:
        """Estima el tiempo de espera basado en estadísticas"""
        if self.stats["messages_processed"] == 0:
            return 30.0  # Estimación inicial
        
        avg_processing_time = self.stats["total_wait_time"] / self.stats["messages_processed"]
        queue_size = self.user_queues[queue_key].qsize()
        
        return avg_processing_time * queue_size
    
    async def cancel_user_messages(self, user_id: str, project_id: str) -> int:
        """Cancela todos los mensajes pendientes de un usuario"""
        queue_key = f"{project_id}_{user_id}"
        cancelled_count = 0
        
        # Crear nueva cola vacía
        new_queue = asyncio.Queue()
        
        # Marcar mensajes como cancelados
        while not self.user_queues[queue_key].empty():
            try:
                message = self.user_queues[queue_key].get_nowait()
                message.status = MessageStatus.CANCELLED
                cancelled_count += 1
            except asyncio.QueueEmpty:
                break
        
        # Reemplazar cola
        self.user_queues[queue_key] = new_queue
        
        logger.info(f"🚫 Cancelados {cancelled_count} mensajes para usuario {user_id}")
        return cancelled_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema de colas"""
        return {
            **self.stats,
            "active_queues": len(self.processing_tasks),
            "total_queues": len(self.user_queues),
            "active_messages": len(self.active_messages),
            "avg_processing_time": (
                self.stats["total_wait_time"] / self.stats["messages_processed"]
                if self.stats["messages_processed"] > 0 else 0
            )
        }

# Instancia global del sistema de colas
message_queue = MessageQueue() 