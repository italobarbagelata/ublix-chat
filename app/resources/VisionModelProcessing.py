import requests
import base64
import os
import logging
from app.resources.PromptTemplates import SYSTEM_PROMPT_VISION_MODEL


class VisionModelProcessor:

    def __init__(self) -> None:
        self.__api_key = os.getenv("OPENAI_API_KEY")
        # Usar el nuevo modelo de visión
        self.__vision_model = "gpt-4o-mini"
        
        if not self.__api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

    def _encode_image(self, image_path):
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            logging.error(f"Error encoding image {image_path}: {str(e)}")
            raise

    def extract_text_from_image(self, image_path: str) -> str:
        if not os.path.exists(image_path):
            logging.error(f"Image file not found: {image_path}")
            raise FileNotFoundError(f"Image file not found: {image_path}")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.__api_key}",
        }

        try:
            # Obtener el tamaño del archivo
            file_size = os.path.getsize(image_path)
            logging.info(f"Image file size: {file_size} bytes")

            # Codificar la imagen
            base64_image = self._encode_image(image_path)
            logging.info(f"Base64 image length: {len(base64_image)}")

            payload = {
                "model": self.__vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": SYSTEM_PROMPT_VISION_MODEL},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": 4096
            }

            logging.info(f"Sending request to OpenAI Vision API for image: {image_path}")
            response = requests.post(
                "https://api.openai.com/v1/chat/completions", 
                headers=headers, 
                json=payload
            )
            
            if response.status_code != 200:
                logging.error(f"OpenAI API error: {response.status_code} - {response.text}")
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
            response_data = response.json()
            content = response_data["choices"][0]["message"].get("content", "")
            
            if not content:
                logging.warning(f"No text content extracted from image: {image_path}")
                return ""
                
            logging.info(f"Successfully extracted text from image: {image_path}")
            return content

        except Exception as e:
            logging.error(f"Error processing image {image_path}: {str(e)}")
            raise