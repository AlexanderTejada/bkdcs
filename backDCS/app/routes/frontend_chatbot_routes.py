# app/routes/frontend_chatbot_routes.py
from fastapi import APIRouter, HTTPException, Request
import logging
from app.services.chatgpt_frontend_service import ChatGPTFrontendService
from app.services.redis_client import RedisClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter(tags=["Frontend Chatbot"])

frontend_chatbot_service = None

def initialize_frontend_chatbot(redis_client):
    global frontend_chatbot_service
    frontend_chatbot_service = ChatGPTFrontendService(redis_client=redis_client)
    logging.info("Servicio de chatbot para frontend inicializado.")

@router.post("/chat")
async def frontend_chatbot(request: Request):
    try:
        if frontend_chatbot_service is None:
            raise HTTPException(status_code=500, detail="Servicio de chatbot no inicializado.")

        data = await request.json()
        mensaje = data.get("mensaje", "").strip()
        historial = data.get("historial", "")

        if not mensaje:
            raise HTTPException(status_code=400, detail="Mensaje vacío.")

        respuesta = frontend_chatbot_service.responder(mensaje, historial)
        return respuesta
    except Exception as e:
        logging.error(f"Error al procesar mensaje del frontend chatbot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar mensaje: {str(e)}")