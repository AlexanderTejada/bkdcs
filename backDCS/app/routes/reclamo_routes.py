from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.repositories.sqlalchemy_reclamo_repository import SQLAlchemyReclamoRepository
from app.repositories.sqlalchemy_usuario_repository import SQLAlchemyUsuarioRepository
from app.database.database import get_db1, get_db2
from app.services.registrar_reclamo_service import RegistrarReclamoService
from app.services.consultar_estado_reclamo_service import ConsultarEstadoReclamoService
from app.services.consultar_reclamo_service import ConsultarReclamoService
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter(tags=["Reclamos"])

# Inicialización de servicios (sin variables globales)
def init_reclamo_services(app):
    pass

# Dependencias para inyectar en las rutas
def get_reclamo_repository(db: Session = Depends(get_db2)):
    return SQLAlchemyReclamoRepository(db)

def get_cliente_repository(db1: Session = Depends(get_db1), db2: Session = Depends(get_db2)):
    return SQLAlchemyUsuarioRepository(db1, db2)

def get_registrar_reclamo_usecase(
    reclamo_repository: SQLAlchemyReclamoRepository = Depends(get_reclamo_repository),
    cliente_repository: SQLAlchemyUsuarioRepository = Depends(get_cliente_repository)
):
    return RegistrarReclamoService(reclamo_repository, cliente_repository)

def get_consultar_estado_usecase(
    reclamo_repository: SQLAlchemyReclamoRepository = Depends(get_reclamo_repository),
    cliente_repository: SQLAlchemyUsuarioRepository = Depends(get_cliente_repository)
):
    return ConsultarEstadoReclamoService(reclamo_repository, cliente_repository)

def get_consultar_reclamo_usecase(
    reclamo_repository: SQLAlchemyReclamoRepository = Depends(get_reclamo_repository)
):
    return ConsultarReclamoService(reclamo_repository)

# 🔹 ENDPOINT PARA EL FRONTEND: obtener todos los reclamos por DNI
@router.get("/todos/{dni}")
async def obtener_todos_reclamos_por_dni(
    dni: str,
    cliente_repository: SQLAlchemyUsuarioRepository = Depends(get_cliente_repository),
    reclamo_repository: SQLAlchemyReclamoRepository = Depends(get_reclamo_repository)
):
    try:
        cliente = cliente_repository.obtener_por_dni(dni)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        reclamos = reclamo_repository.obtener_por_usuario(cliente.ID_USUARIO)
        return {"reclamos": [r.to_dict() for r in reclamos]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener todos los reclamos: {str(e)}")

# 🔸 ENDPOINT GENERAL (TODOS LOS RECLAMOS DEL SISTEMA)
@router.get("/")
async def obtener_todos_los_reclamos(reclamo_repository: SQLAlchemyReclamoRepository = Depends(get_reclamo_repository)):
    try:
        reclamos = reclamo_repository.listar_todos()
        return [r.to_dict() for r in reclamos]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener los reclamos: {str(e)}")

# 🔸 ENDPOINT PARA BOT: devuelve últimos 5 reclamos
@router.get("/{dni}")
async def obtener_reclamos_por_dni(dni: str, consultar_estado_usecase: ConsultarEstadoReclamoService = Depends(get_consultar_estado_usecase)):
    try:
        respuesta, codigo = consultar_estado_usecase.ejecutar(dni)
        if codigo != 200:
            raise HTTPException(status_code=codigo, detail=respuesta.get("error", "Error desconocido"))
        return respuesta
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar los reclamos por DNI: {str(e)}")

# 🔸 ENDPOINT PARA REGISTRAR NUEVO RECLAMO
@router.post("/{dni}")
async def registrar_reclamo(dni: str, data: dict, registrar_reclamo_usecase: RegistrarReclamoService = Depends(get_registrar_reclamo_usecase)):
    if not data or "descripcion" not in data:
        raise HTTPException(status_code=400, detail="La descripción del reclamo es requerida")
    try:
        respuesta, codigo = registrar_reclamo_usecase.ejecutar(dni, data["descripcion"])
        if codigo != 201:
            raise HTTPException(status_code=codigo, detail=respuesta.get("error", "Error desconocido"))
        return respuesta
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar el reclamo: {str(e)}")

# 🔸 ENDPOINT PARA CONSULTAR UN RECLAMO POR ID
@router.get("/id/{id_reclamo}")
async def obtener_reclamo_por_id(id_reclamo: int, consultar_reclamo_usecase: ConsultarReclamoService = Depends(get_consultar_reclamo_usecase)):
    try:
        respuesta, codigo = consultar_reclamo_usecase.ejecutar(id_reclamo)
        if codigo != 200:
            raise HTTPException(status_code=codigo, detail=respuesta.get("error", "Error desconocido"))
        return respuesta
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener el reclamo por ID: {str(e)}")

# 🔸 ENDPOINT PARA ACTUALIZAR ESTADO
@router.put("/{id_reclamo}")
async def actualizar_estado_reclamo(id_reclamo: int, data: dict, reclamo_repository: SQLAlchemyReclamoRepository = Depends(get_reclamo_repository)):
    if not data or "estado" not in data:
        raise HTTPException(status_code=400, detail="El campo 'estado' es requerido")
    try:
        reclamo_actualizado = reclamo_repository.actualizar_estado(id_reclamo, data["estado"])
        if reclamo_actualizado is None:
            raise HTTPException(status_code=404, detail="Reclamo no encontrado")
        return {"mensaje": "Estado del reclamo actualizado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar el estado del reclamo: {str(e)}")
