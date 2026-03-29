"""
Configuración centralizada de logging para Ublix Chat
"""
import logging
import sys
from typing import Optional
from app.resources.constants import MODEL_CHATBOT

class ChatbotLogger:
    """Logger personalizado para el chatbot con mensajes claros en español"""
    
    # Colores ANSI para la consola (opcional)
    COLORS = {
        'RESET': '\033[0m',
        'INFO': '\033[94m',     # Azul
        'SUCCESS': '\033[92m',  # Verde
        'WARNING': '\033[93m',  # Amarillo
        'ERROR': '\033[91m',    # Rojo
        'DEBUG': '\033[90m',    # Gris
    }
    
    @staticmethod
    def setup_logging(level=logging.INFO, use_colors=True):
        """Configura el sistema de logging global"""
        
        # Formato del mensaje sin información redundante
        if use_colors:
            format_str = '%(asctime)s | %(levelname)-8s | %(message)s'
        else:
            format_str = '%(asctime)s | %(levelname)-8s | %(message)s'
        
        # Configurar formato de fecha más legible
        date_format = '%H:%M:%S'
        
        # Configurar el handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(format_str, datefmt=date_format))
        
        # Configurar el logger raíz
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.handlers = []  # Limpiar handlers existentes
        root_logger.addHandler(handler)
        
        # Silenciar logs de bibliotecas externas ruidosas
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
        logging.getLogger('asyncpg').setLevel(logging.WARNING)
        
        return root_logger

class ConversationLogger:
    """Logger específico para flujo de conversación"""
    
    def __init__(self, conversation_id: str, user_id: str):
        self.conversation_id = conversation_id[:8]  # Solo primeros 8 caracteres
        self.user_id = user_id
        self.logger = logging.getLogger(__name__)
        
    def log_inicio_conversacion(self, mensaje: str):
        """Log cuando inicia una conversación"""
        self.logger.info(f"[{self.conversation_id}] Nueva conversación - Usuario: {self.user_id} - Mensaje: '{mensaje[:50]}...'")
    
    def log_proyecto_cargado(self, project_id: str):
        """Log cuando se carga un proyecto"""
        self.logger.info(f"[{self.conversation_id}] Proyecto cargado: {project_id[:8]}...")
    
    def log_herramientas_cargadas(self, herramientas: list):
        """Log de herramientas disponibles"""
        if herramientas:
            self.logger.info(f"[{self.conversation_id}] Herramientas activas: {', '.join(herramientas)}")
        else:
            self.logger.info(f"[{self.conversation_id}] Sin herramientas adicionales activas")
    
    def log_procesamiento_ia(self, modelo: str = None):
        """Log cuando la IA procesa el mensaje"""
        modelo_usado = modelo or MODEL_CHATBOT
        self.logger.info(f"[{self.conversation_id}] Procesando con modelo {modelo_usado}...")
    
    def log_respuesta_generada(self, respuesta: str, tiempo: float):
        """Log cuando se genera la respuesta"""
        resp_preview = respuesta[:100] + "..." if len(respuesta) > 100 else respuesta
        self.logger.info(f"[{self.conversation_id}] Respuesta generada en {tiempo:.2f}s: '{resp_preview}'")
    
    def log_error(self, error: str, critico: bool = False):
        """Log de errores"""
        if critico:
            self.logger.error(f"[{self.conversation_id}] ERROR CRITICO: {error}")
        else:
            self.logger.warning(f"[{self.conversation_id}] Advertencia: {error}")
    
    def log_estado_guardado(self):
        """Log cuando se guarda el estado"""
        self.logger.debug(f"[{self.conversation_id}] Estado de conversación guardado")
    
    def log_herramienta_ejecutada(self, herramienta: str, resultado: Optional[str] = None):
        """Log cuando se ejecuta una herramienta"""
        if resultado:
            self.logger.info(f"[{self.conversation_id}] Herramienta '{herramienta}' ejecutada exitosamente")
        else:
            self.logger.info(f"[{self.conversation_id}] Ejecutando herramienta '{herramienta}'...")

# Función helper para obtener logger formateado
def get_conversation_logger(conversation_id: str, user_id: str) -> ConversationLogger:
    """Obtiene un logger configurado para una conversación específica"""
    return ConversationLogger(conversation_id, user_id)

# Configurar logging al importar el módulo
ChatbotLogger.setup_logging(level=logging.INFO, use_colors=False)