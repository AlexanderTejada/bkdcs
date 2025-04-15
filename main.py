from fastapi import FastAPI
from app.config.config import Config
from app.database.database import init_db
from app.routes import initialize_routes
from app.routes.frontend_chatbot_routes import router as frontend_chatbot_router, initialize_frontend_chatbot
from app.services.chatgpt_service import ChatGPTService
from app.services.chatgpt_validar_reclamo_service import ChatGPTValidarReclamoService
from app.services.detectar_intencion_service import DetectarIntencionService
from app.services.validar_reclamo_chatgpt_usecase import ValidarReclamoService
from app.services.redis_client import RedisClient
from app.adapters.telegram_adapter_chatgpt import TelegramAdapterChatGPT
import logging
import threading
import asyncio

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def create_app() -> FastAPI:
    app = FastAPI(
        title="DECSA API",
        description="API para gestión de reclamos y facturas",
        version="1.0.0"
    )
    app.config = Config

    # === Inicializar servicios base ===
    init_db()
    redis_client = RedisClient().get_client()
    chatgpt_service = ChatGPTService(redis_client=redis_client)
    detectar_intencion_service = DetectarIntencionService(chatgpt_service)
    chatgpt_validar_service = ChatGPTValidarReclamoService(redis_client=redis_client)
    validar_reclamo_service = ValidarReclamoService(chatgpt_validar_service)

    # === Bot de Telegram (opcional) ===
    if Config.TELEGRAM_TOKEN:
        def run_telegram_bot():
            logging.info("Iniciando bot de Telegram en un hilo separado...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                telegram_adapter.run()
            except Exception as e:
                logging.error(f"Error en el bot de Telegram: {str(e)}")
            finally:
                loop.close()

        telegram_adapter = TelegramAdapterChatGPT(
            token=Config.TELEGRAM_TOKEN,
            detectar_intencion_service=detectar_intencion_service,
            validar_reclamo_service=validar_reclamo_service,
            redis_client=redis_client
        )

        telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        telegram_thread.start()
    else:
        logging.warning("🚫 TELEGRAM_TOKEN no definido. Bot de Telegram no será iniciado.")

    # === Inicializar rutas principales y frontend chatbot ===
    initialize_routes(app, redis_client, detectar_intencion_service, validar_reclamo_service)
    initialize_frontend_chatbot(redis_client)
    app.include_router(frontend_chatbot_router, prefix="/api/frontend-chatbot", tags=["Frontend Chatbot"])

    # === Endpoint de prueba ===
    @app.get("/test")
    async def test():
        return {"message": "Backend is running"}

    return app

# Railway usará esta variable directamente
app = create_app()
