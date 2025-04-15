# app/whatsapp_bot_chatgpt.py
from app.config.config import Config
from app.adapters.whatsapp_adapter_chatgpt import WhatsAppAdapterChatGPT
from app.services.detectar_intencion_service import DetectarIntencionService
from app.services.redis_client import RedisClient
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def init_whatsapp_bot_chatgpt(
    app,
    redis_client: RedisClient,
    detectar_intencion_service: DetectarIntencionService
):
    """
    Inicializa el bot de WhatsApp con ChatGPT y lo integra con la aplicación FastAPI.
    """
    logging.info("🚀 Iniciando bot de WhatsApp con ChatGPT...")

    # Los servicios de reclamos y consultas se instanciarán dentro del adapter si son None
    registrar_reclamo_service = None
    actualizar_usuario_service = None
    consultar_estado_reclamo_service = None
    consultar_reclamo_service = None

    # Inicializar el bot con ChatGPT
    bot = WhatsAppAdapterChatGPT(
        Config.WHATSAPP_PHONE_NUMBER_ID,
        Config.WHATSAPP_ACCESS_TOKEN,
        detectar_intencion_service,
        registrar_reclamo_service,
        actualizar_usuario_service,
        consultar_estado_reclamo_service,
        consultar_reclamo_service,
        redis_client,
        app
    )

    logging.info("✅ Bot de WhatsApp con ChatGPT inicializado.")
    return bot