import datetime
import logging
# import pytz # Se eliminará pytz
from langchain_core.messages import BaseMessage, RemoveMessage, ToolMessage, AIMessage, HumanMessage
from typing import Union, List, Dict, Any

def filter_and_prepare_messages_for_agent_node(state):
    """Filters and prepares the messages for agent answer"""
    logging.info("filter_and_prepare_messages_for_agent_node")
    messages = state.get("messages", [])
    if not messages:
        return []
        
    # Optimización: Filtrado en una sola pasada
    filtered_messages = []
    first_ai_found = False
    
    for msg in messages:
        if isinstance(msg, RemoveMessage):
            continue
            
        if not first_ai_found and isinstance(msg, AIMessage):
            first_ai_found = True
            filtered_messages = []
            
        if first_ai_found or not isinstance(msg, ToolMessage):
            filtered_messages.append(msg)
            
    return filtered_messages


def filter_and_prepare_messages_for_summary_node(state):
    """
    Filters and prepares the messages for summarization, normalizing their content. 
    Messages marked for Removal and Tools are also filtered out, and their content is normalized.
    """
    logging.info("filter_and_prepare_messages_for_summary_node")
    messages = state.get("messages", [])
    if not messages:
        return []
    
    # Optimización: Filtrado y normalización en una sola pasada
    filtered_messages = []
    for msg in messages:
        if not isinstance(msg, (RemoveMessage, ToolMessage)):
            filtered_messages.append(normalize_message(msg))
            
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


def get_execution_time(initial_date: datetime.datetime) -> float:
    """Calculate execution time from initial date until now
    
    Args:
        initial_date: Start timestamp of the execution
        
    Returns:
        float: Duration in seconds
    """
    end_time = datetime.datetime.now() # Restaurado a naive
    return (end_time - initial_date).total_seconds()


def calculate_execution_duration(initial_date: datetime.datetime, end_date: datetime.datetime):
    """ Calculate the execution duration """
    return (end_date - initial_date).total_seconds()


def decorate_message(message: BaseMessage, initial_date: datetime.datetime, conversation_id: str):
    """ Decorate the message with the execution time """
    message.additional_kwargs["end_timestamp"] = datetime.datetime.now() # Restaurado a naive
    message.additional_kwargs["end_time_seconds"] = get_execution_time(
        initial_date)
    message.additional_kwargs["conversation_id"] = conversation_id

