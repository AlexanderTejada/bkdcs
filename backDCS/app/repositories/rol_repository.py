# app/repositories/rol_repository.py
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.entities import Rol  # Ajustamos la importación
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SQLAlchemyROLES:
    def __init__(self, session: Session):
        self.session = session

    def create_rol(self, nombre: str, descripcion: str | None, operador_crea: str):
        logging.info(f"Creando nuevo rol: {nombre}")
        db_rol = Rol(
            Nombre=nombre,
            Descripcion=descripcion,
            FechaCrea=datetime.utcnow(),
            UsuarioCrea=operador_crea,
            Anulado=False
        )
        try:
            self.session.add(db_rol)
            self.session.commit()
            self.session.refresh(db_rol)
            logging.info(f"Rol {nombre} creado exitosamente.")
            return db_rol
        except IntegrityError:
            self.session.rollback()
            logging.error(f"Error: El rol {nombre} ya existe.")
            raise ValueError("El rol ya existe.")

    def get_rol_by_id(self, id_rol: int):
        logging.info(f"Buscando rol por ID: {id_rol}")
        rol = self.session.query(Rol).filter(Rol.IdRol == id_rol).first()
        return rol

    def get_all_roles(self):
        logging.info("Obteniendo todos los roles")
        roles = self.session.query(Rol).all()
        return roles

    def update_rol(self, id_rol: int, nombre: str | None, descripcion: str | None, operador_modifica: str | None):
        logging.info(f"Actualizando rol con ID: {id_rol}")
        db_rol = self.get_rol_by_id(id_rol)
        if not db_rol:
            logging.warning(f"Rol con ID {id_rol} no encontrado.")
            return None
        if nombre:
            db_rol.Nombre = nombre
        if descripcion is not None:
            db_rol.Descripcion = descripcion
        if operador_modifica:
            db_rol.UsuarioModifica = operador_modifica
            db_rol.FechaModifica = datetime.utcnow()
        try:
            self.session.commit()
            self.session.refresh(db_rol)
            logging.info(f"Rol con ID {id_rol} actualizado exitosamente.")
            return db_rol
        except IntegrityError:
            self.session.rollback()
            logging.error(f"Error: El nombre {nombre} ya existe.")
            raise ValueError("El nombre del rol ya existe.")

    def delete_rol(self, id_rol: int, operador_anula: str):
        logging.info(f"Anulando rol con ID: {id_rol}")
        db_rol = self.get_rol_by_id(id_rol)
        if not db_rol:
            logging.warning(f"Rol con ID {id_rol} no encontrado.")
            return None
        db_rol.Anulado = True
        db_rol.FechaAnula = datetime.utcnow()
        db_rol.UsuarioAnula = operador_anula
        try:
            self.session.commit()
            self.session.refresh(db_rol)
            logging.info(f"Rol con ID {id_rol} anulado exitosamente.")
            return db_rol
        except Exception as e:
            self.session.rollback()
            logging.error(f"Error al anular rol {id_rol}: {str(e)}")
            raise ValueError("Error al anular rol.")