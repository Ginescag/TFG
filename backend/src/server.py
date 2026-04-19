import datetime

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.dependencies import get_current_user, get_current_robot
from src.config import settings
from src.database import get_db
from src.models import Usuario, Robot, Incidente
from src.schemas import IncidenteRespuesta, RobotAuthParams, RobotHeartbeat, RobotJWTRespuesta, UsuarioActualizar, UsuarioActualizarPassword, UsuarioBase, UsuarioJWTRespuesta, UsuarioLogin, UsuarioRegistro, UsuarioRespuesta, RobotAlta, RobotRespuesta, RobotFirstBootRespuesta, robotRespuestaDelete
from src.security import get_password_hash, verify_password, generar_secreto_robot, generate_jwt_token

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

#USER --> SERVER --> ROBOT
@app.put(
        "/robot/{robot_id}/start-patrol",
        response_model=RobotRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Robots"]
        )
async def start_patrol(robot_id: str,current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to start the patrol of a specific robot.
    """

    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not found"
        )
    
    if robot.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to control this robot"
        )

    robot.estado_operativo = "patrolling"
    db.commit()
    db.refresh(robot)

    return robot

#ROBOT --> SERVER (HEARTBEAT)
@app.put(
        "/robot/{robot_id}/heartbeat",  # ¡Mucho más claro!
        response_model=RobotRespuesta, 
        status_code=status.HTTP_200_OK,
        tags=["Robots"]
        )
async def robot_heartbeat(robot_id: str, heartbeat: RobotHeartbeat, db: Session = Depends(get_db)):
    """
    Endpoint de 'Latido' (Heartbeat).
    El robot llama a esta ruta cada X segundos para avisar al servidor de que sigue online.
    """
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not found"
        )
        
    robot.estado_conexion = "online" 
    if heartbeat.estado_operativo is not None:
        robot.estado_operativo = heartbeat.estado_operativo
    db.commit()
    db.refresh(robot)
    
    return robot

#USER --> SERVER --> ROBOT
@app.put(
        "/robot/{robot_id}/stop-patrol",
        response_model=RobotRespuesta,
        status_code=status.HTTP_200_OK, 
        tags=["Robots"]
        )
async def stop_patrol(robot_id: str,current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to stop the patrol of a specific robot.
    """
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not found"
        )
    
    if robot.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to control this robot"
        )

    robot.estado_operativo = "idle"
    db.commit()
    db.refresh(robot)
    return robot

#ROBOT --> SERVER (TELEMETRY)
# THIS IS DONE BY KAFKA, BUT I LEAVE IT HERE AS AN EXAMPLE ENDPOINT FOR REAL-TIME TELEMETRY
@app.put("/robot/{robot_id}/serve-telemetry", tags=["Robots"])
async def serve_telemetry(robot_id: str):
    """
    Endpoint to serve real-time telemetry from a specific robot and upload it to influxdb.
    """
    return {"status": "telemetry_serving", "robot_id": robot_id}


#ROBOT --> SERVER (INCIDENT DETECTION)
# THIS IS DONE BY KAFKA, BUT I LEAVE IT HERE AS AN EXAMPLE ENDPOINT TO DETECT INCIDENTS IN REAL TIME
@app.put("/robot/{robot_id}/detect-incident", tags=["Robots"])
async def detect_incident(robot_id: str):
    """
    Endpoint to detect real-time incidents through the robot's camera.
    """
    return {"status": "incident_detection_active", "robot_id": robot_id}

#USER --> SERVER
@app.get("/robot/{robot_id}/incidents",
        response_model=list[IncidenteRespuesta],
        status_code=status.HTTP_200_OK,
        tags=["Robots"]
        )
async def list_incidents(robot_id: str,current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to list all incidents associated with a specific robot.
    """

    robot = db.query(Robot).filter(Robot.id == robot_id).first()

    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not found"
        )
    
    if robot.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view incidents for this robot"
        )
    
    Incidentes = db.query(Incidente).filter(Incidente.robot_id == robot_id).all()

    return Incidentes

#ROBOT --> SERVER (FIRST BOOT TO GENERATE SECRET) TOFU
@app.post(
        "/robot/{robot_id}/first-boot",
        response_model=RobotFirstBootRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Robots"]
        )
async def first_boot(robot_id: str, db: Session = Depends(get_db)):
    """
    Endpoint to handle the first boot of a robot and generate its secret. TOFU
    """

    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not yet registered."
        )
    
    if robot.secret_hash is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="First boot already completed for this robot."
        )
    
    # Generate a unique secret for the robot
    secret = generar_secreto_robot()
    robot.secret_hash = get_password_hash(secret)
    db.commit()
    db.refresh(robot)

    robot_response = RobotFirstBootRespuesta(robot_id=robot_id, secret=secret)
    
    return robot_response

#ROBOT --> SERVER (AUTHENTICATION EVERY TIME IT BOOTS)    
@app.post(
        "/robot/{robot_id}/auth",
        response_model=RobotJWTRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Robots"])
async def robot_auth(robot_id: str, auth: RobotAuthParams, db: Session = Depends(get_db)):
    """
    Endpoint para el login diario del robot.
    Compara la secret_key recibida con el secret_hash de la BD.
    Si es correcto, devuelve un Token JWT.
    """

    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not found"
        )
    
    if not robot.secret_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Robot has not completed first boot process yet, no secret generated"
        )

    if not verify_password(auth.secret_key, robot.secret_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret key"
        )

    # Generate a JWT token for the robot
    token = generate_jwt_token(robot_id)

    return RobotJWTRespuesta(access_token=token)

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
        response_model=UsuarioJWTRespuesta,
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
    
    # Generate a JWT token for the user
    token = generate_jwt_token(usuario.id)

    return UsuarioJWTRespuesta(
        access_token=token,
        user_id=usuario.id,
        rol=usuario.rol
    )

@app.get(
        "/user/profile",
        response_model=UsuarioRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Users"]
        )
async def get_user_profile(current_user: Usuario = Depends(get_current_user)):
    
    """
    Endpoint to get a user's profile information.
    """
    return current_user

@app.post(
        "/user/new-robot",
        response_model=RobotRespuesta,
        status_code=status.HTTP_201_CREATED,
        tags=["Robots"]
        )
async def create_robot(robot_data: RobotAlta, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to create a new robot. without hashed secret (the secret is generated when the robot boots for the first time) TOFU
    """

    robotExists = db.query(Robot).filter(Robot.id == robot_data.id).first()
    if robotExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Robot with this ID already exists"
        )

    robot = Robot(
        id=robot_data.id,
        alias=robot_data.alias,
        usuario_id=current_user.id,
        secret_hash=None,  # The secret will be generated on the robot's first boot TOFU
        estado_conexion="offline",
        estado_operativo="idle"
    )

    db.add(robot)
    db.commit()
    db.refresh(robot)
    
    return robot

@app.get(
        "/user/robots",
        response_model=list[RobotRespuesta],
        status_code=status.HTTP_200_OK,
        tags=["Robots"]
        )
async def list_robots(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to list all robots associated with a user.
    """

    user_robots = db.query(Robot).filter(Robot.usuario_id == current_user.id).all()

    return user_robots

@app.delete(
            "/user/robot/{robot_id}/delete",
            response_model=robotRespuestaDelete,
            status_code=status.HTTP_200_OK,
            tags=["Robots"]
            )
async def delete_robot(robot_id: str, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to delete a specific robot.
    """

    robot = db.query(Robot).filter(Robot.id == robot_id, Robot.usuario_id == current_user.id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not found for this user or robot does not exist"
        )

    db.delete(robot)
    db.commit()
    
    return robotRespuestaDelete(robot_id=robot_id)  # Devuelve el ID del robot eliminado para que Flutter pueda actualizar su UI

@app.get(
        "/user/incidents",
        response_model=list[IncidenteRespuesta],
        status_code=status.HTTP_200_OK,
        tags=["Users"]
        )
async def list_user_incidents(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to list all incidents associated with a specific user (through their robots).
    """

    total_incidents = db.query(Incidente).join(Robot).filter(Robot.usuario_id == current_user.id).all()    

    return total_incidents

@app.put(
        "/user/update-password",
        response_model=UsuarioRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Users"]
        )
async def update_password(
    password_data: UsuarioActualizarPassword, 
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint to update a user's password.
    """
    if not verify_password(password_data.oldPassword, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect current password"
        )

    if password_data.oldPassword == password_data.newPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the old password"
        )
    
    if password_data.newPassword.strip() == "" or len(password_data.newPassword) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters long and cannot be empty"
        )
    
    current_user.password_hash = get_password_hash(password_data.newPassword)
    db.commit()
    db.refresh(current_user)
    
    return current_user


@app.put(
        "/user/update-info",
        response_model=UsuarioRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Users"]
        )
async def update_user_info(
    user_data: UsuarioActualizar,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint to update a user's information.
    """
    if not verify_password(user_data.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )
    
    if user_data.email != current_user.email:
        email_exists = db.query(Usuario).filter(Usuario.email == user_data.email).first()
        if email_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another account"
            )
            
    # Asignación directa, el esquema ya garantiza que no son None
    current_user.nombre = user_data.nombre
    current_user.email = user_data.email
    if user_data.tlf:
        current_user.tlf = user_data.tlf
    
    db.commit()
    db.refresh(current_user)
    return current_user