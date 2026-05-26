""" Módulo principal de la aplicación. """

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Work around langchain-openai==0.2.1 + pydantic==2.11 incompatibility.
# Without this, instantiating ChatOpenAI inside a request raises
# "`ChatOpenAI` is not fully defined; you should define `BaseCache`,
# then call `ChatOpenAI.model_rebuild()`."
from langchain_core.caches import BaseCache  # noqa: F401  (needed for rebuild)
from langchain_core.callbacks import Callbacks  # noqa: F401
from langchain_openai import ChatOpenAI
ChatOpenAI.model_rebuild()

from .routes import (chat_router, webhook_router, webhook_router_facebook, webhook_router_whatsapp)
from .database import init_db, close_db

load_dotenv()

def create_app():
    """Crear la aplicación FastAPI"""
    app = FastAPI()
    app.title = "Ublix Enterprise"
    app.description = "PrivateAPI Ublix Enterprise"
    app.version = "1.0.0"

    # Habilitar CORS para todas las rutas
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"]
    )

    # Database lifecycle hooks
    @app.on_event("startup")
    async def startup():
        await init_db()

    @app.on_event("shutdown")
    async def shutdown():
        await close_db()

    # El logging ya está configurado en logger_config.py
    # No necesitamos configuración adicional aquí

    # Incluir las rutas
    app.include_router(chat_router)
    app.include_router(webhook_router)
    app.include_router(webhook_router_facebook)
    app.include_router(webhook_router_whatsapp)
    app.include_router(webhook_router_whatsapp)
    return app
