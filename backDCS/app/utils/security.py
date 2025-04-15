# app/utils/security.py (versión con python-jose)
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.config.config import Config
from app.database.database import get_db2
from app.models.entities import Usuario
from app.repositories.users_repository import SQLAlchemyUSERS

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/usuarios/login")

TIEMPO_EXPIRACION_REFRESH_TOKEN = 7 * 24 * 60

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if not expires_delta:
        expires_delta = timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)

def create_refresh_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if not expires_delta:
        expires_delta = timedelta(minutes=TIEMPO_EXPIRACION_REFRESH_TOKEN)
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db2)):
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if not username or token_type != "access":
            raise HTTPException(status_code=401, detail="Credenciales inválidas o token no válido")
        usuario_service = SQLAlchemyUSERS(db)
        usuario = usuario_service.get_usuario_by_username(username)
        if not usuario or usuario.Anulado:
            raise HTTPException(status_code=401, detail="Usuario no encontrado o anulado")
        return usuario
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

def verify_refresh_token(token: str, db: Session = Depends(get_db2)):
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if not username or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Refresh token inválido")
        usuario_service = SQLAlchemyUSERS(db)
        usuario = usuario_service.get_usuario_by_username(username)
        if not usuario or usuario.Anulado:
            raise HTTPException(status_code=401, detail="Usuario no encontrado o anulado")
        return usuario
    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")

def require_role(role: str):
    def role_checker(usuario: Usuario = Depends(get_current_user)):
        role_names = [r.Nombre for r in usuario.roles]
        if role not in role_names:
            raise HTTPException(status_code=403, detail=f"Se requiere rol '{role}'")
        return usuario
    return role_checker