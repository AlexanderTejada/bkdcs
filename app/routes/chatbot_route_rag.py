from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import logging

router = APIRouter(tags=["Chatbot RAG"])

@router.post("/proxy/consultar")
async def proxy_consultar(request: Request):
    try:
        data = await request.json()
        logging.info(f"🔁 Consulta recibida en /proxy/consultar: {data}")

        async def event_stream():
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        "POST",
                        "http://n8nendpoint.duckdns.org:3000/consultar",
                        json=data,
                        headers={"Content-Type": "application/json"},
                    ) as response:
                        async for chunk in response.aiter_bytes():
                            yield chunk
            except Exception as e:
                logging.error(f"🔻 Error en el stream desde n8n: {str(e)}")
                yield b"data: {\"response\": \"[Error al contactar con el motor RAG]\"}\\n\\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        logging.error(f"❌ Error interno en proxy_consultar: {str(e)}")
        raise HTTPException(status_code=500, detail="Error inesperado en el servidor proxy.")
