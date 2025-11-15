from pydantic import BaseModel, Field
from typing import Literal


class SentimentAnalysis(BaseModel):
    """Modelo para el analisis de sentimiento de un mensaje"""
    score: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Puntuacion de sentimiento: -1 (muy negativo) a 1 (muy positivo)"
    )
    label: Literal["positivo", "neutral", "negativo"] = Field(
        ...,
        description="Etiqueta categorica del sentimiento"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Nivel de confianza del analisis (0-1)"
    )
    should_alert: bool = Field(
        default=False,
        description="Indica si se debe alertar por sentimiento muy negativo"
    )


class MessageSentiment(BaseModel):
    """Modelo para respuesta de sentimiento de un mensaje"""
    message_id: str
    sentiment: str
    sentiment_score: float
    sentiment_confidence: float


class ConversationSentimentStats(BaseModel):
    """Estadisticas de sentimiento para una conversacion"""
    conversation_id: str
    total_messages: int
    positivo: int
    neutral: int
    negativo: int
    average_score: float
    has_negative_alerts: bool


class ProjectSentimentTrends(BaseModel):
    """Tendencias de sentimiento para un proyecto"""
    project_id: str
    period_start: str
    period_end: str
    total_messages: int
    positivo_count: int
    neutral_count: int
    negativo_count: int
    positivo_percentage: float
    neutral_percentage: float
    negativo_percentage: float
    average_score: float
    trend_data: list[dict]  # [{date, positivo, neutral, negativo, avg_score}]
