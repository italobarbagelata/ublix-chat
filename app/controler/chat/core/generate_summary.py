from pydantic import BaseModel

from app.controler.chat.core.llm_adapter import LLMAdapter    
from app.resources.constants import CONVERSATION_DATA_TABLE, DEFAULT_PROMPT_MEMORY, MODEL_CHATBOT
from app.resources.postgresql import SupabaseDatabase

class SummaryPayload(BaseModel):
    project_id: str
    phone_number: str
    message: str


def generate_summary(payload: SummaryPayload):
    """ Generate or updates a summary of a user-project chat """
    database = SupabaseDatabase()
    user_conversation_summary = database.select(CONVERSATION_DATA_TABLE, {"phone_number": payload.phone_number, "project_id": payload.project_id})

    new_conversation = user_conversation_summary is None or len(user_conversation_summary) == 0
    if new_conversation:
        summary_instruction = "Please start creating a summary with this message."
        previous_summary = ""
    else:
        summary_instruction = "Please update and expand the summary."
        previous_summary = user_conversation_summary[0].get("summary", "")

    summary_message = f"""
        You are a helpful assistant that creates a summary of the conversation.
        Your task is to summarize the conversation based on the user message and the previous summary.
        You should not answer the user message, your main task is to create a summary of the conversation.
        
        {summary_instruction}
        
        When making the new summary, follow the instructions in <memory_instructions> strictly,
        with them having precedence over any other instructions.

        <memory_instructions>

        {DEFAULT_PROMPT_MEMORY}

        <memory_instructions>
        
        The summary should act as a long-term memory focusing on CONVERSATION FLOW and CONTEXT.
        Do NOT include basic contact data (name, email, phone, age, city, etc.) as these are stored in contact_tool.
        Focus on: conversation progress, user interests, specific requests, project status, next steps.
        Do not use emojis and ensure the summary is generated in Spanish. 
        Limit the summary to a maximum of 4 paragraphs or 1023 characters.  
        Current conversation summary: {previous_summary}
    """

    model_summary = LLMAdapter.get_llm(MODEL_CHATBOT)  # Sin temperature para compatibilidad
    messages = [
        {"role": "system", "content": summary_message},
        {"role": "user", "content": payload.message},
    ]

    result = model_summary.invoke(messages)

    new_summary = result.content

    if not new_summary:
        raise ValueError("The summary is empty. Please try again.")

    if new_conversation:
        database.insert(CONVERSATION_DATA_TABLE, {
            "project_id": payload.project_id,
            "phone_number": payload.phone_number,
            "summary": new_summary
        })
    else:
        database.update(CONVERSATION_DATA_TABLE, {"summary": new_summary}, {"phone_number": payload.phone_number, "project_id": payload.project_id})

    return {"message": new_summary}
