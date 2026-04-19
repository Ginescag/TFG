from http.client import HTTPException, status

from passlib.context import CryptContext
import secrets
import string
import jwt
from datetime import datetime, timedelta, timezone
from src.config import settings

# ==========================================
# 1. CONFIGURACIÓN DE CRIPTOGRAFÍA (Contraseñas)
# ==========================================
# Configuramos bcrypt como nuestro algoritmo de encriptación unidireccional
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Convierte una contraseña en texto plano en un hash irreversible."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara una contraseña en texto plano con un hash de la base de datos."""
    return pwd_context.verify(plain_password, hashed_password)

def generar_secreto_robot(longitud: int = 32) -> str:
    """Genera una llave maestra aleatoria para el protocolo TOFU de los robots."""
    alfabeto = string.ascii_letters + string.digits
    secreto = ''.join(secrets.choice(alfabeto) for _ in range(longitud))
    # Le añadimos un prefijo para identificar fácilmente qué tipo de clave es
    return f"rbt_sec_{secreto}"

# ==========================================
# 2. CONFIGURACIÓN DE TOKENS (JWT)
# ==========================================

def generate_jwt_token(subject: str) -> str:
    """
    Genera un Token JWT firmado matemáticamente.
    Sirve para identificar tanto a robots (robot_id) como a humanos (user_id).
    """
    # 1. Calculamos la fecha de caducidad
    tiempo_expiracion = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    # 2. Construimos el Payload (El contenido público del token)
    payload = {
        "sub": str(subject),       # 'Subject': El identificador de quien se loguea
        "exp": tiempo_expiracion   # 'Expiration': Fecha límite de validez
    }
    
    # 3. Fabricamos y firmamos el token usando PyJWT
    token_firmado = jwt.encode(
        payload, 
        settings.secret_key, 
        algorithm=settings.algorithm
    )
    
    return token_firmado


def verificar_token(token: str) -> str:
    """
    Decodifica el token y extrae el 'sub' (Sujeto).
    Lanza errores automáticos si el token es falso o está caducado.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        subject = payload.get("sub")
        if not subject:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin ID (subject)")
        return subject
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El token ha caducado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o corrupto")