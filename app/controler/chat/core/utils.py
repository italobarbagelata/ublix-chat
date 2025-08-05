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


def _clean_orphaned_tool_calls(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Remove AI messages with tool_calls that don't have corresponding tool responses.
    This prevents OpenAI 400 errors about orphaned tool_call_ids.
    """
    clean_messages = []
    
    for i, message in enumerate(messages):
        if isinstance(message, AIMessage) and hasattr(message, 'tool_calls') and message.tool_calls:
            # Extract tool call IDs with robust handling of different formats
            tool_call_ids = set()
            
            for tc in message.tool_calls:
                try:
                    # Handle different tool_call formats
                    if hasattr(tc, 'id'):
                        # LangChain ToolCall object
                        tool_call_ids.add(tc.id)
                    elif isinstance(tc, dict):
                        # Dictionary format
                        if 'id' in tc:
                            tool_call_ids.add(tc['id'])
                    else:
                        # Convert to string and extract
                        tc_str = str(tc)
                        if 'id=' in tc_str:
                            # Extract ID from string representation
                            parts = tc_str.split('id=')
                            if len(parts) > 1:
                                id_part = parts[1].split(',')[0].split(' ')[0].strip("'\"")
                                tool_call_ids.add(id_part)
                except Exception as e:
                    logging.warning(f"Error extracting tool_call ID: {e}")
                    continue
            
            # Only check for responses if we found valid tool call IDs
            if tool_call_ids:
                # Look for tool responses in subsequent messages
                has_all_responses = True
                for tool_call_id in tool_call_ids:
                    # Search for corresponding ToolMessage in remaining messages
                    found_response = False
                    for j in range(i + 1, len(messages)):
                        if (isinstance(messages[j], ToolMessage) and 
                            hasattr(messages[j], 'tool_call_id') and 
                            messages[j].tool_call_id == tool_call_id):
                            found_response = True
                            break
                    
                    if not found_response:
                        has_all_responses = False
                        break
                
                if has_all_responses:
                    clean_messages.append(message)
                else:
                    # Log the orphaned tool calls for debugging
                    logging.warning(f" Removing AI message with orphaned tool_calls: {tool_call_ids}")
                    # Skip this message to prevent OpenAI 400 error
                    continue
            else:
                # No valid tool call IDs found, keep the message
                clean_messages.append(message)
        else:
            # Non-AI message or AI message without tool_calls
            clean_messages.append(message)
    
    return clean_messages


def filter_and_prepare_messages_for_agent_node(state):
    """
    Filters and prepares the messages for agent answer.
    Ensures that AI messages with tool_calls have corresponding tool responses.
    """
    logging.info("filter_and_prepare_messages_for_agent_node")
    messages = state["messages"]
    if messages is None:
        messages = []
        
    original_count = len(messages)
    messages = [msg for msg in messages if not isinstance(msg, RemoveMessage)]
    
    # Clean orphaned tool calls to prevent OpenAI 400 errors
    clean_messages = _clean_orphaned_tool_calls(messages)
    
    # Log message counts for debugging
    logging.info(f" Message counts: original={original_count}, after_remove={len(messages)}, after_clean={len(clean_messages)}")
    
    first_ai_index = next((i for i, msg in enumerate(clean_messages) if isinstance(msg, AIMessage)), None)
    
    if first_ai_index is None:
        first_ai_index = 0

    filtered_messages = [msg for i, msg in enumerate(clean_messages) if i >= first_ai_index or not isinstance(msg, ToolMessage)]
    
    logging.info(f" Final message count for agent: {len(filtered_messages)}")
    
    return filtered_messages


def filter_and_prepare_messages_for_summary_node(state):
    """
    Filters and prepares the messages for summarization, normalizing their content. 
    Messages marked for Removal and Tools are also filtered out, and their content is normalized.
    Also cleans orphaned tool calls to prevent issues.
    """
    
    logging.info("filter_and_prepare_messages_for_summary_node")
    messages = state.get("messages", [])
    if messages is None:
        messages = []
    
    messages = [msg for msg in messages if not isinstance(msg, RemoveMessage)]
    
    # Clean orphaned tool calls before processing
    clean_messages = _clean_orphaned_tool_calls(messages)
    
    normalized_messages = [normalize_message(msg) for msg in clean_messages]
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
