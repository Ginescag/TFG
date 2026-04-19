from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Usuario, Robot
from src.security import verificar_token

token_auth_scheme = HTTPBearer()

# ==========================================
# DEPENDENCIAS DE INYECCIÓN DE USUARIOS Y ROBOTS
# ==========================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(token_auth_scheme), 
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Portero para Humanos (Flutter).
    Verifica que el token sea válido y pertenezca a un Usuario registrado.
    """
    token = credentials.credentials
    user_id_str = verificar_token(token)
    
    if not user_id_str.isdigit():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Este token pertenece a un robot, no a un usuario humano."
        )
        
    usuario = db.query(Usuario).filter(Usuario.id == int(user_id_str)).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en la base de datos")
        
    return usuario


def get_current_robot(
    credentials: HTTPAuthorizationCredentials = Depends(token_auth_scheme), 
    db: Session = Depends(get_db)
) -> Robot:
    """
    Portero para Robots (TurtleBot).
    Verifica que el token sea válido y pertenezca a un Robot registrado.
    """
    token = credentials.credentials
    robot_id = verificar_token(token)
    
    if robot_id.isdigit():
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Este token pertenece a un humano, no a un robot."
        )

    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot no encontrado en la base de datos")
        
    return robot