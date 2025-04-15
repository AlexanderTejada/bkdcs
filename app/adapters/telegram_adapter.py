# app/adapters/telegram_adapter.py
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from app.services.registrar_reclamo_service import RegistrarReclamoService
from app.services.actualizar_usuario_service import ActualizarUsuarioService
from app.services.consultar_estado_reclamo_service import ConsultarEstadoReclamoService
from app.services.consultar_reclamo_service import ConsultarReclamoService
from app.services.detectar_intencion_service import DetectarIntencionService
import re
import logging
import json
from app.config.database import get_db1, get_db2
from app.repositories.sqlalchemy_usuario_repository import SQLAlchemyUsuarioRepository
from app.repositories.sqlalchemy_reclamo_repository import SQLAlchemyReclamoRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TelegramAdapter:
    def __init__(self, token, detectar_intencion_service: DetectarIntencionService,
                 reclamo_service: RegistrarReclamoService, actualizar_service: ActualizarUsuarioService,
                 consulta_estado_service: ConsultarEstadoReclamoService,
                 consulta_reclamo_service: ConsultarReclamoService,
                 redis_client, app):
        self.token = token
        self.detectar_intencion_service = detectar_intencion_service
        session_db1 = get_db1()
        session_db2 = get_db2()
        self.reclamo_service = reclamo_service if reclamo_service else RegistrarReclamoService(
            SQLAlchemyReclamoRepository(session_db2),
            SQLAlchemyUsuarioRepository(session_db1, session_db2)
        )
        self.actualizar_service = actualizar_service if actualizar_service else ActualizarUsuarioService(
            SQLAlchemyUsuarioRepository(session_db1, session_db2)
        )
        self.consulta_estado_service = consulta_estado_service if consulta_estado_service else ConsultarEstadoReclamoService(
            SQLAlchemyReclamoRepository(session_db2),
            SQLAlchemyUsuarioRepository(session_db1, session_db2)
        )
        self.consulta_reclamo_service = consulta_reclamo_service if consulta_reclamo_service else ConsultarReclamoService(
            SQLAlchemyReclamoRepository(session_db2)
        )
        self.redis_client = redis_client
        self.app = ApplicationBuilder().token(self.token).build()
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
            "¡Bienvenido! Soy DECSA, tu asistente virtual oficial, diseñado para brindarte soporte en todo momento. Estoy aquí para ayudarte con nuestros servicios eléctricos y otras responsabilidades. ¿En qué te gustaría que te ayude hoy?"
        )

    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        self.redis_client.delete(f"user:{user_id}:historial")
        self.redis_client.delete(f"user:{user_id}:estado")
        await update.message.reply_text(
            "Memoria de la conversación reiniciada. ¿En qué puedo ayudarte ahora? Te sugiero hacer un reclamo, actualizar datos o consultar el estado de un reclamo.")

    def preprocess_text(self, text):
        """Preprocesa el texto para corregir errores ortográficos comunes usando regex."""
        logging.info(f"Preprocesando texto original: {text}")
        text = text.lower()
        text = re.sub(r'\bk\w*',
                      lambda m: m.group(0).replace('k', 'qu') if 'k' in m.group(0) and 'qu' in m.group(0).replace('k',
                                                                                                                  'qu') else m.group(
                          0).replace('k', 'c'), text)
        text = re.sub(r'\bz\w*',
                      lambda m: m.group(0).replace('z', 's') if 'z' in m.group(0) and len(m.group(0)) > 1 else m.group(
                          0), text)
        text = re.sub(r'\bx\w*',
                      lambda m: m.group(0).replace('x', 's') if 'x' in m.group(0) and len(m.group(0)) > 1 else m.group(
                          0).replace('x', 'j'), text)
        text = re.sub(r'\b(k|q)uier[oa]|kere\b', 'quiero', text)
        text = re.sub(r'\b(ak|ac)tua(l|ll)?(l|ll)?iz(ar|er)|aktuali[zs]ar\b', 'actualizar', text)
        text = re.sub(r'\b(rek|rec|rel)al[mo]|reclamoo?\b', 'reclamo', text)
        text = re.sub(r'\b(kom|con|kol)sul(tar|tar)|consul[dt]ar\b', 'consultar', text)
        text = re.sub(r'\b(ha|as)cer|aser\b', 'hacer', text)
        text = re.sub(r'\b(direk|dier|dir)ec(c|k)ion|direcsion\b', 'direccion', text)
        text = re.sub(r'\b(est|es)tadoo?\b', 'estado', text)
        text = re.sub(r'(\w*?)([aeiou])\2(\w*)', r'\1\2\3', text)
        text = re.sub(r'(\w)r(\w)e', r'\1er\2', text)
        logging.info(f"Texto preprocesado: {text}")
        return text

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = str(update.effective_user.id)
            texto_usuario = update.message.text.strip().lower()
            texto_preprocesado = self.preprocess_text(texto_usuario)

            historial_clave = f"user:{user_id}:historial"
            estado_clave = f"user:{user_id}:estado"

            self.redis_client.rpush(historial_clave, f"Usuario: {texto_usuario}")
            historial = " | ".join(self.redis_client.lrange(historial_clave, -5, -1) or [])
            logging.info(f"Historial actual: {historial}")

            estado = self.redis_client.hgetall(estado_clave) or {"fase": "inicio"}
            logging.info(f"Estado actual: {estado}")

            if texto_usuario == "cancelar":
                self.redis_client.hset(estado_clave, "fase", "inicio")
                self.redis_client.hdel(estado_clave, "dni")
                self.redis_client.hdel(estado_clave, "accion")
                self.redis_client.hdel(estado_clave, "nombre")
                self.redis_client.hdel(estado_clave, "campo_actualizar")
                self.redis_client.hdel(estado_clave, "descripcion")
                await update.message.reply_text(
                    "✅ Proceso cancelado. ¿En qué puedo ayudarte ahora? Si necesitas asistencia, puedo ayudarte a hacer un reclamo, actualizar datos o consultar el estado de un reclamo."
                )
                logging.info("Proceso cancelado")
                return

            if estado["fase"] == "inicio":
                logging.info("Entrando en fase inicio")
                respuesta_cruda = self.detectar_intencion_service.ejecutar_con_historial(texto_preprocesado, historial)
                try:
                    resultado = json.loads(respuesta_cruda)
                    intencion = resultado.get("intencion", "Conversar")
                    respuesta = resultado.get("respuesta",
                                              "No entendí, ¿en qué puedo ayudarte? Si necesitas asistencia, puedo ayudarte a hacer un reclamo, actualizar datos o consultar el estado de un reclamo.")
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Error al parsear respuesta: {respuesta_cruda}, Error: {str(e)}")
                    intencion = "Conversar"
                    respuesta = "No entendí, ¿en qué puedo ayudarte? Si necesitas asistencia, puedo ayudarte a hacer un reclamo, actualizar datos o consultar el estado de un reclamo."

                logging.info(f"Intención detectada: {intencion}, Respuesta: {respuesta}")

                if intencion == "Reclamo":
                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "reclamo")
                    await update.message.reply_text("Perfecto, para realizar un reclamo, por favor dime tu DNI.")
                elif intencion == "Actualizar":
                    if "calle" in texto_preprocesado:
                        campo_actualizar = "CALLE"
                        mensaje = "¡Perfecto! Por favor, dame tu DNI para actualizar tu calle."
                    elif "barrio" in texto_preprocesado:
                        campo_actualizar = "BARRIO"
                        mensaje = "¡Perfecto! Por favor, dame tu DNI para actualizar tu barrio."
                    elif "celular" in texto_preprocesado or "teléfono" in texto_preprocesado:
                        campo_actualizar = "CELULAR"
                        mensaje = "¡Perfecto! Por favor, dame tu DNI para actualizar tu celular."
                    elif "correo" in texto_preprocesado or "mail" in texto_preprocesado:
                        campo_actualizar = "EMAIL"
                        mensaje = "¡Perfecto! Por favor, dame tu DNI para actualizar tu correo electrónico."
                    else:
                        self.redis_client.hset(estado_clave, "fase", "seleccionar_dato")
                        await update.message.reply_text(
                            "¿Qué dato deseas actualizar? Puedes elegir entre:\n📍 Calle\n🏘️ Barrio\n📱 Celular\n✉️ Correo electrónico\n\nPor favor, escribe el dato que deseas actualizar o escribe 'cancelar' para salir.")
                        return

                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "actualizar")
                    self.redis_client.hset(estado_clave, "campo_actualizar", campo_actualizar)
                    await update.message.reply_text(mensaje)
                elif intencion == "Consultar":
                    self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                    self.redis_client.hset(estado_clave, "accion", "consultar")
                    await update.message.reply_text(
                        "¡Perfecto! Para consultar el estado de tus reclamos, por favor dime tu DNI.")
                else:  # Conversar
                    await update.message.reply_text(respuesta)

            elif estado["fase"] == "seleccionar_dato":
                logging.info("Entrando en fase seleccionar_dato")
                opciones_validas = {
                    "calle": "CALLE",
                    "barrio": "BARRIO",
                    "celular": "CELULAR",
                    "teléfono": "CELULAR",
                    "correo": "EMAIL",
                    "mail": "EMAIL"
                }

                if texto_usuario not in opciones_validas:
                    await update.message.reply_text(
                        "⚠️ Opción no válida. Por favor, escribe 'calle', 'barrio', 'celular' o 'correo'. O escribe 'cancelar' para salir.")
                    return

                campo_actualizar = opciones_validas[texto_usuario]
                self.redis_client.hset(estado_clave, "fase", "pedir_dni")
                self.redis_client.hset(estado_clave, "accion", "actualizar")
                self.redis_client.hset(estado_clave, "campo_actualizar", campo_actualizar)
                await update.message.reply_text(f"Perfecto, por favor dame tu DNI para actualizar tu {texto_usuario}.")

            elif estado["fase"] == "pedir_dni":
                logging.info("Entrando en fase pedir_dni")
                if not re.match(r'^\d{7,8}$', texto_usuario):
                    await update.message.reply_text(
                        "⚠️ El DNI ingresado no es válido. Ingresa solo números (7 u 8 dígitos), o escribe 'cancelar' para salir.")
                    return

                logging.info(f"Buscando usuario con DNI: {texto_usuario} en DECSA_DB1")
                usuario_db1 = self.actualizar_service.usuario_repository.obtener_de_db1(texto_usuario)
                if usuario_db1:
                    nombre = f"{usuario_db1[0]['Apellido'].strip()} {usuario_db1[0]['Nombre'].strip()}"
                    logging.info(f"Usuario encontrado en DECSA_DB1: {nombre}")
                    self.redis_client.hset(estado_clave, "fase", "confirmar_dni")
                    self.redis_client.hset(estado_clave, "dni", texto_usuario)
                    self.redis_client.hset(estado_clave, "nombre", nombre)
                    await update.message.reply_text(
                        f"¿Eres {nombre}? Por favor, confirma con 'sí' o 'no', o escribe 'cancelar' para salir.")
                else:
                    logging.info(f"Buscando usuario con DNI: {texto_usuario} en DECSA_DB2")
                    usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(texto_usuario)
                    if usuario_db2:
                        logging.info(f"Usuario encontrado en DECSA_DB2: {usuario_db2.NOMBRE_COMPLETO}")
                        nombre = usuario_db2.NOMBRE_COMPLETO.strip()
                        self.redis_client.hset(estado_clave, "fase", "confirmar_dni")
                        self.redis_client.hset(estado_clave, "dni", texto_usuario)
                        self.redis_client.hset(estado_clave, "nombre", nombre)
                        await update.message.reply_text(
                            f"¿Eres {nombre}? Por favor, confirma con 'sí' o 'no', o escribe 'cancelar' para salir.")
                    else:
                        logging.info(f"Usuario con DNI {texto_usuario} no encontrado en ninguna base")
                        await update.message.reply_text(
                            "No encontré un usuario con ese DNI. Verifica e intenta de nuevo.")
                        self.redis_client.hset(estado_clave, "fase", "inicio")

            elif estado["fase"] == "confirmar_dni":
                logging.info("Entrando en fase confirmar_dni")
                if texto_usuario not in ["sí", "si", "no"]:
                    await update.message.reply_text(
                        "Por favor, responde 'sí' o 'no' para confirmar tu identidad, o escribe 'cancelar' para salir.")
                    return
                if texto_usuario == "no":
                    self.redis_client.hset(estado_clave, "fase", "inicio")
                    await update.message.reply_text("Entendido. Por favor, ingresa un DNI correcto para continuar.")
                    return

                dni = estado.get("dni")
                if estado.get("accion") == "consultar":
                    self.redis_client.hset(estado_clave, "fase", "consultar_reclamos")
                    await update.message.reply_text(
                        f"Gracias por confirmar, {estado.get('nombre')}. Aquí están tus últimos 5 reclamos:\n{self.format_reclamos(dni)}\nSi quieres ver un reclamo específico, dime su ID (o escribe 'cancelar' para salir)."
                    )
                elif estado.get("accion") == "reclamo":
                    self.redis_client.hset(estado_clave, "fase", "solicitar_descripcion")
                    await update.message.reply_text(
                        f"Gracias por confirmar, {estado.get('nombre')}. Por favor, describe el problema o detalle de tu reclamo (o escribe 'cancelar' para salir)."
                    )
                else:  # Para "actualizar"
                    dni = estado.get("dni")
                    campo = estado.get("campo_actualizar")

                    usuario_db2 = self.actualizar_service.usuario_repository.obtener_por_dni(dni)
                    usuario_db1 = self.actualizar_service.usuario_repository.obtener_de_db1(
                        dni) if not usuario_db2 else None

                    current_value = "No disponible"
                    if usuario_db2 and hasattr(usuario_db2, campo):
                        current_value = getattr(usuario_db2, campo) or "No disponible"
                    elif usuario_db1 and campo in usuario_db1[0]:
                        current_value = usuario_db1[0][campo] or "No disponible"

                    self.redis_client.hset(estado_clave, "fase", "confirmar_actualizacion")
                    await update.message.reply_text(
                        f"Tu {campo.lower()} actual es: *{current_value}*. Por favor, dime el nuevo {campo.lower()} que deseas registrar o escribe 'cancelar' para cancelar el proceso."
                    )

            elif estado["fase"] == "consultar_reclamos":
                logging.info("Entrando en fase consultar_reclamos")
                if re.match(r'^\d+$', texto_usuario):
                    id_reclamo = int(texto_usuario)
                    respuesta, codigo = self.consulta_reclamo_service.ejecutar(id_reclamo)
                    if codigo == 200:
                        await update.message.reply_text(
                            f"Detalles del reclamo ID {id_reclamo}:\n"
                            f"- Descripción: {respuesta['reclamo'].get('DESCRIPCION', 'No disponible')}\n"
                            f"- Estado: {respuesta['reclamo'].get('ESTADO', 'No disponible')}\n"
                            f"- Fecha de Reclamo: {respuesta['reclamo'].get('FECHA_RECLAMO', 'No disponible')}\n"
                            f"- Fecha de Cierre: {respuesta['reclamo'].get('FECHA_CIERRE', 'No disponible')}\n"
                            f"- Cliente: {respuesta['cliente'].get('nombre', 'No disponible')} (DNI: {respuesta['cliente'].get('dni', 'No disponible')})\n"
                            f"- Número de Suministro: {respuesta['cliente'].get('codigo_suministro', 'No disponible')}\n"
                            f"- Número de Medidor: {respuesta['cliente'].get('numero_medidor', 'No disponible')}\n"
                            f"- Dirección: {respuesta['cliente'].get('direccion', 'No disponible')}"
                        )
                    else:
                        await update.message.reply_text(f"Error: {respuesta.get('error', 'Reclamo no encontrado')}")
                else:
                    await update.message.reply_text(
                        "Por favor, ingresa un ID de reclamo válido (un número) o escribe 'cancelar' para salir."
                    )

            elif estado["fase"] == "solicitar_descripcion":
                logging.info("Entrando en fase solicitar_descripcion")
                if not texto_usuario or len(texto_usuario.strip()) < 3:
                    await update.message.reply_text(
                        "⚠️ Por favor, proporciona una descripción válida con al menos 3 caracteres, o escribe 'cancelar' para salir."
                    )
                    return

                self.redis_client.hset(estado_clave, "fase", "ejecutar_accion")
                self.redis_client.hset(estado_clave, "descripcion", texto_usuario)
                await self.handle_message(update, context)

            elif estado["fase"] == "confirmar_actualizacion":
                logging.info("Entrando en fase confirmar_actualizacion")
                self.redis_client.hset(estado_clave, "fase", "ejecutar_accion")
                self.redis_client.hset(estado_clave, "valor_actualizar", texto_usuario)
                await self.handle_message(update, context)

            elif estado["fase"] == "ejecutar_accion":
                logging.info("Entrando en fase ejecutar_accion")
                dni = estado.get("dni")
                accion = estado.get("accion")
                nombre = estado.get("nombre")
                descripcion = estado.get("descripcion", "")
                valor_actualizar = estado.get("valor_actualizar", "")

                try:
                    if accion == "reclamo":
                        if not descripcion:
                            await update.message.reply_text(
                                "⚠️ No se proporcionó una descripción. Por favor, describe el problema (o escribe 'cancelar' para salir)."
                            )
                            self.redis_client.hset(estado_clave, "fase", "solicitar_descripcion")
                            return
                        resultado, status = self.reclamo_service.ejecutar(dni, descripcion)
                        if status == 201:
                            reclamo_id = resultado["id_reclamo"]
                            respuesta = f"Tu reclamo ha sido registrado exitosamente. ID del reclamo: {reclamo_id}, Estado: Pendiente.\n\nResumen: Has reportado el siguiente problema: {descripcion}"
                        else:
                            respuesta = resultado.get("error",
                                                      "Lo siento, no pude registrar tu reclamo en este momento.")
                    elif accion == "actualizar":
                        if not valor_actualizar or valor_actualizar in ["la mosca", "cancelar"]:
                            await update.message.reply_text(
                                "Por favor, proporciona un valor válido (ej. 'Calle 123' para calle), o escribe 'cancelar' para cancelar el proceso.")
                            return
                        campo = estado.get("campo_actualizar")
                        resultado, status = self.actualizar_service.ejecutar(dni, {campo: valor_actualizar})
                        if status == 200:
                            usuario = self.actualizar_service.usuario_repository.obtener_por_dni(
                                dni) or self.actualizar_service.usuario_repository.obtener_de_db1(dni)
                            respuesta = (f"✅ ¡Actualización exitosa!\n\n✔️ Datos actualizados:\n"
                                         f"📛 Nombre: {usuario.NOMBRE_COMPLETO}\n"
                                         f"🔢 N° Suministro: {usuario.CODIGO_SUMINISTRO}\n"
                                         f"🔍 N° Medidor: {usuario.NUMERO_MEDIDOR}\n"
                                         f"📱 Teléfono: {usuario.CELULAR}\n"
                                         f"✉️ Correo: {usuario.EMAIL}\n"
                                         f"📍 Calle: {usuario.CALLE}\n"
                                         f"🏘️ Barrio: {usuario.BARRIO}\n"
                                         f"\nResumen: Has actualizado tu {campo.lower()} a '{valor_actualizar}'.")
                        else:
                            respuesta = resultado.get("error",
                                                      "Lo siento, no pude actualizar tus datos en este momento.")
                    else:
                        respuesta = "Acción no válida"

                    self.redis_client.rpush(historial_clave, f"Bot: {respuesta}")
                    await update.message.reply_text(respuesta)
                    await update.message.reply_text(
                        "¿Hay algo más en lo que pueda asistirte? Te sugiero hacer un reclamo o consultar el estado de un reclamo.")
                    self.redis_client.hset(estado_clave, "fase", "inicio")
                    self.redis_client.hdel(estado_clave, "descripcion")
                    self.redis_client.hdel(estado_clave, "valor_actualizar")

                except Exception as e:
                    logging.error(f"Error en ejecutar_accion: {str(e)}")
                    await update.message.reply_text(
                        f"❌ Ocurrió un error al procesar tu solicitud: {str(e)}. Por favor, intenta de nuevo o escribe 'cancelar' para reiniciar.")
                    self.redis_client.hset(estado_clave, "fase", "inicio")

        except Exception as e:
            logging.error(f"Error en handle_message: {str(e)}")
            await update.message.reply_text(
                f"Lo siento, ocurrió un error: {str(e)}. Por favor, intenta de nuevo o escribe 'cancelar' para reiniciar.")
            self.redis_client.hset(estado_clave, "fase", "inicio")

    def run(self):
        logging.info("🚀 Bot de Telegram corriendo...")
        self.app.run_polling()

    def format_reclamos(self, reclamo_data=None, is_single=False):
        """Formatea una lista o un reclamo individual de manera legible."""
        if is_single and reclamo_data:
            return (
                f"Detalles del reclamo ID {reclamo_data['reclamo'].get('ID_RECLAMO', 'No disponible')}:\n"
                f"- Descripción: {reclamo_data['reclamo'].get('DESCRIPCION', 'No disponible')}\n"
                f"- Estado: {reclamo_data['reclamo'].get('ESTADO', 'No disponible')}\n"
                f"- Fecha de Reclamo: {reclamo_data['reclamo'].get('FECHA_RECLAMO', 'No disponible')}\n"
                f"- Fecha de Cierre: {reclamo_data['reclamo'].get('FECHA_CIERRE', 'No disponible')}\n"
                f"- Cliente: {reclamo_data['cliente'].get('nombre', 'No disponible')} (DNI: {reclamo_data['cliente'].get('dni', 'No disponible')})\n"
                f"- Número de Suministro: {reclamo_data['cliente'].get('codigo_suministro', 'No disponible')}\n"
                f"- Número de Medidor: {reclamo_data['cliente'].get('numero_medidor', 'No disponible')}\n"
                f"- Dirección: {reclamo_data['cliente'].get('direccion', 'No disponible')}"
            )
        else:
            respuesta, codigo = self.consulta_estado_service.ejecutar(reclamo_data) if reclamo_data else (None, 404)
            if codigo == 200 and "reclamos" in respuesta:
                reclamos = respuesta["reclamos"][:5]
                if not reclamos:
                    return "No tienes reclamos registrados recientemente."
                return "\n".join([
                                     f"ID: {r['ID_RECLAMO']}, Estado: {r['ESTADO']}, Descripción: {r['DESCRIPCION'][:50]}{'...' if len(r['DESCRIPCION']) > 50 else ''}"
                                     for r in reclamos])
            return "No pude obtener tus reclamos. Intenta de nuevo."