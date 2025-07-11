"""
Utilidades para el Sistema de LangGraph Mejorado

Funciones de apoyo para procesamiento de mensajes y estado.
"""

import logging
from typing import List, Any, Dict, Optional
from datetime import datetime

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage, RemoveMessage

logger = logging.getLogger(__name__)


def filter_and_prepare_messages_for_enhanced_agent(state: Dict[str, Any]) -> List[BaseMessage]:
    """
    Filtra y prepara mensajes para el agente mejorado.
    
    Maneja problemas de formato y compatibilidad con OpenAI.
    Soluciona warnings de Pydantic normalizando mensajes dict.
    
    Args:
        state: Estado mejorado
        
    Returns:
        Lista de mensajes preparados
    """
    
    logger.info("filter_and_prepare_messages_for_enhanced_agent")
    
    # Obtener mensajes del estado y normalizar PRIMERO para evitar Pydantic warnings
    raw_messages = state.get("messages", [])
    if not raw_messages:
        raw_messages = []
    
    # CRÍTICO: Normalizar mensajes dict ANTES de cualquier procesamiento
    # Esto previene los warnings de Pydantic de serialización
    normalized_raw_messages = []
    for msg in raw_messages:
        try:
            # Si es dict (típico cuando viene de persistencia LangGraph), normalizar inmediatamente
            if isinstance(msg, dict):
                logger.debug(f"Normalizando mensaje dict para prevenir warning Pydantic")
                normalized_msg = normalize_message_content(msg)
                normalized_raw_messages.append(normalized_msg)
            elif isinstance(msg, BaseMessage):
                # Asegurar que el contenido esté bien normalizado
                normalized_msg = normalize_message_content(msg)
                normalized_raw_messages.append(normalized_msg)
            else:
                logger.warning(f"Mensaje de tipo desconocido: {type(msg)}")
                # Intentar convertir
                try:
                    normalized_msg = normalize_message_content(msg)
                    normalized_raw_messages.append(normalized_msg)
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error normalizando mensaje inicial: {e}")
            continue
    
    # Filtrar mensajes eliminados
    messages = [msg for msg in normalized_raw_messages if not isinstance(msg, RemoveMessage)]
    
    # Asegurar que todos los mensajes están completamente normalizados
    normalized_messages = []
    for msg in messages:
        try:
            # Doble normalización para garantizar formato correcto
            if not isinstance(msg, BaseMessage):
                normalized_msg = normalize_message_content(msg)
            else:
                # Verificar que el contenido sea string válido
                if not isinstance(msg.content, str):
                    normalized_msg = normalize_message_content(msg)
                else:
                    normalized_msg = msg
                    
            if normalized_msg:
                normalized_messages.append(normalized_msg)
        except Exception as e:
            logger.warning(f"Error en segunda normalización: {e}")
            continue
    
    # CRÍTICO: Limpiar secuencias de tool_calls ANTES de enviar a OpenAI
    # Esto previene el error: "An assistant message with 'tool_calls' must be followed by tool messages"
    cleaned_messages = _clean_tool_call_sequences(normalized_messages)
    
    # Filtrar lógica específica para agente
    first_ai_index = next((i for i, msg in enumerate(cleaned_messages) if isinstance(msg, AIMessage)), None)
    
    if first_ai_index is None:
        first_ai_index = 0
    
    # Filtrar mensajes de herramientas anteriores al primer AI
    filtered_messages = [
        msg for i, msg in enumerate(cleaned_messages) 
        if i >= first_ai_index or not isinstance(msg, ToolMessage)
    ]
    
    logger.info(f"Mensajes preparados: {len(filtered_messages)} de {len(raw_messages)} originales (limpiados: {len(cleaned_messages)})")
    
    return filtered_messages


def _clean_tool_call_sequences(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Limpia secuencias de tool_calls para evitar errores de OpenAI API.
    
    Args:
        messages: Lista de mensajes normalizados
        
    Returns:
        Lista de mensajes con secuencias de tool_calls válidas
    """
    
    if not messages:
        return []
    
    cleaned = []
    i = 0
    
    while i < len(messages):
        msg = messages[i]
        
        # Si es AIMessage con tool_calls
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            # Obtener IDs de tool_calls esperados
            expected_ids = set()
            for tc in msg.tool_calls:
                if isinstance(tc, dict) and 'id' in tc:
                    expected_ids.add(tc['id'])
            
            # Buscar ToolMessage correspondientes
            found_ids = set()
            tool_messages = []
            j = i + 1
            
            # Buscar hasta encontrar todos los ToolMessage o llegar al final
            while j < len(messages) and len(found_ids) < len(expected_ids):
                next_msg = messages[j]
                
                if (isinstance(next_msg, ToolMessage) and 
                    hasattr(next_msg, 'tool_call_id') and 
                    next_msg.tool_call_id in expected_ids):
                    found_ids.add(next_msg.tool_call_id)
                    tool_messages.append(next_msg)
                elif isinstance(next_msg, AIMessage):
                    # Parar si encontramos otro AIMessage
                    break
                j += 1
            
            # Solo incluir si TODOS los tool_calls tienen respuesta
            if len(found_ids) == len(expected_ids):
                cleaned.append(msg)
                cleaned.extend(tool_messages)
                i = j  # Saltar mensajes procesados
            else:
                # Crear AIMessage limpio sin tool_calls
                clean_ai = AIMessage(content=msg.content)
                cleaned.append(clean_ai)
                i += 1
        
        # Si es ToolMessage huérfano, omitir
        elif isinstance(msg, ToolMessage):
            i += 1
        
        # Mensaje normal
        else:
            cleaned.append(msg)
            i += 1
    
    return cleaned


def normalize_message_content(message: BaseMessage) -> BaseMessage:
    """
    Normaliza el contenido de un mensaje para compatibilidad con OpenAI.
    Maneja casos específicos que causan warnings de Pydantic en LangGraph.
    
    Args:
        message: Mensaje a normalizar
        
    Returns:
        Mensaje normalizado con contenido string válido
    """
    
    try:
        # Manejar caso donde el mensaje es un dict (causa de warning)
        if isinstance(message, dict):
            content = message.get('content', '')
            if isinstance(content, dict):
                content = content.get('text', str(content))
            
            # Intentar crear mensaje apropiado basado en el contenido del dict
            message_type = message.get('type', 'human')
            if message_type == 'ai':
                return AIMessage(content=str(content))
            elif message_type == 'tool':
                return ToolMessage(content=str(content), tool_call_id=message.get('tool_call_id', ''))
            else:
                return HumanMessage(content=str(content))
        
        # CRÍTICO: Manejar AIMessage que causa warnings específicos de serialización
        if isinstance(message, AIMessage):
            # Crear AIMessage limpio solo con contenido string - esto previene warnings
            clean_content = message.content
            if not isinstance(clean_content, str):
                if clean_content is None:
                    clean_content = ""
                elif isinstance(clean_content, dict):
                    clean_content = clean_content.get("text", str(clean_content))
                elif isinstance(clean_content, list):
                    clean_content = " ".join(str(item) for item in clean_content)
                else:
                    clean_content = str(clean_content)
            
            # Crear nuevo AIMessage limpio que NO cause warnings de Pydantic
            normalized = AIMessage(content=clean_content.strip())
            
            # Solo preservar tool_calls si están limpios
            if hasattr(message, 'tool_calls') and message.tool_calls:
                try:
                    # Verificar que tool_calls sean serializables
                    import json
                    json.dumps(message.tool_calls, default=str)
                    normalized.tool_calls = message.tool_calls
                except (TypeError, ValueError):
                    # Si tool_calls no son serializables, omitirlos
                    logger.debug("Omitiendo tool_calls no serializables en AIMessage")
                    pass
            
            return normalized
        
        # Obtener contenido del mensaje
        content = message.content
        
        # Si el contenido no es string, convertirlo
        if not isinstance(content, str):
            if content is None:
                content = ""
            elif isinstance(content, dict):
                # Si es dict, intentar extraer texto
                if "text" in content:
                    content = content["text"]
                elif "content" in content:
                    content = content["content"] 
                else:
                    content = str(content)
            elif isinstance(content, list):
                # Si es lista, unir elementos
                content = " ".join(str(item) for item in content)
            else:
                content = str(content)
        
        # Asegurar que es string y no vacío
        content = content.strip() if content else ""
        
        # Crear mensaje normalizado del mismo tipo
        if isinstance(message, HumanMessage):
            normalized = HumanMessage(content=content)
        elif isinstance(message, AIMessage):
            normalized = AIMessage(content=content)
            # Preservar tool_calls si existen y son válidos
            if hasattr(message, 'tool_calls') and message.tool_calls:
                try:
                    normalized.tool_calls = message.tool_calls
                except Exception:
                    # Si hay problema con tool_calls, omitirlos
                    pass
        elif isinstance(message, ToolMessage):
            tool_call_id = getattr(message, 'tool_call_id', '')
            normalized = ToolMessage(content=content, tool_call_id=str(tool_call_id))
        else:
            # Para otros tipos, crear mensaje base
            try:
                normalized = message.__class__(content=content)
            except:
                # Fallback a HumanMessage si falla la creación
                normalized = HumanMessage(content=content)
        
        # CRÍTICO: Limpiar additional_kwargs para prevenir warnings Pydantic
        if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
            try:
                # Solo preservar kwargs básicos y serializables
                clean_kwargs = {}
                for k, v in message.additional_kwargs.items():
                    # Solo permitir tipos básicos que no causen warnings
                    if isinstance(v, (str, int, float, bool, type(None))):
                        clean_kwargs[k] = v
                    elif k in ['agent_version', 'processing_route', 'intent_category', 'confidence_score']:
                        # Preservar metadatos importantes pero convertir a string
                        clean_kwargs[k] = str(v)
                    # Omitir otros kwargs que pueden causar warnings
                
                # Solo asignar si tenemos kwargs limpios
                if clean_kwargs:
                    normalized.additional_kwargs = clean_kwargs
            except Exception:
                # Si hay problema, omitir additional_kwargs completamente
                pass
        
        return normalized
        
    except Exception as e:
        logger.error(f"Error normalizando mensaje: {e}")
        # Devolver mensaje con contenido vacío como fallback
        try:
            return HumanMessage(content="")
        except:
            # Último recurso
            return message


def ensure_message_compatibility(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Asegura que los mensajes sean compatibles con OpenAI API.
    
    Args:
        messages: Lista de mensajes
        
    Returns:
        Lista de mensajes compatibles
    """
    
    compatible_messages = []
    
    for msg in messages:
        try:
            # Verificar que el contenido sea string válido
            if not isinstance(msg.content, str):
                msg = normalize_message_content(msg)
            
            # Verificar que no esté vacío (OpenAI no acepta mensajes vacíos)
            if msg.content.strip():
                compatible_messages.append(msg)
            else:
                logger.debug(f"Eliminando mensaje vacío de tipo {type(msg).__name__}")
                
        except Exception as e:
            logger.warning(f"Error verificando compatibilidad del mensaje: {e}")
            continue
    
    return compatible_messages


def clean_state_for_serialization(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Limpia el estado para serialización, eliminando objetos no serializables.
    Convierte todos los mensajes a dicts simples para evitar warnings de Pydantic.
    Args:
        state: Estado a limpiar
    Returns:
        Estado limpio sin objetos que causen warnings
    """
    import copy
    cleaned_state = {}
    def msg_to_dict(msg):
        # Si ya es dict, lo dejamos igual
        if isinstance(msg, dict):
            return msg
        # Si tiene método dict(), lo usamos
        if hasattr(msg, "dict"):
            return msg.dict()
        # Si tiene __dict__, lo usamos
        if hasattr(msg, "__dict__"):
            return dict(msg.__dict__)
        # Si es string, lo dejamos igual
        if isinstance(msg, str):
            return {"content": msg}
        # Último recurso: convertir a string
        return {"content": str(msg)}
    for key, value in state.items():
        try:
            if key == "messages" and isinstance(value, list):
                cleaned_state[key] = [msg_to_dict(m) for m in value]
            elif key == "conversation" and isinstance(value, dict):
                # Limpiar también conversation["messages"] si existe
                conv = copy.deepcopy(value)
                if "messages" in conv and isinstance(conv["messages"], list):
                    conv["messages"] = [msg_to_dict(m) for m in conv["messages"]]
                cleaned_state[key] = conv
            else:
                if _is_serializable(value):
                    cleaned_state[key] = value
                else:
                    try:
                        cleaned_state[key] = str(value)
                    except Exception:
                        logger.warning(f"Campo {key} no serializable, omitiendo")
                        continue
        except Exception as e:
            logger.warning(f"Error limpiando campo {key}: {e}")
            cleaned_state[key] = value
    return cleaned_state


def _create_ultra_clean_message(msg: Any) -> Optional[BaseMessage]:
    """
    Crea un mensaje ultra-limpio que NO cause warnings de Pydantic.
    
    Args:
        msg: Mensaje original (cualquier tipo)
        
    Returns:
        BaseMessage ultra-limpio o None si no se puede limpiar
    """
    
    try:
        # Extraer contenido básico
        if isinstance(msg, dict):
            content = str(msg.get('content', ''))
            msg_type = msg.get('type', 'human')
        elif isinstance(msg, BaseMessage):
            content = str(msg.content) if msg.content else ""
            msg_type = msg.__class__.__name__.lower().replace('message', '')
        else:
            content = str(msg)
            msg_type = 'human'
        
        # Asegurar que el contenido es string limpio
        content = content.strip()
        if not content:
            content = ""
        
        # Crear mensaje completamente limpio sin metadatos
        if msg_type == 'ai':
            return AIMessage(content=content)
        elif msg_type == 'tool':
            # Para ToolMessage, necesitamos tool_call_id
            tool_call_id = ""
            if isinstance(msg, dict):
                tool_call_id = str(msg.get('tool_call_id', ''))
            elif hasattr(msg, 'tool_call_id'):
                tool_call_id = str(msg.tool_call_id)
            return ToolMessage(content=content, tool_call_id=tool_call_id)
        else:
            return HumanMessage(content=content)
            
    except Exception as e:
        logger.warning(f"Error creando mensaje ultra-limpio: {e}")
        return None


def _is_serializable(obj: Any) -> bool:
    """
    Verifica si un objeto es serializable a JSON.
    
    Args:
        obj: Objeto a verificar
        
    Returns:
        bool: True si es serializable
    """
    try:
        import json
        json.dumps(obj, default=str)
        return True
    except (TypeError, ValueError):
        return False


def normalize_state_messages(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza TODOS los mensajes en el estado para prevenir warnings de Pydantic.
    
    Esta función debe ser llamada al inicio de cada nodo para asegurar que
    los mensajes dict (típicos de persistencia LangGraph) se conviertan a BaseMessage.
    
    Args:
        state: Estado a normalizar
        
    Returns:
        Estado con mensajes normalizados
    """
    
    # Crear copia del estado para no modificar el original
    normalized_state = dict(state)
    
    # Normalizar messages globales
    if "messages" in normalized_state:
        normalized_state["messages"] = _normalize_message_list(normalized_state["messages"])
    
    # Normalizar messages en conversation
    if "conversation" in normalized_state and isinstance(normalized_state["conversation"], dict):
        if "messages" in normalized_state["conversation"]:
            normalized_state["conversation"]["messages"] = _normalize_message_list(
                normalized_state["conversation"]["messages"]
            )
    
    return normalized_state


def _normalize_message_list(messages: List[Any]) -> List[BaseMessage]:
    """
    Normaliza una lista de mensajes, convirtiendo dict a BaseMessage.
    
    Args:
        messages: Lista de mensajes a normalizar
        
    Returns:
        Lista de BaseMessage normalizados
    """
    
    if not messages:
        return []
    
    normalized = []
    for msg in messages:
        try:
            if isinstance(msg, dict):
                # Convertir dict a BaseMessage apropiado
                normalized_msg = normalize_message_content(msg)
                normalized.append(normalized_msg)
            elif isinstance(msg, BaseMessage):
                # Verificar que el contenido esté normalizado
                if not isinstance(msg.content, str):
                    normalized_msg = normalize_message_content(msg)
                    normalized.append(normalized_msg)
                else:
                    normalized.append(msg)
            else:
                # Intentar convertir otros tipos
                try:
                    normalized_msg = normalize_message_content(msg)
                    normalized.append(normalized_msg)
                except Exception:
                    logger.warning(f"No se pudo normalizar mensaje de tipo {type(msg)}")
                    continue
        except Exception as e:
            logger.warning(f"Error normalizando mensaje: {e}")
            continue
    
    return normalized