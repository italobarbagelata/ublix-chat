from typing import Literal
from app.controler.chat.core.state import CustomState
import logging

def invoke_tools_summary(state: CustomState) -> Literal["tools", "summarize_conversation"]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        logging.info("the invoke_tools_summary was called and returned tools")
        #logging.info(last_message)
        return "tools"
    logging.info("the invoke_tools_summary was called and returned summarize_conversation")
    return "summarize_conversation"
