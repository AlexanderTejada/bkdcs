# app/adapters/chattigo_adapter.py
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ChattigoAdapter:
    def __init__(
        self,
        chattigo_api_key: str,  # Puede ser un JWT fijo o lo obtendremos dinámicamente
        chattigo_base_url: str,
        chattigo_did: str,
        chattigo_id: str,
        detectar_intencion_service: DetectarIntencionService,
        validar_reclamo_service: ValidarReclamoService,
        reclamo_service: RegistrarReclamoService = None,
        actualizar_service: ActualizarUsuarioService = None,
        consulta_estado_service: ConsultarEstadoReclamoService = None,
        consulta_reclamo_service: ConsultarReclamoService = None,
        redis_client: RedisClient = None
    ):
        self.chattigo_api_key = chattigo_api_key
        self.chattigo_base_url = chattigo_base_url
        self.chattigo_did = chattigo_did
        self.chattigo_id = chattigo_id
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
        self.consultar_facturas_service = ConsultarFacturasService(self.usuario_repository)
        self.redis_client = redis_client
        self.tiempo_inicio = int(time.time())
        logging.info(f"Inicializando ChattigoAdapter con did: {self.chattigo_did}, id: {self.chattigo_id}")

    async def handle_message(self, request: Request):
        try:
            data = await request.json()
            logging.info(f"Mensaje recibido de Chattigo: {json.dumps(data, indent=2)}")

            # Formato según la documentación de Chattigo
            if "channel" not in data or "msisdn" not in data or "content" not in data:
                raise HTTPException(status_code=400, detail="Solicitud inválida de Chattigo")

            channel = data["channel"]
            if channel != "WHATSAPP":
                logging.info(f"Ignorando mensaje de canal no WhatsApp: {channel}")
                return {"status": "ok"}

            user_id = data["msisdn"]  # Número del usuario (destino)
            texto_usuario = data["content"].strip().lower()  # Contenido del mensaje
            # No usamos timestamp porque no está en la estructura de Chattigo, pero podríamos añadirlo si lo incluyen

            texto_preprocesado = preprocess_text(texto_usuario)

            historial_clave = f"user:{user_id}:historial"
            estado_clave = f"user:{user_id}:estado"

            self.redis_client.rpush(historial_clave, f"Usuario: {texto_usuario}")
            historial = " | ".join(self.redis_client.lrange(historial_clave, -5, -1) or [])
            logging.info(f"Historial actual: {historial}")

            estado = self.redis_client.hgetall(estado_clave) or {"fase": "inicio"}
            logging.info(f"Estado actual: {estado}")

            if texto_usuario in ["cancelar", "salir"] and estado["fase"] != "inicio":
                self.redis_client.hset(estado_clave, "fase", "inicio")
                self.redis_client.hdel(estado_clave, "dni")
                self.redis_client.hdel(estado_clave, "accion")
                self.redis_client.hdel(estado_clave, "nombre")
                self.redis_client.hdel(estado_clave, "campo_actualizar")
                self.redis_client.hdel(estado_clave, "descripcion")
                await self.send_message(user_id, "✅ Entendido, he detenido el proceso. ¿En qué puedo ayudarte ahora? Puedo asistirte con reclamos, actualizar datos, consultar estados o facturas.")
                logging.info("Proceso cancelado por el usuario")
                return {"status": "ok"}
            elif texto_usuario in ["cancelar", "salir"] and estado["fase"] == "inicio":
                await self.send_message(user_id, "No hay ningún proceso activo para cancelar. ¿En qué puedo ayudarte hoy? Puedo asistirte con reclamos, actualizar datos, consultar estados o facturas.")
                return {"status": "ok"}

            if estado["fase"] == "inicio":
                logging.info("Fase inicio: Detectando intención con ChatGPT")
                respuesta_cruda = self.detectar_intencion_service.ejecutar_con_historial(texto_preprocesado, historial)
                try:
                    resultado = json.loads(respuesta_cruda)
                    intencion = resultado.get("intencion", "Conversar")
                    respuesta = resultado.get("respuesta", "No entendí bien tu mensaje. ¿En qué puedo ayudarte hoy? Puedes decirme si quieres hacer un reclamo, actualizar datos, consultar algo o ver tu factura.")
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Error al parsear respuesta: {respuesta_cruda}, Error: {str(e)}")
                    intencion = "Conversar"
                    respuesta = "No entendí bien tu mensaje. ¿En qué puedo ayudarte hoy? Puedes decirme si quieres hacer un reclamo, actualizar datos, consultar algo o ver tu factura."

                logging.info(f"Intención detectada: {intencion}, Respuesta: {respuesta}")
                await self.send_message(user_id, respuesta)

                if intencion == "Reclamo":
                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "reclamo")
                elif intencion == "Actualizar":
                    self.redis_client.hset(estado_clave, "fase", "seleccionar_dato")
                elif intencion == "Consultar":
                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "consultar")
                elif intencion == "ConsultarFacturas":
                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "consultar_facturas")

            elif estado["fase"] == "seleccionar_dato":
                opciones_validas = {"calle": "CALLE", "barrio": "BARRIO", "celular": "CELULAR", "teléfono": "CELULAR", "correo": "EMAIL", "mail": "EMAIL"}
                if texto_usuario not in opciones_validas:
                    await self.send_message(user_id, "No reconocí eso. Por favor, dime 'calle', 'barrio', 'celular' o 'correo'. Di 'cancelar' o 'salir' para detener el proceso.")
                    return {"status": "ok"}
                campo_actualizar = opciones_validas[texto_usuario]
                self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                self.redis_client.hset(estado_clave, "accion", "actualizar")
                self.redis_client.hset(estado_clave, "campo_actualizar", campo_actualizar)
                await self.send_message(user_id, f"Entendido, quieres actualizar tu {texto_usuario}. Por favor, dame tu DNI para continuar. Di 'cancelar' o 'salir' para detener el proceso.")

            elif estado["fase"] == "pedir_dni":
                if not re.match(r'^\d+$', texto_usuario):
                    await self.send_message(user_id, "Eso no parece un DNI válido. Por favor, ingresa solo números. Di 'cancelar' o 'salir' para detener el proceso.")
                    return {"status": "ok"}
                usuario_db1 = self.actualizar_service.usuario_repository.obtener_de_db1(texto_usuario)
                if usuario_db1:
                    primer_registro = usuario_db1[0]
                    nombre = f"{primer_registro['Apellido'].strip()} {primer_registro['Nombre'].strip()}"
                    self.redis_client.hset(estado_clave, "fase", "confirmar_dni")
                    self.redis_client.hset(estado_clave, "dni", texto_usuario)
                    self.redis_client.hset(estado_clave, "nombre", nombre)
                    await self.send_message(user_id, f"¿Eres {nombre}? Dime 'sí' o 'no' para confirmar. Di 'cancelar' o 'salir' para detener el proceso.")
                else:
                    usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(texto_usuario)
                    if usuario_db2:
                        nombre = usuario_db2.NOMBRE_COMPLETO.strip()
                        self.redis_client.hset(estado_clave, "fase", "confirmar_dni")
                        self.redis_client.hset(estado_clave, "dni", texto_usuario)
                        self.redis_client.hset(estado_clave, "nombre", nombre)
                        await self.send_message(user_id, f"¿Eres {nombre}? Dime 'sí' o 'no' para confirmar. Di 'cancelar' o 'salir' para detener el proceso.")
                    else:
                        await self.send_message(user_id, "No encontré a nadie con ese DNI. Verifica el número e inténtalo de nuevo. Di 'cancelar' o 'salir' para detener el proceso.")

            elif estado["fase"] == "confirmar_dni":
                if texto_usuario not in ["sí", "si", "no"]:
                    await self.send_message(user_id, "Por favor, dime 'sí' o 'no' para confirmar. Di 'cancelar' o 'salir' para detener el proceso.")
                    return {"status": "ok"}
                if texto_usuario == "no":
                    self.redis_client.hset(estado_clave, "fase", "inicio")
                    await self.send_message(user_id, "Entendido, parece que el DNI no es correcto. Dime otro cuando quieras.")
                    return {"status": "ok"}
                dni = estado.get("dni")
                if estado.get("accion") == "reclamo":
                    self.redis_client.hset(estado_clave, "fase", "solicitar_descripcion")
                    await self.send_message(user_id, f"Gracias por confirmar, {estado.get('nombre')}. Cuéntame qué problema tienes para registrar tu reclamo. Debe estar relacionado con cortes de luz, energía eléctrica o daños por el servicio. Di 'cancelar' o 'salir' para detener el proceso.")
                elif estado.get("accion") == "consultar":
                    self.redis_client.hset(estado_clave, "fase", "consultar_reclamos")
                    resultado, codigo = self.consulta_estado_service.ejecutar(dni)
                    if codigo == 200:
                        await self.send_message(user_id, f"Gracias, {estado.get('nombre')}. Aquí están tus últimos 5 reclamos:\n{self.format_reclamos(dni)}\nSi quieres detalles de uno, dime su ID. Di 'cancelar' o 'salir' para detener el proceso.")
                    else:
                        await self.send_message(user_id, "No encontré reclamos para tu DNI. Verifica e intenta de nuevo. Di 'cancelar' o 'salir' para detener el proceso.")
                        self.redis_client.hset(estado_clave, "fase", "inicio")
                elif estado.get("accion") == "actualizar":
                    campo = estado.get("campo_actualizar")
                    usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(dni)
                    current_value = getattr(usuario_db2, campo) if usuario_db2 and hasattr(usuario_db2, campo) else "No disponible"
                    self.redis_client.hset(estado_clave, "fase", "confirmar_actualizacion")
                    await self.send_message(user_id, f"Tu {campo.lower()} actual es: *{current_value}*. Dime el nuevo valor para actualizarlo. Di 'cancelar' o 'salir' para detener el proceso.")
                elif estado.get("accion") == "consultar_facturas":
                    resultado, status = self.consultar_facturas_service.ejecutar(dni)
                    if status == 200:
                        facturas = resultado.get("facturas", [])
                        if not facturas:
                            await self.send_message(user_id, "No encontré facturas para tu DNI. Verifica e intenta de nuevo.")
                        else:
                            facturas = facturas[:10]
                            mensaje = (
                                f"Gracias, {estado.get('nombre')}. Aquí están tus últimas facturas:\n\n"
                                + "\n".join([f"{i + 1}. Factura {factura['Periodo']} - ${factura['TotalFactura']:.2f} (Vence: {factura['VencimientoFactura']})" for i, factura in enumerate(facturas)])
                                + "\n\n¿En qué más puedo ayudarte?"
                            )
                            await self.send_message(user_id, mensaje)
                        self.redis_client.hset(estado_clave, "fase", "inicio")
                    else:
                        await self.send_message(user_id, "No encontré tu factura. Verifica el DNI e intenta de nuevo.")
                        self.redis_client.hset(estado_clave, "fase", "inicio")

            elif estado["fase"] == "solicitar_descripcion":
                if len(texto_usuario.strip()) < 3:
                    await self.send_message(user_id, "Por favor, dame más detalles (al menos 3 caracteres). Debe estar relacionado con cortes de luz, energía eléctrica o daños por el servicio. Di 'cancelar' o 'salir' para detener el proceso.")
                    return {"status": "ok"}
                self.redis_client.hset(estado_clave, "fase", "validar_reclamo")
                self.redis_client.hset(estado_clave, "descripcion", texto_usuario)
                await self.handle_message(request)

            elif estado["fase"] == "validar_reclamo":
                descripcion = estado.get("descripcion", "")
                logging.info(f"Validando reclamo con IA: {descripcion}")
                respuesta_cruda = self.validar_reclamo_service.ejecutar(descripcion, historial)
                logging.info(f"Respuesta cruda de ChatGPT (validación): {respuesta_cruda}")
                try:
                    resultado = json.loads(respuesta_cruda)
                    es_valido = resultado.get("es_valido", False)
                    mensaje_validacion = resultado.get("mensaje", "No se pudo validar el reclamo.")
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Error al parsear validación: {respuesta_cruda}, Error: {str(e)}")
                    es_valido = False
                    mensaje_validacion = "No pude validar tu reclamo debido a un problema técnico."

                if es_valido:
                    self.redis_client.hset(estado_clave, "fase", "ejecutar_accion")
                    await self.handle_message(request)
                else:
                    await self.send_message(user_id, f"No parece un reclamo válido: {mensaje_validacion}. Por favor, describe un problema relacionado con cortes de luz, energía eléctrica o daños por el servicio. Di 'cancelar' o 'salir' para detener el proceso.")
                    self.redis_client.hset(estado_clave, "fase", "solicitar_descripcion")

            elif estado["fase"] == "consultar_reclamos":
                if re.match(r'^\d+$', texto_usuario):
                    id_reclamo = int(texto_usuario)
                    respuesta, codigo = self.consulta_reclamo_service.ejecutar(id_reclamo)
                    if codigo == 200:
                        reclamo = respuesta["reclamo"]
                        cliente = respuesta["cliente"]
                        fecha_reclamo = reclamo.get('FECHA_RECLAMO', 'No disponible')
                        if fecha_reclamo != 'No disponible':
                            try:
                                fecha_reclamo_dt = datetime.fromisoformat(fecha_reclamo.replace('Z', '+00:00'))
                                fecha_reclamo = fecha_reclamo_dt.strftime("%d/%m/%Y %H:%M")
                            except ValueError:
                                fecha_reclamo = "No disponible"
                        calle = cliente.get('direccion', 'No disponible')
                        barrio = cliente.get('barrio', 'No disponible')
                        direccion = f"calle {calle}, barrio {barrio}" if calle != 'No disponible' and barrio != 'No disponible' else (calle if calle != 'No disponible' else barrio if barrio != 'No disponible' else 'No disponible')
                        await self.send_message(user_id, f"Detalles del reclamo ID {id_reclamo}:\n"
                                                        f"- Descripción: {reclamo.get('DESCRIPCION', 'No disponible')}\n"
                                                        f"- Estado: {reclamo.get('ESTADO', 'No disponible')}\n"
                                                        f"- Fecha de Reclamo: {fecha_reclamo}\n"
                                                        f"- Cliente: {cliente.get('nombre', 'No disponible')} (DNI: {cliente.get('dni', 'No disponible')})\n"
                                                        f"- Dirección: {direccion}")
                        self.redis_client.hset(estado_clave, "fase", "inicio")
                    else:
                        await self.send_message(user_id, f"No encontré ese reclamo. Intenta con otro ID. Di 'cancelar' o 'salir' para detener el proceso.")
                else:
                    await self.send_message(user_id, "Por favor, dame un ID de reclamo (solo números). Di 'cancelar' o 'salir' para detener el proceso.")

            elif estado["fase"] == "confirmar_actualizacion":
                self.redis_client.hset(estado_clave, "fase", "ejecutar_accion")
                self.redis_client.hset(estado_clave, "valor_actualizar", texto_usuario)
                await self.handle_message(request)

            elif estado["fase"] == "ejecutar_accion":
                dni = estado.get("dni")
                accion = estado.get("accion")
                descripcion = estado.get("descripcion", "")
                valor_actualizar = estado.get("valor_actualizar", "")
                nombre = estado.get("nombre")

                if accion == "reclamo":
                    resultado, status = self.reclamo_service.ejecutar(dni, descripcion)
                    if status == 201:
                        reclamo_id = resultado["id_reclamo"]
                        respuesta = f"Listo, {nombre}. Tu reclamo está registrado con ID: {reclamo_id}, Estado: Pendiente. Resumen: {descripcion}"
                    else:
                        respuesta = "Lo siento, no pude registrar tu reclamo ahora. ¿Intentamos de nuevo?"
                elif accion == "actualizar":
                    campo = estado.get("campo_actualizar")
                    resultado, status = self.actualizar_service.ejecutar(dni, {campo: valor_actualizar})
                    if status == 200:
                        usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(dni)
                        usuario_db1 = self.actualizar_service.usuario_repository.obtener_de_db1(dni) if not usuario_db2 else None
                        if usuario_db2:
                            respuesta = (f"✅ ¡Actualización exitosa, {nombre}!\n\n✔️ Datos actualizados:\n"
                                        f"📛 Nombre: {usuario_db2.NOMBRE_COMPLETO}\n"
                                        f"📍 Calle: {usuario_db2.CALLE}\n"
                                        f"🏘️ Barrio: {usuario_db2.BARRIO}\n"
                                        f"📱 Teléfono: {usuario_db2.CELULAR}\n"
                                        f"✉️ Correo: {usuario_db2.EMAIL}")
                        elif usuario_db1:
                            respuesta = (f"✅ ¡Actualización exitosa, {nombre}!\n\n✔️ Datos actualizados:\n"
                                        f"📛 Nombre: {usuario_db1[0]['Apellido']} {usuario_db1[0]['Nombre']}\n"
                                        f"📍 Calle: {usuario_db1[0].get('Calle', 'No disponible')}\n"
                                        f"🏘️ Barrio: {usuario_db1[0].get('Barrio', 'No disponible')}\n"
                                        f"📱 Teléfono: {usuario_db1[0].get('Telefono', 'No disponible')}\n"
                                        f"✉️ Correo: {usuario_db1[0].get('Email', 'No disponible')}")
                        else:
                            respuesta = "Actualización exitosa, pero no pude recuperar tus datos actualizados."
                    else:
                        respuesta = "No pude actualizar eso ahora. ¿Probamos otra vez?"
                else:
                    respuesta = "Algo salió mal. ¿En qué más puedo ayudarte?"

                await self.send_message(user_id, respuesta)
                await self.send_message(user_id, "¿Necesitas algo más? Puedo ayudarte con un reclamo, actualizar datos, consultar estados o facturas.")
                self.redis_client.hset(estado_clave, "fase", "inicio")
                self.redis_client.hdel(estado_clave, "descripcion")
                self.redis_client.hdel(estado_clave, "valor_actualizar")

        except Exception as e:
            logging.error(f"Error en handle_message: {str(e)}")
            await self.send_message(user_id, f"Uy, algo falló: {str(e)}. Intentemos de nuevo.")
            self.redis_client.hset(estado_clave, "fase", "inicio")

        return {"status": "ok"}

    async def send_message(self, to: str, text: str):
        try:
            url = f"{self.chattigo_base_url}/inbound"
            headers = {
                "Authorization": f"Bearer {self.chattigo_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "id": self.chattigo_id,
                "did": self.chattigo_did,
                "msisdn": to,
                "name": "Bot DECSA",  # Nombre del bot que responde
                "type": "text",
                "channel": "WHATSAPP",
                "content": text,
                "isAttachment": False
            }
            logging.info(f"Enviando respuesta a Chattigo: {json.dumps(payload, indent=2)}")
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logging.info(f"Respuesta de Chattigo: {response.text}")
            return response.json()
        except Exception as e:
            logging.error(f"Error al enviar mensaje a Chattigo: {str(e)}")
            raise

    def format_reclamos(self, dni=None, is_single=False):
        if is_single and dni:
            logging.warning("format_reclamos llamado con is_single=True y dni, pero se espera un id_reclamo")
            return "Función no implementada para reclamo individual por DNI"
        else:
            respuesta, codigo = self.consulta_estado_service.ejecutar(dni) if dni else (None, 404)
            if codigo == 200:
                if "mensaje" in respuesta:
                    return respuesta["mensaje"]
                reclamos = respuesta.get("reclamos", [])
                if not reclamos:
                    return "No tienes reclamos registrados recientemente."
                return "\n".join([
                    f"ID: {r['ID_RECLAMO']}, Estado: {r['ESTADO']}, Descripción: {r['DESCRIPCION'][:50]}{'...' if len(r['DESCRIPCION']) > 50 else ''}"
                    for r in reclamos
                ])
            return "No pude obtener tus reclamos. Intenta de nuevo."

    def __del__(self):
        self.session_db1.close()
        self.session_db2.close()