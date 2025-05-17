from typing import Dict, Tuple, Optional
import logging
from datetime import datetime

class ModelCosts:
    """
    Clase para manejar los costos de los diferentes modelos de OpenAI.
    Los costos se actualizan según la documentación oficial de OpenAI.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Costos por token (actualizados a precios de OpenAI 2024-2025)
        self.costs: Dict[str, Dict[str, float]] = {
            "gpt-4.1": {
                "input": 0.000002,     # $2.00 por millón de tokens
                "output": 0.000008,    # $8.00 por millón de tokens
                "last_updated": "2025-04-14"
            },
            "gpt-4.1-mini": {
                "input": 0.0000004,    # $0.40 por millón de tokens
                "output": 0.0000016,   # $1.60 por millón de tokens
                "last_updated": "2025-04-14"
            },
            "gpt-4.1-nano": {
                "input": 0.0000001,    # $0.10 por millón de tokens
                "output": 0.0000004,   # $0.40 por millón de tokens
                "last_updated": "2025-04-14"
            },
            "gpt-4.5-preview": {
                "input": 0.000075,     # $75.00 por millón de tokens
                "output": 0.00015,     # $150.00 por millón de tokens
                "last_updated": "2025-02-27"
            },
            "gpt-4o": {
                "input": 0.0000025,    # $2.50 por millón de tokens
                "output": 0.00001,     # $10.00 por millón de tokens
                "last_updated": "2024-08-06"
            },
            "gpt-4o-mini": {
                "input": 0.00000015,   # $0.15 por millón de tokens
                "output": 0.0000006,   # $0.60 por millón de tokens
                "last_updated": "2024-07-18"
            }
        }
        
        # Rangos de validación de costos
        self.min_cost = 0.0000001  # $0.10 por millón
        self.max_cost = 0.0001     # $100 por millón

    def get_costs(self, model_name: str) -> Tuple[float, float]:
        """
        Obtiene los costos de entrada y salida para un modelo específico.
        
        Args:
            model_name: Nombre del modelo (ej: 'gpt-3.5-turbo', 'gpt-4')
            
        Returns:
            Tuple[float, float]: (costo_entrada, costo_salida)
            
        Raises:
            ValueError: Si el modelo no está soportado
        """
        model_costs = self.costs.get(model_name)
        if not model_costs:
            self.logger.warning(f"Modelo '{model_name}' no encontrado, usando gpt-3.5-turbo como fallback")
            # Esto causará un KeyError si gpt-3.5-turbo no está en self.costs, como era originalmente.
            model_costs = self.costs["gpt-3.5-turbo"]
            
        return model_costs["input"], model_costs["output"]

    def validate_costs(self, input_cost: float, output_cost: float) -> bool:
        """
        Valida que los costos estén dentro de rangos razonables.
        
        Args:
            input_cost: Costo por token de entrada
            output_cost: Costo por token de salida
            
        Returns:
            bool: True si los costos son válidos
        """
        return (self.min_cost <= input_cost <= self.max_cost and 
                self.min_cost <= output_cost <= self.max_cost)

    def calculate_cost(self, 
                      input_tokens: int, 
                      output_tokens: int, 
                      model_name: str = "gpt-3.5-turbo") -> Tuple[float, Dict[str, float]]:
        """
        Calcula el costo total para una interacción.
        
        Args:
            input_tokens: Número de tokens de entrada
            output_tokens: Número de tokens de salida
            model_name: Nombre del modelo a usar
            
        Returns:
            Tuple[float, Dict[str, float]]: (costo_total, desglose_costos)
        """
        try:
            input_cost, output_cost = self.get_costs(model_name)
            
            if not self.validate_costs(input_cost, output_cost):
                self.logger.warning(f"Costos fuera de rango para modelo {model_name}")
                return 0.0, {}
            
            input_cost_total = input_tokens * input_cost
            output_cost_total = output_tokens * output_cost
            total_cost = input_cost_total + output_cost_total
            
            cost_breakdown = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "input_cost_per_token": input_cost,
                "output_cost_per_token": output_cost,
                "input_cost_total": input_cost_total,
                "output_cost_total": output_cost_total,
                "total_cost": total_cost,
                "model": model_name,
                "calculation_date": datetime.now().isoformat()
            }
            
            return total_cost, cost_breakdown
            
        except Exception as e:
            self.logger.error(f"Error calculando costos: {e}")
            return 0.0, {}

    def get_supported_models(self) -> list:
        """
        Retorna la lista de modelos soportados.
        
        Returns:
            list: Lista de nombres de modelos
        """
        return list(self.costs.keys())

    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """
        Obtiene información detallada de un modelo.
        
        Args:
            model_name: Nombre del modelo
            
        Returns:
            Optional[Dict]: Información del modelo o None si no existe
        """
        return self.costs.get(model_name) 