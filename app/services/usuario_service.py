# app/services/usuario_service.py
import logging
from app.models.entities import Cliente
from app.repositories.sqlalchemy_usuario_repository import SQLAlchemyUsuarioRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class UsuarioService:
    def __init__(self, usuario_repo: SQLAlchemyUsuarioRepository):
        self.usuario_repo = usuario_repo

    def obtener_usuario_por_dni(self, dni):
        """Obtiene un cliente por su DNI en DECSA_EXC (DB2). Si no existe, lo copia desde PR_CAU (DB1)."""
        logging.info(f"Buscando cliente con DNI: {dni}")

        cliente = self.usuario_repo.obtener_por_dni(dni)

        if not cliente:
            logging.warning(f"Cliente con DNI {dni} no encontrado en DECSA_EXC. Buscando en PR_CAU...")
            cliente = self.copiar_cliente_a_db2(dni)

            if isinstance(cliente, tuple):
                cliente = cliente[0] if cliente[1] == 201 else None

            if not cliente:
                logging.error(f"Cliente con DNI {dni} no encontrado en ninguna base de datos.")
                return {"error": "Cliente no encontrado"}, 404

        return cliente.to_dict(), 200

    def copiar_cliente_a_db2(self, dni):
        """Copia un cliente desde PR_CAU a DECSA_EXC si no existe."""
        logging.info(f"Intentando copiar cliente con DNI: {dni}")

        if self.usuario_repo.existe_en_db2(dni):
            logging.warning(f"El cliente con DNI {dni} ya existe en DECSA_EXC")
            return {"error": "El cliente ya existe en DECSA_EXC"}, 409

        cliente_copiado = self.usuario_repo.copiar_cliente_a_db2(dni)
        if not cliente_copiado:
            logging.error(f"Cliente con DNI {dni} no encontrado en PR_CAU")
            return {"error": "Cliente no encontrado en PR_CAU"}, 404

        logging.info(f"Cliente con DNI {dni} copiado exitosamente a DECSA_EXC")
        return cliente_copiado.to_dict(), 201

    def actualizar_cliente(self, dni, data):
        """Actualiza los datos de un cliente en DECSA_EXC. Si no existe, lo copia primero desde PR_CAU."""
        logging.info(f"Intentando actualizar cliente con DNI: {dni}")

        cliente = self.usuario_repo.obtener_por_dni(dni)

        if not cliente:
            logging.warning(f"Cliente con DNI {dni} no encontrado en DECSA_EXC. Copiando desde PR_CAU...")
            cliente = self.copiar_cliente_a_db2(dni)

            if isinstance(cliente, tuple):
                cliente = cliente[0] if cliente[1] == 201 else None

            if not cliente:
                logging.error(f"No se pudo copiar el cliente con DNI {dni} desde PR_CAU.")
                return {"error": "Cliente no encontrado"}, 404

        # Campos que se pueden actualizar desde la app o bot
        campos_permitidos = ["CALLE", "CELULAR", "EMAIL", "BARRIO", "OBSERVACIONES"]
        for campo in campos_permitidos:
            if campo in data:
                setattr(cliente, campo, data[campo])

        self.usuario_repo.actualizar_cliente(cliente)
        logging.info(f"Cliente con DNI {dni} actualizado exitosamente")
        return cliente.to_dict(), 200