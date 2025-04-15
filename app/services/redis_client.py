# app/services/redis_client.py

import redis
import logging
from typing import Optional, List
from app.config.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class RedisClient:
    def __init__(self):
        self.client = None
        self._connect()

    def _connect(self):
        try:
            if Config.REDIS_URL:
                self.client = redis.from_url(Config.REDIS_URL, decode_responses=True)
                logging.info("✅ Conexión a Redis establecida usando REDIS_URL.")
            else:
                self.client = redis.StrictRedis(
                    host=Config.REDIS_HOST,
                    port=int(Config.REDIS_PORT),
                    db=0,
                    decode_responses=True
                )
                logging.info("⚠️ REDIS_URL no encontrado, usando host y puerto manuales.")
            self.client.ping()
            logging.info("✅ Cliente de Redis inicializado correctamente.")
        except redis.ConnectionError as e:
            logging.error(f"❌ Error de conexión con Redis: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"❌ Error inesperado al conectar a Redis: {str(e)}")
            raise

    def get_client(self) -> redis.Redis:
        if self.client is None:
            self._connect()
        return self.client

    def get(self, key: str) -> Optional[str]:
        return self.client.get(key)

    def set(self, key: str, value: str):
        self.client.set(key, value)

    def setex(self, key: str, time: int, value: str):
        self.client.setex(key, time, value)

    def rpush(self, key: str, value: str):
        self.client.rpush(key, value)

    def lrange(self, key: str, start: int, end: int) -> List[str]:
        return self.client.lrange(key, start, end)

    def ltrim(self, key: str, start: int, end: int):
        self.client.ltrim(key, start, end)

    def hgetall(self, key: str) -> dict:
        return self.client.hgetall(key)

    def hset(self, key: str, field: str, value: str):
        self.client.hset(key, field, value)

    def hdel(self, key: str, field: str):
        self.client.hdel(key, field)

    def delete(self, key: str):
        self.client.delete(key)

    def flushdb(self):
        self.client.flushdb()
        logging.info("🧹 Redis limpio con flushdb.")
