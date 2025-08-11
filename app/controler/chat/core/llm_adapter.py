from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseLanguageModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class LLMAdapter:
    """Adapter class to standardize LLM interactions"""
    
    @staticmethod
    def get_llm(model_name: str, temperature: Optional[float] = None) -> BaseLanguageModel:
        """
        Factory method to create LLM instances based on model name
        
        Args:
            model_name: The model to use (e.g., 'gpt-4', 'gpt-5-mini')
            temperature: Optional temperature override. If None, uses model-specific defaults
        """
        ChatOpenAI.model_rebuild()
        
        # Si se especifica temperature explícita, usarla
        if temperature is not None:
            logger.info(f"Using explicit temperature {temperature} for {model_name}")
            return ChatOpenAI(model=model_name, temperature=temperature)
        
        # Configuración automática basada en el modelo
        model_lower = model_name.lower()
        
        if 'gpt-5' in model_lower or 'gpt5' in model_lower:
            # GPT-5 (incluye gpt-5, gpt5, gpt-5-mini, gpt5-mini, etc.): usar temperature 1
            logger.info(f"Detected GPT-5 model ({model_name}), using temperature=1")
            return ChatOpenAI(model=model_name, temperature=1)
        
        elif 'gpt-4' in model_lower or 'gpt4' in model_lower:
            # GPT-4 (incluye gpt-4, gpt4, gpt-4o, gpt-4o-mini, gpt4-turbo, etc.): usar temperature 0
            logger.info(f"Detected GPT-4 model ({model_name}), using temperature=0")
            return ChatOpenAI(model=model_name, temperature=0)
        
        else:
            # Otros modelos: default conservador de 0.5
            logger.info(f"Unknown model type ({model_name}), using default temperature=0.5")
            return ChatOpenAI(model=model_name, temperature=0.5)