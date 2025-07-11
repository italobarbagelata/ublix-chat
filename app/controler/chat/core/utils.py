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


def get_execution_time(initial_date: Union[str, datetime.datetime]):
    end_time = datetime.datetime.now()
    
    # Handle both string (ISO format) and datetime objects
    if isinstance(initial_date, str):
        # Parse ISO format string to datetime
        if 'Z' in initial_date or '+' in initial_date:
            # Handle timezone-aware strings
            start_time = datetime.datetime.fromisoformat(initial_date.replace('Z', '+00:00'))
            # Convert to naive datetime for comparison
            start_time = start_time.replace(tzinfo=None)
        else:
            # Handle timezone-naive strings
            start_time = datetime.datetime.fromisoformat(initial_date)
    elif isinstance(initial_date, datetime.datetime):
        # Ensure datetime is timezone-naive for comparison
        start_time = initial_date.replace(tzinfo=None) if initial_date.tzinfo else initial_date
    else:
        # Fallback: assume it's current time
        start_time = end_time
    
    return (end_time - start_time).total_seconds()


def calculate_execution_duration(initial_date: datetime.datetime, end_date: datetime.datetime):
    """ Calculate the execution duration """
    return (end_date - initial_date).total_seconds()


def decorate_message(message: BaseMessage, initial_date: datetime.datetime, conversation_id: str):
    """ Decorate the message with the execution time """
    message.additional_kwargs["end_timestamp"] = datetime.datetime.now()
    message.additional_kwargs["end_time_seconds"] = get_execution_time(
        initial_date)
    message.additional_kwargs["conversation_id"] = conversation_id
