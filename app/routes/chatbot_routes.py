# app/routes/chatbot_routes.py
from fastapi import APIRouter, HTTPException
from app.services.detectar_intencion_service import DetectarIntencionService
import logging
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter(tags=["Chatbot"])  # Categoría "Chatbot"

chatbot_service = None

def set_detectar_intencion_usecase(service: DetectarIntencionService):
    global chatbot_service
    chatbot_service = service
    logging.info("DetectarIntencionService establecido en chatbot_routes.")

@router.post("")
async def chat_with_bot(data: dict):
    global chatbot_service
    if chatbot_service is None:
        raise HTTPException(status_code=500, detail="Servicio de chatbot no inicializado.")
    if "message" not in data:
        raise HTTPException(status_code=400, detail="El campo 'message' es requerido")
    try:
        respuesta_cruda = chatbot_service.ejecutar(data["message"])
        resultado = json.loads(respuesta_cruda)
        return {"response": resultado.get("respuesta", "No entendí tu mensaje.")}
    except (json.JSONDecodeError, TypeError) as e:
        logging.error(f"Error al procesar respuesta del chatbot: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error al procesar respuesta: {str(e)}")
    except Exception as e:
        logging.error(f"Error al interactuar con el chatbot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al interactuar con el chatbot: {str(e)}")