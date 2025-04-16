from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseLanguageModel
import logging

logger = logging.getLogger(__name__)

class LLMAdapter:
    """Adapter class to standardize LLM interactions"""

    @staticmethod
    def get_llm(model_name: str, temperature: float = 0) -> BaseLanguageModel:
        try:
            model = ChatOpenAI(model=model_name, temperature=temperature)
            return model
        except Exception as e:
            logger.exception(f"Error al instanciar ChatOpenAI: {e}")
            raise