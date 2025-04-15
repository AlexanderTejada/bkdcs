# app/routes/whatsapp_routes.py
from fastapi import APIRouter, HTTPException, Request
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter(tags=["WhatsApp"])  # Categoría "WhatsApp"

whatsapp_adapter = None

def set_whatsapp_adapter(adapter):
    global whatsapp_adapter
    whatsapp_adapter = adapter
    logging.info("Adaptador de WhatsApp configurado para las rutas.")

@router.get("/webhook")
async def whatsapp_webhook_verify(request: Request):
    try:
        if whatsapp_adapter is None:
            raise HTTPException(status_code=500, detail="Adaptador de WhatsApp no inicializado.")
        query = request.query_params
        mode = query.get("hub.mode")
        token = query.get("hub.verify_token")
        challenge = query.get("hub.challenge")

        if mode == "subscribe" and token == whatsapp_adapter.verify_token:
            logging.info("Webhook de WhatsApp verificado exitosamente.")
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Verificación fallida.")
    except Exception as e:
        logging.error(f"Error al verificar webhook de WhatsApp: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al verificar webhook: {str(e)}")

@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    try:
        if whatsapp_adapter is None:
            raise HTTPException(status_code=500, detail="Adaptador de WhatsApp no inicializado.")
        body = await request.json()
        logging.info(f"Mensaje recibido de WhatsApp: {body}")
        response = await whatsapp_adapter.handle_message(request)  # Añadimos await y pasamos request
        return response or {"status": "Mensaje procesado"}
    except Exception as e:
        logging.error(f"Error al procesar mensaje de WhatsApp: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar mensaje: {str(e)}")