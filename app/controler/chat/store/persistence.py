import logging
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from app.controler.chat.classes.chat_state import ChatState
from app.controler.chat.classes.project import Project
from app.controler.chat.core.state import CustomState
from app.controler.chat.core.utils import calculate_execution_duration
from app.resources.postgresql import SupabaseDatabase
from app.resources.constants import (
    AI_MESSAGE_TABLE,
    MESSAGES_TABLE,
    PROJECTS_TABLE,
    CONVERSATION_DATA_TABLE,
    MEMORY_STATES_TABLE,
)
from uuid import uuid4
import threading
import datetime

class Persist(object):

    def __init__(self):
        self.db = SupabaseDatabase()

    def upsert(self, table, filter_criteria, data):
        """Upsert operation with proper error handling."""
        try:
            existing_record = self.db.select(table, filters=filter_criteria)
            if existing_record:
                self.db.update(table, data=data, filters=filter_criteria)
            else:
                self.db.insert(table, {**filter_criteria, **data})
        except Exception as e:
            logging.error(f"Error in upsert operation: {e}")
            raise

    def delete(self, table, filter_criteria):
        """Delete records with proper error handling."""
        try:
            logging.info(f"Deleting records from table: {table}")
            logging.info(f"Filter criteria: {filter_criteria}")
            result = self.db.delete(table, filters=filter_criteria)
            logging.info(f"Deletion result: {result}")
            return result
        except Exception as e:
            logging.error(f"Error in delete operation: {e}")
            raise

    def find_one(self, table, filter_criteria):
        """Find a single record with proper error handling."""
        try:
            logging.info(f"Finding one record in table: {table}")
            logging.info(f"Filter criteria: {filter_criteria}")
            results = self.db.select(table, filters=filter_criteria)
            #logging.info(f"Query results: {results}")
            return results[0] if results else None
        except Exception as e:
            logging.error(f"Error in find_one operation: {e}")
            raise

    def find(self, table, filter_criteria):
        """Find multiple records with proper error handling."""
        try:
            logging.info(f"Finding records in table: {table}")
            logging.info(f"Filter criteria: {filter_criteria}")
            results = self.db.select(table, filters=filter_criteria)
            #logging.info(f"Query results: {results}")
            return results if results else []
        except Exception as e:
            logging.error(f"Error in find operation: {e}")
            raise

    def save_state(self, state: ChatState):
        """Save chat state with proper error handling."""
        try:
            state_data = {
                "project_id": state.project_id,
                "user_id": state.user_id,
                "state": state.to_json()
            }
            self.upsert(MEMORY_STATES_TABLE, 
                        {"project_id": state.project_id, "user_id": state.user_id},
                        state_data)
        except Exception as e:
            logging.error(f"Error saving state: {e}")
            raise

    def fetch_state(self, project_id, user_id):
        """Fetch chat state with proper error handling."""
        try:
            state = self.find_one(MEMORY_STATES_TABLE, {
                "project_id": project_id,
                "user_id": user_id
            })
            return state["state"] if state else None
        except Exception as e:
            logging.error(f"Error fetching state: {e}")
            raise

    def find_project(self, project_id) -> Project:
        """Find project with proper error handling."""
        try:
            logging.info(f"Searching for project with ID: {project_id}")
            project = self.find_one(PROJECTS_TABLE, {"project_id": project_id})
            
            if not project:
                logging.error(f"Project not found in database. Project ID: {project_id}")
                raise ValueError(f"Project with id {project_id} not found in the database and table {PROJECTS_TABLE}. Please verify the project ID.")
            
            #logging.info(f"Project found: {project}")
            return Project.from_dict(project)
        except Exception as e:
            logging.error(f"Error while fetching project {project_id}: {str(e)}")
            raise

    def persist_conversation(self, conversation: CustomState):
        logging.info(f"Persisting conversation")
        try:
            project_id = conversation["project"].id
            phone_number = conversation["user_id"]
            username = conversation["username"]
            source_id = conversation["source_id"]
            source = conversation["source"]
            database = SupabaseDatabase()
            tool_messages = []
            conversation_id = conversation["conversation_id"]
            last_execution = conversation["exec_init"]
            
            # Optimización: Preparar todos los mensajes antes de insertar
            messages_to_insert = []
            ai_message_id = None
            last_ai_message_index = None  # Para rastrear el índice del último mensaje de IA
            
            for i, message in enumerate(conversation["messages"]):
                if message.additional_kwargs.get("saved", False):
                    continue

                message.additional_kwargs["saved"] = True

                if isinstance(message, ToolMessage):
                    context = str(message.content).replace("\n", " ")
                    tool_messages.append({
                        "conversation_id": conversation_id,
                        "type": "tool",
                        "content": context,
                        "tool": message.name,
                        "call_timestamp": last_execution.isoformat(),
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "duration": 0
                    })
                    continue

                execution_duration = calculate_execution_duration(
                    last_execution, message.additional_kwargs["end_timestamp"])
                last_execution = message.additional_kwargs["end_timestamp"]
                
                if isinstance(message, HumanMessage):
                    messages_to_insert.append({
                        "conversation_id": conversation_id,
                        "project_id": project_id,
                        "phone_number": phone_number,
                        "username": username,
                        "source_id": source_id,
                        "source": source,
                        "type": "human",
                        "content": message.content,
                        "latency": execution_duration
                    })
                    
                elif isinstance(message, AIMessage):
                    is_ai_response = i == len(conversation["messages"]) - 1
                    
                    ai_message_payload = {
                        "conversation_id": conversation_id,
                        "project_id": project_id,
                        "phone_number": phone_number,
                        "username": username,
                        "source_id": source_id,
                        "source": source,
                        "type": "ai",
                        "content": message.content,
                        "latency": execution_duration,
                        "has_context": len(tool_messages) > 0
                    }
                    
                    # Agregar todos los mensajes de IA a la lista, incluyendo el último
                    if is_ai_response:
                        last_ai_message_index = len(messages_to_insert)  # Guardar el índice
                        messages_to_insert.append(ai_message_payload)
                    else:
                        tool_call = self.get_tool_call(message)
                        if tool_call:
                            token_usage = self.get_token_usage(message)
                            tool_messages.append({
                                "conversation_id": conversation_id,
                                "type": "ai_tool",
                                "content": tool_call.get("arguments"),
                                "tool": tool_call.get("name"),
                                "call_timestamp": last_execution.isoformat(),
                                "input_tokens": token_usage.get("prompt_tokens"),
                                "output_tokens": token_usage.get("completion_tokens"),
                                "duration": execution_duration
                            })
                        else: # AIMessage no final y no herramienta
                           messages_to_insert.append(ai_message_payload)
            
            # Insertar mensajes en batch manteniendo el orden
            if messages_to_insert:
                try:
                    # Insertar todos los mensajes en orden
                    inserted_messages = database.batch_insert(MESSAGES_TABLE, messages_to_insert)
                    
                    # Obtener el ID del último mensaje de IA si existe
                    if last_ai_message_index is not None and inserted_messages:
                        if isinstance(inserted_messages, list) and len(inserted_messages) > last_ai_message_index:
                            ai_message_id = inserted_messages[last_ai_message_index].get("id")
                        elif isinstance(inserted_messages, dict):
                            # Si batch_insert devuelve un solo dict, es probable que sea el último insertado
                            ai_message_id = inserted_messages.get("id")
                            
                except Exception as e:
                    logging.error(f"Error inserting messages batch: {e}")
                    # Fallback a inserción individual manteniendo el orden
                    for i, msg in enumerate(messages_to_insert):
                        result = database.insert(MESSAGES_TABLE, msg)
                        # Si es el último mensaje de IA, guardar su ID
                        if i == last_ai_message_index and result:
                            if isinstance(result, list) and len(result) > 0:
                                ai_message_id = result[0].get("id")
                            elif isinstance(result, dict):
                                ai_message_id = result.get("id")
            
            # Insertar tool messages en batch
            if tool_messages and ai_message_id:
                try:
                    for tool_message in tool_messages:
                        tool_message["message_id"] = ai_message_id
                        tool_message["id"] = str(uuid4())
                    database.batch_insert(AI_MESSAGE_TABLE, tool_messages)
                except Exception as e:
                    logging.error(f"Error inserting tool messages batch: {e}")
                    # Fallback a inserción individual
                    for tool_message in tool_messages:
                        database.insert(AI_MESSAGE_TABLE, tool_message)
                        
            logging.info(f"Persistencia de conversación completada para ID: {conversation_id}")
                        
        except Exception as e:
            logging.error(f"Error in persist_conversation: {e}")
        

    def get_tool_call(self, message):
        try:
            tool_calls = message.additional_kwargs.get("tool_calls", [])
            tool_calls = tool_calls[0].get("function")
            return {
                "arguments": tool_calls.get("arguments"),
                "name": tool_calls.get("name"),
            }
        except Exception as e:
            logging.error(f"Error getting tool call: {e}")
            return {
                "arguments": "{}",
                "name": "",
            }
            
    def get_token_usage(self, message):
        try:
            token_usage = message.response_metadata.get("token_usage")
            return {
                "prompt_tokens": token_usage.get("prompt_tokens"),
                "completion_tokens": token_usage.get("completion_tokens"),
            }
        except Exception as e:
            logging.error(f"Error getting token usage: {e}")
            return {
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

    def update_summary(self, conversation: CustomState):
        """
        Actualiza el resumen de la conversación. 
        Se ejecuta en segundo plano para no bloquear el flujo principal.
        """
        threading.Thread(target=self._update_summary_thread, 
                         args=(conversation,), 
                         daemon=True).start()
        return None
        
    def _update_summary_thread(self, conversation: CustomState):
        """Método interno que se ejecuta en un hilo separado para actualizar el resumen."""
        try:
            filter_criteria = {
                "project_id": conversation["project"].id,
                "phone_number": conversation["user_id"]
            }

            summary = self.find(CONVERSATION_DATA_TABLE, filter_criteria)
        
            if len(summary) == 0:
                self.db.insert(CONVERSATION_DATA_TABLE, {
                    "project_id": conversation["project"].id,
                    "phone_number": conversation["user_id"],
                    "summary": conversation["summary"]
                })
            else:
                self.db.update(CONVERSATION_DATA_TABLE, 
                            {"summary": conversation["summary"]}, 
                            filter_criteria)
                            
            logging.info(f"Actualización de resumen completada para proyecto: {conversation['project'].id}, usuario: {conversation['user_id']}")
        except Exception as e:
            logging.error(f"Error updating summary: {e}")

    def get_summary(self, conversation: CustomState):
        """Get the summary of a conversation based on project_id and phone_number

        Args:
            project_id: str : The id of the project
            phone_number: str : The phone number of the user

        Returns:
            str: The summary of the conversation or empty string if not found
        """
        filter_criteria = {
            "project_id": conversation["project"].id,
            "phone_number": conversation["user_id"]
        }

        database = SupabaseDatabase()
        summary_records = database.select(CONVERSATION_DATA_TABLE, filter_criteria)

        if len(summary_records) > 0 and "summary" in summary_records[0]:
            return summary_records[0]["summary"]
        return ""