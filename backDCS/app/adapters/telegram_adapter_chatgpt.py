from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
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
import re
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TelegramAdapterChatGPT:
    def __init__(
        self,
        token: str,
        detectar_intencion_service: DetectarIntencionService,
        validar_reclamo_service: ValidarReclamoService,
        reclamo_service: RegistrarReclamoService = None,
        actualizar_service: ActualizarUsuarioService = None,
        consulta_estado_service: ConsultarEstadoReclamoService = None,
        consulta_reclamo_service: ConsultarReclamoService = None,
        redis_client: RedisClient = None,
        app=None
    ):
        self.token = token
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
        self.app = ApplicationBuilder().token(self.token).build()
        logging.info(f"Inicializando TelegramAdapterChatGPT con token: {self.token[:10]}...")
        self.setup_handlers()

    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("reset", self.reset))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        self.redis_client.delete(f"user:{user_id}:historial")
        self.redis_client.delete(f"user:{user_id}:estado")
        await update.message.reply_text(
            "👋 *¡Hola!* Soy DECSA, tu asistente virtual oficial. Estoy aquí para ayudarte con tus servicios eléctricos.\n\n"
            "_¿En qué puedo ayudarte hoy?_\nPuedo asistirte con:\n- *Reclamos*\n- *Actualizar datos*\n- *Consultas*\n- *Facturas*",
            parse_mode="Markdown"
        )

    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        self.redis_client.delete(f"user:{user_id}:historial")
        self.redis_client.delete(f"user:{user_id}:estado")
        await update.message.reply_text(
            "🔄 *Conversación reiniciada*\n\n_¿En qué puedo ayudarte ahora?_\nPuedo asistirte con:\n- *Reclamos*\n- *Datos*\n- *Consultas*\n- *Facturas*",
            parse_mode="Markdown"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = str(update.effective_user.id)
            texto_usuario = update.message.text.strip().lower()
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
                await update.message.reply_text(
                    "✅ *Proceso detenido*\n\n_¿En qué puedo ayudarte ahora?_\nPuedo asistirte con:\n- *Reclamos*\n- *Datos*\n- *Consultas*\n- *Facturas*",
                    parse_mode="Markdown"
                )
                logging.info("Proceso cancelado por el usuario")
                return
            elif texto_usuario in ["cancelar", "salir"] and estado["fase"] == "inicio":
                await update.message.reply_text(
                    "ℹ️ *No hay ningún proceso activo*\n\n_¿Cómo puedo ayudarte hoy?_\nPuedo asistirte con:\n- *Reclamos*\n- *Actualizar datos*\n- *Consultas*\n- *Facturas*",
                    parse_mode="Markdown"
                )
                return

            if estado["fase"] == "inicio":
                logging.info("Fase inicio: Detectando intención con ChatGPT")
                respuesta_cruda = self.detectar_intencion_service.ejecutar_con_historial(texto_preprocesado, historial)
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
                await update.message.reply_text(respuesta, parse_mode="Markdown")

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
                    await update.message.reply_text(
                        "❌ *Opción no reconocida*\n\n_Por favor, elige una de las siguientes:_\n*calle* | *barrio* | *celular* | *correo*\n\n_O di *cancelar* para salir_",
                        parse_mode="Markdown"
                    )
                    return
                campo_actualizar = opciones_validas[texto_usuario]
                self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                self.redis_client.hset(estado_clave, "accion", "actualizar")
                self.redis_client.hset(estado_clave, "campo_actualizar", campo_actualizar)
                await update.message.reply_text(
                    f"✅ *¡Entendido!* Quieres actualizar tu _{texto_usuario}_\n\n_Por favor, indícame tu DNI_\n_O di *cancelar* para salir_",
                    parse_mode="Markdown"
                )

            elif estado["fase"] == "pedir_dni":
                if not re.match(r'^\d+$', texto_usuario):
                    await update.message.reply_text(
                        "❌ *DNI no válido*\n\n_Por favor, ingresa solo números_\n_O di *cancelar* para salir_",
                        parse_mode="Markdown"
                    )
                    return
                usuario_db1 = self.actualizar_service.usuario_repository.obtener_de_db1(texto_usuario)
                if usuario_db1:
                    primer_registro = usuario_db1[0]
                    nombre = f"{primer_registro['Apellido'].strip()} {primer_registro['Nombre'].strip()}"
                    self.redis_client.hset(estado_clave, "fase", "confirmar_dni")
                    self.redis_client.hset(estado_clave, "dni", texto_usuario)
                    self.redis_client.hset(estado_clave, "nombre", nombre)
                    await update.message.reply_text(
                        f"👤 ¿Eres *{nombre}*?\n\n_Responde *sí* o *no* para confirmar_\n_O di *cancelar* para salir_",
                        parse_mode="Markdown"
                    )
                else:
                    usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(texto_usuario)
                    if usuario_db2:
                        nombre = usuario_db2.NOMBRE_COMPLETO.strip()
                        self.redis_client.hset(estado_clave, "fase", "confirmar_dni")
                        self.redis_client.hset(estado_clave, "dni", texto_usuario)
                        self.redis_client.hset(estado_clave, "nombre", nombre)
                        await update.message.reply_text(
                            f"👤 ¿Eres *{nombre}*?\n\n_Responde *sí* o *no* para confirmar_\n_O di *cancelar* para salir_",
                            parse_mode="Markdown"
                        )
                    else:
                        await update.message.reply_text(
                            "🔍 *No encontré a nadie con ese DNI*\n\n_Por favor, verifica el número e inténtalo de nuevo_\n_O di *cancelar* para salir_",
                            parse_mode="Markdown"
                        )

            elif estado["fase"] == "confirmar_dni":
                if texto_usuario not in ["sí", "si", "no"]:
                    await update.message.reply_text(
                        "ℹ️ _Por favor, responde solo *sí* o *no* para confirmar_\n\n_O di *cancelar* para salir_",
                        parse_mode="Markdown"
                    )
                    return
                if texto_usuario == "no":
                    self.redis_client.hset(estado_clave, "fase", "inicio")
                    await update.message.reply_text(
                        "ℹ️ *Entendido, el DNI no es correcto*\n\n_Dime otro cuando quieras o pregunta otra cosa_",
                        parse_mode="Markdown"
                    )
                    return
                dni = estado.get("dni")
                if estado.get("accion") == "reclamo":
                    self.redis_client.hset(estado_clave, "fase", "solicitar_descripcion")
                    await update.message.reply_text(
                        f"✅ *¡Gracias por confirmar, {estado.get('nombre')}!* \n\n"
                        f"_Cuéntame qué problema tienes para registrar tu reclamo_\n"
                        f"*(Debe estar relacionado con cortes de luz, energía eléctrica o daños por el servicio)*\n\n"
                        f"_O di *cancelar* para salir_",
                        parse_mode="Markdown"
                    )
                elif estado.get("accion") == "consultar":
                    self.redis_client.hset(estado_clave, "fase", "consultar_reclamos")
                    resultado, codigo = self.consulta_estado_service.ejecutar(dni)
                    if codigo == 200:
                        await update.message.reply_text(
                            f"✅ *Gracias, {estado.get('nombre')}*\n\n"
                            f"_Aquí están tus últimos 5 reclamos:_\n{self.format_reclamos(dni)}\n\n"
                            f"_Si quieres detalles de uno, dime su ID_\n_O di *cancelar* para salir_",
                            parse_mode="Markdown"
                        )
                    else:
                        await update.message.reply_text(
                            "🔍 *No encontré reclamos para tu DNI*\n\n_Verifica e intenta de nuevo_\n_O di *cancelar* para salir_",
                            parse_mode="Markdown"
                        )
                        self.redis_client.hset(estado_clave, "fase", "inicio")
                elif estado.get("accion") == "actualizar":
                    campo = estado.get("campo_actualizar")
                    usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(dni)
                    current_value = getattr(usuario_db2, campo) if usuario_db2 and hasattr(usuario_db2, campo) else "No disponible"
                    self.redis_client.hset(estado_clave, "fase", "confirmar_actualizacion")
                    await update.message.reply_text(
                        f"✅ *Tu {campo.lower()} actual es:*\n*{current_value}*\n\n"
                        f"_Dime el nuevo valor para actualizarlo_\n_O di *cancelar* para salir_",
                        parse_mode="Markdown"
                    )
                elif estado.get("accion") == "consultar_facturas":
                    resultado, status = self.consultar_facturas_service.ejecutar(dni)
                    if status == 200:
                        facturas = resultado.get("facturas", [])
                        logging.info(f"Facturas crudas recibidas: {facturas[:2]}")
                        if not facturas:
                            await update.message.reply_text(
                                "🔍 *No encontré facturas para tu DNI*\n\n_Verifica e intenta de nuevo_\n_O di *cancelar* para salir_",
                                parse_mode="Markdown"
                            )
                        else:
                            factura = facturas[0]
                            try:
                                fecha_emision = factura.get('FechaEmision', datetime.now())
                                if isinstance(fecha_emision, datetime):
                                    fecha_emision = fecha_emision.strftime('%d/%m/%Y')
                                vencimiento = factura.get('Vencimiento', datetime.now())
                                if isinstance(vencimiento, datetime):
                                    vencimiento = vencimiento.strftime('%d/%m/%Y')

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
                                await update.message.reply_text(mensaje, parse_mode="Markdown")
                            except Exception as e:
                                logging.error(f"Error al formatear la factura: {str(e)} - Datos: {factura}")
                                await update.message.reply_text(
                                    f"❌ *No pude mostrar tu factura*\n\n_Error:_ _{str(e)}_\n\n_Intenta de nuevo o di *cancelar* para salir_",
                                    parse_mode="Markdown"
                                )
                                self.redis_client.hset(estado_clave, "fase", "inicio")
                                return
                        self.redis_client.hset(estado_clave, "fase", "inicio")
                    else:
                        await update.message.reply_text(
                            "🔍 *No encontré tu factura*\n\n_Verifica el DNI e intenta de nuevo_\n_O di *cancelar* para salir_",
                            parse_mode="Markdown"
                        )
                        self.redis_client.hset(estado_clave, "fase", "inicio")

            elif estado["fase"] == "solicitar_descripcion":
                if len(texto_usuario.strip()) < 3:
                    await update.message.reply_text(
                        "ℹ️ *Necesito más detalles*\n\n_Describe el problema con al menos 3 caracteres_\n"
                        f"*(Relacionado con cortes de luz, energía eléctrica o daños por el servicio)*\n\n"
                        f"_O di *cancelar* para salir_",
                        parse_mode="Markdown"
                    )
                    return
                self.redis_client.hset(estado_clave, "fase", "validar_reclamo")
                self.redis_client.hset(estado_clave, "descripcion", texto_usuario)
                await self.handle_message(update, context)

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
                    await self.handle_message(update, context)
                else:
                    await update.message.reply_text(
                        f"❌ *No parece un reclamo válido*\n\n_{mensaje_validacion}_\n\n"
                        f"_Por favor, describe un problema relacionado con cortes de luz, energía eléctrica o daños por el servicio_\n"
                        f"_O di *cancelar* para salir_",
                        parse_mode="Markdown"
                    )
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
                        await update.message.reply_text(
                            f"✅ *Detalles del reclamo ID {id_reclamo}:*\n\n"
                            f"- *Descripción*: _{reclamo.get('DESCRIPCION', 'No disponible')}_\n"
                            f"- *Estado*: _{reclamo.get('ESTADO', 'No disponible')}_\n"
                            f"- *Fecha de Reclamo*: _{fecha_reclamo}_\n"
                            f"- *Cliente*: _{cliente.get('nombre', 'No disponible')} (DNI: {cliente.get('dni', 'No disponible')})_\n"
                            f"- *Dirección*: _{direccion}_",
                            parse_mode="Markdown"
                        )
                        self.redis_client.hset(estado_clave, "fase", "inicio")
                    else:
                        await update.message.reply_text(
                            "🔍 *No encontré ese reclamo*\n\n_Intenta con otro ID_\n_O di *cancelar* para salir_",
                            parse_mode="Markdown"
                        )
                else:
                    await update.message.reply_text(
                        "ℹ️ *Por favor, dame un ID de reclamo*\n\n_(Solo números)_\n_O di *cancelar* para salir_",
                        parse_mode="Markdown"
                    )

            elif estado["fase"] == "confirmar_actualizacion":
                self.redis_client.hset(estado_clave, "fase", "ejecutar_accion")
                self.redis_client.hset(estado_clave, "valor_actualizar", texto_usuario)
                await self.handle_message(update, context)

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
                        respuesta = (
                            f"✅ *¡Listo, {nombre}!* Tu reclamo está registrado\n\n"
                            f"*ID*: _{reclamo_id}_\n"
                            f"*Estado*: _Pendiente_\n"
                            f"*Resumen*: _{descripcion}_\n\n"
                            f"_¿En qué más puedo ayudarte?_"
                        )
                    else:
                        respuesta = "❌ *Lo siento, no pude registrar tu reclamo*\n\n_¿Intentamos de nuevo?_"
                elif accion == "actualizar":
                    campo = estado.get("campo_actualizar")
                    resultado, status = self.actualizar_service.ejecutar(dni, {campo: valor_actualizar})
                    if status == 200:
                        usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(dni)
                        usuario_db1 = self.actualizar_service.usuario_repository.obtener_de_db1(dni) if not usuario_db2 else None
                        if usuario_db2:
                            respuesta = (
                                f"✅ *¡Actualización exitosa, {nombre}!*\n\n"
                                f"✔️ *Datos actualizados:*\n"
                                f"📛 *Nombre*: _{usuario_db2.NOMBRE_COMPLETO}_\n"
                                f"📍 *Calle*: _{usuario_db2.CALLE}_\n"
                                f"🏘️ *Barrio*: _{usuario_db2.BARRIO}_\n"
                                f"📱 *Teléfono*: _{usuario_db2.CELULAR}_\n"
                                f"✉️ *Correo*: _{usuario_db2.EMAIL}_\n\n"
                                f"_¿En qué más puedo ayudarte?_"
                            )
                        elif usuario_db1:
                            respuesta = (
                                f"✅ *¡Actualización exitosa, {nombre}!*\n\n"
                                f"✔️ *Datos actualizados:*\n"
                                f"📛 *Nombre*: _{usuario_db1[0]['Apellido']} {usuario_db1[0]['Nombre']}_\n"
                                f"📍 *Calle*: _{usuario_db1[0].get('Calle', 'No disponible')}_\n"
                                f"🏘️ *Barrio*: _{usuario_db1[0].get('Barrio', 'No disponible')}_\n"
                                f"📱 *Teléfono*: _{usuario_db1[0].get('Telefono', 'No disponible')}_\n"
                                f"✉️ *Correo*: _{usuario_db1[0].get('Email', 'No disponible')}_\n\n"
                                f"_¿En qué más puedo ayudarte?_"
                            )
                        else:
                            respuesta = (
                                "✅ *Actualización exitosa*\n\n"
                                f"_No pude recuperar tus datos actualizados_\n\n"
                                f"_¿En qué más puedo ayudarte?_"
                            )
                    else:
                        respuesta = "❌ *No pude actualizar eso ahora*\n\n_¿Probamos otra vez?_"
                else:
                    respuesta = "❓ *Algo salió mal*\n\n_¿Cómo puedo ayudarte ahora?_"

                await update.message.reply_text(respuesta, parse_mode="Markdown")
                await update.message.reply_text(
                    "ℹ️ *¿En qué más puedo ayudarte?*\n\n_Puedo asistirte con:_\n- *Reclamos*\n- *Datos*\n- *Consultas*\n- *Facturas*",
                    parse_mode="Markdown"
                )
                self.redis_client.hset(estado_clave, "fase", "inicio")
                self.redis_client.hdel(estado_clave, "descripcion")
                self.redis_client.hdel(estado_clave, "valor_actualizar")

        except Exception as e:
            logging.error(f"Error en handle_message: {str(e)}")
            await update.message.reply_text(
                f"❌ *Uy, algo falló*\n\n_Error:_ _{str(e)}_\n\n_Intentemos de nuevo o di *cancelar* para salir_",
                parse_mode="Markdown"
            )
            self.redis_client.hset(estado_clave, "fase", "inicio")

    def run(self):
        logging.info("🚀 Bot de Telegram (ChatGPT) corriendo...")
        self.app.run_polling()

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