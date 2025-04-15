# app/services/reclamo_service.py
import logging
from app.services.registrar_reclamo_service import RegistrarReclamoService
from app.services.consultar_estado_reclamo_service import ConsultarEstadoReclamoService
from app.services.actualizar_estado_reclamo_service import ActualizarEstadoReclamoService
from app.services.cancelar_reclamo_service import CancelarReclamoService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ReclamoService:
    def __init__(self, registrar_reclamo_service: RegistrarReclamoService, consultar_estado_service: ConsultarEstadoReclamoService, actualizar_estado_service: ActualizarEstadoReclamoService, cancelar_reclamo_service: CancelarReclamoService):
        self.registrar_reclamo_service = registrar_reclamo_service
        self.consultar_estado_service = consultar_estado_service
        self.actualizar_estado_service = actualizar_estado_service
        self.cancelar_reclamo_service = cancelar_reclamo_service

    def crear_reclamo(self, dni, descripcion):
        """Crea un reclamo para un cliente."""
        return self.registrar_reclamo_service.ejecutar(dni, descripcion)

    def cancelar_reclamo(self, id_reclamo):
        """Permite cancelar un reclamo si está en estado 'Pendiente'."""
        return self.cancelar_reclamo_service.ejecutar(id_reclamo)

    def actualizar_estado(self, id_reclamo, nuevo_estado):
        """Actualiza el estado de un reclamo."""
        return self.actualizar_estado_service.ejecutar(id_reclamo, nuevo_estado)

    def obtener_reclamos(self, dni):
        """Obtiene todos los reclamos de un cliente por DNI."""
        return self.consultar_estado_service.ejecutar(dni)