import uuid
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from src.database import Base
from datetime import datetime, timezone

class Usuario(Base):
    __tablename__ = "usuarios"

    # Primary key and basic user information
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    tlf = Column(String(20))
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), default="user")  # 'admin' or 'user'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships: One user can own multiple robots
    # cascade="all, delete" ensures that if a user is deleted, their robots are deleted too
    robots = relationship("Robot", back_populates="usuario", cascade="all, delete")


class Robot(Base):
    __tablename__ = "robots"

    # String Primary Key (Useful for QR codes or Serial Numbers)
    id = Column(String(50), primary_key=True, index=True)
    
    # Foreign Key linking to the 'usuarios' table
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"))
    
    # Security and identification
    secret_hash = Column(String(255), nullable=True)
    alias = Column(String(50))
    
    # Robot statuses
    estado_conexion = Column(String(20), default="offline")
    estado_operativo = Column(String(30), default="idle")
    
    # Timestamps
    ultima_actividad = Column(DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    usuario = relationship("Usuario", back_populates="robots")
    
    # One robot can generate multiple incidents
    incidentes = relationship("Incidente", back_populates="robot", cascade="all, delete")


class Incidente(Base):
    __tablename__ = "incidentes"

    # Using UUIDs for incidents to prevent ID guessing and scale better
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Key linking to the 'robots' table (Note: robot id is a String(50))
    robot_id = Column(String(50), ForeignKey("robots.id", ondelete="CASCADE"))
    
    # Data fields
    bucket_name = Column(String(100), nullable=True)
    video_filename = Column(String(255), nullable=True)
    revisado = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    robot = relationship("Robot", back_populates="incidentes")

    @property
    def robot_alias(self):
        """Alias del robot asociado, para incluirlo en las respuestas de incidencias."""
        return self.robot.alias if self.robot else None

    # Table arguments to match the performance indexes defined in init.sql
    __table_args__ = (
        Index('idx_incidentes_robot_fecha', 'robot_id', 'created_at'),
        Index('idx_incidentes_no_revisados', 'revisado', postgresql_where=(revisado == False)),
    )