from fastapi import FastAPI
from .user_routes import router as user_router, init_cliente_services
from .reclamo_routes import router as reclamo_router, init_reclamo_services
from .factura_routes import router as factura_router, init_factura_services
from .roles_routes import router as roles_router
from .autenticacion_routes import router as autenticacion_router
from .chatbot_routes import router as chatbot_router, set_detectar_intencion_usecase
from .whatsapp_routes import router as whatsapp_router, set_whatsapp_adapter
from .chattigo_routes import router as chattigo_router, set_chattigo_adapter
from app.adapters.whatsapp_adapter_chatgpt import WhatsAppAdapterChatGPT
from app.adapters.chattigo_adapter_chatgpt import ChattigoAdapterChatGPT
from app.routes.chatbot_route_rag import router as chatbot_rag_router

from app.config.config import Config
from app.services.validar_reclamo_chatgpt_usecase import ValidarReclamoService
from app.services.chatgpt_validar_reclamo_service import ChatGPTValidarReclamoService
from app.utils.extensions import init_cors
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def initialize_routes(
    app: FastAPI,
    redis_client,
    detectar_intencion_service,  # Para ambos: WhatsApp y Chattigo (ChatGPT)
    validar_reclamo_service
):
    init_cors(app)
    app.include_router(user_router, prefix="/api/usuarios", tags=["Clientes"])
    app.include_router(reclamo_router, prefix="/api/reclamos", tags=["Reclamos"])
    app.include_router(factura_router, prefix="/api/facturas", tags=["Facturas"])
    app.include_router(roles_router, prefix="/api/roles", tags=["Roles"])
    app.include_router(autenticacion_router, prefix="/api/admin/usuarios", tags=["Autenticación"])
    app.include_router(chatbot_router, prefix="/api/chatbot", tags=["Chatbot"])
    app.include_router(chatbot_rag_router, prefix="/api/chatbot", tags=["Chatbot RAG"])

    app.include_router(whatsapp_router, prefix="/whatsapp", tags=["WhatsApp"])
    app.include_router(chattigo_router, prefix="/chattigo", tags=["Chattigo"])

    init_cliente_services(app)
    init_reclamo_services(app)
    init_factura_services(app)

    # Inicializar adaptador de WhatsApp (usando ChatGPT)
    logging.info("Creando adaptador de WhatsApp con ChatGPT...")
    whatsapp_adapter = WhatsAppAdapterChatGPT(
        Config.WHATSAPP_PHONE_NUMBER_ID,
        Config.WHATSAPP_ACCESS_TOKEN,
        detectar_intencion_service,  # Usa ChatGPT
        validar_reclamo_service,
        Config.WHATSAPP_VERIFY_TOKEN,
        redis_client=redis_client,
        app=app
    )
    set_whatsapp_adapter(whatsapp_adapter)
    logging.info("Adaptador de WhatsApp con ChatGPT creado.")

    # Inicializar adaptador de Chattigo (usando ChatGPT)
    logging.info("Creando adaptador de Chattigo con ChatGPT...")
    chattigo_adapter = ChattigoAdapterChatGPT(
        username=Config.CHATTIGO_USERNAME,  # Usar configuración
        password=Config.CHATTIGO_PASSWORD,  # Usar configuración
        detectar_intencion_service=detectar_intencion_service,
        validar_reclamo_service=validar_reclamo_service,
        redis_client=redis_client
    )
    set_chattigo_adapter(chattigo_adapter)
    logging.info("Adaptador de Chattigo con ChatGPT creado.")

    logging.info("Rutas y adaptadores inicializados correctamente.")