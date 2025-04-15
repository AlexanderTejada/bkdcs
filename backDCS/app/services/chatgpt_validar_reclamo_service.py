# app/services/chatgpt_validar_reclamo_service.py
import logging
import time
import json
import re
from openai import OpenAI
from app.config.config import Config
from app.services.redis_client import RedisClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ChatGPTValidarReclamoService:
    def __init__(self, redis_client: RedisClient = None):
        self.client = OpenAI(api_key=Config.CHATGPT_API_KEY)
        self.redis_client = redis_client
        logging.info("ChatGPTValidarReclamoService inicializado con API Key configurada.")

    def validar_reclamo(self, descripcion, historial=""):
        try:
            if self.redis_client:
                cache_key = f"chatgpt_validar:v1:{hash(descripcion + historial)}"
                cached_response = self.redis_client.get(cache_key)
                if cached_response:
                    logging.info(f"Respuesta obtenida del caché: {cached_response}")
                    return cached_response.decode('utf-8')

            full_prompt = f"""
            Analiza esta descripción de un reclamo: '{descripcion}'. 
            Determina si está relacionada con temas de una distribuidora eléctrica, como cortes de luz, apagones, problemas con la energía eléctrica, facturación errónea, o daños a electrodomésticos por fallos en el suministro, y si describe un problema real que el usuario está reportando. 
            Sé flexible y considera sinónimos como 'apagón' para corte de luz, pero rechaza preguntas hipotéticas o frases que no afirmen un problema concreto (por ejemplo, 'qué pasa si...'). 
            Devuelve una respuesta en formato JSON con los campos 'es_valido' (true/false) y 'mensaje' (explicación breve y amigable). 
            Ejemplos válidos: 'Hubo un apagón en todo el barrio', 'Se cortó la luz 3 horas', 'Me llegó una factura mal', 'Se me quemó la heladera por un pico de tensión'. 
            Ejemplos no válidos: 'Mi perro se escapó', 'Necesito un delivery', 'Qué pasa si le dices que un camión cortó los cables'. 
            Si no es válido y es una pregunta hipotética como 'qué pasa si...', responde con un tono cálido explicando que no es un reclamo y ofrece una breve respuesta a la pregunta, por ejemplo: 'Eso suena más como una consulta que un reclamo. Si un camión cortó los cables, podrías reportarlo como un problema real diciendo algo como "Un camión cortó los cables y me quedé sin luz". ¿Quieres registrar algo así?' 
            Asegúrate de responder siempre en formato JSON válido y no encierres la respuesta en bloques de código como ```json```.
            """

            start_time = time.time()

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Sos un asistente que responde en JSON."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.4,
                max_tokens=200
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
                texto_respuesta = '{"es_valido": false, "mensaje": "No pude validar el reclamo debido a un problema técnico."}'

            if self.redis_client:
                self.redis_client.setex(cache_key, 3600, texto_respuesta)
                logging.info(f"Respuesta guardada en caché: {cache_key}")

            return texto_respuesta

        except Exception as e:
            logging.error(f"Error con gpt-4o-mini: {str(e)}")
            return '{"es_valido": false, "mensaje": "Ups, algo falló al validar el reclamo."}'