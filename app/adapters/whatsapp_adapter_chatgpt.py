# app/adapters/whatsapp_adapter_chatgpt.py
import logging
import json
from datetime import datetime
import time
import requests
import re
from fastapi import FastAPI, Request, HTTPException
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

class WhatsAppAdapterChatGPT:
    def __init__(
            self,
            phone_number_id: str,
            access_token: str,
            detectar_intencion_service: DetectarIntencionService,
            validar_reclamo_service: ValidarReclamoService,
            verify_token: str,
            reclamo_service: RegistrarReclamoService = None,
            actualizar_service: ActualizarUsuarioService = None,
            consulta_estado_service: ConsultarEstadoReclamoService = None,
            consulta_reclamo_service: ConsultarReclamoService = None,
            redis_client: RedisClient = None,
            app: FastAPI = None
    ):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.verify_token = verify_token
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
        self.app = app
        self.tiempo_inicio = int(time.time())
        logging.info(f"Inicializando WhatsAppAdapterChatGPT con phone_number_id: {self.phone_number_id}")
        logging.info(f"Access token (primeros 10 caracteres): {self.access_token[:10]}...")
        logging.info(f"Verify token: {self.verify_token}")

    async def handle_message(self, request: Request):
        try:
            data = await request.json()
            logging.info(f"Mensaje recibido de WhatsApp: {data}")

            if "object" not in data or "entry" not in data:
                raise HTTPException(status_code=400, detail="Solicitud inválida")

            entry = data["entry"][0]
            changes = entry.get("changes", [])
            if not changes:
                raise HTTPException(status_code=400, detail="No hay cambios en la solicitud")

            change = changes[0]
            value = change.get("value", {})

            if "messages" not in value or "statuses" in value:
                return {"status": "ok"}

            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue

                if message.get("from") == self.phone_number_id:
                    continue

                try:
                    mensaje_timestamp = int(message.get("timestamp", 0))
                    if mensaje_timestamp < self.tiempo_inicio:
                        logging.info(f"⏳ Mensaje ignorado (antiguo): {mensaje_timestamp} < {self.tiempo_inicio}")
                        continue
                except ValueError:
                    logging.warning("⚠️ Timestamp inválido")
                    continue

                user_id = message["from"]
                texto_usuario = message["text"]["body"].strip().lower()
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
                    await self.send_message(user_id,
                                           "✅ *Proceso detenido*\n\n_¿En qué puedo ayudarte ahora?_\nPuedo asistirte con:\n- *Reclamos*\n- *Datos*\n- *Consultas*\n- *Facturas*")
                    logging.info("Proceso cancelado por el usuario")
                    return {"status": "ok"}
                elif texto_usuario in ["cancelar", "salir"] and estado["fase"] == "inicio":
                    await self.send_message(user_id,
                                           "ℹ️ *No hay ningún proceso activo*\n\n_¿Cómo puedo ayudarte hoy?_\nPuedo asistirte con:\n- *Reclamos*\n- *Actualizar datos*\n- *Consultas*\n- *Facturas*")
                    return {"status": "ok"}

                if estado["fase"] == "inicio":
                    logging.info("Fase inicio: Detectando intención con ChatGPT")
                    respuesta_cruda = self.detectar_intencion_service.ejecutar_con_historial(texto_preprocesado,
                                                                                             historial)
                    try:
                        resultado = json.loads(respuesta_cruda)
                        intencion = resultado.get("intencion", "Conversar")
                        respuesta = resultado.get("respuesta",
                                                  "🤔 *No entendí bien tu mensaje*\n\n_¿Cómo puedo ayudarte hoy?_\nPuedo asistirte con:\n- *Reclamos*\n- *Actualizar datos*\n- *Consultar estados*\n- *Ver tu factura*")
                    except (json.JSONDecodeError, TypeError) as e:
                        logging.warning(f"Error al parsear respuesta: {respuesta_cruda}, Error: {str(e)}")
                        intencion = "Conversar"
                        respuesta = "🤔 *No entendí bien tu mensaje*\n\n_¿Cómo puedo ayudarte hoy?_\nPuedo asistirte con:\n- *Reclamos*\n- *Actualizar datos*\n- *Consultar estados*\n- *Ver tu factura*"

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
                    opciones_validas = {"calle": "CALLE", "barrio": "BARRIO", "celular": "CELULAR",
                                        "teléfono": "CELULAR", "correo": "EMAIL", "mail": "EMAIL"}
                    if texto_usuario not in opciones_validas:
                        await self.send_message(user_id,
                                               "❌ *Opción no reconocida*\n\n_Por favor, elige una de las siguientes:_\n*calle* | *barrio* | *celular* | *correo*\n\n_O di *cancelar* para salir_")
                        return {"status": "ok"}
                    campo_actualizar = opciones_validas[texto_usuario]
                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "actualizar")
                    self.redis_client.hset(estado_clave, "campo_actualizar", campo_actualizar)
                    await self.send_message(user_id,
                                           f"✅ *¡Entendido!* Quieres actualizar tu _{texto_usuario}_\n\n_Por favor, indícame tu DNI_\n_O di *cancelar* para salir_")

                elif estado["fase"] == "pedir_dni":
                    if not re.match(r'^\d+$', texto_usuario):
                        await self.send_message(user_id,
                                               "❌ *DNI no válido*\n\n_Por favor, ingresa solo números_\n_O di *cancelar* para salir_")
                        return {"status": "ok"}
                    usuario_db1 = self.actualizar_service.usuario_repository.obtener_de_db1(texto_usuario)
                    if usuario_db1:
                        primer_registro = usuario_db1[0]
                        nombre = f"{primer_registro['Apellido'].strip()} {primer_registro['Nombre'].strip()}"
                        self.redis_client.hset(estado_clave, "fase", "confirmar_dni")
                        self.redis_client.hset(estado_clave, "dni", texto_usuario)
                        self.redis_client.hset(estado_clave, "nombre", nombre)
                        await self.send_message(user_id,
                                               f"👤 ¿Eres *{nombre}*?\n\n_Responde *sí* o *no* para confirmar_\n_O di *cancelar* para salir_")
                    else:
                        usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(texto_usuario)
                        if usuario_db2:
                            nombre = usuario_db2.NOMBRE_COMPLETO.strip()
                            self.redis_client.hset(estado_clave, "fase", "confirmar_dni")
                            self.redis_client.hset(estado_clave, "dni", texto_usuario)
                            self.redis_client.hset(estado_clave, "nombre", nombre)
                            await self.send_message(user_id,
                                                   f"👤 ¿Eres {nombre}?\n\n_Responde *sí* o *no* para confirmar_\n_O di *cancelar* para salir_")
                        else:
                            await self.send_message(user_id,
                                                   "🔍 *No encontré a nadie con ese DNI*\n\n_Por favor, verifica el número e inténtalo de nuevo_\n_O di *cancelar* para salir_")

                elif estado["fase"] == "confirmar_dni":
                    if texto_usuario not in ["sí", "si", "no"]:
                        await self.send_message(user_id,
                                               " _Por favor, responde solo *sí* o *no* para confirmar_\n\n_O di *cancelar* para salir_")
                        return {"status": "ok"}
                    if texto_usuario == "no":
                        self.redis_client.hset(estado_clave, "fase", "inicio")
                        await self.send_message(user_id,
                                               "ℹ️ *Entendido, el DNI no es correcto*\n\n_Dime otro cuando quieras o pregunta otra cosa_")
                        return {"status": "ok"}
                    dni = estado.get("dni")
                    if estado.get("accion") == "reclamo":
                        self.redis_client.hset(estado_clave, "fase", "solicitar_descripcion")
                        await self.send_message(user_id,
                                               f"✅ *¡Gracias por confirmar, {estado.get('nombre')}!* \n\n_Cuéntame qué problema tienes para registrar tu reclamo_\n*(Debe estar relacionado con cortes de luz, energía eléctrica o daños por el servicio)*\n\n_O di *cancelar* para salir_")
                    elif estado.get("accion") == "consultar":
                        self.redis_client.hset(estado_clave, "fase", "consultar_reclamos")
                        resultado, codigo = self.consulta_estado_service.ejecutar(dni)
                        if codigo == 200:
                            await self.send_message(user_id,
                                                   f"✅ *Gracias, {estado.get('nombre')}*\n\n_Aquí están tus últimos 5 reclamos:_\n{self.format_reclamos(dni)}\n\n_Si quieres detalles de uno, dime su ID_\n_O di *cancelar* para salir_")
                        else:
                            await self.send_message(user_id,
                                                   "🔍 *No encontré reclamos para tu DNI*\n\n_Verifica e intenta de nuevo_\n_O di *cancelar* para salir_")
                            self.redis_client.hset(estado_clave, "fase", "inicio")
                    elif estado.get("accion") == "actualizar":
                        campo = estado.get("campo_actualizar")
                        usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(dni)
                        current_value = getattr(usuario_db2, campo) if usuario_db2 and hasattr(usuario_db2,
                                                                                               campo) else "No disponible"
                        self.redis_client.hset(estado_clave, "fase", "confirmar_actualizacion")
                        await self.send_message(user_id,
                                               f"✅ *Tu {campo.lower()} actual es:*\n*{current_value}*\n\n_Dime el nuevo valor para actualizarlo_\n_O di *cancelar* para salir_")
                    elif estado.get("accion") == "consultar_facturas":
                        resultado, status = self.consultar_facturas_service.ejecutar(dni)
                        if status == 200:
                            facturas = resultado.get("facturas", [])
                            logging.info(f"Facturas crudas recibidas: {facturas[:2]}")  # Log para inspeccionar datos
                            if not facturas:
                                await self.send_message(user_id,
                                                       "🔍 *No encontré facturas para tu DNI*\n\n_Verifica e intenta de nuevo_\n_O di *cancelar* para salir_")
                            else:
                                factura = facturas[0]  # Última factura
                                try:
                                    # Manejo de fechas como string o datetime
                                    fecha_emision = factura.get('FechaEmision', datetime.now())
                                    if isinstance(fecha_emision, datetime):
                                        fecha_emision = fecha_emision.strftime('%d/%m/%Y')
                                    vencimiento = factura.get('Vencimiento', datetime.now())
                                    if isinstance(vencimiento, datetime):
                                        vencimiento = vencimiento.strftime('%d/%m/%Y')

                                    # Usamos 'Total' en lugar de 'TotalFactura'
                                    total_factura = factura.get('Total', None)
                                    if total_factura is None:
                                        logging.warning(f"Campo 'Total' no encontrado en factura: {factura}")
                                        total_factura = "No disponible"
                                    else:
                                        try:
                                            total_factura = float(total_factura)
                                        except (TypeError, ValueError):
                                            logging.error(f"'Total' no convertible a float: {total_factura}")
                                            total_factura = "No disponible"

                                    mensaje = (
                                        f"✅ *Factura de {estado.get('nombre')}* _(DNI: {dni})_\n\n"
                                        f"📋 *Número de cuenta*: _{factura.get('CodigoSuministro', 'No disponible')}_\n"
                                        f"📄 *N° Comprobante*: _{factura.get('NumeroComprobante', 'No disponible')}_\n"
                                        f"📅 *Fecha Emisión*: _{fecha_emision}_\n"
                                        f"✅ *Estado*: _{factura.get('Estado', 'No disponible')}_\n"
                                    )
                                    if isinstance(total_factura, float):
                                        mensaje += f"💰 *Total*: _${total_factura:.2f}_\n"
                                    else:
                                        mensaje += f"💰 *Total*: _{total_factura}_\n"
                                    mensaje += (
                                        f"⏰ *Vencimiento*: _{vencimiento}_\n"
                                        f"🏠 *Dirección*: _{factura.get('Calle', 'No disponible')}, {factura.get('Barrio', 'No disponible')}_\n"
                                        f"⚡ *Medidor*: _{factura.get('NumeroMedidor', 'No disponible')}_\n"
                                        f"📆 *Período*: _{factura.get('Periodo', 'No disponible')}_\n"
                                        f"🔋 *Consumo*: _{float(factura.get('Consumo', 0))} kWh_\n\n"
                                        f"_Para ver todas tus facturas, visita:_ https://frontdecsa.vercel.app/\n\n"
                                        f"*¿En qué más puedo ayudarte?*"
                                    )
                                    logging.info(f"Mensaje formateado: {mensaje}")
                                    await self.send_message(user_id, mensaje)
                                except Exception as e:
                                    logging.error(f"Error al formatear la factura: {str(e)} - Datos: {factura}")
                                    await self.send_message(user_id,
                                                           f"❌ *No pude mostrar tu factura*\n\n_Error:_ _{str(e)}_\n\n_Intenta de nuevo o di *cancelar* para salir_")
                                    self.redis_client.hset(estado_clave, "fase", "inicio")
                                    return {"status": "ok"}
                            self.redis_client.hset(estado_clave, "fase", "inicio")
                        else:
                            await self.send_message(user_id,
                                                   "🔍 *No encontré tu factura*\n\n_Verifica el DNI e intenta de nuevo_\n_O di *cancelar* para salir_")
                            self.redis_client.hset(estado_clave, "fase", "inicio")

                elif estado["fase"] == "solicitar_descripcion":
                    if len(texto_usuario.strip()) < 3:
                        await self.send_message(user_id,
                                               "ℹ️ *Necesito más detalles*\n\n_Describe el problema con al menos 3 caracteres_\n*(Relacionado con cortes de luz, energía eléctrica o daños por el servicio)*\n\n_O di *cancelar* para salir_")
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
                        await self.send_message(user_id,
                                               f"❌ *No parece un reclamo válido*\n\n_{mensaje_validacion}_\n\n_Por favor, describe un problema relacionado con cortes de luz, energía eléctrica o daños por el servicio_\n_O di *cancelar* para salir_")
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
                            direccion = f"calle {calle}, barrio {barrio}" if calle != 'No disponible' and barrio != 'No disponible' else (
                                calle if calle != 'No disponible' else barrio if barrio != 'No disponible' else 'No disponible')
                            await self.send_message(user_id,
                                                   f"✅ *Detalles del reclamo ID {id_reclamo}:*\n\n"
                                                   f"- *Descripción*: _{reclamo.get('DESCRIPCION', 'No disponible')}_\n"
                                                   f"- *Estado*: _{reclamo.get('ESTADO', 'No disponible')}_\n"
                                                   f"- *Fecha de Reclamo*: _{fecha_reclamo}_\n"
                                                   f"- *Cliente*: _{cliente.get('nombre', 'No disponible')} (DNI: {cliente.get('dni', 'No disponible')})_\n"
                                                   f"- *Dirección*: _{direccion}_")
                            self.redis_client.hset(estado_clave, "fase", "inicio")
                        else:
                            await self.send_message(user_id,
                                                   "🔍 *No encontré ese reclamo*\n\n_Intenta con otro ID_\n_O di *cancelar* para salir_")
                    else:
                        await self.send_message(user_id,
                                               "ℹ️ *Por favor, dame un ID de reclamo*\n\n_(Solo números)_\n_O di *cancelar* para salir_")

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
                            respuesta = f"✅ *¡Listo, {nombre}!* Tu reclamo está registrado\n\n" \
                                        f"*ID*: _{reclamo_id}_\n" \
                                        f"*Estado*: _Pendiente_\n" \
                                        f"*Resumen*: _{descripcion}_\n\n" \
                                        f"_¿En qué más puedo ayudarte?_"
                        else:
                            respuesta = "❌ *Lo siento, no pude registrar tu reclamo*\n\n_¿Intentamos de nuevo?_"
                    elif accion == "actualizar":
                        campo = estado.get("campo_actualizar")
                        resultado, status = self.actualizar_service.ejecutar(dni, {campo: valor_actualizar})
                        if status == 200:
                            usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(dni)
                            usuario_db1 = self.actualizar_service.usuario_repository.obtener_de_db1(
                                dni) if not usuario_db2 else None
                            if usuario_db2:
                                respuesta = (f"✅ *¡Actualización exitosa, {nombre}!*\n\n"
                                             f"✔️ *Datos actualizados:*\n"
                                             f"📛 *Nombre*: _{usuario_db2.NOMBRE_COMPLETO}_\n"
                                             f"📍 *Calle*: _{usuario_db2.CALLE}_\n"
                                             f"🏘️ *Barrio*: _{usuario_db2.BARRIO}_\n"
                                             f"📱 *Teléfono*: _{usuario_db2.CELULAR}_\n"
                                             f"✉️ *Correo*: _{usuario_db2.EMAIL}_\n\n"
                                             f"_¿En qué más puedo ayudarte?_")
                            elif usuario_db1:
                                respuesta = (f"✅ *¡Actualización exitosa, {nombre}!*\n\n"
                                             f"✔️ *Datos actualizados:*\n"
                                             f"📛 *Nombre*: _{usuario_db1[0]['Apellido']} {usuario_db1[0]['Nombre']}_\n"
                                             f"📍 *Calle*: _{usuario_db1[0].get('Calle', 'No disponible')}_\n"
                                             f"🏘️ *Barrio*: _{usuario_db1[0].get('Barrio', 'No disponible')}_\n"
                                             f"📱 *Teléfono*: _{usuario_db1[0].get('Telefono', 'No disponible')}_\n"
                                             f"✉️ *Correo*: _{usuario_db1[0].get('Email', 'No disponible')}_\n\n"
                                             f"_¿En qué más puedo ayudarte?_")
                            else:
                                respuesta = "✅ *Actualización exitosa*\n\n_No pude recuperar tus datos actualizados_\n\n_¿En qué más puedo ayudarte?_"
                        else:
                            respuesta = "❌ *No pude actualizar eso ahora*\n\n_¿Probamos otra vez?_"
                    else:
                        respuesta = "❓ *Algo salió mal*\n\n_¿Cómo puedo ayudarte ahora?_"

                    await self.send_message(user_id, respuesta)
                    await self.send_message(user_id,
                                           "ℹ️ *¿En qué más puedo ayudarte?*\n\n_Puedo asistirte con:_\n- *Reclamos*\n- *Datos*\n- *Consultas*\n- *Facturas*")
                    self.redis_client.hset(estado_clave, "fase", "inicio")
                    self.redis_client.hdel(estado_clave, "descripcion")
                    self.redis_client.hdel(estado_clave, "valor_actualizar")

        except Exception as e:
            logging.error(f"Error en handle_message: {str(e)}")
            await self.send_message(user_id,
                                   f"❌ *Uy, algo falló*\n\n_Error:_ _{str(e)}_\n\n_Intentemos de nuevo o di *cancelar* para salir_")
            self.redis_client.hset(estado_clave, "fase", "inicio")

        return {"status": "ok"}

    def deformar_numero_argentino(self, numero: str) -> str:
        if numero.startswith("549"):
            cod_area = numero[3:6]
            numero_local = numero[6:]
            return f"54{cod_area}15{numero_local}"
        return numero

    async def send_message(self, to: str, text: str):
        try:
            url = f"https://graph.facebook.com/v20.0/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            numero_deformado = self.deformar_numero_argentino(to)
            logging.info(f"Enviando mensaje a {numero_deformado}: {text}")
            data = {
                "messaging_product": "whatsapp",
                "to": numero_deformado,
                "type": "text",
                "text": {
                    "body": text
                }
            }
            logging.info(f"URL de la solicitud: {url}")
            logging.info(f"Datos enviados: {json.dumps(data, indent=2)}")
            response = requests.post(url, headers=headers, json=data)
            logging.info(f"Respuesta de WhatsApp: Status Code: {response.status_code}, Contenido: {response.text}")
            if response.status_code != 200:
                logging.error(f"Error al enviar mensaje a WhatsApp: {response.text}")
                raise HTTPException(status_code=500, detail=f"Error al enviar mensaje a WhatsApp: {response.text}")
            logging.info(f"Mensaje enviado a {numero_deformado}: {text}")
            return response.json()
        except Exception as e:
            logging.error(f"Excepción al enviar mensaje a WhatsApp: {str(e)}")
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