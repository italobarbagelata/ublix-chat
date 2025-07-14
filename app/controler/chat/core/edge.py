from typing import Literal
from app.controler.chat.core.state import CustomState
import logging

def invoke_tools_summary(state: CustomState) -> Literal["tools", "summarize_conversation"]:
    """
    Router SIMPLIFICADO - Sin intent detection, lógica simple y directa.
    """
    try:
        messages = state.get("messages", [])
        
        if not messages:
            logging.info("Router: No messages found, ending conversation")
            return "summarize_conversation"
        
        last_message = messages[-1]
        
        # Lógica simple: si el último mensaje tiene tool_calls, ir a tools
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logging.info(f"Router: AI requested {len(last_message.tool_calls)} tools, routing to tools node")
            return "tools"
        
        # Si hay muchos mensajes (conversación larga), finalizar
        if len(messages) > 20:
            logging.info(f"Router: Long conversation ({len(messages)} messages), ending conversation")
            return "summarize_conversation"
        
        # Para conversaciones normales, finalizar (el AI ya respondió)
        logging.info("Router: Normal conversation completed, ending conversation")
        return "summarize_conversation"
        
    except Exception as e:
        logging.error(f"Router error in invoke_tools_summary: {e}")
        return "summarize_conversation"

def route_from_tools(state: CustomState) -> Literal["agent"]:
    """
    Router simple: después de herramientas, siempre volver al agent.
    """
    logging.info("Router: Post-tools execution, returning to agent")
    return "agent"

def should_continue_conversation(state: CustomState) -> Literal["agent", "summarize_conversation"]:
    """
    Router simple: decide si continuar la conversación.
    """
    messages = state.get("messages", [])
    
    # Si hay demasiados mensajes, finalizar
    if len(messages) > 50:
        logging.info(f"Router: Very long conversation ({len(messages)} messages), ending conversation")
        return "summarize_conversation"
    
    # Por defecto, continuar
    return "agent"