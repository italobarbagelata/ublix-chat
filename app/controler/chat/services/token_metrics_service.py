from datetime import datetime
from typing import List, Dict
from app.controler.chat.classes.token_metrics import TokenMetrics
from app.controler.chat.store.persistence_state import MemoryStatePersistence

class TokenMetricsService:
    def __init__(self):
        self.db = MemoryStatePersistence()
        self.collection = "token_metrics"

    def save_metrics(self, metrics: TokenMetrics):
        """Guarda las métricas de tokens en la base de datos"""
        return self.db.save_token_metrics(metrics)

    def get_project_metrics(self, project_id: str) -> List[TokenMetrics]:
        """Obtiene todas las métricas de un proyecto"""
        return self.db.get_project_token_metrics(project_id)

    def get_user_metrics(self, user_id: str) -> List[TokenMetrics]:
        """Obtiene todas las métricas de un usuario"""
        return self.db.get_user_token_metrics(user_id)

    def get_conversation_metrics(self, conversation_id: str) -> List[TokenMetrics]:
        """Obtiene todas las métricas de una conversación"""
        return self.db.get_conversation_token_metrics(conversation_id)

    def get_project_summary(self, project_id: str) -> Dict:
        """Obtiene un resumen de las métricas de un proyecto"""
        metrics = self.get_project_metrics(project_id)
        total_tokens = sum(m.tokens["total"] for m in metrics)
        total_cost = sum(m.cost or 0 for m in metrics)
        
        return {
            "total_interactions": len(metrics),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "average_tokens_per_interaction": total_tokens / len(metrics) if metrics else 0,
            "average_cost_per_interaction": total_cost / len(metrics) if metrics else 0,
            "tokens_by_type": {
                "system_prompt": sum(m.tokens.get("system_prompt", 0) for m in metrics),
                "input": sum(m.tokens.get("input", 0) for m in metrics),
                "output": sum(m.tokens.get("output", 0) for m in metrics),
                "context": sum(m.tokens.get("context", 0) for m in metrics),
                "tools": sum(m.tokens.get("tools", 0) for m in metrics),
                "date_time": sum(m.tokens.get("date_time", 0) for m in metrics),
                "new_summary": sum(m.tokens.get("new_summary", 0) for m in metrics),
                "tools_input": sum(m.tokens.get("tools_input", 0) for m in metrics),
                "tools_total": sum(m.tokens.get("tools_total", 0) for m in metrics),
                "project_info": sum(m.tokens.get("project_info", 0) for m in metrics),
                "tools_output": sum(m.tokens.get("tools_output", 0) for m in metrics),
                "prompt_memory": sum(m.tokens.get("prompt_memory", 0) for m in metrics),
                "previous_summary": sum(m.tokens.get("previous_summary", 0) for m in metrics),
                "total_input_approx": sum(m.tokens.get("total_input_approx", 0) for m in metrics),
                "total_output_approx": sum(m.tokens.get("total_output_approx", 0) for m in metrics)
            }
        } 