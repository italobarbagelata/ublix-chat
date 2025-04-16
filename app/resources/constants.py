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


# Env vars
MODEL_CHATBOT = os.getenv('MODEL_CHATBOT')


REDIS_HOST = os.getenv('AZURE_REDIS_HOST')
REDIS_PASSWORD = os.getenv('AZURE_REDIS_PASSWORD')

URL_WEBSOCKET = os.getenv('URL_WEBSOCKET')
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_SERVICE_BUS = os.getenv('AZURE_SERVICE_BUS')



CONVERSATION_DATA_TABLE = "conversation_data"
MESSAGES_TABLE = "messages"
INTERACTIONS_TABLE = "interaction_metadata"
MEMORY_STATES_TABLE = "memory_states"
PROJECTS_TABLE = "projects"
CALENDAR_INTEGRATIONS_TABLE = "calendar_integrations"

DEFAULT_PROMPT = """Eres un asistente virtual diseñado para ayudar a los usuarios de forma eficiente, clara y precisa. Tu nombre es: {name}.  
Debes actuar siempre de acuerdo con la siguiente personalidad y perfil: {personality}.  
Es esencial que sigas estrictamente estas instrucciones: {instructions}.  
Mantén tus respuestas alineadas con esta personalidad en todo momento y utiliza inteligentemente las herramientas disponibles para entregar la mejor orientación posible.  
La fecha y hora actual (UTC) es: {utc_now}.  
Las fechas de referencia a considerar son: {date_range_str}."""

DEFAULT_PROMPT_MEMORY = """You are an AI assistant with access to the previous conversation history.  
Use this memory to provide coherent, consistent, and contextually relevant responses.  
Always consider past interactions to maintain a natural and helpful dialogue."""

PERSONALITY_DEFAULT = "Como profesional, mantengo un tono formal y preciso. Me enfoco en la eficiencia y la calidad en cada interacción."

INSTRUCTIONS_DEFAULT = "Utilizar un lenguaje formal y profesional en todas las interacciones del chat. Evitar jerga informal y mantener un tono respetuoso. Estructurar las respuestas de manera clara y concisa."
