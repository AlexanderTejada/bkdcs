# services/consultar_facturas_service.py
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ConsultarFacturasService:
    def __init__(self, usuario_repository):
        self.usuario_repository = usuario_repository

    def ejecutar(self, dni: str):
        try:
            datos = self.usuario_repository.obtener_de_db1(dni)
            if not datos:
                logging.warning(f"No se encontraron datos para el DNI {dni} en PR_CAU")
                return {"mensaje": "No se encontraron datos para ese DNI"}, 404

            # Verificar si el cliente existe pero no tiene facturas
            if not any(dato.get("NumeroComprobante") for dato in datos):
                logging.info(f"Cliente con DNI {dni} encontrado, pero no tiene facturas")
                return {"facturas": [], "mensaje": "No tienes facturas registradas"}, 200

            # Formatear la información de las facturas
            facturas = []
            for dato in datos:
                if not dato.get("NumeroComprobante"):  # Saltar filas sin factura
                    continue
                factura_info = {
                    "Nombre": f"{dato['Apellido']} {dato['Nombre']}".strip() or "Usuario Desconocido",
                    "DNI": dato["Dni"],
                    "CodigoSuministro": dato["CodigoSuministro"] if dato["CodigoSuministro"] else "No disponible",
                    "NumeroComprobante": dato["NumeroComprobante"] if dato["NumeroComprobante"] else "No disponible",
                    "FechaEmision": (dato["FechaEmision"].strftime("%d/%m/%Y")
                                     if dato["FechaEmision"] and isinstance(dato["FechaEmision"], datetime)
                                     else "No disponible"),
                    "Estado": "Pagada" if dato["EstadoFactura"] == "P" else "Pendiente",
                    "Total": float(dato["TotalFactura"]) if dato["TotalFactura"] is not None else 0.0,
                    "Vencimiento": (dato["VencimientoFactura"].strftime("%d/%m/%Y")
                                    if dato["VencimientoFactura"] and isinstance(dato["VencimientoFactura"], datetime)
                                    else "No disponible"),
                    "ObservacionPostal": dato["ObservacionPostal"] if dato["ObservacionPostal"] else "No disponible",
                    "Barrio": dato["Barrio"] if dato["Barrio"] else "No disponible",
                    "Calle": dato["Calle"] if dato["Calle"] else "No disponible",
                    "NumeroMedidor": dato["NumeroMedidor"] if dato["NumeroMedidor"] else "No disponible",
                    "Periodo": dato["Periodo"] if dato["Periodo"] else "No disponible",
                    "Consumo": float(dato["Consumo"]) if dato["Consumo"] is not None else 0.0
                }
                facturas.append(factura_info)

            logging.info(f"Facturas encontradas para el DNI {dni}: {len(facturas)}")
            return {"facturas": facturas}, 200

        except Exception as e:
            logging.error(f"Error al consultar factura para el DNI {dni}: {str(e)}")
            return {"error": "Error al consultar las facturas", "detalle": str(e)}, 500