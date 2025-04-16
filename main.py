import os
from dotenv import load_dotenv
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

load_dotenv(verbose=True)

# Log environment information
logger.info(f"Starting application in {os.getenv('ENVIRONMENT', 'development')} mode")

from app import create_app
app = create_app()

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)