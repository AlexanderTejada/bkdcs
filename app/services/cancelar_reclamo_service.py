# app/services/cancelar_reclamo_service.py
import logging
from app.repositories.sqlalchemy_reclamo_repository import SQLAlchemyReclamoRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class CancelarReclamoService:
    def __init__(self, reclamo_repository: SQLAlchemyReclamoRepository):
        self.reclamo_repository = reclamo_repository

    def ejecutar(self, id_reclamo: int):
        try:
            reclamo = self.reclamo_repository.obtener_por_id(id_reclamo)
            if not reclamo:
                return {"error": "Reclamo no encontrado"}, 404

            if reclamo.ESTADO != "Pendiente":
                return {"error": "No puedes cancelar un reclamo que ya está en proceso o cerrado"}, 400

            reclamo.ESTADO = "Cancelado por el cliente"
            self.reclamo_repository.actualizar_estado(id_reclamo, "Cancelado por el cliente")
            logging.info(f"Reclamo {id_reclamo} cancelado exitosamente")
            return {"message": "Reclamo cancelado exitosamente"}, 200
        except Exception as e:
            logging.error(f"Error al cancelar reclamo {id_reclamo}: {str(e)}")
            return {"error": f"Error al cancelar reclamo: {str(e)}"}, 500