import os
from dotenv import load_dotenv
import logging

# Importar y configurar el sistema de logging personalizado
from app.core.logger_config import ChatbotLogger

# Configurar logging con el sistema mejorado
ChatbotLogger.setup_logging(level=logging.INFO, use_colors=False)
logger = logging.getLogger(__name__)

load_dotenv(verbose=True)

# Log environment information
logger.info(f"Iniciando aplicación en modo {os.getenv('ENVIRONMENT', 'desarrollo')}")

from app import create_app
app = create_app()

if __name__ == "__main__":
    import uvicorn
    logger.info("Servidor iniciando en http://0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)