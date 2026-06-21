from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# ==========================================
# 1. USUARIO SCHEMAS
# ==========================================

class UsuarioBase(BaseModel):
    """Base fields shared by multiple User schemas"""
    nombre: str
    email: EmailStr
    tlf: Optional[str] = None

class UsuarioRegistro(UsuarioBase):
    """Data required from Flutter to register a new user"""
    password: str  # Plain text password (will be hashed in server.py)

class UsuarioLogin(BaseModel):
    """Data required for Login"""
    email: EmailStr
    password: str

class UsuarioRespuesta(UsuarioBase):
    """Data returned to the client (NEVER include the password_hash)"""
    id: int
    rol: str
    created_at: datetime

    class Config:
        from_attributes = True  # Allows Pydantic to read SQLAlchemy objects


class UsuarioActualizar(UsuarioBase):
    """Datos recibidos para actualizar el perfil, exige la contraseña por seguridad"""
    password: str

class UsuarioActualizarPassword(BaseModel):
    """Esquema específico para actualizar SOLO la contraseña"""
    oldPassword: str
    newPassword: str

class UsuarioJWTRespuesta(BaseModel):
    """Respuesta tras un login exitoso, contiene el token y datos básicos del usuario"""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    rol: str

# ==========================================
# 2. ROBOT SCHEMAS
# ==========================================

class RobotAlta(BaseModel):
    """Data received from Flutter when pairing a new robot"""
    id: str  # Extracted from the QR code payload
    alias: Optional[str] = "Mi TurtleBot"

class RobotRespuesta(BaseModel):
    """Standard data returned when requesting robot info"""
    id: str
    alias: str
    usuario_id: int
    estado_conexion: str
    estado_operativo: str
    ultima_actividad: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class RobotFirstBootRespuesta(BaseModel):
    """Respuesta EXCLUSIVA para el Robot en su primer encendido"""
    status: str = "first_boot_completed"
    robot_id: str
    secret: str  # secret generated on first boot (TOFU) that the robot will use for future authentication


class RobotAuthParams(BaseModel):
    """Datos que envía el robot para autenticarse (ocultos en el Body)"""
    secret_key: str
class RobotJWTRespuesta(BaseModel):
    """Data returned to the robot after successful authentication, containing the JWT token"""
    access_token: str
    token_type: str = "bearer"

class RobotHeartbeat(BaseModel):
    """Data sent by the robot in each heartbeat to update its status"""
    estado_operativo: Optional[str] = None  # El robot puede enviar su nuevo estado operativo

class robotRespuestaDelete(BaseModel):
    """Data returned after successfully deleting a robot"""
    status: str = "robot_deleted"
    robot_id: str

class DashboardURLRespuesta(BaseModel):
    """URL de Grafana (filtrada al robot) que la app abre en el navegador"""
    url: str

class RobotAliasActualizar(BaseModel):
    """Body para renombrar (alias) un robot"""
    alias: str

# ==========================================
# 3. INCIDENTE SCHEMAS
# ==========================================

class IncidenteRespuesta(BaseModel):
    """Data returned when Flutter asks for the incident list"""
    id: UUID
    robot_id: str
    bucket_name: Optional[str]
    video_filename: Optional[str]
    revisado: bool
    created_at: datetime

    class Config:
        from_attributes = True

class IncidenteURLRespuesta(BaseModel):
    """Data returned when Flutter requests the video URL for an incident"""
    video_url: Optional[str] = None
