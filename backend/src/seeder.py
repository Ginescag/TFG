import sys
import os
from uuid import uuid4

# Añadimos la carpeta actual al path para que Python encuentre el módulo 'src'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database import SessionLocal
from src.models import Usuario, Robot, Incidente
from src.security import get_password_hash, generar_secreto_robot

def seed():
    db = SessionLocal()
    try:
        print("🌱 Iniciando el sembrado de la base de datos...")

        # 1. Crear Usuario Administrador
        admin_email = "admin@tfg.com"
        admin = db.query(Usuario).filter(Usuario.email == admin_email).first()
        if not admin:
            print("👤 Creando administrador...")
            admin = Usuario(
                nombre="Admin Sistema",
                email=admin_email,
                password_hash=get_password_hash("admin123"),
                rol="admin",
                tlf="600000000"
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Crear Usuario Normal
        user_email = "user@tfg.com"
        user = db.query(Usuario).filter(Usuario.email == user_email).first()
        if not user:
            print("👤 Creando usuario normal...")
            user = Usuario(
                nombre="Ginés Piloto",
                email=user_email,
                password_hash=get_password_hash("user123"),
                rol="user",
                tlf="611222333"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 3. Crear Robots para el usuario normal
        print("🤖 Configurando robots...")
        
        # Robot 1: Ya operativo (con secreto generado)
        rbt1_id = "RBT-01"
        robot1 = db.query(Robot).filter(Robot.id == rbt1_id).first()
        rbt1_secret = generar_secreto_robot()
        if not robot1:
            robot1 = Robot(
                id=rbt1_id,
                usuario_id=user.id,
                alias="TurtleBot Salón",
                secret_hash=get_password_hash(rbt1_secret),
                estado_conexion="online",
                estado_operativo="idle"
            )
            db.add(robot1)

        # Robot 2: Nuevo (esperando First Boot)
        rbt2_id = "RBT-02"
        robot2 = db.query(Robot).filter(Robot.id == rbt2_id).first()
        if not robot2:
            robot2 = Robot(
                id=rbt2_id,
                usuario_id=user.id,
                alias="TurtleBot Pasillo",
                secret_hash=None, # Pendiente de TOFU
                estado_conexion="offline",
                estado_operativo="idle"
            )
            db.add(robot2)

        db.commit()

        # 4. Crear Incidentes de prueba para el Robot 1
        print("🚨 Generando incidentes históricos...")
        incidentes_count = db.query(Incidente).filter(Incidente.robot_id == rbt1_id).count()
        if incidentes_count == 0:
            inc1 = Incidente(
                id=uuid4(),
                robot_id=rbt1_id,
                video_url="http://localhost:9000/tfg-incidents/video1.mp4",
                revisado=False
            )
            inc2 = Incidente(
                id=uuid4(),
                robot_id=rbt1_id,
                video_url="http://localhost:9000/tfg-incidents/video2.mp4",
                revisado=True
            )
            db.add_all([inc1, inc2])
            db.commit()

        print("\n✅ ¡Base de datos poblada con éxito!")
        print("-" * 50)
        print(f"🔑 USER LOGIN: {user_email} / user123")
        print(f"🔑 ADMIN LOGIN: {admin_email} / admin123")
        print(f"🤖 ROBOT 1 ID: {rbt1_id} | SECRET: {rbt1_secret}")
        print(f"🤖 ROBOT 2 ID: {rbt2_id} | (Pendiente de First Boot)")
        print("-" * 50)

    except Exception as e:
        print(f"❌ Error durante el seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()