import multiprocessing

# Configuración base
workers = 1  # Reducido para Azure App Service
timeout = 120
worker_class = "uvicorn.workers.UvicornWorker"
bind = "0.0.0.0:8000"  # Cambiado para escuchar en todas las interfaces
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Límites de request
limit_request_line = 8190
limit_request_field_size = 8190
limit_request_fields = 100

# Configuración específica para Azure
keepalive = 65
max_requests = 1000
max_requests_jitter = 50

# Configuración de Uvicorn
raw_env = [
    "UVICORN_CMD_ARGS=--limit-max-request-size 100",
    "UVICORN_HOST=0.0.0.0",
    "UVICORN_PORT=8000"
]
