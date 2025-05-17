import tiktoken
import time
import logging
from functools import lru_cache
from typing import Dict, Union, Optional

# Encoder global para evitar cargarlo múltiples veces
TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")

class TokenCounter:
    def __init__(self):
        self._high_priority_cache: Dict[str, Dict] = {}  # Para mensajes frecuentes
        self._low_priority_cache: Dict[str, Dict] = {}   # Para mensajes menos frecuentes
        self._cache_ttl = 300  # 5 minutos
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # 1 minuto
        self.logger = logging.getLogger(__name__)

    def _cleanup_cache(self):
        """Limpia las cachés expiradas"""
        current_time = time.time()
        self._high_priority_cache = {
            k: v for k, v in self._high_priority_cache.items()
            if current_time - v['timestamp'] < self._cache_ttl
        }
        self._low_priority_cache = {
            k: v for k, v in self._low_priority_cache.items()
            if current_time - v['timestamp'] < self._cache_ttl
        }

    @lru_cache(maxsize=1000)
    def _count_tokens_impl(self, text: str) -> int:
        """Implementación base del conteo de tokens con caché LRU"""
        if not text:
            return 0
        try:
            return len(TOKEN_ENCODER.encode(text))
        except Exception as e:
            self.logger.error(f"Error counting tokens: {e}")
            return 0

    def count_tokens(self, text: str, priority: str = 'low') -> int:
        """
        Cuenta tokens con sistema de prioridades y caché
        
        Args:
            text: Texto a contar
            priority: 'high' para mensajes frecuentes, 'low' para mensajes menos frecuentes
        """
        if not text:
            return 0

        # Limpiar caché periódicamente
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_cache()
            self._last_cleanup = current_time

        # Seleccionar caché según prioridad
        cache = self._high_priority_cache if priority == 'high' else self._low_priority_cache
        
        # Verificar caché
        if text in cache:
            return cache[text]['count']

        # Contar tokens
        count = self._count_tokens_impl(text)
        
        # Guardar en caché
        cache[text] = {
            'count': count,
            'timestamp': current_time
        }
        
        return count

    def count_message_tokens(self, message, priority: str = 'low') -> int:
        """Cuenta tokens de un mensaje incluyendo su rol y contenido"""
        if not message:
            return 0
        
        try:
            # Usar un formato más eficiente para el caché
            cache_key = f"{message.__class__.__name__}:{hash(str(message))}"
            cache = self._high_priority_cache if priority == 'high' else self._low_priority_cache
            
            if cache_key in cache:
                return cache[cache_key]['count']
            
            # Obtener el contenido del mensaje
            if isinstance(message, str):
                content = message
                role = 'user'
            else:
                content = message.content if hasattr(message, 'content') else str(message)
                role = message.type if hasattr(message, 'type') else 'user'
            
            # Contar tokens de metadatos si existen
            metadata_tokens = 0
            if hasattr(message, 'id') and message.id:
                metadata_tokens += self.count_tokens(str(message.id), 'low')
            if hasattr(message, 'timestamp') and message.timestamp:
                metadata_tokens += self.count_tokens(str(message.timestamp), 'low')
            if hasattr(message, 'conversation_id') and message.conversation_id:
                metadata_tokens += self.count_tokens(str(message.conversation_id), 'low')
            
            # Formato optimizado
            formatted_message = f"{role}:{content}"
            content_tokens = self.count_tokens(formatted_message, priority)
            total_tokens = content_tokens + metadata_tokens
            
            # Guardar en caché
            cache[cache_key] = {
                'count': total_tokens,
                'timestamp': time.time()
            }
            
            return total_tokens
            
        except Exception as e:
            self.logger.error(f"Error counting message tokens: {e}")
            return 0

    def count_system_prompt_tokens(self, prompt: str) -> int:
        """Cuenta tokens del prompt del sistema"""
        if not prompt:
            return 0
        formatted_prompt = f"system:{prompt}"
        return self.count_tokens(formatted_prompt, 'high')  # Alta prioridad para prompts del sistema

    def count_conversation_tokens(self, messages: list) -> int:
        """Cuenta tokens de una conversación completa"""
        total_tokens = 0
        for msg in messages:
            total_tokens += self.count_message_tokens(msg, 'low')
        return total_tokens

    def count_tool_tokens(self, tool, separate: bool = False) -> Union[int, Dict[str, int]]:
        """
        Cuenta tokens de una herramienta
        
        Args:
            tool: La herramienta para contar tokens
            separate (bool): Si es True, devuelve un diccionario con input y output separados
            
        Returns:
            int o dict: Total de tokens o diccionario con input y output
        """
        if not tool:
            return 0 if not separate else {"input": 0, "output": 0}
            
        try:
            input_tokens = 0
            output_tokens = 0
            
            # Obtener entrada de la herramienta
            if hasattr(tool, 'input') and tool.input:
                input_tokens = self.count_tokens(str(tool.input), 'low')
            elif hasattr(tool, 'name') and tool.name:
                input_tokens = self.count_tokens(str(tool.name), 'low')
                if hasattr(tool, 'args') and tool.args:
                    input_tokens += self.count_tokens(str(tool.args), 'low')
                    
            # Obtener salida de la herramienta
            if hasattr(tool, 'output') and tool.output:
                output_tokens = self.count_tokens(str(tool.output), 'low')
            elif hasattr(tool, 'result') and tool.result:
                output_tokens = self.count_tokens(str(tool.result), 'low')
                
            # Si no se ha podido separar, contar toda la herramienta
            if input_tokens == 0 and output_tokens == 0:
                total = self.count_tokens(str(tool), 'low')
                input_tokens = int(total * 0.3)
                output_tokens = total - input_tokens
                
            if separate:
                return {"input": input_tokens, "output": output_tokens}
            else:
                return input_tokens + output_tokens
                
        except Exception as e:
            self.logger.error(f"Error counting tool tokens: {e}")
            return 0 if not separate else {"input": 0, "output": 0}

    def count_tools_tokens(self, tools: list, separate: bool = False) -> Union[int, Dict[str, int]]:
        """
        Cuenta tokens de una lista de herramientas
        
        Args:
            tools (list): Lista de herramientas
            separate (bool): Si es True, devuelve un diccionario con input y output separados
            
        Returns:
            int o dict: Total de tokens o diccionario con input y output
        """
        if not tools:
            return 0 if not separate else {"input": 0, "output": 0}
            
        total_input = 0
        total_output = 0
        
        for tool in tools:
            result = self.count_tool_tokens(tool, separate=True)
            total_input += result["input"]
            total_output += result["output"]
            
        if separate:
            return {"input": total_input, "output": total_output}
        else:
            return total_input + total_output
