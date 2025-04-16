from main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
else:
    # Esto es necesario para que Gunicorn pueda encontrar la aplicación
    application = app 