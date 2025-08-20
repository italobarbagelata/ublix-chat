from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END, START
from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import json

# Estado simple
class SimpleState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

# Crear grafo simple
def create_simple_graph():
    workflow = StateGraph(SimpleState)
    
    def agent(state):
        messages = state["messages"]
        print(f"Agent received {len(messages)} messages")
        for i, msg in enumerate(messages):
            print(f"  Message {i}: {type(msg).__name__}: {str(msg.content)[:50]}")
        return {"messages": [AIMessage(content=f"Response to: {messages[-1].content}")]}
    
    workflow.add_node("agent", agent)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

# Test
graph = create_simple_graph()

# Primera invocación
print("\n=== First invocation ===")
result1 = graph.invoke(
    {"messages": [HumanMessage(content="Hello")]},
    {"configurable": {"thread_id": "test_user"}}
)

# Segunda invocación - debería tener el historial
print("\n=== Second invocation ===")
result2 = graph.invoke(
    {"messages": [HumanMessage(content="Do you remember me?")]},
    {"configurable": {"thread_id": "test_user"}}
)

print("\n=== Result ===")
print(f"Total messages in final state: {len(result2['messages'])}")
