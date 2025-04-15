# app/services/consultar_estado_reclamo_service.py
from app.repositories.sqlalchemy_reclamo_repository import SQLAlchemyReclamoRepository
from app.repositories.sqlalchemy_usuario_repository import SQLAlchemyUsuarioRepository
import logging

class ConsultarEstadoReclamoService:
    def __init__(self, reclamo_repository: SQLAlchemyReclamoRepository, usuario_repository: SQLAlchemyUsuarioRepository):
        self.reclamo_repository = reclamo_repository
        self.usuario_repository = usuario_repository

    def ejecutar(self, dni: str):
        """Consulta los últimos 5 reclamos de un cliente a partir de su DNI."""
        try:
            logging.info(f"Buscando cliente con DNI {dni} para consultar reclamos")
            cliente = self.usuario_repository.obtener_por_dni(dni)
            if not cliente:
                logging.info(f"Cliente con DNI {dni} no encontrado en DB2, no tiene reclamos")
                return {"reclamos": [], "mensaje": "No tienes reclamos registrados porque aún no has interactuado con el sistema"}, 200

            if not cliente.ID_USUARIO:
                logging.error(f"ID_USUARIO no válido para cliente con DNI {dni}: {cliente.ID_USUARIO}")
                return {"reclamos": [], "mensaje": "Error interno: ID de usuario no válido"}, 500

            logging.info(f"Cliente encontrado con DNI {dni}, ID_USUARIO: {cliente.ID_USUARIO}")
            reclamos = self.reclamo_repository.obtener_por_usuario(cliente.ID_USUARIO)
            if not reclamos:
                logging.info(f"No se encontraron reclamos para ID_USUARIO {cliente.ID_USUARIO}")
                return {"reclamos": [], "mensaje": "No tienes reclamos registrados"}, 200

            # Ordenar los reclamos por ID_RECLAMO (descendente) y limitar a los últimos 5
            reclamos = sorted(reclamos, key=lambda r: r.ID_RECLAMO, reverse=True)[:5]

            logging.info(f"Reclamos encontrados para DNI {dni}: {len(reclamos)} reclamos")
            return {
                "cliente": {
                    "nombre": cliente.NOMBRE_COMPLETO,
                    "dni": cliente.DNI,
                    "direccion": cliente.CALLE,
                    "barrio": cliente.BARRIO,
                    "codigo_suministro": cliente.CODIGO_SUMINISTRO
                },
                "reclamos": [reclamo.to_dict() for reclamo in reclamos]
            }, 200
        except Exception as e:
            logging.error(f"Error al consultar reclamos para DNI {dni}: {str(e)}")
            raise