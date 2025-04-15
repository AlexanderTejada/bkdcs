import os
from dotenv import load_dotenv
import logging

# === Logging elegante ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === Carga del archivo .env (solo si existe, útil en local) ===
load_dotenv()
logging.info(".env cargado si existía en entorno local.")

def get_env_variable(var_name: str, default_value: str = "") -> str:
    value = os.getenv(var_name, default_value)
    if not value and not default_value:
        logging.warning(f"⚠️ Variable de entorno '{var_name}' no definida. Usando valor por defecto vacío.")
    return value

# === Configuraciones extraídas del entorno ===

# JWT
CLAVE_SECRETA = get_env_variable("JWT_SECRET_KEY", "your-secret-key")
ALGORITMO_JWT = get_env_variable("JWT_ALGORITHM", "HS256")
TIEMPO_EXPIRACION_TOKEN = int(get_env_variable("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# SQL Server - DB1
SQL_SERVER_DB1 = get_env_variable("SQL_SERVER_DB1")
SQL_DATABASE_DB1 = get_env_variable("SQL_DATABASE_DB1")
SQL_USER_DB1 = get_env_variable("SQL_USER_DB1")
SQL_PASSWORD_DB1 = get_env_variable("SQL_PASSWORD_DB1")
SQL_DRIVER_DB1 = get_env_variable("SQL_DRIVER_DB1", "ODBC Driver 17 for SQL Server")

# SQL Server - DB2
SQL_SERVER_DB2 = get_env_variable("SQL_SERVER_DB2")
SQL_DATABASE_DB2 = get_env_variable("SQL_DATABASE_DB2")
SQL_USER_DB2 = get_env_variable("SQL_USER_DB2")
SQL_PASSWORD_DB2 = get_env_variable("SQL_PASSWORD_DB2")
SQL_DRIVER_DB2 = get_env_variable("SQL_DRIVER_DB2", "ODBC Driver 17 for SQL Server")

# URIs
DB_URI1 = f"mssql+pyodbc://{SQL_USER_DB1}:{SQL_PASSWORD_DB1}@{SQL_SERVER_DB1}/{SQL_DATABASE_DB1}?driver={SQL_DRIVER_DB1}"
DB_URI2 = f"mssql+pyodbc://{SQL_USER_DB2}:{SQL_PASSWORD_DB2}@{SQL_SERVER_DB2}/{SQL_DATABASE_DB2}?driver={SQL_DRIVER_DB2}"

# Redis
REDIS_URL = get_env_variable("REDIS_URL", "")
REDIS_HOST = get_env_variable("REDIS_HOST", "localhost")
REDIS_PORT = int(get_env_variable("REDIS_PORT", "6379"))

# Telegram
TELEGRAM_TOKEN = get_env_variable("TELEGRAM_BOT_TOKEN")

# LLaMA
LLAMA_API_URL = get_env_variable("LLAMA_API_URL", "http://localhost:11434/api/generate")
LLAMA_MODEL = get_env_variable("LLAMA_MODEL", "llama3:latest")

# APIs
CHATGPT_API_KEY = get_env_variable("CHATGPT_API_KEY")
DEEPSEEK_API_KEY = get_env_variable("DEEPSEEK_API_KEY")

# Chattigo
CHATTIGO_USERNAME = get_env_variable("CHATTIGO_USERNAME")
CHATTIGO_PASSWORD = get_env_variable("CHATTIGO_PASSWORD")
CHATTIGO_WEBHOOK_URL = get_env_variable("CHATTIGO_WEBHOOK_URL")
CHATTIGO_HSM_TEMPLATE_WELCOME = get_env_variable("CHATTIGO_HSM_TEMPLATE_WELCOME")

# CORS
CORS_ALLOWED_ORIGINS = get_env_variable("CORS_ALLOWED_ORIGINS", "").split(",")

# === Clase de Configuración General ===
class Config:
    SECRET_KEY = get_env_variable("SECRET_KEY", "supersecretkey")
    SQLALCHEMY_DATABASE_URI = DB_URI2
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_BINDS = {
        "db1": DB_URI1,
        "db2": DB_URI2
    }

    CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS

    LLAMA_API_URL = LLAMA_API_URL
    LLAMA_MODEL = LLAMA_MODEL
    CHATGPT_API_KEY = CHATGPT_API_KEY
    DEEPSEEK_API_KEY = DEEPSEEK_API_KEY

    REDIS_URL = REDIS_URL
    REDIS_HOST = REDIS_HOST
    REDIS_PORT = REDIS_PORT

    JWT_SECRET_KEY = CLAVE_SECRETA
    JWT_ALGORITHM = ALGORITMO_JWT
    ACCESS_TOKEN_EXPIRE_MINUTES = TIEMPO_EXPIRACION_TOKEN

    TELEGRAM_TOKEN = TELEGRAM_TOKEN

    CHATTIGO_USERNAME = CHATTIGO_USERNAME
    CHATTIGO_PASSWORD = CHATTIGO_PASSWORD
    CHATTIGO_WEBHOOK_URL = CHATTIGO_WEBHOOK_URL
    CHATTIGO_HSM_TEMPLATE_WELCOME = CHATTIGO_HSM_TEMPLATE_WELCOME

    @classmethod
    def validate(cls):
        required = [
            ("CHATGPT_API_KEY", cls.CHATGPT_API_KEY),
            ("TELEGRAM_TOKEN", cls.TELEGRAM_TOKEN),
            ("CHATTIGO_USERNAME", cls.CHATTIGO_USERNAME),
            ("CHATTIGO_PASSWORD", cls.CHATTIGO_PASSWORD),
        ]
        for var_name, val in required:
            if not val:
                raise ValueError(f"❌ Variable de entorno obligatoria faltante: {var_name}")
        logging.info("✅ Todas las variables de configuración obligatorias están presentes.")
