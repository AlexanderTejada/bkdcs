# app/routes/roles_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db2
from app.repositories.rol_repository import SQLAlchemyROLES
from app.utils.security import get_current_user, require_role
from app.models.entities import Usuario
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter(tags=["Roles"])  # Categoría "Roles"

@router.post("")
async def crear_rol(
    rol_data: dict,
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(require_role("admin"))
):
    rol_service = SQLAlchemyROLES(db)
    try:
        if "Nombre" not in rol_data or "OperadorCrea" not in rol_data:
            raise HTTPException(status_code=400, detail="Nombre y OperadorCrea son requeridos")
        nuevo_rol = rol_service.create_rol(
            rol_data["Nombre"],
            rol_data.get("Descripcion"),
            rol_data["OperadorCrea"]
        )
        return nuevo_rol.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Error al crear rol: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear rol: {str(e)}")

@router.get("/{id_rol}")
async def obtener_rol(
    id_rol: int,
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(get_current_user)
):
    rol_service = SQLAlchemyROLES(db)
    rol = rol_service.get_rol_by_id(id_rol)
    if not rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")
    return rol.to_dict()

@router.get("")
async def obtener_todos_roles(
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(require_role("admin"))
):
    rol_service = SQLAlchemyROLES(db)
    roles = rol_service.get_all_roles()
    return [rol.to_dict() for rol in roles]

@router.put("/{id_rol}")
async def actualizar_rol(
    id_rol: int,
    rol_data: dict,
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(require_role("admin"))
):
    rol_service = SQLAlchemyROLES(db)
    try:
        rol_actualizado = rol_service.update_rol(
            id_rol,
            rol_data.get("Nombre"),
            rol_data.get("Descripcion"),
            rol_data.get("OperadorModifica")
        )
        if not rol_actualizado:
            raise HTTPException(status_code=404, detail="Rol no encontrado.")
        return rol_actualizado.to_dict()
    except Exception as e:
        logging.error(f"Error al actualizar rol: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar rol: {str(e)}")

@router.delete("/{id_rol}")
async def anular_rol(
    id_rol: int,
    rol_data: dict,
    db: Session = Depends(get_db2),
    current_user: Usuario = Depends(require_role("admin"))
):
    rol_service = SQLAlchemyROLES(db)
    try:
        if "OperadorAnula" not in rol_data:
            raise HTTPException(status_code=400, detail="OperadorAnula es requerido")
        rol_anulado = rol_service.delete_rol(
            id_rol,
            rol_data["OperadorAnula"]
        )
        if not rol_anulado:
            raise HTTPException(status_code=404, detail="Rol no encontrado.")
        return {"message": "Rol anulado exitosamente."}
    except Exception as e:
        logging.error(f"Error al anular rol: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al anular rol: {str(e)}")