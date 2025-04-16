""" Módulo principal de la aplicación. """

import logging
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import (chat_router)

load_dotenv()

app = FastAPI()


def create_app():
    """Crear la aplicación FastAPI"""

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

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    # Incluir las rutas
    app.include_router(chat_router)
    return app


app = create_app()
