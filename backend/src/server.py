from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.config import settings
from src.database import get_db
from src.models import Usuario, Robot, Incidente
from src.schemas import UsuarioActualizar, UsuarioActualizarPassword, UsuarioBase, UsuarioLogin, UsuarioRegistro, UsuarioRespuesta, RobotAlta, RobotRespuesta, RobotFirstBootRespuesta
from src.security import get_password_hash, verify_password, generar_secreto_robot

# 1. Initialize the FastAPI application
app = FastAPI(
    title="API - Robot de Patrulla TFG",
    description="Backend for the control and telemetry of TurtleBot4",
    version="1.0.0"
)

# 2. CORS Configuration
# This is important so that Flutter 
# has permission to make requests to this backend without the browser blocking it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, set the exact Flutter URL
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, PUT, DELETE...
    allow_headers=["*"],
)

# 3. Base Endpoints
@app.get("/", tags=["Base"])
async def root():
    return {
        "mensaje": "¡Servidor FastAPI operativo!",
        "entorno": settings.environment
    }

@app.get("/health", tags=["Base"])
async def health_check():
    """
    Endpoint to check the system's health.
    Useful for the frontend or Docker to know if the backend is alive.
    """
    return {
        "status": "ok",
        "database_configured": bool(settings.database_url),
        "minio_configured": bool(settings.minio_endpoint),
        "kafka_configured": bool(settings.kafka_broker_url),
        "influxdb_configured": bool(settings.influxdb_url)
    }


# 4. ROBOT ENDPOINTS

@app.put("/robot/{robot_id}/start-patrol", tags=["Robots"])
async def start_patrol(robot_id: str):
    """
    Endpoint to start the patrol of a specific robot.
    """
    return {"status": "patrol_started", "robot_id": robot_id}

@app.put("/robot/{robot_id}/active_check", tags=["Robots"])
async def active_check(robot_id: str):
    """
    Endpoint to check if the robot is active and update its last activity timestamp.
    """
    return {"status": "active_check_successful", "robot_id": robot_id}

@app.put("/robot/{robot_id}/stop-patrol", tags=["Robots"])
async def stop_patrol(robot_id: str):
    """
    Endpoint to stop the patrol of a specific robot.
    """
    return {"status": "patrol_stopped", "robot_id": robot_id}

# THIS IS DONE BY KAFKA, BUT I LEAVE IT HERE AS AN EXAMPLE ENDPOINT FOR REAL-TIME TELEMETRY
@app.put("/robot/{robot_id}/serve-telemetry", tags=["Robots"])
async def serve_telemetry(robot_id: str):
    """
    Endpoint to serve real-time telemetry from a specific robot and upload it to influxdb.
    """
    return {"status": "telemetry_serving", "robot_id": robot_id}

# THIS IS DONE BY KAFKA, BUT I LEAVE IT HERE AS AN EXAMPLE ENDPOINT TO DETECT INCIDENTS IN REAL TIME
@app.put("/robot/{robot_id}/detect-incident", tags=["Robots"])
async def detect_incident(robot_id: str):
    """
    Endpoint to detect real-time incidents through the robot's camera.
    """
    return {"status": "incident_detection_active", "robot_id": robot_id}

@app.get("/robot/{robot_id}/incidents", tags=["Robots"])
async def list_incidents(robot_id: str):
    """
    Endpoint to list all incidents associated with a specific robot.
    """
    return {"status": "incidents_listed", "robot_id": robot_id, "incidents": []}

@app.put("/robot/{robot_id}/first-boot", tags=["Robots"])
async def first_boot(robot_id: str):
    """
    Endpoint to handle the first boot of a robot and generate its secret. TOFU
    """
    return {"status": "first_boot_completed", "robot_id": robot_id}

@app.post("/robot/{robot_id}/auth", tags=["Robots"])
async def robot_auth(robot_id: str, secret_key: str):
    """
    Endpoint para el login diario del robot.
    Compara la secret_key recibida con el secret_hash de la BD.
    Si es correcto, devuelve un Token JWT.
    """
    return {"status": "authenticated", "token": "tu_token_jwt_temporal"}

# 5. USER ENDPOINTS

@app.post(
    "/user/register", 
    response_model=UsuarioRespuesta, 
    status_code=status.HTTP_201_CREATED, 
    tags=["Users"]
)
async def register_user(user_data: UsuarioRegistro, db: Session = Depends(get_db)):
    """
    Endpoint to register a new user.
    """
    # 1. Check if the email is already in the database
    existing_user = db.query(Usuario).filter(Usuario.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # 2. Hash the plain text password
    hashed_pw = get_password_hash(user_data.password)

    # 3. Create the new user object for the database
    new_user = Usuario(
        nombre=user_data.nombre,
        tlf=user_data.tlf,
        email=user_data.email,
        password_hash=hashed_pw
    )

    # 4. Save the new user to the database
    db.add(new_user)
    db.commit()
    
    # 5. Get the new ID generated by PostgreSQL
    db.refresh(new_user)

    # 6. Return the user object (FastAPI will filter it using UsuarioRespuesta)
    return new_user

@app.post(
        "/user/login",
        response_model=UsuarioLogin,
        status_code=status.HTTP_200_OK,
        tags=["Users"]
        )
async def login_user(credentials: UsuarioLogin, db: Session = Depends(get_db)):
    """
    Endpoint to log in a user.
    """
    usuario = db.query(Usuario).filter(Usuario.email == credentials.email).first()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(credentials.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    return {"status": "login_successful", "user_id": usuario.id, "email": usuario.email, "rol": usuario.rol}

@app.get(
        "/user/{user_id}/profile",
        response_model=UsuarioRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Users"]
        )
async def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    
    """
    Endpoint to get a user's profile information.
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@app.post(
        "/user/{user_id}/new-robot",
        status_code=status.HTTP_201_CREATED,
        tags=["Robots"]
        )
async def create_robot(user_id: int, robot_data: RobotAlta, db: Session = Depends(get_db)):
    """
    Endpoint to create a new robot. without hashed secret (the secret is generated when the robot boots for the first time) TOFU
    """

    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    robotExists = db.query(Robot).filter(Robot.id == robot_data.id).first()
    if robotExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Robot with this ID already exists"
        )

    robot = Robot(
        id=robot_data.id,
        alias=robot_data.alias,
        usuario_id=user_id,
        secret_hash=None,  # The secret will be generated on the robot's first boot TOFU
        estado_conexion="offline",
        estado_operativo="idle"
    )

    db.add(robot)
    db.commit()
    db.refresh(robot)
    
    return robot


@app.get(
        "/user/{user_id}/robots",
        response_model=list[RobotRespuesta],
        status_code=status.HTTP_200_OK,
        tags=["Robots"]
        )
async def list_robots(user_id: int, db: Session = Depends(get_db)):
    """
    Endpoint to list all robots associated with a user.
    """
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user_robots = db.query(Robot).filter(Robot.usuario_id == user_id).all()

    return user_robots

@app.delete(
            "/user/{user_id}/robot/{robot_id}",
            status_code=status.HTTP_200_NO_CONTENT,
            tags=["Robots"]
            )
async def delete_robot(user_id: int, robot_id: str, db: Session = Depends(get_db)):
    """
    Endpoint to delete a specific robot.
    """

    robot = db.query(Robot).filter(Robot.id == robot_id, Robot.usuario_id == user_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not found for this user, user does not exist or robot does not exist"
        )

    db.delete(robot)
    db.commit()
    
    return {"status": "robot_deleted", "robot_id": robot_id}


@app.get("/user/{user_id}/incidents", tags=["Users"])
async def list_user_incidents(user_id: int):
    """
    Endpoint to list all incidents associated with a specific user (through their robots).
    """
    return {"status": "user_incidents_listed", "user_id": user_id, "incidents": []}

@app.put("/user/{user_id}/update-password",
         status_code=status.HTTP_200_OK,
         tags=["Users"])
async def update_password(user_id: int, password_data: UsuarioActualizarPassword, db: Session = Depends(get_db)):
    """
    Endpoint to update a user's password.
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not verify_password(password_data.oldPassword, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect current password"
        )

    user.password_hash = get_password_hash(password_data.newPassword)
    db.commit()
    db.refresh(user)
    
    return {"status": "password_updated", "msg": "Password updated successfully"}

@app.put(
        "/user/{user_id}/update-info",
        response_model=UsuarioRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Users"])
async def update_user_info(user_id: int, user_data: UsuarioActualizar, db: Session = Depends(get_db)):
    """
    Endpoint to update a user's information.
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )
    
    if user_data.mail != user.email:
        email_exists = db.query(Usuario).filter(Usuario.email == user_data.email).first()
        if email_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another account"
            )
    
    user.nombre = user_data.nombre
    user.tlf = user_data.tlf
    user.email = user_data.email
    db.commit()
    db.refresh(user)
    return user