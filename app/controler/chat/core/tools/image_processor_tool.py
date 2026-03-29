import logging
from typing import Optional, Dict, Any
from langchain_core.tools import BaseTool
from langchain_core.callbacks.manager import CallbackManagerForToolRun
from openai import AsyncOpenAI
import json
import os
from pydantic import Field

logger = logging.getLogger(__name__)

class ImageProcessorTool(BaseTool):
    name: str = "image_processor"
    description: str = """
    Herramienta para extraer texto de imágenes.
    Útil cuando el usuario envía una imagen y necesitas leer su contenido.
    """
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self):
        super().__init__()
        self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    async def _process_image_with_gpt(self, image_url: str) -> str:
        """
        Procesa la imagen con GPT-4 Vision para extraer el texto.
        """
        try:
            response = await self._client.chat.completions.create(
                model=os.getenv("MODEL_CHATBOT"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extrae todo el texto visible en esta imagen. Si hay números, fechas, montos o cualquier otro dato relevante, inclúyelos también. Responde solo con el texto extraído, sin explicaciones adicionales."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
                
        except Exception as e:
            logger.error(f"Error processing image with GPT: {str(e)}")
            return f"Error procesando la imagen: {str(e)}"
    
    async def _arun(
        self,
        image_url: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Procesa la imagen usando GPT-4 Vision.
        """
        try:
            logger.info(f"🖼️ IMAGE_PROCESSOR TOOL LLAMADO con URL: {image_url}")
            result = await self._process_image_with_gpt(image_url)
            logger.info(f"🖼️ IMAGE_PROCESSOR RESULTADO: {result[:100]}...")
            return result
        except Exception as e:
            logger.error(f"Error in image processor: {str(e)}")
            return f"Error procesando la imagen: {str(e)}"
    
    def _run(
        self,
        image_url: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Implementación síncrona usando asyncio.
        """
        import asyncio
        try:
            # Ejecutar la versión async de manera síncrona
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._arun(image_url, run_manager))
                return result
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in sync image processor: {str(e)}")
            return f"Error procesando la imagen: {str(e)}" 