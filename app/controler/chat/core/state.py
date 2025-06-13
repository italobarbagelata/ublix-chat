from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from app.controler.chat.classes.project import Project


class CustomState(TypedDict):
    project: Project
    user_id: str
    exec_init: str
    messages: Annotated[Sequence[BaseMessage], add_messages]
    summary: str
    conversation_id: str
    username: str
    source_id: str
    source: str
    unique_id: str

