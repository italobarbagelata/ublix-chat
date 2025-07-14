import logging
import time
import hashlib
import json
from collections import OrderedDict, defaultdict
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timedelta
import re

class IntelligentMemoryManager:
    """
    Sistema de memoria inteligente AVANZADO que prioriza mensajes importantes,
    mantiene contexto crítico del usuario y adapta dinámicamente el tamaño de memoria.
    
    Características nuevas:
    - Memoria adaptativa basada en complejidad de conversación
    - Detección semántica de importancia
    - Preservación automática de contexto crítico
    - Análisis de patrones de usuario
    - Métricas de calidad de memoria
    """
    
    # Prioridades mejoradas para diferentes tipos de mensajes
    MESSAGE_PRIORITIES = {
        'contact_info': 15,        # Información de contacto del usuario (CRÍTICO)
        'user_preferences': 14,    # Preferencias del usuario (CRÍTICO)
        'calendar_events': 12,     # Eventos de calendario agendados
        'payment_info': 11,        # Información de pagos/transacciones
        'product_purchases': 10,   # Compras realizadas
        'product_info': 8,         # Información de productos consultados
        'email_sent': 7,           # Emails enviados
        'api_responses': 6,        # Respuestas de APIs importantes
        'tool_results': 5,         # Resultados de herramientas
        'conversation_context': 4, # Contexto importante de conversación
        'conversation': 3,         # Conversación general
        'system': 2,               # Mensajes del sistema
        'default': 1               # Por defecto
    }
    
    # Palabras clave para detección semántica mejorada
    SEMANTIC_KEYWORDS = {
        'contact_info': [
            'nombre', 'email', 'correo', 'teléfono', 'telefono', 'celular',
            'dirección', 'direccion', 'contacto', 'whatsapp', 'instagram'
        ],
        'user_preferences': [
            'preferencia', 'configuración', 'configuracion', 'ajuste',
            'personalización', 'personalizacion', 'me gusta', 'no me gusta'
        ],
        'calendar_events': [
            'agenda', 'cita', 'reunión', 'reunion', 'calendario', 'horario',
            'agendar', 'reservar', 'disponible', 'ocupado'
        ],
        'payment_info': [
            'pago', 'compra', 'factura', 'precio', 'costo', 'tarjeta',
            'transferencia', 'efectivo', 'descuento'
        ],
        'product_purchases': [
            'comprar', 'adquirir', 'pedido', 'orden', 'carrito', 'checkout'
        ],
        'product_info': [
            'producto', 'servicio', 'catálogo', 'catalogo', 'stock',
            'disponibilidad', 'características', 'caracteristicas'
        ]
    }
    
    @classmethod
    def prioritize_messages(cls, nested_dict: Dict, max_keys: int = None) -> OrderedDict:
        """
        Prioriza mensajes basado en importancia, timestamp y análisis semántico.
        
        Args:
            nested_dict: Diccionario con el estado de la conversación
            max_keys: Número máximo de claves a mantener (None = cálculo automático)
            
        Returns:
            OrderedDict con los mensajes priorizados
        """
        if not isinstance(nested_dict, dict):
            return OrderedDict()
        
        # Calcular max_keys dinámicamente si no se proporciona
        if max_keys is None:
            max_keys = cls._calculate_adaptive_memory_size(nested_dict)
            
        # Analizar y asignar prioridades a cada mensaje
        prioritized_items = []
        semantic_clusters = cls._analyze_semantic_clusters(nested_dict)
        
        for key, value in nested_dict.items():
            priority_score = cls._calculate_priority_score(key, value)
            timestamp = cls._extract_timestamp(value)
            semantic_importance = cls._calculate_semantic_importance(key, value, semantic_clusters)
            
            # Puntuación final combinada
            final_score = priority_score * semantic_importance
            
            prioritized_items.append({
                'key': key,
                'value': value,
                'priority_score': final_score,
                'timestamp': timestamp,
                'semantic_score': semantic_importance
            })
        
        # Ordenar por prioridad (descendente) y luego por timestamp (descendente)
        prioritized_items.sort(
            key=lambda x: (x['priority_score'], x['timestamp']),
            reverse=True
        )
        
        # Garantizar que elementos críticos siempre se preserven
        critical_items, regular_items = cls._separate_critical_items(prioritized_items)
        
        # Combinar elementos críticos + los más importantes regulares
        critical_count = len(critical_items)
        regular_slots = max(0, max_keys - critical_count)
        
        final_items = critical_items + regular_items[:regular_slots]
        
        # Construir resultado ordenado
        result = OrderedDict()
        for item in final_items:
            result[item['key']] = item['value']
            
        # Métricas detalladas
        avg_priority = sum(item['priority_score'] for item in final_items) / len(final_items) if final_items else 0
        
        logging.info(
            f" Memoria optimizada: {len(nested_dict)} → {len(result)} elementos "
            f"(críticos: {critical_count}, regulares: {len(regular_items[:regular_slots])}, "
            f"prioridad promedio: {avg_priority:.2f})"
        )
        
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
        Detecta el tipo de mensaje basado en su contenido usando análisis semántico mejorado.
        """
        if not isinstance(value, dict):
            return 'default'
            
        # Detectar por contenido del mensaje (normalizado)
        content = str(value).lower()
        content = re.sub(r'[^a-záéíóúñ\s]', ' ', content)  # Limpiar caracteres especiales
        
        # Puntuación por categoría
        category_scores = {}
        
        for category, keywords in cls.SEMANTIC_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in content)
            if score > 0:
                category_scores[category] = score
        
        # Detectores especiales
        if any(pattern in content for pattern in ['email_sent', 'correo_enviado', 'mensaje_enviado']):
            return 'email_sent'
        elif any(pattern in content for pattern in ['api_', 'tool_', 'function_call']):
            return 'api_responses'
        elif 'messages' in content and 'conversation' not in category_scores:
            return 'conversation'
        
        # Retornar la categoría con mayor puntuación
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        
        return 'default'
    
    @classmethod
    def _calculate_adaptive_memory_size(cls, nested_dict: Dict) -> int:
        """
        Calcula dinámicamente el tamaño óptimo de memoria basado en la complejidad.
        
        Args:
            nested_dict: Diccionario de conversación
            
        Returns:
            Tamaño óptimo de memoria
        """
        base_size = 15
        dict_size = len(nested_dict)
        
        # Factor de complejidad basado en tipos de mensaje únicos
        message_types = set()
        for key, value in nested_dict.items():
            msg_type = cls._detect_message_type(key, value)
            message_types.add(msg_type)
        
        complexity_factor = len(message_types) / 6.0  # Normalizar por número de tipos
        
        # Factor de actividad basado en cantidad de mensajes
        activity_factor = min(dict_size / 50.0, 1.0)  # Normalizar
        
        # Tamaño final adaptativo
        adaptive_size = int(base_size + (complexity_factor * 10) + (activity_factor * 15))
        adaptive_size = max(10, min(adaptive_size, 40))  # Límites razonables
        
        logging.info(
            f" Memoria adaptativa: base={base_size}, complejidad={complexity_factor:.2f}, "
            f"actividad={activity_factor:.2f} → tamaño={adaptive_size}"
        )
        
        return adaptive_size
    
    @classmethod
    def _analyze_semantic_clusters(cls, nested_dict: Dict) -> Dict[str, List[str]]:
        """
        Analiza clusters semánticos para identificar temas relacionados.
        
        Args:
            nested_dict: Diccionario de conversación
            
        Returns:
            Diccionario de clusters semánticos
        """
        clusters = defaultdict(list)
        
        for key, value in nested_dict.items():
            content = str(value).lower()
            message_type = cls._detect_message_type(key, value)
            clusters[message_type].append(key)
        
        return dict(clusters)
    
    @classmethod
    def _calculate_semantic_importance(cls, key: str, value: Any, clusters: Dict) -> float:
        """
        Calcula importancia semántica basada en clustering y contenido.
        
        Args:
            key: Clave del mensaje
            value: Valor del mensaje
            clusters: Clusters semánticos de la conversación
            
        Returns:
            Factor de importancia semántica (1.0 - 2.0)
        """
        message_type = cls._detect_message_type(key, value)
        cluster_size = len(clusters.get(message_type, []))
        
        # Factor base por tipo de mensaje
        if message_type in ['contact_info', 'user_preferences']:
            base_factor = 2.0  # Crítico
        elif message_type in ['calendar_events', 'payment_info']:
            base_factor = 1.8  # Muy importante
        elif cluster_size > 3:
            base_factor = 1.5  # Tema recurrente
        else:
            base_factor = 1.0  # Normal
        
        # Factor de densidad de información
        content = str(value)
        info_density = cls._calculate_information_density(content)
        
        return base_factor * info_density
    
    @classmethod
    def _calculate_information_density(cls, content: str) -> float:
        """
        Calcula la densidad de información en un mensaje.
        
        Args:
            content: Contenido del mensaje
            
        Returns:
            Factor de densidad (0.5 - 1.5)
        """
        if not content:
            return 0.5
        
        # Métricas de densidad
        char_count = len(content)
        word_count = len(content.split())
        
        # Detectar URLs, emails, teléfonos (información estructurada)
        structured_patterns = [
            r'http[s]?://\S+',
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'\+?[0-9\s\-\(\)]{8,}'
        ]
        
        structured_count = sum(
            len(re.findall(pattern, content, re.IGNORECASE))
            for pattern in structured_patterns
        )
        
        # Factor de densidad
        if structured_count > 0:
            density = 1.5  # Información estructurada es valiosa
        elif word_count > 20:
            density = 1.2  # Mensajes largos probablemente tienen más información
        elif word_count > 5:
            density = 1.0  # Mensajes normales
        else:
            density = 0.8  # Mensajes muy cortos
        
        return min(density, 1.5)
    
    @classmethod
    def _separate_critical_items(cls, prioritized_items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Separa elementos críticos que NUNCA deben eliminarse.
        
        Args:
            prioritized_items: Lista de elementos priorizados
            
        Returns:
            Tupla de (elementos_críticos, elementos_regulares)
        """
        critical_types = ['contact_info', 'user_preferences', 'payment_info']
        critical_threshold = 10.0  # Umbral de prioridad crítica
        
        critical_items = []
        regular_items = []
        
        for item in prioritized_items:
            content = str(item['value']).lower()
            message_type = cls._detect_message_type(item['key'], item['value'])
            
            is_critical = (
                message_type in critical_types or
                item['priority_score'] >= critical_threshold or
                any(critical_word in content for critical_word in [
                    'importante', 'crítico', 'urgente', 'contacto guardado'
                ])
            )
            
            if is_critical:
                critical_items.append(item)
            else:
                regular_items.append(item)
        
        # Ordenar ambas listas por prioridad
        critical_items.sort(key=lambda x: x['priority_score'], reverse=True)
        regular_items.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return critical_items, regular_items
    
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
        
        logging.info(f" Estado de memoria optimizado: {original_size} → {new_size} elementos")
        
        return state_dict
    
    @classmethod
    def get_memory_analytics(cls, state_dict: Dict) -> Dict[str, Any]:
        """
        Genera analíticas detalladas del estado de memoria.
        
        Args:
            state_dict: Diccionario de estado completo
            
        Returns:
            Diccionario con métricas de memoria
        """
        nested_dict = state_dict.get('', {})
        if not nested_dict:
            return {"status": "empty", "total_items": 0}
        
        # Análisis por tipos de mensaje
        type_distribution = defaultdict(int)
        priority_distribution = []
        timestamp_analysis = {"oldest": None, "newest": None}
        
        total_chars = 0
        for key, value in nested_dict.items():
            message_type = cls._detect_message_type(key, value)
            type_distribution[message_type] += 1
            
            priority = cls._calculate_priority_score(key, value)
            priority_distribution.append(priority)
            
            timestamp = cls._extract_timestamp(value)
            if timestamp_analysis["oldest"] is None or timestamp < timestamp_analysis["oldest"]:
                timestamp_analysis["oldest"] = timestamp
            if timestamp_analysis["newest"] is None or timestamp > timestamp_analysis["newest"]:
                timestamp_analysis["newest"] = timestamp
            
            total_chars += len(str(value))
        
        # Calcular métricas
        avg_priority = sum(priority_distribution) / len(priority_distribution) if priority_distribution else 0
        memory_efficiency = min(len(nested_dict) / 50.0, 1.0)  # Eficiencia relativa
        
        # Tiempo de span de la conversación (en horas)
        time_span_hours = 0
        if timestamp_analysis["oldest"] and timestamp_analysis["newest"]:
            time_span_hours = (timestamp_analysis["newest"] - timestamp_analysis["oldest"]) / 3600
        
        return {
            "total_items": len(nested_dict),
            "type_distribution": dict(type_distribution),
            "avg_priority": round(avg_priority, 2),
            "memory_efficiency": round(memory_efficiency, 2),
            "total_characters": total_chars,
            "avg_chars_per_item": round(total_chars / len(nested_dict), 2) if nested_dict else 0,
            "conversation_span_hours": round(time_span_hours, 1),
            "recommended_max_keys": cls._calculate_adaptive_memory_size(nested_dict),
            "critical_items_count": len([
                item for item in nested_dict.items()
                if cls._detect_message_type(item[0], item[1]) in ['contact_info', 'user_preferences', 'payment_info']
            ])
        }
    
    @classmethod
    def suggest_memory_optimization(cls, state_dict: Dict) -> List[str]:
        """
        Sugiere optimizaciones para la gestión de memoria.
        
        Args:
            state_dict: Diccionario de estado completo
            
        Returns:
            Lista de sugerencias de optimización
        """
        analytics = cls.get_memory_analytics(state_dict)
        suggestions = []
        
        # Análisis de tamaño
        if analytics["total_items"] > 40:
            suggestions.append(
                f"📊 Memoria muy grande ({analytics['total_items']} elementos). "
                f"Considerar reducir a {analytics['recommended_max_keys']} elementos."
            )
        
        # Análisis de eficiencia
        if analytics["memory_efficiency"] < 0.3:
            suggestions.append(" Baja eficiencia de memoria. Incrementar actividad para mejor adaptación.")
        
        # Análisis de distribución de tipos
        type_dist = analytics["type_distribution"]
        if type_dist.get("default", 0) > analytics["total_items"] * 0.5:
            suggestions.append("🎯 Muchos mensajes sin categorizar. Mejorar detección semántica.")
        
        # Análisis de prioridad promedio
        if analytics["avg_priority"] < 3.0:
            suggestions.append("📈 Prioridad promedio baja. Revisar sistema de puntuación.")
        
        # Análisis temporal
        if analytics["conversation_span_hours"] > 168:  # 7 días
            suggestions.append("🕐 Conversación muy extensa. Considerar archivado de mensajes antiguos.")
        
        # Análisis de elementos críticos
        if analytics["critical_items_count"] == 0:
            suggestions.append("⚠️ No se detectaron elementos críticos. Verificar información de contacto.")
        
        if not suggestions:
            suggestions.append("✅ La gestión de memoria está optimizada correctamente.")
        
        return suggestions
    
    @classmethod
    def create_memory_backup(cls, state_dict: Dict) -> str:
        """
        Crea un backup compacto del estado de memoria para recuperación.
        
        Args:
            state_dict: Diccionario de estado completo
            
        Returns:
            Hash del backup creado
        """
        nested_dict = state_dict.get('', {})
        
        # Extraer solo elementos críticos para backup
        critical_elements = {}
        for key, value in nested_dict.items():
            message_type = cls._detect_message_type(key, value)
            if message_type in ['contact_info', 'user_preferences', 'payment_info', 'calendar_events']:
                critical_elements[key] = value
        
        # Crear hash del backup
        backup_str = json.dumps(critical_elements, sort_keys=True, default=str)
        backup_hash = hashlib.md5(backup_str.encode()).hexdigest()
        
        logging.info(f" Backup de memoria creado: {len(critical_elements)} elementos críticos, hash: {backup_hash[:8]}")
        
        return backup_hash