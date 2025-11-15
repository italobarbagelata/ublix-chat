import os
import json
from openai import OpenAI
from app.models.sentiment import SentimentAnalysis
from typing import Optional


class SentimentService:
    """Servicio para analizar el sentimiento de mensajes usando OpenAI"""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"  # Modelo economico para analisis simple
        self.alert_threshold = -0.6  # Umbral para alertas (muy negativo)

    async def analyze_sentiment(self, message_text: str) -> SentimentAnalysis:
        """
        Analiza el sentimiento de un mensaje de texto

        Args:
            message_text: Texto del mensaje a analizar

        Returns:
            SentimentAnalysis con score, label, confidence y should_alert
        """
        try:
            # Prompt optimizado para analisis de sentimiento
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Eres un experto en analisis de sentimiento.
Analiza el sentimiento del mensaje y responde SOLO con un JSON en este formato exacto:
{
  "score": <numero entre -1.0 y 1.0>,
  "label": "<positivo|neutral|negativo>",
  "confidence": <numero entre 0.0 y 1.0>
}

Criterios:
- score: -1.0 = muy negativo, 0.0 = neutral, 1.0 = muy positivo
- label: "positivo" si score > 0.3, "negativo" si score < -0.3, "neutral" entre -0.3 y 0.3
- confidence: que tan seguro estas del analisis (0.0 = nada seguro, 1.0 = muy seguro)

Considera contexto, tono, emojis y palabras clave en espanol."""
                    },
                    {
                        "role": "user",
                        "content": message_text
                    }
                ],
                temperature=0.3,  # Baja temperatura para respuestas consistentes
                max_tokens=100,  # Respuesta corta
                response_format={"type": "json_object"}
            )

            # Parsear respuesta JSON
            result = json.loads(response.choices[0].message.content)

            # Validar y crear objeto SentimentAnalysis
            score = float(result.get("score", 0.0))
            label = result.get("label", "neutral")
            confidence = float(result.get("confidence", 0.5))

            # Determinar si debe alertar
            should_alert = score <= self.alert_threshold and confidence >= 0.7

            return SentimentAnalysis(
                score=score,
                label=label,
                confidence=confidence,
                should_alert=should_alert
            )

        except Exception as e:
            print(f"Error en analisis de sentimiento: {str(e)}")
            # Retornar sentimiento neutral en caso de error
            return SentimentAnalysis(
                score=0.0,
                label="neutral",
                confidence=0.0,
                should_alert=False
            )

    def should_analyze(self, message_type: str, message_text: str) -> bool:
        """
        Determina si un mensaje debe ser analizado

        Args:
            message_type: Tipo de mensaje (human, ai)
            message_text: Texto del mensaje

        Returns:
            True si debe analizarse, False en caso contrario
        """
        # Solo analizar mensajes humanos
        if message_type != "human":
            return False

        # No analizar mensajes muy cortos (menos de 3 palabras)
        if len(message_text.split()) < 3:
            return False

        # No analizar comandos o mensajes automaticos
        if message_text.startswith("/") or message_text.startswith("!"):
            return False

        return True


# Singleton instance
_sentiment_service_instance: Optional[SentimentService] = None

def get_sentiment_service() -> SentimentService:
    """Obtiene la instancia singleton del servicio de sentimiento"""
    global _sentiment_service_instance
    if _sentiment_service_instance is None:
        _sentiment_service_instance = SentimentService()
    return _sentiment_service_instance
