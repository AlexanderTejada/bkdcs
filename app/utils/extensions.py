# app/utils/extensions.py
from fastapi.middleware.cors import CORSMiddleware
from app.config.config import Config  # Ajustamos la importación

def init_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.CORS_ALLOWED_ORIGINS,  # Usamos la configuración de CORS desde Config
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )