# app/routes/factura_routes.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.repositories.sqlalchemy_usuario_repository import SQLAlchemyUsuarioRepository
from app.database.database import get_db1, get_db2
from app.services.consultar_facturas_service import ConsultarFacturasService
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter(tags=["Facturas"])

def init_factura_services(app):
    pass  # Vacío porque usamos Depends

def get_cliente_repository(db1: Session = Depends(get_db1), db2: Session = Depends(get_db2)):
    return SQLAlchemyUsuarioRepository(db1, db2)

def get_consultar_facturas_usecase(cliente_repository: SQLAlchemyUsuarioRepository = Depends(get_cliente_repository)):
    return ConsultarFacturasService(cliente_repository)

@router.get("/{dni}")
async def obtener_facturas_por_dni(dni: str, consultar_facturas_usecase: ConsultarFacturasService = Depends(get_consultar_facturas_usecase)):
    try:
        resultado, status = consultar_facturas_usecase.ejecutar(dni)
        if status != 200:
            raise HTTPException(status_code=status, detail=resultado.get("error", "Error desconocido"))
        return resultado
    except Exception as e:
        logging.error(f"Error al obtener facturas por DNI: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener facturas por DNI: {str(e)}")