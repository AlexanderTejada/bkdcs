# app/models/entities.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

# Tabla intermedia usuarios-roles
usuario_rol = Table(
    'UsuarioRol',
    Base.metadata,
    Column('IdUsuario', Integer, ForeignKey('Usuarios.IdUsuario', ondelete='CASCADE'), primary_key=True),
    Column('IdRol', Integer, ForeignKey('Rol.IdRol', ondelete='CASCADE'), primary_key=True),
    Column('FechaCrea', DateTime, default=datetime.now),
    Column('UsuarioCrea', String(255), nullable=False),
    Column('Anulado', Boolean, nullable=False, default=False),
    Column('UsuarioAnula', String(255), nullable=True),
    Column('FechaAnula', DateTime, nullable=True),
    Column('UsuarioModifica', String(255), nullable=True),
    Column('FechaModifica', DateTime, nullable=True)
)

class Cliente(Base):
    __tablename__ = 'Clientes'
    __bind_key__ = 'db2'

    ID_USUARIO = Column(Integer, primary_key=True)
    DNI = Column(String(20), nullable=False, unique=True)
    NOMBRE_COMPLETO = Column(String(150), nullable=False)
    SEXO = Column(String(1), nullable=True)
    CELULAR = Column(String(20), nullable=True)
    EMAIL = Column(String(100), nullable=True)
    CODIGO_POSTAL = Column(String(10), nullable=True)
    FECHA_ALTA = Column(DateTime, nullable=True)
    OBSERVACIONES = Column(String(500), nullable=True)
    CODIGO_SUMINISTRO = Column(String(50), nullable=False)
    NUMERO_MEDIDOR = Column(String(50), nullable=False)
    CALLE = Column(String(200), nullable=True)
    BARRIO = Column(String(200), nullable=True)

    reclamos = relationship("Reclamo", back_populates="cliente", lazy="joined")

    def to_dict(self, include_reclamos=False):
        data = {
            'ID_USUARIO': self.ID_USUARIO,
            'DNI': self.DNI,
            'NOMBRE_COMPLETO': self.NOMBRE_COMPLETO,
            'SEXO': self.SEXO,
            'CELULAR': self.CELULAR,
            'EMAIL': self.EMAIL,
            'CODIGO_POSTAL': self.CODIGO_POSTAL,
            'FECHA_ALTA': self.FECHA_ALTA.isoformat() if self.FECHA_ALTA else None,
            'OBSERVACIONES': self.OBSERVACIONES,
            'CODIGO_SUMINISTRO': self.CODIGO_SUMINISTRO,
            'NUMERO_MEDIDOR': self.NUMERO_MEDIDOR,
            'CALLE': self.CALLE,
            'BARRIO': self.BARRIO
        }
        if include_reclamos:
            data['reclamos'] = [r.to_dict() for r in self.reclamos]
        return data

class Reclamo(Base):
    __tablename__ = 'Reclamos'
    __bind_key__ = 'db2'

    ID_RECLAMO = Column(Integer, primary_key=True)
    ID_USUARIO = Column(Integer, ForeignKey('Clientes.ID_USUARIO'), nullable=False)
    DESCRIPCION = Column(String(500), nullable=False)
    ESTADO = Column(String(20), default="Pendiente")
    FECHA_RECLAMO = Column(DateTime, default=datetime.now)
    FECHA_CIERRE = Column(DateTime, nullable=True)

    cliente = relationship("Cliente", back_populates="reclamos")

    def to_dict(self):
        return {
            'ID_RECLAMO': self.ID_RECLAMO,
            'ID_USUARIO': self.ID_USUARIO,
            'DESCRIPCION': self.DESCRIPCION,
            'ESTADO': self.ESTADO,
            'FECHA_RECLAMO': self.FECHA_RECLAMO.isoformat() if self.FECHA_RECLAMO else None,
            'FECHA_CIERRE': self.FECHA_CIERRE.isoformat() if self.FECHA_CIERRE else None,
            'cliente': {
                'nombre': self.cliente.NOMBRE_COMPLETO if self.cliente else "Desconocido",
                'dni': self.cliente.DNI if self.cliente else "Desconocido",
                'celular': self.cliente.CELULAR if self.cliente else "N/A",
                'email': self.cliente.EMAIL if self.cliente else "N/A"
            },
            'calle': self.cliente.CALLE if self.cliente else "Sin calle",
            'barrio': self.cliente.BARRIO if self.cliente else "Sin barrio",
            'codigo_postal': self.cliente.CODIGO_POSTAL if self.cliente else "N/A",
            'numeroSuministro': self.cliente.CODIGO_SUMINISTRO if self.cliente else "N/A",
            'medidor': self.cliente.NUMERO_MEDIDOR if self.cliente else "N/A",
        }

class Rol(Base):
    __tablename__ = 'Rol'
    IdRol = Column(Integer, primary_key=True)
    Nombre = Column(String(50), nullable=False, unique=True)
    Descripcion = Column(String(255), nullable=True)
    FechaCrea = Column(DateTime, default=datetime.now)
    UsuarioCrea = Column(String(255), nullable=False)
    Anulado = Column(Boolean, nullable=False, default=False)
    FechaAnula = Column(DateTime, nullable=True)
    UsuarioAnula = Column(String(255), nullable=True)
    FechaModifica = Column(DateTime, nullable=True)
    UsuarioModifica = Column(String(255), nullable=True)
    usuarios = relationship('Usuario', secondary=usuario_rol, back_populates='roles')

    def to_dict(self):
        return {
            'IdRol': self.IdRol,
            'Nombre': self.Nombre,
            'Descripcion': self.Descripcion,
            'FechaCrea': self.FechaCrea.isoformat() if self.FechaCrea else None,
            'UsuarioCrea': self.UsuarioCrea,
            'Anulado': self.Anulado,
            'FechaAnula': self.FechaAnula.isoformat() if self.FechaAnula else None,
            'UsuarioAnula': self.UsuarioAnula,
            'FechaModifica': self.FechaModifica.isoformat() if self.FechaModifica else None,
            'UsuarioModifica': self.UsuarioModifica,
        }

class Usuario(Base):
    __tablename__ = 'Usuarios'
    IdUsuario = Column(Integer, primary_key=True)
    Usuario = Column(String(100), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    Pass = Column(String(255), nullable=False)
    FechaCrea = Column(DateTime, default=datetime.now)
    OperadorCrea = Column(String(255), nullable=False)
    Anulado = Column(Boolean, nullable=False, default=False)
    FechaAnula = Column(DateTime, nullable=True)
    UsuarioAnula = Column(String(255), nullable=True)
    FechaModifica = Column(DateTime, nullable=True)
    UsuarioModifica = Column(String(255), nullable=True)
    roles = relationship('Rol', secondary=usuario_rol, back_populates='usuarios')

    def to_dict(self):
        return {
            'IdUsuario': self.IdUsuario,
            'Usuario': self.Usuario,
            'email': self.email,
            'FechaCrea': self.FechaCrea.isoformat() if self.FechaCrea else None,
            'OperadorCrea': self.OperadorCrea,
            'Anulado': self.Anulado,
            'FechaAnula': self.FechaAnula.isoformat() if self.FechaAnula else None,
            'UsuarioAnula': self.UsuarioAnula,
            'FechaModifica': self.FechaModifica.isoformat() if self.FechaModifica else None,
            'UsuarioModifica': self.UsuarioModifica,
            'roles': [rol.to_dict() for rol in self.roles]
        }