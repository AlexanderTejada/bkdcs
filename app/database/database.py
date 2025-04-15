# app/config/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config.config import Config
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Crear motores para las bases de datos
engine_db1 = create_engine(Config.SQLALCHEMY_BINDS["db1"], pool_size=10, max_overflow=20)
engine_db2 = create_engine(Config.SQLALCHEMY_BINDS["db2"], pool_size=10, max_overflow=20)

# Crear fábricas de sesiones
SessionLocal_db1 = sessionmaker(autocommit=False, autoflush=False, bind=engine_db1)
SessionLocal_db2 = sessionmaker(autocommit=False, autoflush=False, bind=engine_db2)

# Dependencias para FastAPI
def get_db1():
    db = SessionLocal_db1()
    try:
        yield db
    finally:
        db.close()

def get_db2():
    db = SessionLocal_db2()
    try:
        yield db
    finally:
        db.close()

# Función para inicializar las bases de datos (opcional, para logging o verificaciones)
def init_db():
    logging.info("Bases de datos inicializadas con FastAPI")
    # Aquí podrías agregar verificaciones de conexión si lo deseas