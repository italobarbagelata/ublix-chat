import logging
import asyncio
import datetime
import uuid
from typing import Any, Dict, Optional
from app.controler.chat.classes.token_metrics import TokenMetrics
from app.controler.chat.services.token_metrics_service import TokenMetricsService
from app.controler.chat.services.memory_optimization_service import MemoryOptimizationService
from app.controler.chat.services.token_calculation_service import TokenCalculationService
from app.controler.chat.classes.model_costs import ModelCosts
from app.controler.chat.store.persistence import Persist

class BackgroundProcessingService:
    """Servicio para manejar todas las tareas en segundo plano"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.token_metrics_service = TokenMetricsService()
        self.memory_service = MemoryOptimizationService()
        self.token_service = TokenCalculationService()
        self.model_costs = ModelCosts()
        self.database = Persist()
    
    async def process_all_background_tasks(
        self,
        final_state: Dict[str, Any],
        token_metrics_result: Optional[Dict[str, int]],
        ai_response_obj: Any,
        model_name: str,
        initial_time: datetime.datetime,
        conversation_id: str,
        project_id: str,
        user_id: str,
        source_id: str,
        graph: Any
    ):
        """Procesa todas las tareas en segundo plano de manera paralela"""
        try:
            # Ejecutar todas las tareas en paralelo
            await asyncio.gather(
                self._process_metrics(
                    token_metrics_result, ai_response_obj, model_name, 
                    initial_time, conversation_id, project_id, user_id, source_id
                ),
                self.memory_service.optimize_and_save_state(graph, project_id, user_id),
                self._persist_conversation(final_state),
                return_exceptions=True
            )
            
        except Exception as e:
            self.logger.error(f"Error en tareas en segundo plano: {e}", exc_info=True)
    
    async def _process_metrics(
        self,
        token_metrics_result: Optional[Dict[str, int]],
        ai_response_obj: Any,
        model_name: str,
        initial_time: datetime.datetime,
        conversation_id: str,
        project_id: str,
        user_id: str,
        source_id: str
    ):
        """Procesa y guarda métricas de tokens"""
        try:
            if token_metrics_result and ai_response_obj:
                output_tokens_count = self.token_service.calculate_output_tokens(
                    ai_response_obj, model_name
                )
                
                total_input_tokens_approx = sum([
                    token_metrics_result.get("system_tokens", 0),
                    token_metrics_result.get("input_tokens", 0),
                    token_metrics_result.get("context_tokens", 0),
                    token_metrics_result.get("prompt_memory_tokens", 0),
                    token_metrics_result.get("project_info_tokens", 0),
                    token_metrics_result.get("previous_summary_tokens", 0),
                    token_metrics_result.get("date_time_tokens", 0)
                ])
                
                total_output_tokens_approx = output_tokens_count
                
                total_cost_val, cost_breakdown_val = self.model_costs.calculate_cost(
                    input_tokens=total_input_tokens_approx,
                    output_tokens=total_output_tokens_approx,
                    model_name=model_name
                )
                
                metrics_obj = TokenMetrics(
                    project_id=project_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id="message_id",
                    timestamp=initial_time,
                    tokens={
                        "system_prompt": token_metrics_result.get("system_tokens", 0),
                        "input": token_metrics_result.get("input_tokens", 0),
                        "output": output_tokens_count,
                        "context": token_metrics_result.get("context_tokens", 0),
                        "tools_input": 0,
                        "tools_output": 0,
                        "tools_total": 0,
                        "prompt_memory": token_metrics_result.get("prompt_memory_tokens", 0),
                        "new_summary": 0,
                        "project_info": token_metrics_result.get("project_info_tokens", 0),
                        "previous_summary": token_metrics_result.get("previous_summary_tokens", 0),
                        "date_time": token_metrics_result.get("date_time_tokens", 0),
                        "total_input_approx": total_input_tokens_approx,
                        "total_output_approx": total_output_tokens_approx,
                        "total": total_input_tokens_approx + total_output_tokens_approx
                    },
                    cost=total_cost_val,
                    source=source_id,
                    cost_breakdown=cost_breakdown_val
                )
                
                await asyncio.to_thread(self.token_metrics_service.save_metrics, metrics_obj)
                
        except Exception as e:
            self.logger.error(f"Error processing metrics: {e}", exc_info=True)
    
    async def _persist_conversation(self, final_state: Dict[str, Any]):
        """Persiste la conversación en la base de datos"""
        try:
            await asyncio.to_thread(self.database.persist_conversation, final_state)
        except Exception as e:
            self.logger.error(f"Error persisting conversation: {e}", exc_info=True) 