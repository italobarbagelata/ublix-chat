from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseLanguageModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# Configuración de temperatura por familia de modelos
MODEL_TEMPERATURES = {
    'gpt-5': 1.0,      # GPT-5 family: temperature 1 recomendado
    'gpt-4': 0.0,      # GPT-4 family: temperature 0 para consistencia
    'default': 0.5     # Otros modelos: default conservador
}


class LLMAdapter:
    """
    Adapter class para estandarizar interacciones con LLMs.

    Soporta:
    - GPT-5 family: gpt-5-nano, gpt-5-mini, gpt-5, gpt-5.2, gpt-5.2-pro
    - GPT-4 family: gpt-4, gpt-4o, gpt-4o-mini, gpt-4-turbo
    - Otros modelos compatibles con OpenAI API
    """

    @staticmethod
    def get_llm(model_name: str, temperature: Optional[float] = None) -> BaseLanguageModel:
        """
        Factory method para crear instancias de LLM basado en el nombre del modelo.

        Args:
            model_name: Nombre del modelo (ej: 'gpt-5-mini', 'gpt-5-nano')
            temperature: Override de temperatura. Si es None, usa defaults por modelo.

        Returns:
            BaseLanguageModel configurado
        """
        # Si se especifica temperature explícita, usarla
        if temperature is not None:
            logger.debug(f"LLM: {model_name} con temperature={temperature} (explícita)")
            return ChatOpenAI(model=model_name, temperature=temperature)

        # Detectar familia de modelo y aplicar temperatura apropiada
        model_lower = model_name.lower()

        if 'gpt-5' in model_lower or 'gpt5' in model_lower:
            # GPT-5 family: gpt-5-nano, gpt-5-mini, gpt-5, gpt-5.2, gpt-5.2-pro
            temp = MODEL_TEMPERATURES['gpt-5']
            logger.debug(f"LLM: {model_name} (GPT-5 family) con temperature={temp}")
            return ChatOpenAI(model=model_name, temperature=temp)

        elif 'gpt-4' in model_lower or 'gpt4' in model_lower:
            # GPT-4 family: gpt-4, gpt-4o, gpt-4o-mini, gpt-4-turbo
            temp = MODEL_TEMPERATURES['gpt-4']
            logger.debug(f"LLM: {model_name} (GPT-4 family) con temperature={temp}")
            return ChatOpenAI(model=model_name, temperature=temp)

        else:
            # Otros modelos: default conservador
            temp = MODEL_TEMPERATURES['default']
            logger.debug(f"LLM: {model_name} (otro) con temperature={temp}")
            return ChatOpenAI(model=model_name, temperature=temp)

    @staticmethod
    def get_small_llm(temperature: Optional[float] = None) -> BaseLanguageModel:
        """
        Obtiene el modelo económico para tareas simples.
        Usa MODEL_CHATBOT_SMALL de las constantes.

        Ideal para: análisis de sentimiento, clasificación, OCR, resúmenes cortos.
        """
        from app.resources.constants import MODEL_CHATBOT_SMALL
        return LLMAdapter.get_llm(MODEL_CHATBOT_SMALL, temperature)

    @staticmethod
    def get_main_llm(temperature: Optional[float] = None) -> BaseLanguageModel:
        """
        Obtiene el modelo principal para chatbot.
        Usa MODEL_CHATBOT de las constantes.

        Ideal para: conversaciones, razonamiento complejo, uso de herramientas.
        """
        from app.resources.constants import MODEL_CHATBOT
        return LLMAdapter.get_llm(MODEL_CHATBOT, temperature)
