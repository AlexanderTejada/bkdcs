# app/adapters/chattigo_adapter_chatgpt.py
import logging
import json
from datetime import datetime
import time
import requests
import re
from fastapi import Request, HTTPException
from app.services.registrar_reclamo_service import RegistrarReclamoService
from app.services.actualizar_usuario_service import ActualizarUsuarioService
from app.services.consultar_estado_reclamo_service import ConsultarEstadoReclamoService
from app.services.consultar_reclamo_service import ConsultarReclamoService
from app.services.consultar_facturas_service import ConsultarFacturasService
from app.services.detectar_intencion_service import DetectarIntencionService
from app.services.validar_reclamo_chatgpt_usecase import ValidarReclamoService
from app.services.redis_client import RedisClient
from app.database.database import SessionLocal_db1, SessionLocal_db2
from app.repositories.sqlalchemy_usuario_repository import SQLAlchemyUsuarioRepository
from app.repositories.sqlalchemy_reclamo_repository import SQLAlchemyReclamoRepository
from app.utils.text_processor import preprocess_text
from app.config.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class ChattigoAdapterChatGPT:
    def __init__(
            self,
            username: str,
            password: str,
            detectar_intencion_service: DetectarIntencionService,
            validar_reclamo_service: ValidarReclamoService,
            reclamo_service: RegistrarReclamoService = None,
            actualizar_service: ActualizarUsuarioService = None,
            consulta_estado_service: ConsultarEstadoReclamoService = None,
            consulta_reclamo_service: ConsultarReclamoService = None,
            consultar_facturas_service: ConsultarFacturasService = None,
            redis_client: RedisClient = None
    ):
        self.username = username
        self.password = password
        self.token = None
        self.token_expiry = 0
        self.detectar_intencion_service = detectar_intencion_service
        self.validar_reclamo_service = validar_reclamo_service
        self.session_db1 = SessionLocal_db1()
        self.session_db2 = SessionLocal_db2()
        self.usuario_repository = SQLAlchemyUsuarioRepository(self.session_db1, self.session_db2)
        self.reclamo_service = reclamo_service if reclamo_service else RegistrarReclamoService(
            SQLAlchemyReclamoRepository(self.session_db2), self.usuario_repository
        )
        self.actualizar_service = actualizar_service if actualizar_service else ActualizarUsuarioService(
            self.usuario_repository
        )
        self.consulta_estado_service = consulta_estado_service if consulta_estado_service else ConsultarEstadoReclamoService(
            SQLAlchemyReclamoRepository(self.session_db2), self.usuario_repository
        )
        self.consulta_reclamo_service = consulta_reclamo_service if consulta_reclamo_service else ConsultarReclamoService(
            SQLAlchemyReclamoRepository(self.session_db2)
        )
        self.consultar_facturas_service = consultar_facturas_service if consultar_facturas_service else ConsultarFacturasService(
            self.usuario_repository
        )
        self.redis_client = redis_client if redis_client else RedisClient().get_client()
        self.tiempo_inicio = int(time.time())
        logging.info(f"Inicializando ChattigoAdapterChatGPT con usuario: {self.username}")

    async def handle_message(self, request: Request):
        try:
            data = await request.json()
            logging.info(f"📩 [CHATTIGO RAW PAYLOAD]:\n{data}")

            if "msisdn" not in data or "content" not in data or "did" not in data:
                raise HTTPException(status_code=400, detail="Estructura inválida en mensaje recibido de Chattigo")

            user_id = data["msisdn"]
            texto_usuario = data["content"].strip().lower()
            did = data["did"]
            user_name = data.get("name", "Usuario")

            if not texto_usuario:
                logging.info("Mensaje vacío, ignorado")
                return {"status": "ok"}

            texto_preprocesado = preprocess_text(texto_usuario)
            historial_clave = f"user:{user_id}:historial"
            estado_clave = f"user:{user_id}:estado"

            self.redis_client.rpush(historial_clave, f"Usuario: {texto_usuario}")
            historial = " | ".join(self.redis_client.lrange(historial_clave, -5, -1) or [])
            logging.info(f"Historial actual: {historial}")

            estado = self.redis_client.hgetall(estado_clave) or {"fase": "inicio"}
            logging.info(f"Estado actual: {estado}")

            if texto_usuario in ["cancelar", "salir"]:
                self.redis_client.hset(estado_clave, "fase", "inicio")
                for campo in ["dni", "accion", "nombre", "campo_actualizar", "descripcion", "valor_actualizar"]:
                    self.redis_client.hdel(estado_clave, campo)
                await self.send_message(user_id, did, message="¡Hola! ¿En qué puedo ayudarte hoy?")
                return {"status": "ok"}

            if estado["fase"] == "inicio":
                logging.info("Fase inicio: Detectando intención con ChatGPT")
                respuesta_cruda = self.detectar_intencion_service.ejecutar_con_historial(texto_preprocesado, historial)
                try:
                    resultado = json.loads(respuesta_cruda)
                    intencion = resultado.get("intencion", "Conversar")
                    respuesta = resultado.get("respuesta", "Por favor, selecciona una opción:")
                except (json.JSONDecodeError, TypeError):
                    intencion = "Conversar"
                    respuesta = "Por favor, selecciona una opción:"

                # Enviar mensaje de bienvenida
                await self.send_message(user_id, did, message="¡Hola! ¿En qué puedo ayudarte hoy?")

                if intencion == "Reclamo":
                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "reclamo")
                    await self.send_message(user_id, did, message="Por favor, ingresa tu DNI para registrar el reclamo.")
                elif intencion == "Actualizar":
                    self.redis_client.hset(estado_clave, "fase", "seleccionar_dato")
                    await self.send_message(user_id, did, message="¿Qué dato deseas actualizar? (Por ejemplo: nombre, dirección, teléfono)")
                elif intencion == "Consultar":
                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "consultar")
                    await self.send_message(user_id, did, message="Por favor, ingresa tu DNI para consultar el estado de tu reclamo.")
                elif intencion == "ConsultarFacturas":
                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "consultar_facturas")
                    await self.send_message(user_id, did, message="Por favor, ingresa tu DNI para consultar tus facturas.")
                return {"status": "ok"}

            return {"status": "ok"}

        except Exception as e:
            logging.error(f"Error en handle_message: {str(e)}")
            await self.send_message(user_id, did, message="Lo siento, ocurrió un error. ¿En qué puedo ayudarte ahora?")
            raise HTTPException(status_code=500, detail=f"Error interno al procesar mensaje desde Chattigo: {str(e)}")

    async def send_message(
            self,
            msisdn: str,
            did: str,
            message: str
    ):
        try:
            if not self.token or time.time() > self.token_expiry:
                token_response = requests.post(
                    "https://massive.chattigo.com/api-bot/login",
                    json={"username": self.username, "password": self.password}
                )
                if token_response.status_code != 200:
                    logging.error(f"Error al obtener token JWT: {token_response.text}")
                    raise HTTPException(status_code=500, detail="Error de autenticación con Chattigo")
                token_data = token_response.json()
                self.token = token_data.get("access_token")
                self.token_expiry = time.time() + token_data.get("expires_in", 3600)
                logging.info(f"Token obtenido: {self.token}")

            url = "https://massive.chattigo.com/api-bot/outbound"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            payload = {
                         "id": did, #obtner el id?
                         "idChat": msisdn, #obtener el id del chat
                         "chatType": "OUTBOUND",
                         "did": did,
                         "msisdn": msisdn,
                        "type": "Text",
                         "channel": "WHATSAPP",
                         "channelId": 12676,
                         "channelProvider": "APICLOUDBSP",
                         "content": message,
                         "name": "BotDecsa",
                         "idCampaign": "7732",
                         "isAttachment": False,
                         "stateAgent": "BOT"

            }


            logging.info(f"Enviando mensaje a Chattigo: {json.dumps(payload, indent=2)}")
            response = requests.post(url, headers=headers, json=payload)
            logging.info(f"Respuesta de Chattigo: Status {response.status_code} - {response.text}")

            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Error al enviar mensaje a Chattigo: {response.text}")

        except Exception as e:
            logging.error(f"Excepción en send_message: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def __del__(self):
        self.session_db1.close()
        self.session_db2.close()