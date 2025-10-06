import datetime
import logging
from typing import List, Union, Dict, Any
from langchain_core.messages import (
    BaseMessage,
    RemoveMessage,
    ToolMessage,
    AIMessage,
    HumanMessage
)


def filter_and_prepare_messages_for_agent_node(state):
    """Filters and prepares the messages for agent answer"""
    logging.info("filter_and_prepare_messages_for_agent_node")
    messages = state["messages"]
    if messages is None:
        messages = []

    messages = [msg for msg in messages if not isinstance(msg, RemoveMessage)]
    first_ai_index = next((i for i, msg in enumerate(messages) if isinstance(msg, AIMessage)), None)

    if first_ai_index is None:
        first_ai_index = 0

    filtered_messages = [msg for i, msg in enumerate(messages) if i >= first_ai_index or not isinstance(msg, ToolMessage)]
    return filtered_messages


def filter_and_prepare_messages_for_summary_node(state):
    """
    Filters and prepares the messages for summarization, normalizing their content. 
    Messages marked for Removal and Tools are also filtered out, and their content is normalized.
    """

    logging.info("filter_and_prepare_messages_for_summary_node")
    messages = state.get("messages", [])
    if messages is None:
        messages = []

    messages = [msg for msg in messages if not isinstance(msg, RemoveMessage)]
    normalized_messages = [normalize_message(msg) for msg in messages]
    filtered_messages = [msg for msg in normalized_messages if not isinstance(msg, ToolMessage)]
    return filtered_messages


def clean_message_content(
    message_content: Union[str, List[Dict[str, Any]], Dict[str, Any]]
) -> str:
    """ Clean and normalize the messages' content of LLM Models """
    
    if isinstance(message_content, str):
        # Ej. para OpenAI Models - gpt....
        return message_content
    
    elif isinstance(message_content, list):
        # Ej. para Anthropic Models - claude....
        text_parts = []
        for item in message_content:
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
        return ' '.join(text_parts)
    
    elif isinstance(message_content, dict):
        # TODO: Para otros modelos LLMs - meta....
        return message_content.get('text', str(message_content))
    
    else:
        return str(message_content)


def normalize_message(
    message: BaseMessage
) -> BaseMessage:
    """ Normalize each individual message, building a new instance of clean content"""
    
    if isinstance(message, HumanMessage):
        return HumanMessage(content=clean_message_content(message.content))
    elif isinstance(message, AIMessage):
        return AIMessage(content=clean_message_content(message.content))
    return message


def calculate_execution_duration(initial_date: datetime.datetime, end_date: datetime.datetime):
    """ Calculate the execution duration """
    return (end_date - initial_date).total_seconds()


def decorate_message(message: BaseMessage, initial_date: datetime.datetime, conversation_id: str):
    """ Decorate the message with the execution time """
    end_datetime = datetime.datetime.now()
    message.additional_kwargs["end_timestamp"] = end_datetime
    message.additional_kwargs["end_time_seconds"] = (end_datetime - initial_date).total_seconds()
    message.additional_kwargs["conversation_id"] = conversation_id
    
    return end_datetime


def clean_response_from_image_patterns(response_text: str) -> str:
    """
    Limpia la respuesta removiendo patrones markdown de imágenes.
    
    Args:
        response_text (str): Texto de respuesta que puede contener patrones ![Imagen](URL)
        
    Returns:
        str: Texto limpio sin patrones de imagen
    """
    import re
    
    if not response_text:
        return response_text
    
    # Remover patrones ![Imagen](URL) o ![imagen](URL) (case insensitive)
    # El patrón busca: ![ + cualquier texto + ]( + cualquier cosa hasta ) + )
    pattern = r'!\[[^\]]*\]\([^)]+\)'
    cleaned_text = re.sub(pattern, '', response_text, flags=re.IGNORECASE)
    
    # Remover líneas vacías excesivas pero conservar saltos de línea simples
    cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)  # Múltiples saltos de línea a máximo 2
    cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)  # Múltiples espacios/tabs (pero NO saltos de línea)
    cleaned_text = cleaned_text.strip()
    
    return cleaned_text
