import os
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === Ajuste de ruta para encontrar el .env en la raíz del proyecto ===
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # sube de config/ a app/ a raíz
ENV_FILE = os.path.join(BASE_DIR, ".env")

if not os.path.exists(ENV_FILE):
    logging.error(f"Archivo .env no encontrado en {ENV_FILE}")
    raise FileNotFoundError(f"Archivo .env no encontrado en {ENV_FILE}")

load_dotenv(ENV_FILE)
logging.info(f"✅ Archivo .env cargado desde {ENV_FILE}")

def get_env_variable(var_name: str, default_value: str = "") -> str:
    value = os.getenv(var_name, default_value)
    if not value and not default_value:
        logging.warning(f"Variable {var_name} no definida, usando valor por defecto: '{default_value}'")
    return value

# JWT
CLAVE_SECRETA = get_env_variable("JWT_SECRET_KEY", "your-secret-key")
ALGORITMO_JWT = get_env_variable("JWT_ALGORITHM", "HS256")
TIEMPO_EXPIRACION_TOKEN = int(get_env_variable("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# SQL Server - DB1 (solo lectura)
SQL_SERVER_DB1 = get_env_variable("SQL_SERVER_DB1", "179.41.8.106,1433")
SQL_DATABASE_DB1 = get_env_variable("SQL_DATABASE_DB1", "PR_CAU")
SQL_USER_DB1 = get_env_variable("SQL_USER_DB1", "lectura")
SQL_PASSWORD_DB1 = get_env_variable("SQL_PASSWORD_DB1", "procoop")
SQL_DRIVER_DB1 = get_env_variable("SQL_DRIVER_DB1", "ODBC Driver 17 for SQL Server")

# SQL Server - DB2 (lectura/escritura)
SQL_SERVER_DB2 = get_env_variable("SQL_SERVER_DB2", "168.226.219.57,2424")
SQL_DATABASE_DB2 = get_env_variable("SQL_DATABASE_DB2", "DECSA_EXC")
SQL_USER_DB2 = get_env_variable("SQL_USER_DB2", "sa")
SQL_PASSWORD_DB2 = get_env_variable("SQL_PASSWORD_DB2", "Excel159753")
SQL_DRIVER_DB2 = get_env_variable("SQL_DRIVER_DB2", "ODBC Driver 17 for SQL Server")

# URIs
DB_URI1 = f"mssql+pyodbc://{SQL_USER_DB1}:{SQL_PASSWORD_DB1}@{SQL_SERVER_DB1}/{SQL_DATABASE_DB1}?driver={SQL_DRIVER_DB1}"
DB_URI2 = f"mssql+pyodbc://{SQL_USER_DB2}:{SQL_PASSWORD_DB2}@{SQL_SERVER_DB2}/{SQL_DATABASE_DB2}?driver={SQL_DRIVER_DB2}"

# Redis
REDIS_URL = get_env_variable("REDIS_URL")
REDIS_HOST = get_env_variable("REDIS_HOST", "localhost")
REDIS_PORT = int(get_env_variable("REDIS_PORT", "6379"))

# WhatsApp
WHATSAPP_PHONE_NUMBER_ID = get_env_variable("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = get_env_variable("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_VERIFY_TOKEN = get_env_variable("WHATSAPP_VERIFY_TOKEN")

# Chattigo
CHATTIGO_USERNAME = get_env_variable("CHATTIGO_USERNAME", "masiveapi@decsa")
CHATTIGO_PASSWORD = get_env_variable("CHATTIGO_PASSWORD", "Api.2025")
CHATTIGO_WEBHOOK_URL = get_env_variable("CHATTIGO_WEBHOOK_URL", "https://coral-large-absolutely.ngrok-free.app/chattigo")
CHATTIGO_HSM_TEMPLATE_WELCOME = get_env_variable("CHATTIGO_HSM_TEMPLATE_WELCOME", "hola_decsa")

# Telegram
TELEGRAM_TOKEN = get_env_variable("TELEGRAM_BOT_TOKEN")

class Config:
    SECRET_KEY = get_env_variable("SECRET_KEY", "supersecretkey")
    SQLALCHEMY_DATABASE_URI = DB_URI2
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_BINDS = {
        "db1": DB_URI1,
        "db2": DB_URI2
    }

    # CORS
    CORS_ALLOWED_ORIGINS = get_env_variable("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")

    # Llama
    LLAMA_API_URL = get_env_variable("LLAMA_API_URL", "http://localhost:11434/api/generate")
    LLAMA_MODEL = get_env_variable("LLAMA_MODEL", "llama3:latest")

    # Integraciones
    DEEPSEEK_API_KEY = get_env_variable("DEEPSEEK_API_KEY")
    CHATGPT_API_KEY = get_env_variable("CHATGPT_API_KEY")

    # Redis
    REDIS_URL = REDIS_URL
    REDIS_HOST = REDIS_HOST
    REDIS_PORT = REDIS_PORT

    # JWT
    JWT_SECRET_KEY = CLAVE_SECRETA
    JWT_ALGORITHM = ALGORITMO_JWT
    ACCESS_TOKEN_EXPIRE_MINUTES = TIEMPO_EXPIRACION_TOKEN

    # WhatsApp
    WHATSAPP_PHONE_NUMBER_ID = WHATSAPP_PHONE_NUMBER_ID
    WHATSAPP_ACCESS_TOKEN = WHATSAPP_ACCESS_TOKEN
    WHATSAPP_VERIFY_TOKEN = WHATSAPP_VERIFY_TOKEN

    # Chattigo
    CHATTIGO_USERNAME = CHATTIGO_USERNAME
    CHATTIGO_PASSWORD = CHATTIGO_PASSWORD
    CHATTIGO_WEBHOOK_URL = CHATTIGO_WEBHOOK_URL
    CHATTIGO_HSM_TEMPLATE_WELCOME = CHATTIGO_HSM_TEMPLATE_WELCOME

    # Telegram
    TELEGRAM_TOKEN = TELEGRAM_TOKEN

    @classmethod
    def validate(cls):
        required_vars = [
            ("SQLALCHEMY_DB1_URI", cls.SQLALCHEMY_BINDS["db1"]),
            ("SQLALCHEMY_DB2_URI", cls.SQLALCHEMY_BINDS["db2"]),
            ("CHATGPT_API_KEY", cls.CHATGPT_API_KEY),
            ("WHATSAPP_PHONE_NUMBER_ID", cls.WHATSAPP_PHONE_NUMBER_ID),
            ("WHATSAPP_ACCESS_TOKEN", cls.WHATSAPP_ACCESS_TOKEN),
            ("WHATSAPP_VERIFY_TOKEN", cls.WHATSAPP_VERIFY_TOKEN),
            ("CHATTIGO_USERNAME", cls.CHATTIGO_USERNAME),
            ("CHATTIGO_PASSWORD", cls.CHATTIGO_PASSWORD),
            ("TELEGRAM_TOKEN", cls.TELEGRAM_TOKEN),
        ]
        for var_name, var_value in required_vars:
            if not var_value:
                logging.error(f"Variable de configuración requerida no definida: {var_name}")
                raise ValueError(f"Variable de configuración requerida no definida: {var_name}")
        logging.info("✅ Todas las variables de configuración requeridas están definidas.")