# app/services/redis_client.py
import redis
from typing import Optional, List
from app.config.config import Config
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class RedisClient:
    def __init__(self, host: str = None, port: str = None):
        self.host = host or Config.REDIS_HOST
        self.port = port or Config.REDIS_PORT
        self.client = None
        self._connect()

    def _connect(self):
        try:
            self.client = redis.StrictRedis(
                host=self.host,
                port=int(self.port),
                db=0,
                decode_responses=True
            )
            self.client.ping()
            logging.info("✅ Cliente de Redis inicializado correctamente")
        except redis.ConnectionError as e:
            logging.error(f"❌ Error al conectar con Redis: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"❌ Error inesperado al inicializar Redis: {str(e)}")
            raise

    def get_client(self) -> redis.StrictRedis:
        if self.client is None:
            self._connect()
        return self.client

    def get(self, key: str) -> Optional[str]:
        try:
            return self.client.get(key)
        except redis.RedisError as e:
            logging.error(f"Error al obtener clave {key} de Redis: {str(e)}")
            raise

    def set(self, key: str, value: str):
        try:
            self.client.set(key, value)
        except redis.RedisError as e:
            logging.error(f"Error al establecer clave {key} en Redis: {str(e)}")
            raise

    def setex(self, key: str, time: int, value: str):
        try:
            self.client.setex(key, time, value)
        except redis.RedisError as e:
            logging.error(f"Error al establecer clave {key} con expiración en Redis: {str(e)}")
            raise

    def rpush(self, key: str, value: str):
        try:
            self.client.rpush(key, value)
        except redis.RedisError as e:
            logging.error(f"Error al agregar valor a la lista {key} en Redis: {str(e)}")
            raise

    def lrange(self, key: str, start: int, end: int) -> List[str]:
        try:
            return self.client.lrange(key, start, end)
        except redis.RedisError as e:
            logging.error(f"Error al obtener rango de la lista {key} en Redis: {str(e)}")
            raise

    def ltrim(self, key: str, start: int, end: int):
        try:
            self.client.ltrim(key, start, end)
        except redis.RedisError as e:
            logging.error(f"Error al recortar la lista {key} en Redis: {str(e)}")
            raise

    def hgetall(self, key: str) -> dict:
        try:
            return self.client.hgetall(key)
        except redis.RedisError as e:
            logging.error(f"Error al obtener hash {key} en Redis: {str(e)}")
            raise

    def hset(self, key: str, field: str, value: str):
        try:
            self.client.hset(key, field, value)
        except redis.RedisError as e:
            logging.error(f"Error al establecer campo {field} en hash {key} en Redis: {str(e)}")
            raise

    def hdel(self, key: str, field: str):
        try:
            self.client.hdel(key, field)
        except redis.RedisError as e:
            logging.error(f"Error al eliminar campo {field} de hash {key} en Redis: {str(e)}")
            raise

    def delete(self, key: str):
        try:
            self.client.delete(key)
        except redis.RedisError as e:
            logging.error(f"Error al eliminar clave {key} en Redis: {str(e)}")
            raise

    def flushdb(self):
        try:
            self.client.flushdb()
            logging.info("🌟 Memoria de Redis reseteada")
        except redis.RedisError as e:
            logging.error(f"Error al resetear Redis: {str(e)}")
            raise