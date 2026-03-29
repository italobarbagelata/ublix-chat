from enum import Enum
import datetime
import os
from dotenv import load_dotenv
load_dotenv()

# tablas
DATASOURCES_COLLECTION = "datasources"
PROJECTS_COLLECTION = 'projects'
APIS_COLLECTION = 'apis'
AI_MESSAGE_TABLE = "message_ai_metadata"
INSTAGRAM_COLLECTION = 'integration_instagram'
TOKEN_METRICS_TABLE = "token_metrics"



# Status codes
STATUS_OK = 200
STATUS_CREATED = 201
STATUS_NO_CONTENT = 204
STATUS_BAD_REQUEST = 400
STATUS_UNAUTHORIZED = 401
STATUS_FORBIDDEN = 403
STATUS_NOT_FOUND = 404
STATUS_UNSUPPORTED = 405
STATUS_CONFLICT = 409
STATUS_INTERNAL_SERVER_ERROR = 500
STATUS_NOT_IMPLEMENTED = 501


# =============================================================================
# CONFIGURACIÓN DE MODELOS LLM
# =============================================================================
# Modelos disponibles (2026):
#   - gpt-5-nano:  $0.05/$0.40 per 1M tokens - Más barato, tareas simples
#   - gpt-5-mini:  $0.25/$2.00 per 1M tokens - Balance calidad/precio
#   - gpt-4o-mini: $0.15/$0.60 per 1M tokens - Legacy, aún disponible
#   - gpt-5.2:     $1.75/$14.00 per 1M tokens - Flagship
# =============================================================================

# Modelo principal para chatbot (configurable por env)
MODEL_CHATBOT = os.getenv('MODEL_CHATBOT', 'gpt-5-mini')

# Modelo económico para tareas simples (sentiment, clasificación, OCR)
MODEL_CHATBOT_SMALL = os.getenv('MODEL_CHATBOT_SMALL', 'gpt-5-nano')

# Modelo para embeddings
MODEL_ENCODING = os.getenv('MODEL_ENCODING', 'text-embedding-3-small')

URL_WEBSOCKET = os.getenv('URL_WEBSOCKET')
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_SERVICE_BUS = os.getenv('AZURE_SERVICE_BUS')



CONVERSATION_DATA_TABLE = "conversation_data"
MESSAGES_TABLE = "messages"
INTERACTIONS_TABLE = "interaction_metadata"
MEMORY_STATES_TABLE = "memory_states"
PROJECTS_TABLE = "projects"
CALENDAR_INTEGRATIONS_TABLE = "calendar_integrations"

DEFAULT_PROMPT = """Eres {name}, un asistente virtual eficiente y conciso.

REGLA PRINCIPAL - RESPUESTA DIRECTA:
- Para saludos (hola, buenos días, etc.) → Responder directamente SIN usar herramientas
- Para confirmaciones (sí, no, ok, gracias) → Responder directamente SIN usar herramientas
- Para preguntas sobre productos/servicios/datos → Usar herramientas

CUÁNDO USAR HERRAMIENTAS:
- Preguntas sobre productos, precios, servicios → unified_search_tool
- El usuario PROPORCIONA su nombre/email/teléfono → save_contact_tool
- Preguntas sobre fecha/hora actual → current_datetime_tool (máx 1 vez)
- Imágenes enviadas → image_processor

CUÁNDO NO USAR HERRAMIENTAS:
- Saludos simples
- Confirmaciones y agradecimientos
- Si ya tienes la información de una búsqueda anterior

FORMATO:
- URLs: [texto](url)
- Respuestas: máximo 250 caracteres, directo al punto
- Idioma: el mismo del usuario

Fecha UTC: {utc_now}. Fechas referencia: {date_range_str}."""

DEFAULT_PROMPT_MEMORY = """You are an AI assistant with access to the previous conversation history.  
Use this memory to provide coherent, consistent, and contextually relevant responses.  
Always consider past interactions to maintain a natural and helpful dialogue."""

PERSONALITY_DEFAULT = "Como profesional, mantengo un tono formal y preciso. Me enfoco en la eficiencia y la calidad en cada interacción."

INSTRUCTIONS_DEFAULT = "Utilizar un lenguaje formal y profesional en todas las interacciones del chat. Evitar jerga informal y mantener un tono respetuoso. Estructurar las respuestas de manera clara y concisa."
