# app/services/consultar_reclamo_service.py
from app.repositories.sqlalchemy_reclamo_repository import SQLAlchemyReclamoRepository
import logging

class ConsultarReclamoService:
    def __init__(self, reclamo_repository: SQLAlchemyReclamoRepository):
        self.reclamo_repository = reclamo_repository

    def ejecutar(self, id_reclamo: int):
        """Consulta un reclamo específico por su ID, incluyendo datos del cliente."""
        try:
            reclamo = self.reclamo_repository.obtener_por_id(id_reclamo)
            if not reclamo:
                logging.warning(f"Reclamo con ID {id_reclamo} no encontrado")
                return {"error": "Reclamo no encontrado"}, 404

            logging.info(f"Reclamo con ID {id_reclamo} encontrado")
            return {
                "reclamo": reclamo.to_dict(),
                "cliente": {
                    "nombre": reclamo.cliente.NOMBRE_COMPLETO if reclamo.cliente else "Desconocido",
                    "dni": reclamo.cliente.DNI if reclamo.cliente else "Desconocido",
                    "direccion": reclamo.cliente.CALLE if reclamo.cliente else "Desconocido",
                    "barrio": reclamo.cliente.BARRIO if reclamo.cliente else "Desconocido",
                    "codigo_suministro": reclamo.cliente.CODIGO_SUMINISTRO if reclamo.cliente else "Desconocido",
                    "numero_medidor": reclamo.cliente.NUMERO_MEDIDOR if reclamo.cliente else "No disponible"
                }
            }, 200

        except Exception as e:
            logging.error(f"Error al consultar el reclamo {id_reclamo}: {str(e)}")
            return {"error": "Error al consultar el reclamo", "detalle": str(e)}, 500