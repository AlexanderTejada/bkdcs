# app/telegram_bot_chatgpt.py
from app.config.config import Config
from app.adapters.telegram_adapter_chatgpt import TelegramAdapterChatGPT
from app.services.detectar_intencion_service import DetectarIntencionService
from app.services.redis_client import RedisClient
import logging
import threading
import asyncio

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def run_bot(bot):
    """
    Ejecuta el bot de Telegram en un bucle de eventos asyncio dentro de un hilo separado.
    """
    # Crear un nuevo bucle de eventos para este hilo
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        bot.run()
    finally:
        loop.close()


def init_telegram_bot_chatgpt(
        app,
        redis_client: RedisClient,
        detectar_intencion_service: DetectarIntencionService
):
    """
    Inicializa el bot de Telegram con ChatGPT y lo integra con la aplicación FastAPI.
    """
    logging.info("🚀 Iniciando bot de Telegram con ChatGPT...")

    # Los casos de uso de reclamos y consultas se instanciarán dentro del adapter si son None
    registrar_reclamo_service = None
    actualizar_usuario_service = None
    consultar_estado_reclamo_service = None
    consultar_reclamo_service = None

    # Inicializar y correr el bot con ChatGPT
    bot = TelegramAdapterChatGPT(
        Config.TELEGRAM_BOT_TOKEN,
        detectar_intencion_service,
        registrar_reclamo_service,
        actualizar_usuario_service,
        consultar_estado_reclamo_service,
        consultar_reclamo_service,
        redis_client,
        app
    )

    # Iniciar el bot en un hilo separado con un bucle de eventos asyncio
    bot_thread = threading.Thread(target=run_bot, args=(bot,))
    bot_thread.daemon = True  # Hacer que el hilo sea daemon para que se detenga al cerrar la app
    bot_thread.start()

    logging.info("✅ Bot de Telegram con ChatGPT iniciado en un hilo separado.")