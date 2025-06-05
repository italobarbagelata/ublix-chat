import logging
import datetime
import asyncio
from typing import Dict, Any, Optional
from app.controler.chat.classes.token_counter import TokenCounter
from app.controler.chat.core.nodes import get_date_range, TIMEZONE

class TokenCalculationService:
    """Servicio para calcular tokens de manera optimizada y paralela"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.token_counter = TokenCounter()
    
    async def calculate_tokens_async(self, message: str, project: Any, user_id: str, graph) -> Optional[Dict[str, int]]:
        """Calcula tokens en segundo plano con paralelización optimizada"""
        try:
            # Paralelizar operaciones independientes
            tasks = []
            
            # Tarea 1: Calcular tokens del system prompt y input
            async def calculate_basic_tokens():
                system_prompt = project.instructions if project and hasattr(project, 'instructions') else ""
                system_tokens = self.token_counter.count_system_prompt_tokens(system_prompt)
                input_tokens = self.token_counter.count_message_tokens(message, 'high')
                return {"system_tokens": system_tokens, "input_tokens": input_tokens}
            
            # Tarea 2: Calcular tokens de información del proyecto
            async def calculate_project_tokens():
                project_info_tokens = 0
                if hasattr(project, 'name') and project.name:
                    project_info_tokens += self.token_counter.count_tokens(project.name, 'low')
                if hasattr(project, 'personality') and project.personality:
                    project_info_tokens += self.token_counter.count_tokens(project.personality, 'low')
                
                prompt_memory_tokens = 0
                if hasattr(project, 'prompt_memory') and project.prompt_memory:
                    formatted_prompt_memory = f"system: {project.prompt_memory}"
                    prompt_memory_tokens = self.token_counter.count_tokens(formatted_prompt_memory, 'low')
                
                return {"project_info_tokens": project_info_tokens, "prompt_memory_tokens": prompt_memory_tokens}
            
            # Tarea 3: Calcular tokens de fecha/hora
            async def calculate_datetime_tokens():
                date_time_tokens = 0
                try:
                    now_in_timezone = datetime.datetime.now().astimezone(TIMEZONE)
                    now_str = now_in_timezone.isoformat()
                    
                    date_range = get_date_range()
                    date_range_str = ", ".join(date_range)
                    date_time_tokens += self.token_counter.count_tokens(now_str, 'low')
                    date_time_tokens += self.token_counter.count_tokens(date_range_str, 'low')
                    date_time_tokens += self.token_counter.count_tokens("\nConsidera que las fechas de referencia son: ", 'low')
                except Exception as e:
                    self.logger.warning(f"Error counting date/time tokens: {e}")
                return {"date_time_tokens": date_time_tokens}
            
            # Tarea 4: Calcular tokens de contexto y resumen
            async def calculate_context_tokens():
                current_checkpoints = graph.checkpointer.get({"configurable": {"thread_id": user_id}})
                context_tokens = 0
                previous_summary_content = ""
                previous_summary_tokens = 0
                
                if current_checkpoints:
                    state_values_for_context = current_checkpoints.values if hasattr(current_checkpoints, 'values') else current_checkpoints
                    messages_from_state = []
                    try:
                        if isinstance(state_values_for_context, dict):
                            latest_checkpoint_data = list(state_values_for_context.get('', {}).values())[-1] if state_values_for_context.get('') else None
                            if isinstance(latest_checkpoint_data, dict):
                                messages_from_state = latest_checkpoint_data.get("messages", [])
                                previous_summary_content = latest_checkpoint_data.get("summary", "")
                    except Exception as e:
                        self.logger.warning(f"Error extracting messages from checkpoint: {e}")
                    
                    if messages_from_state:
                        context_tokens = self.token_counter.count_conversation_tokens(messages_from_state)
                    
                    if previous_summary_content:
                        formatted_summary_prompt = f"system: Summary of conversation earlier: {previous_summary_content}"
                        previous_summary_tokens = self.token_counter.count_tokens(formatted_summary_prompt, 'low')
                
                return {"context_tokens": context_tokens, "previous_summary_tokens": previous_summary_tokens}
            
            # Ejecutar todas las tareas en paralelo
            basic_tokens_task = asyncio.create_task(calculate_basic_tokens())
            project_tokens_task = asyncio.create_task(calculate_project_tokens())
            datetime_tokens_task = asyncio.create_task(calculate_datetime_tokens())
            context_tokens_task = asyncio.create_task(calculate_context_tokens())
            
            # Esperar resultados en paralelo
            basic_result, project_result, datetime_result, context_result = await asyncio.gather(
                basic_tokens_task,
                project_tokens_task, 
                datetime_tokens_task,
                context_tokens_task,
                return_exceptions=True
            )
            
            # Combinar resultados con manejo de errores
            combined_result = {}
            
            if isinstance(basic_result, dict):
                combined_result.update(basic_result)
            else:
                self.logger.error(f"Error in basic tokens calculation: {basic_result}")
                combined_result.update({"system_tokens": 0, "input_tokens": 0})
            
            if isinstance(project_result, dict):
                combined_result.update(project_result)
            else:
                self.logger.error(f"Error in project tokens calculation: {project_result}")
                combined_result.update({"project_info_tokens": 0, "prompt_memory_tokens": 0})
            
            if isinstance(datetime_result, dict):
                combined_result.update(datetime_result)
            else:
                self.logger.error(f"Error in datetime tokens calculation: {datetime_result}")
                combined_result.update({"date_time_tokens": 0})
            
            if isinstance(context_result, dict):
                combined_result.update(context_result)
            else:
                self.logger.error(f"Error in context tokens calculation: {context_result}")
                combined_result.update({"context_tokens": 0, "previous_summary_tokens": 0})
            
            return combined_result
            
        except Exception as e:
            self.logger.error(f"Error calculating tokens: {e}", exc_info=True)
            return None
    
    def calculate_output_tokens(self, ai_response_obj, model_name: str) -> int:
        """Calcula tokens de salida para una respuesta AI"""
        try:
            return self.token_counter.count_message_tokens(
                ai_response_obj.content if hasattr(ai_response_obj, 'content') else str(ai_response_obj),
                model_name
            )
        except Exception as e:
            self.logger.error(f"Error calculating output tokens: {e}")
            return 0 