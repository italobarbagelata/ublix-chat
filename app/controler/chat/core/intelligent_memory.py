import logging
import time
from collections import OrderedDict
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta

class IntelligentMemoryManager:
    """
    Sistema de memoria inteligente que prioriza mensajes importantes
    y mantiene contexto crítico del usuario.
    """
    
    # Prioridades para diferentes tipos de mensajes
    MESSAGE_PRIORITIES = {
        'contact_info': 10,      # Información de contacto del usuario
        'calendar_events': 9,    # Eventos de calendario agendados
        'product_info': 8,       # Información de productos consultados
        'email_sent': 7,         # Emails enviados
        'api_responses': 6,      # Respuestas de APIs importantes
        'tool_results': 5,       # Resultados de herramientas
        'user_preferences': 9,   # Preferencias del usuario
        'conversation': 3,       # Conversación general
        'system': 2,             # Mensajes del sistema
        'default': 1             # Por defecto
    }
    
    @classmethod
    def prioritize_messages(cls, nested_dict: Dict, max_keys: int = 10) -> OrderedDict:
        """
        Prioriza mensajes basado en importancia y timestamp.
        
        Args:
            nested_dict: Diccionario con el estado de la conversación
            max_keys: Número máximo de claves a mantener
            
        Returns:
            OrderedDict con los mensajes priorizados
        """
        if not isinstance(nested_dict, dict):
            return OrderedDict()
            
        # Analizar y asignar prioridades a cada mensaje
        prioritized_items = []
        
        for key, value in nested_dict.items():
            priority_score = cls._calculate_priority_score(key, value)
            timestamp = cls._extract_timestamp(value)
            
            prioritized_items.append({
                'key': key,
                'value': value,
                'priority_score': priority_score,
                'timestamp': timestamp
            })
        
        # Ordenar por prioridad (descendente) y luego por timestamp (descendente)
        prioritized_items.sort(
            key=lambda x: (x['priority_score'], x['timestamp']),
            reverse=True
        )
        
        # Mantener solo los elementos más importantes
        result = OrderedDict()
        for item in prioritized_items[:max_keys]:
            result[item['key']] = item['value']
            
        logging.info(f"🧠 Memoria optimizada: {len(nested_dict)} → {len(result)} elementos")
        
        return result
    
    @classmethod
    def _calculate_priority_score(cls, key: str, value: Any) -> float:
        """
        Calcula la puntuación de prioridad para un mensaje.
        
        Args:
            key: Clave del mensaje
            value: Valor del mensaje
            
        Returns:
            Puntuación de prioridad (mayor = más importante)
        """
        # Prioridad base según el tipo de mensaje
        message_type = cls._detect_message_type(key, value)
        base_priority = cls.MESSAGE_PRIORITIES.get(message_type, 1)
        
        # Factores adicionales
        recency_factor = cls._calculate_recency_factor(value)
        interaction_factor = cls._calculate_interaction_factor(value)
        
        # Puntuación final
        final_score = base_priority * recency_factor * interaction_factor
        
        return final_score
    
    @classmethod
    def _detect_message_type(cls, key: str, value: Any) -> str:
        """
        Detecta el tipo de mensaje basado en su contenido.
        """
        if not isinstance(value, dict):
            return 'default'
            
        # Detectar por contenido del mensaje
        content = str(value).lower()
        
        # Patrones para detectar tipos de mensaje
        if any(keyword in content for keyword in ['email', 'correo', 'teléfono', 'telefono', 'nombre']):
            return 'contact_info'
        elif any(keyword in content for keyword in ['agenda', 'cita', 'reunión', 'calendar']):
            return 'calendar_events'
        elif any(keyword in content for keyword in ['producto', 'precio', 'comprar']):
            return 'product_info'
        elif any(keyword in content for keyword in ['email_sent', 'correo_enviado']):
            return 'email_sent'
        elif any(keyword in content for keyword in ['preferencia', 'configuración']):
            return 'user_preferences'
        elif any(keyword in content for keyword in ['api_', 'tool_']):
            return 'api_responses'
        elif 'messages' in content:
            return 'conversation'
        else:
            return 'default'
    
    @classmethod
    def _extract_timestamp(cls, value: Any) -> float:
        """
        Extrae el timestamp de un mensaje.
        """
        if isinstance(value, dict):
            # Buscar diferentes formatos de timestamp
            for timestamp_key in ['timestamp', 'created_at', 'time', 'date']:
                if timestamp_key in value:
                    ts = value[timestamp_key]
                    if isinstance(ts, (int, float)):
                        return float(ts)
                    elif isinstance(ts, str):
                        try:
                            return datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
                        except:
                            pass
        
        # Si no se encuentra timestamp, usar tiempo actual
        return time.time()
    
    @classmethod
    def _calculate_recency_factor(cls, value: Any) -> float:
        """
        Calcula factor de recencia (más reciente = mayor factor).
        """
        timestamp = cls._extract_timestamp(value)
        now = time.time()
        age_hours = (now - timestamp) / 3600  # Edad en horas
        
        # Factor de decaimiento exponencial
        # Mensajes recientes (< 1 hora) = factor 1.0
        # Mensajes de 24 horas = factor 0.5
        # Mensajes de 7 días = factor 0.1
        if age_hours < 1:
            return 1.0
        elif age_hours < 24:
            return 0.8
        elif age_hours < 168:  # 7 días
            return 0.5
        else:
            return 0.2
    
    @classmethod
    def _calculate_interaction_factor(cls, value: Any) -> float:
        """
        Calcula factor de interacción (más interacciones = mayor factor).
        """
        if isinstance(value, dict):
            # Contar referencias o interacciones
            interaction_count = value.get('interaction_count', 1)
            return min(1.0 + (interaction_count - 1) * 0.1, 2.0)
        
        return 1.0
    
    @classmethod
    def optimize_memory_state(cls, state_dict: Dict, max_keys: int = 10) -> Dict:
        """
        Optimiza el estado completo de memoria.
        
        Args:
            state_dict: Diccionario de estado completo
            max_keys: Número máximo de claves a mantener
            
        Returns:
            Estado optimizado
        """
        if not isinstance(state_dict, dict):
            return state_dict
        
        # Optimizar el diccionario anidado principal
        nested_dict = state_dict.get('', {})
        if nested_dict:
            optimized_nested = cls.prioritize_messages(nested_dict, max_keys)
            state_dict[''] = optimized_nested
        
        # Log de optimización
        original_size = len(nested_dict) if nested_dict else 0
        new_size = len(state_dict.get('', {}))
        
        logging.info(f"🧠 Estado de memoria optimizado: {original_size} → {new_size} elementos")
        
        return state_dict