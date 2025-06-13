from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseLanguageModel

class LLMAdapter:
    """Adapter class to standardize LLM interactions"""
    
    @staticmethod
    def get_llm(model_name: str, temperature: float = 0) -> BaseLanguageModel:
        """Factory method to create LLM instances based on model name"""
        ChatOpenAI.model_rebuild()
        return ChatOpenAI(model=model_name, temperature=temperature)