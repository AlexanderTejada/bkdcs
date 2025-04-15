# app/routes/chattigo_routes.py

from fastapi import APIRouter, Request, HTTPException
from app.config.config import Config
import logging
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Crear un enrutador para las rutas de Chattigo
router = APIRouter()

# Variable global para almacenar el adaptador de Chattigo
_chattigo_adapter = None

def set_chattigo_adapter(adapter):
    """
    Configura el adaptador de Chattigo para ser usado por las rutas.
    """
    global _chattigo_adapter
    _chattigo_adapter = adapter
    logging.info("✅ Adaptador de Chattigo configurado para las rutas.")

def get_chattigo_adapter():
    """
    Obtiene el adaptador de Chattigo para usarlo en las rutas.
    """
    if _chattigo_adapter is None:
        logging.error("❌ Adaptador de Chattigo no inicializado.")
        raise RuntimeError("Adaptador de Chattigo no inicializado.")
    return _chattigo_adapter

@router.post("/", tags=["chattigo"])
async def chattigo_root_webhook(request: Request):
    """
    Ruta principal que Chattigo invoca (sin /webhook).
    Captura y maneja el payload entrante desde la plataforma.
    """
    try:
        raw_body = await request.body()
        logging.info(f"📩 [CHATTIGO RAW PAYLOAD]:\n{raw_body.decode('utf-8')}")

        data = await request.json()
        logging.info(f"📦 [CHATTIGO JSON DECODIFICADO]:\n{json.dumps(data, indent=2)}")

        adapter = get_chattigo_adapter()
        logging.info("🔄 Llamando a handle_message del adaptador...")
        response = await adapter.handle_message(request)
        logging.info(f"✅ Respuesta de handle_message: {response}")
        return response or {"status": "Mensaje procesado"}
    except Exception as e:
        logging.error(f"❌ Error al manejar la solicitud del webhook de Chattigo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al manejar la solicitud: {str(e)}")

@router.get("/payloads", tags=["chattigo"])
async def get_payloads():
    """
    Devuelve los últimos payloads recibidos de Chattigo almacenados en Redis.
    """
    try:
        keys = get_chattigo_adapter().redis_client.keys("chattigo:payload:*")
        payloads = []
        for key in keys:
            payload = get_chattigo_adapter().redis_client.get(key)
            if payload:
                payloads.append({
                    "key": key.decode("utf-8"),
                    "payload": json.loads(payload.decode("utf-8"))
                })
        return {"payloads": payloads}
    except Exception as e:
        logging.error(f"❌ Error al obtener payloads de Redis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener payloads: {str(e)}")
