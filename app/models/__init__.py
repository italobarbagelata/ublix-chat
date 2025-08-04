# Importar ChatRequest desde models.py para mantener compatibilidad
import sys
import os
import importlib.util

# Cargar ChatRequest desde models.py del directorio padre
parent_dir = os.path.dirname(os.path.dirname(__file__))
models_path = os.path.join(parent_dir, 'models.py')

ChatRequest = None
if os.path.exists(models_path):
    try:
        spec = importlib.util.spec_from_file_location("app_models", models_path)
        app_models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_models)
        ChatRequest = app_models.ChatRequest
    except Exception as e:
        # Fallback silencioso si no se puede cargar
        pass

# Importar modelos de calendar
try:
    from .calendar import (
        CalendarEventLocalCreate,
        CalendarEventLocalUpdate,
        CalendarEventLocalResponse,
        CalendarEventListResponse
    )
except ImportError:
    # Definir modelos vacíos como fallback
    CalendarEventLocalCreate = None
    CalendarEventLocalUpdate = None
    CalendarEventLocalResponse = None
    CalendarEventListResponse = None

__all__ = [
    "ChatRequest",
    "CalendarEventLocalCreate",
    "CalendarEventLocalUpdate", 
    "CalendarEventLocalResponse",
    "CalendarEventListResponse"
]