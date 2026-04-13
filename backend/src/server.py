from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings

# 1. Inicializamos la aplicación FastAPI
app = FastAPI(
    title="API - Robot de Patrulla TFG",
    description="Backend para el control y telemetría del TurtleBot4",
    version="1.0.0"
)

# 2. Configuración de CORS (Cross-Origin Resource Sharing)
# Esto es importante para que Flutter 
# tenga permiso para hacer peticiones a este backend sin que el navegador lo bloquee.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción se pone la URL exacta de Flutter
    allow_credentials=True,
    allow_methods=["*"],  # Permite GET, POST, PUT, DELETE...
    allow_headers=["*"],
)

# 3. Endpoints Base
@app.get("/", tags=["Base"])
async def root():
    return {
        "mensaje": "¡Servidor FastAPI operativo!",
        "entorno": settings.ENVIRONMENT
    }

@app.get("/api/health", tags=["Base"])
async def health_check():
    """
    Endpoint para comprobar la salud del sistema.
    Útil para que el frontend o Docker sepan si el backend está vivo.
    """
    return {
        "status": "ok",
        "database_configured": bool(settings.database_url),
        "minio_configured": bool(settings.minio_endpoint)
    }