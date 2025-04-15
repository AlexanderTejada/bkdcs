# app/repositories/users_repository.py
from sqlalchemy.orm import Session
from app.models.entities import Usuario, Rol
import logging
from datetime import datetime  # Necesario para FechaModifica y FechaAnula

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SQLAlchemyUSERS:
    def __init__(self, session: Session):
        self.session = session

    def create_usuario(self, username: str, email: str, password: str, operador_crea: str, roles: list[str] = None):
        from app.utils.security import hash_password  # Importamos aquí para evitar circularidad
        if self.get_usuario_by_username(username):
            raise ValueError(f"El usuario {username} ya existe.")
        hashed_password = hash_password(password)
        usuario = Usuario(
            Usuario=username,
            email=email,
            Pass=hashed_password,
            OperadorCrea=operador_crea,
            Anulado=False
        )
        self.session.add(usuario)
        self.session.flush()
        if roles:
            for rol_name in roles:
                rol = self.session.query(Rol).filter(Rol.Nombre == rol_name, Rol.Anulado == False).first()
                if not rol:
                    raise ValueError(f"El rol {rol_name} no existe.")
                usuario.roles.append(rol)
        self.session.commit()
        return usuario

    def get_usuario_by_id(self, id_usuario: int):
        return self.session.query(Usuario).filter(Usuario.IdUsuario == id_usuario).first()

    def get_usuario_by_username(self, username: str):
        return self.session.query(Usuario).filter(Usuario.Usuario == username).first()

    def get_all_usuarios(self):
        return self.session.query(Usuario).all()

    def update_usuario(self, id_usuario: int, username: str, email: str, password: str, operador_modifica: str, roles: list[str] = None):
        from app.utils.security import hash_password  # Importamos aquí para evitar circularidad
        usuario = self.get_usuario_by_id(id_usuario)
        if not usuario:
            return None
        if username:
            usuario.Usuario = username
        if email:
            usuario.email = email
        if password:
            usuario.Pass = hash_password(password)
        if operador_modifica:
            usuario.OperadorModifica = operador_modifica
            usuario.FechaModifica = datetime.now()
        if roles is not None:
            usuario.roles = []
            for rol_name in roles:
                rol = self.session.query(Rol).filter(Rol.Nombre == rol_name, Rol.Anulado == False).first()
                if not rol:
                    raise ValueError(f"El rol {rol_name} no existe.")
                usuario.roles.append(rol)
        self.session.commit()
        return usuario

    def delete_usuario(self, id_usuario: int, operador_anula: str):
        usuario = self.get_usuario_by_id(id_usuario)
        if not usuario:
            return None
        usuario.Anulado = True
        usuario.OperadorAnula = operador_anula
        usuario.FechaAnula = datetime.now()
        self.session.commit()
        return usuario

    def authenticate_user(self, username: str, password: str):
        from app.utils.security import verify_password  # Importamos aquí para evitar circularidad
        usuario = self.get_usuario_by_username(username)
        if not usuario or usuario.Anulado:
            return None
        if not verify_password(password, usuario.Pass):
            return None
        return usuario