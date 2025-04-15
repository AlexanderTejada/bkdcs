# app/services/chatgpt_service.py
import logging
import time
import json
import re
from openai import OpenAI
from app.config.config import Config
from app.services.redis_client import RedisClient  # Ajustamos la importación

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ChatGPTService:
    def __init__(self, redis_client: RedisClient = None):
        self.client = OpenAI(api_key=Config.CHATGPT_API_KEY)
        self.redis_client = redis_client
        logging.info("ChatGPTService inicializado con API Key configurada.")

    def generar_respuesta(self, prompt, historial=""):
        try:
            if self.redis_client:
                cache_key = f"chatgpt:v1:{hash(prompt + historial)}"
                cached_response = self.redis_client.get(cache_key)
                if cached_response:
                    logging.info(f"Respuesta obtenida del caché: {cached_response}")
                    return cached_response.decode('utf-8')

            full_prompt = f"""
            Eres DECSA, un asistente virtual oficial de Distribuidora Eléctrica de Caucete S.A. (DECSA). Tu función es ayudar a los usuarios con:
            1) Hacer reclamos sobre servicios eléctricos.
            2) Actualizar datos personales.
            3) Consultar el estado de un reclamo.
            4) Consultar facturas.

            Normas:
            - En el primer mensaje, preséntate como DECSA.
            - No repitas la presentación si ya hubo diálogo.
            - Sé cálido, directo, empático.
            - Detecta la intención: Reclamo, Actualizar, Consultar, ConsultarFacturas, Conversar.
            - Si la intención es "Actualizar", pide especificar entre: calle, barrio, celular o correo.
            - Reclamos, Consultas y Facturas deben pedir el DNI.
            - No encierres la respuesta en bloques de código como ```json```.
            - Devuelve solo un objeto JSON.

            Historial reciente:
            {historial}

            Mensaje actual: "{prompt}"

            Responde en formato JSON con:
            - "intencion": "Reclamo", "Actualizar", "Consultar", "ConsultarFacturas" o "Conversar".
            - "respuesta": Texto cálido y claro con una instrucción para avanzar.
            """

            start_time = time.time()

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Sos un asistente que responde en JSON."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.4,
                max_tokens=500
            )

            texto_respuesta = response.choices[0].message.content.strip()
            logging.info(f"Tiempo de respuesta: {time.time() - start_time:.2f} segundos")
            logging.info(f"Respuesta de ChatGPT: {texto_respuesta}")

            # Limpieza de bloques ```json ... ``` si aparecen
            match = re.match(r"```(?:json)?\s*(\{.*\})\s*```", texto_respuesta, re.DOTALL)
            if match:
                texto_respuesta = match.group(1).strip()

            # Validación de formato JSON
            try:
                json.loads(texto_respuesta)
            except json.JSONDecodeError:
                logging.warning(f"Respuesta no es JSON válido: {texto_respuesta}")
                texto_respuesta = '{"intencion": "Conversar", "respuesta": "No entendí bien. ¿En qué te ayudo? Decime si querés un reclamo, actualizar datos, consultar algo o ver tu factura."}'

            if self.redis_client:
                self.redis_client.setex(cache_key, 3600, texto_respuesta)
                logging.info(f"Respuesta guardada en caché: {cache_key}")

            return texto_respuesta

        except Exception as e:
            logging.error(f"Error con gpt-4o-mini: {str(e)}")
            return '{"intencion": "Conversar", "respuesta": "Ups, algo falló. ¿En qué te ayudo?"}'

    def detectar_intencion(self, mensaje, historial=""):
        logging.info(f"Enviando a ChatGPT: '{mensaje}'")
        return self.generar_respuesta(mensaje, historial)