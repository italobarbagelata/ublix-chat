import multiprocessing

# Configuración base
workers = 3
timeout = 3600
worker_class = "uvicorn.workers.UvicornWorker"
bind = "127.0.0.1:8000"
loglevel = "info"

# Límites de request
limit_request_line = 8190
limit_request_field_size = 8190
limit_request_fields = 100

# Este es el más importante:
raw_env = ["UVICORN_CMD_ARGS=--limit-max-request-size 100"]
