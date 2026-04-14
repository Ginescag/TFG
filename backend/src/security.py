from passlib.context import CryptContext
import secrets
import string

# Configuramos bcrypt como nuestro algoritmo de encriptación
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def generar_secreto_robot(longitud: int = 32) -> str:
    alfabeto = string.ascii_letters + string.digits
    secreto = ''.join(secrets.choice(alfabeto) for _ in range(longitud))
    # Le añadimos un prefijo para que sea fácil identificar qué es cuando lo leamos
    return f"rbt_sec_{secreto}"