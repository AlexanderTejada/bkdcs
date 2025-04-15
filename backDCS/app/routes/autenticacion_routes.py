# app/routes/autenticacion_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.database import get_db2  # Ajustamos la importación
from app.repositories.users_repository import SQLAlchemyUSERS  # Ajustamos la importación
from app.utils.security import get_current_user, require_role, create_access_token, verify_refresh_token  # Ajustamos la importación
from app.models.entities import Usuario  # Ajustamos la importación
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
router = APIRouter()

class UsuarioCreate(BaseModel):
    Usuario: str
    email: str
    Pass: str
    OperadorCrea: str
    roles: list[str] = []

class UsuarioUpdate(BaseModel):
    Usuario: str | None = None
    email: str | None = None
    Pass: str | None = None
    OperadorModifica: str | None = None
    roles: list[str] = None

class UsuarioDelete(BaseModel):
    OperadorAnula: str

class UsuarioResponse(BaseModel):
    IdUsuario: int
    Usuario: str
    email: str
    FechaCrea: str
    OperadorCrea: str
    Anulado: bool
    FechaAnula: str | None = None
    UsuarioAnula: str | None = None
    FechaModifica: str | None = None
    UsuarioModifica: str | None = None
    roles: list[dict]

class LoginRequest(BaseModel):
    Usuario: str
    Pass: str

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("", response_model=UsuarioResponse)
async def crear_usuario(
    usuario_data: UsuarioCreate,
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(require_role("admin"))
):
    usuario_service = SQLAlchemyUSERS(db)
    try:
        nuevo_usuario = usuario_service.create_usuario(
            usuario_data.Usuario,
            usuario_data.email,
            usuario_data.Pass,
            usuario_data.OperadorCrea,
            usuario_data.roles
        )
        return nuevo_usuario.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{id_usuario}", response_model=UsuarioResponse)
async def obtener_usuario(
    id_usuario: int,
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(get_current_user)
):
    usuario_service = SQLAlchemyUSERS(db)
    usuario = usuario_service.get_usuario_by_id(id_usuario)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return usuario.to_dict()

@router.get("", response_model=list[UsuarioResponse])
async def obtener_todos_usuarios(
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(require_role("admin"))
):
    usuario_service = SQLAlchemyUSERS(db)
    usuarios = usuario_service.get_all_usuarios()
    return [usuario.to_dict() for usuario in usuarios]

@router.put("/{id_usuario}", response_model=UsuarioResponse)
async def actualizar_usuario(
    id_usuario: int,
    usuario_data: UsuarioUpdate,
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(require_role("admin"))
):
    usuario_service = SQLAlchemyUSERS(db)
    usuario_actualizado = usuario_service.update_usuario(
        id_usuario,
        usuario_data.Usuario,
        usuario_data.email,
        usuario_data.Pass,
        usuario_data.OperadorModifica,
        usuario_data.roles
    )
    if not usuario_actualizado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return usuario_actualizado.to_dict()

@router.delete("/{id_usuario}")
async def anular_usuario(
    id_usuario: int,
    usuario_data: UsuarioDelete,
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(require_role("admin"))
):
    usuario_service = SQLAlchemyUSERS(db)
    usuario_anulado = usuario_service.delete_usuario(
        id_usuario,
        usuario_data.OperadorAnula
    )
    if not usuario_anulado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return {"message": "Usuario anulado exitosamente."}

@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db2)):
    print("logeando")
    usuario_service = SQLAlchemyUSERS(db)
    usuario = usuario_service.authenticate_user(request.Usuario, request.Pass)

    if not usuario:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    role_names = [rol.Nombre for rol in usuario.roles]
    access_token = create_access_token(data={"sub": usuario.Usuario, "roles": role_names})

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh")
async def refresh_token(request: RefreshRequest, db: Session = Depends(get_db2)):
    usuario = verify_refresh_token(request.refresh_token, db)
    role_names = [rol.Nombre for rol in usuario.roles]
    new_access_token = create_access_token(data={"sub": usuario.Usuario, "roles": role_names})

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }