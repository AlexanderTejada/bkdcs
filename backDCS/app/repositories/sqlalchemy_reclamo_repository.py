# app/repositories/sqlalchemy_reclamo_repository.py
from sqlalchemy.orm import Session, joinedload
from app.models.entities import Reclamo, Cliente  # Ajustamos la importación
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SQLAlchemyReclamoRepository:
    def __init__(self, session: Session):
        self.session = session

    def obtener_por_id(self, id_reclamo: int):
        try:
            reclamo = (
                self.session.query(Reclamo)
                .options(joinedload(Reclamo.cliente))
                .filter(Reclamo.ID_RECLAMO == id_reclamo)
                .first()
            )
            if reclamo:
                logging.info(f"Reclamo encontrado con ID {id_reclamo}")
            else:
                logging.info(f"Reclamo con ID {id_reclamo} no encontrado")
            return reclamo
        except Exception as e:
            logging.error(f"Error al obtener reclamo con ID {id_reclamo}: {str(e)}")
            raise

    def obtener_por_usuario(self, id_usuario: int):
        try:
            if not isinstance(id_usuario, int):
                logging.error(f"ID_USUARIO no es un entero válido: {id_usuario}")
                raise ValueError(f"ID_USUARIO debe ser un entero, pero se recibió: {id_usuario}")

            logging.info(f"Buscando reclamos para ID_USUARIO {id_usuario}")
            reclamos = (
                self.session.query(Reclamo)
                .filter(Reclamo.ID_USUARIO == id_usuario)
                .all()
            )
            logging.info(f"Se encontraron {len(reclamos)} reclamos para ID_USUARIO {id_usuario}")
            return reclamos
        except Exception as e:
            logging.error(f"Error al obtener reclamos para ID_USUARIO {id_usuario}: {str(e)}")
            raise

    def guardar(self, reclamo: Reclamo):
        try:
            self.session.add(reclamo)
            self.session.commit()
            logging.info(f"Reclamo guardado correctamente con ID {reclamo.ID_RECLAMO}")
            return reclamo
        except Exception as e:
            self.session.rollback()
            logging.error(f"Error al guardar reclamo: {str(e)}")
            raise

    def actualizar_estado(self, id_reclamo: int, nuevo_estado: str):
        try:
            reclamo = self.obtener_por_id(id_reclamo)
            if reclamo:
                reclamo.ESTADO = nuevo_estado
                # Si el estado es "Resuelto", actualizamos FECHA_CIERRE
                if nuevo_estado == "Resuelto":
                    reclamo.FECHA_CIERRE = datetime.now()
                # Si el estado cambia de "Resuelto" a otro, limpiamos FECHA_CIERRE
                elif reclamo.FECHA_CIERRE and nuevo_estado != "Resuelto":
                    reclamo.FECHA_CIERRE = None
                self.session.commit()
                logging.info(f"Estado del reclamo {id_reclamo} actualizado a {nuevo_estado}")
                return reclamo
            logging.warning(f"Reclamo con ID {id_reclamo} no encontrado para actualizar estado.")
            return None
        except Exception as e:
            self.session.rollback()
            logging.error(f"Error al actualizar estado del reclamo {id_reclamo}: {str(e)}")
            raise

    def listar_todos(self):
        try:
            reclamos = (
                self.session.query(Reclamo)
                .options(joinedload(Reclamo.cliente))
                .all()
            )
            logging.info(f"Se listaron {len(reclamos)} reclamos desde DB2")
            return reclamos
        except Exception as e:
            logging.error(f"Error al listar todos los reclamos: {str(e)}")
            raise

    def listar_pendientes(self):
        try:
            reclamos = (
                self.session.query(Reclamo)
                .options(joinedload(Reclamo.cliente))
                .filter(Reclamo.ESTADO == "Pendiente")
                .all()
            )
            logging.info(f"Se listaron {len(reclamos)} reclamos pendientes desde DB2")
            return reclamos
        except Exception as e:
            logging.error(f"Error al listar reclamos pendientes: {str(e)}")
            raise