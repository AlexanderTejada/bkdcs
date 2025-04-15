import logging
import time
import json
import re
from openai import OpenAI
from app.config.config import Config
from app.services.redis_client import RedisClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ChatGPTFrontendService:
    def __init__(self, redis_client: RedisClient = None):
        self.client = OpenAI(api_key=Config.CHATGPT_API_KEY)
        self.redis_client = redis_client
        logging.info("ChatGPTFrontendService inicializado con API Key configurada.")

    def generar_respuesta(self, prompt, historial=""):
        try:
            prompt_lower = prompt.lower().strip()

            if self.redis_client:
                cache_key = f"chatgpt_frontend:v7:{hash(prompt_lower + historial)}"
                cached_response = self.redis_client.get(cache_key)
                if cached_response:
                    logging.info("Respuesta obtenida del caché.")
                    return json.loads(cached_response.decode('utf-8'))

            # === UBICACIÓN ===
            if any(p in prompt_lower for p in ["ubicación", "dónde están", "donde estan", "dirección", "cómo llegar"]):
                respuesta_final = (
                    "Estamos ubicados aquí:<br>"
                    '<div style="max-width: 100%; overflow: hidden;">'
                    '<iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3396.4549832678567!2d-68.2861766234939!3d-31.64876977415544!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x96810ef84ae0d12b%3A0x46e87234c4e6827f!2sDISTRIBUIDORA%20EL%C3%89CTRICA%20DE%20CAUCETE%20S.A.!5e0!3m2!1ses!2sar!4v1744301180879!5m2!1ses!2sar" width="100%" height="180" style="border:0; border-radius: 0.5rem; margin-top: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>'
                    '</div>'
                )

            # === TELÉFONOS ===
            elif any(p in prompt_lower for p in [
                "teléfono", "teléfonos", "número", "números", "llamar", "contacto",
                "soporte", "emergencia", "técnico", "servicio técnico", "a quién tengo que llamar"
            ]):
                respuesta_final = (
                    "Nuestros teléfonos de atención las 24 hs son:<br>"
                    '- <a href="tel:4255832">425-5832</a><br>'
                    '- <a href="tel:4255831">425-5831</a><br>'
                    '- <a href="tel:4961784">496-1784</a><br>'
                    '- <a href="tel:4962512">496-2512</a><br>'
                    '- <a href="tel:08006668456">0800-666-8456</a><br><br>'
                    "Para cortes de luz, emergencias o riesgos a la seguridad pública."
                )

            # === HORARIOS ===
            elif any(p in prompt_lower for p in ["horarios", "hora", "abren", "cierran", "atención", "trabajan"]):
                respuesta_final = (
                    "Nuestros horarios de atención son:<br>"
                    "- Lunes a Miércoles: 7:00 a 14:00<br>"
                    "- Jueves: 7:00 a 14:00 (cierre temprano)<br>"
                    "- Viernes: 7:00 a 14:00<br>"
                    "- Sábado y Domingo: cerrado"
                )

            # === FACTURAS ===
            elif any(p in prompt_lower for p in ["factura", "facturas", "pagar", "pago", "cómo pagar", "como pago"]):
                respuesta_final = (
                    'Podés pagar tu factura aquí:<br>'
                    '<a href="https://www.cooponlineweb.com.ar/DECSACAUCETE/Login" target="_blank">Ir al portal de pago</a><br><br>'
                    'Y si necesitás ayuda, consultá el instructivo:<br>'
                    '<a href="https://decsacaucete.com.ar/index.php/instructivo-pago-facturas-online/" target="_blank">Ver instructivo</a>'
                )

            # === RECLAMOS (EXPLÍCITOS O IMPLÍCITOS) ===
            elif any(p in prompt_lower for p in [
                "reclamo", "reclamar", "queja", "problema", "fallo", "error",
                "sin luz", "sin energía", "se me quemó", "me cortaron", "no tengo luz", "basura", "desastre", "arruinó", "defecto"
            ]):
                full_prompt = f"""
                Eres DECSA, un asistente virtual de atención al cliente.

                Un usuario está manifestando una situación problemática.
                No puedes solucionar el problema directamente, pero debes responder con empatía, cortesía y precisión.

                Instrucciones:
                - Muestra comprensión.
                - Indica que puede registrar su reclamo en la sección de reclamos de la web.
                - Menciona que también puede consultar el estado de su reclamo allí mismo si ya lo hizo.
                - No inventes teléfonos, horarios ni direcciones.
                - No incluyas enlaces, solo menciona "nuestra página web" si es necesario.

                Pregunta del usuario:
                "{prompt}"

                Responde solo en JSON:
                {{
                    "respuesta": "Texto útil para el usuario"
                }}
                """

                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Sos un asistente que responde en JSON y no puede inventar datos."},
                        {"role": "user", "content": full_prompt}
                    ],
                    temperature=0.4,
                    max_tokens=200
                )

                texto_respuesta = response.choices[0].message.content.strip()
                match = re.match(r"```(?:json)?\s*(\{.*\})\s*```", texto_respuesta, re.DOTALL)
                if match:
                    texto_respuesta = match.group(1).strip()

                try:
                    respuesta_json = json.loads(texto_respuesta)
                    respuesta_final = respuesta_json["respuesta"]
                except json.JSONDecodeError:
                    respuesta_final = (
                        "Podés registrar tu reclamo en la sección correspondiente de nuestra página web. "
                        "Desde allí también podés consultar el estado si ya lo hiciste."
                    )

            # === NO CLASIFICADA (dinámico inteligente) ===
            else:
                full_prompt = f"""
                Eres DECSA, un asistente virtual de atención al cliente.

                Recibiste este mensaje del usuario:
                "{prompt}"

                ¿Contiene una queja, frustración o problema aunque no lo diga explícitamente?
                Si es así, responde con empatía y guía al usuario a hacer un reclamo en la página web, sin inventar datos ni teléfonos.

                Si no se entiende o es ambigua, responde amablemente que puedes ayudar con ubicación, teléfonos, horarios, reclamos o facturas.

                Formato JSON únicamente:
                {{
                    "respuesta": "Texto breve y adecuado"
                }}
                """

                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Sos un asistente que responde en JSON y no puede inventar información."},
                        {"role": "user", "content": full_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )

                texto_respuesta = response.choices[0].message.content.strip()
                match = re.match(r"```(?:json)?\s*(\{.*\})\s*```", texto_respuesta, re.DOTALL)
                if match:
                    texto_respuesta = match.group(1).strip()

                try:
                    respuesta_json = json.loads(texto_respuesta)
                    respuesta_final = respuesta_json["respuesta"]
                except json.JSONDecodeError:
                    respuesta_final = (
                        "¿Podés especificar mejor tu consulta? Puedo ayudarte con ubicación, teléfonos, horarios, reclamos o facturas."
                    )

            # === CACHÉ ===
            if self.redis_client:
                self.redis_client.setex(cache_key, 3600, json.dumps({"respuesta": respuesta_final}))
                logging.info("Respuesta guardada en caché.")

            return {"respuesta": respuesta_final}

        except Exception as e:
            logging.error(f"Error al generar respuesta: {str(e)}")
            return {"respuesta": "Hubo un error al procesar tu consulta. Por favor, intentá nuevamente."}

    def responder(self, mensaje, historial=""):
        logging.info(f"Enviando a ChatGPT Frontend: '{mensaje}'")
        return self.generar_respuesta(mensaje, historial)
