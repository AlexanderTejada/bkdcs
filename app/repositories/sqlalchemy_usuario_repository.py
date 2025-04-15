# app/repositories/sqlalchemy_usuario_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.entities import Cliente
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SQLAlchemyUsuarioRepository:
    def __init__(self, session_db1: Session, session_db2: Session):
        self.session_db1 = session_db1
        self.session_db2 = session_db2

    def obtener_por_dni(self, dni: str):
        logging.info(f"Buscando cliente con DNI {dni} en DECSA_EXC")
        result = self.session_db2.query(Cliente).filter(Cliente.DNI == dni).first()
        return result

    def obtener_de_db1(self, dni: str):
        logging.info(f"Buscando datos de persona con DNI {dni} en PR_CAU")
        consulta = text("""
            SELECT 
                persona.COD_PER AS IdPersona,
                persona.APELLIDOS AS Apellido,
                persona.NOMBRES AS Nombre,
                persona.NUM_DNI AS Dni,
                persona.SEXO AS Sexo,
                persona.TELEFONO AS Telefono,
                persona.EMAIL AS Email,
                persona.COD_POS AS CodigoPostal,
                persona.FEC_ALTA AS FechaAlta,
                persona.OBSERVAC AS Observaciones,
                factu.COD_SUM AS CodigoSuministro,
                factu.NUM_COM AS NumeroComprobante,
                factu.FECHA AS FechaEmision,
                factu.PAGA AS EstadoFactura,
                factu.TOTAL1 AS TotalFactura,
                factu.VTO1 AS VencimientoFactura,
                sumi.OBS_POS AS ObservacionPostal,
                barrio.DES_BAR AS Barrio,
                calle.DES_CAL AS Calle,
                ser.NUM_MED AS NumeroMedidor,
                conser.PERIODO AS Periodo,
                conser.CONSUMO AS Consumo
            FROM PERSONAS AS persona
            LEFT JOIN FACTURAS AS factu ON persona.COD_PER = factu.COD_PER
            LEFT JOIN SUMSOC AS sumi ON factu.COD_SUM = sumi.COD_SUM
            LEFT JOIN CONS_SER AS conser ON conser.ID_FAC = factu.ID_FAC
            LEFT JOIN BARRIOS AS barrio ON sumi.COD_BAR = barrio.COD_BAR
            LEFT JOIN CALLES AS calle ON sumi.COD_CAL = calle.COD_CAL
            LEFT JOIN SERSOC AS ser ON sumi.COD_SUM = ser.COD_SUM
            WHERE persona.NUM_DNI = :dni
            ORDER BY factu.ID_FAC DESC
        """)

        result = self.session_db1.execute(consulta, {'dni': dni}).mappings().fetchall()
        if result:
            logging.info(f"Usuario con DNI {dni} encontrado en PR_CAU: {result}")
            return [dict(row) for row in result]
        else:
            logging.warning(f"Usuario con DNI {dni} no encontrado en PR_CAU")
            return []

    def existe_en_db2(self, dni: str):
        result = self.session_db2.query(Cliente).filter_by(DNI=dni).first() is not None
        logging.info(f"Verificando existencia en DECSA_EXC para DNI {dni}: {result}")
        return result

    def guardar_cliente_en_db2(self, cliente: Cliente):
        try:
            self.session_db2.add(cliente)
            self.session_db2.commit()
            logging.info(f"Cliente guardado en DECSA_EXC con DNI {cliente.DNI}")
        except Exception as e:
            self.session_db2.rollback()
            logging.error(f"Error al guardar cliente en DECSA_EXC: {str(e)}")
            raise

    def copiar_cliente_a_db2(self, dni: str):
        if self.existe_en_db2(dni):
            logging.warning(f"Cliente con DNI {dni} ya existe en DECSA_EXC")
            return self.obtener_por_dni(dni)

        datos = self.obtener_de_db1(dni)
        if not datos:
            logging.warning(f"No se encontraron datos en DB1 para DNI {dni}")
            return None

        try:
            # Asegurarse de que NOMBRE_COMPLETO tenga un valor válido
            nombre_completo = f"{datos[0].get('Apellido', '')} {datos[0].get('Nombre', '')}".strip()
            if not nombre_completo:
                logging.warning(f"NOMBRE_COMPLETO vacío para DNI {dni}, usando valor por defecto")
                nombre_completo = "Usuario Desconocido"

            # Usar el DNI pasado como parámetro si no está presente en los datos
            dni_valor = str(datos[0].get('Dni', dni)) or dni
            if not dni_valor:
                logging.error(f"No se pudo determinar el DNI para el cliente con DNI {dni}")
                raise ValueError(f"No se pudo determinar el DNI para el cliente con DNI {dni}")

            logging.info(f"Creando nuevo cliente en DB2 con DNI {dni_valor}, NOMBRE_COMPLETO: {nombre_completo}")

            nuevo_cliente = Cliente(
                DNI=dni_valor,
                NOMBRE_COMPLETO=nombre_completo,
                SEXO=datos[0].get('Sexo') or None,
                CELULAR=datos[0].get('Telefono') or None,
                EMAIL=datos[0].get('Email') or None,
                CODIGO_POSTAL=datos[0].get('CodigoPostal') or None,
                FECHA_ALTA=datos[0].get('FechaAlta') or None,
                OBSERVACIONES=datos[0].get('Observaciones') or None,
                CODIGO_SUMINISTRO=datos[0].get('CodigoSuministro', '') or '',
                NUMERO_MEDIDOR=datos[0].get('NumeroMedidor') or None,
                CALLE=datos[0].get('Calle') or None,
                BARRIO=datos[0].get('Barrio') or None
            )

            self.guardar_cliente_en_db2(nuevo_cliente)
            if not nuevo_cliente.ID_USUARIO:
                logging.error(f"ID_USUARIO no generado para cliente con DNI {dni}")
                raise ValueError(f"ID_USUARIO no generado para cliente con DNI {dni}")
            logging.info(f"Cliente copiado a DB2 con DNI {dni}, ID_USUARIO generado: {nuevo_cliente.ID_USUARIO}")
            return nuevo_cliente
        except Exception as e:
            logging.error(f"Error al copiar cliente a DB2 para DNI {dni}: {str(e)}")
            raise

    def actualizar_cliente(self, cliente: Cliente):
        try:
            self.session_db2.merge(cliente)
            self.session_db2.commit()
            logging.info(f"Cliente actualizado correctamente en DECSA_EXC con DNI {cliente.DNI}")
        except Exception as e:
            self.session_db2.rollback()
            logging.error(f"Error al actualizar cliente en DECSA_EXC: {str(e)}")
            raise