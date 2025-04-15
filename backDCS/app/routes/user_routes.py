# app/routes/user_routes.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.services.actualizar_usuario_service import ActualizarUsuarioService
from app.repositories.sqlalchemy_usuario_repository import SQLAlchemyUsuarioRepository
from app.database.database import get_db1, get_db2
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter(tags=["Clientes"])  # Categoría "Clientes"

# Inicialización de servicios (sin variables globales)
def init_cliente_services(app):
    # No necesitamos inicializar servicios aquí, ya que usaremos dependencias
    pass

# Dependencias para inyectar en las rutas
def get_cliente_repository(db1: Session = Depends(get_db1), db2: Session = Depends(get_db2)):
    return SQLAlchemyUsuarioRepository(db1, db2)

def get_actualizar_cliente_usecase(cliente_repository: SQLAlchemyUsuarioRepository = Depends(get_cliente_repository)):
    return ActualizarUsuarioService(cliente_repository)

@router.get("/{dni}")
async def validar_cliente(dni: str, cliente_repository: SQLAlchemyUsuarioRepository = Depends(get_cliente_repository)):
    """Valida si el cliente existe, buscando primero en DECSA_EXC (DB2) y luego en PR_CAU (DB1)."""
    try:
        logging.info(f"Validando cliente con DNI: {dni}")
        cliente_db2 = cliente_repository.obtener_por_dni(dni)
        if cliente_db2:
            logging.info(f"Cliente encontrado en DECSA_EXC: {cliente_db2.NOMBRE_COMPLETO}")
            return cliente_db2.to_dict()

        cliente_db1 = cliente_repository.obtener_de_db1(dni)
        if cliente_db1:
            logging.info(f"Cliente encontrado en PR_CAU")
            # Combinar Apellido y Nombre para formar NOMBRE_COMPLETO
            apellido = cliente_db1[0]["Apellido"] or ""
            nombre = cliente_db1[0]["Nombre"] or ""
            nombre_completo = f"{apellido} {nombre}".strip() or "Usuario Desconocido"
            return {
                "DNI": cliente_db1[0]["Dni"],
                "NOMBRE_COMPLETO": nombre_completo,
                "CODIGO_SUMINISTRO": cliente_db1[0]["CodigoSuministro"],
                "NUMERO_MEDIDOR": cliente_db1[0]["NumeroMedidor"],
                "CALLE": cliente_db1[0]["Calle"],
                "BARRIO": cliente_db1[0]["Barrio"],
                "CELULAR": cliente_db1[0].get("Telefono"),
                "CODIGO_POSTAL": cliente_db1[0].get("CodigoPostal")
            }

        logging.warning(f"Cliente con DNI {dni} no encontrado en ninguna base")
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    except Exception as e:
        logging.error(f"Error al validar cliente: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al validar cliente: {str(e)}")

@router.put("/{dni}")
async def actualizar_datos_cliente(dni: str, data: dict, actualizar_cliente_usecase: ActualizarUsuarioService = Depends(get_actualizar_cliente_usecase)):
    """Actualiza los datos de un cliente existente o lo copia desde PR_CAU si no existe en DECSA_EXC."""
    if not data:
        raise HTTPException(status_code=400, detail="Datos de actualización requeridos")
    try:
        logging.info(f"Actualizando cliente con DNI: {dni}")
        respuesta, status_code = actualizar_cliente_usecase.ejecutar(dni, data)
        if status_code != 200:
            raise HTTPException(status_code=status_code, detail=respuesta.get("error", "Error desconocido"))
        return respuesta
    except Exception as e:
        logging.error(f"Error al actualizar datos del cliente: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar datos: {str(e)}")