
import datetime
import json
import threading
from uuid import UUID
import uvicorn

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from confluent_kafka import Consumer, Producer, KafkaError
import boto3

from src.dependencies import get_current_admin, get_current_user, get_current_robot
from src.config import settings
from src.database import SessionLocal, get_db
from src.models import Usuario, Robot, Incidente
from src.schemas import IncidenteRespuesta, IncidenteURLRespuesta, RobotAuthParams, RobotHeartbeat, RobotJWTRespuesta, UsuarioActualizar, UsuarioActualizarPassword, UsuarioBase, UsuarioJWTRespuesta, UsuarioLogin, UsuarioRegistro, UsuarioRespuesta, RobotAlta, RobotRespuesta, RobotFirstBootRespuesta, robotRespuestaDelete
from src.security import get_password_hash, verificar_token, verify_password, generar_secreto_robot, generate_jwt_token

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

#============================
# 3. KAFKA SETTINGS
#============================

def create_server_consumers():

    """
    Function to create Kafka consumers for incidents and telemetry.
    We will have two separate consumers to handle the different topics independently.
    """

    incident_consumer = Consumer({
        'bootstrap.servers': settings.kafka_broker_url,
        'group.id': 'incident-consumer',
        'auto.offset.reset': 'earliest'
    })
    
    incident_consumer.subscribe([settings.kafka_incident_topic])

    telemetry_consumer = Consumer({
        'bootstrap.servers': settings.kafka_broker_url,
        'group.id': 'telemetry-consumer',
        'auto.offset.reset': 'latest'
    })

    telemetry_consumer.subscribe([settings.kafka_telemetry_topic])

    producer_robot_comms = Producer({
        'bootstrap.servers': settings.kafka_broker_url
    })
    
    return incident_consumer, telemetry_consumer, producer_robot_comms

@app.on_event("startup")
async def startup_event():
    """
    This function runs when the FastAPI server starts.
    We can use it to initialize resources, such as Kafka consumers.
    """
    print("Iniciando recursos del servidor...")

    incident_consumer, telemetry_consumer, producer_robot_comms = create_server_consumers()

    app.state.producer_robot_comms = producer_robot_comms

    threading.Thread(target=detect_incident, args=(incident_consumer,), daemon=True).start()
    threading.Thread(target=serve_telemetry, args=(telemetry_consumer,), daemon=True).start()

@app.on_event("shutdown")
async def shutdown_event():
    """
    This function runs when the FastAPI server is shutting down.
    flushes and closes the Kafka producer to ensure all messages are sent before exiting.
    """
    producer : Producer = getattr(app.state, "producer_robot_comms", None)
    if producer:
        print("Cerrando Kafka producer...")
        producer.flush()
        producer.close()

#============================
# 4. ROBOT ENDPOINTS
#============================

#ROBOT --> SERVER (HEARTBEAT)
@app.put(
        "/robot/heartbeat",
        response_model=RobotRespuesta, 
        status_code=status.HTTP_200_OK,
        tags=["Robots"]
        )
async def robot_heartbeat(heartbeat: RobotHeartbeat, curr_robot: Robot = Depends(get_current_robot), db: Session = Depends(get_db)):
    """
    Endpoint de 'Latido' (Heartbeat).
    El robot llama a esta ruta cada X segundos para avisar al servidor de que sigue online.
    El campo estado_operativo es la fuente de verdad del estado real del robot:
    el servidor actualiza la DB con el valor que manda el robot, no al revés.
    """

    # Vocabulario canónico de estados operativos.
    # Debe coincidir exactamente con los strings que emite patrol_nav.py.
    VALID_OPERATIONAL_STATES = {
        "idle",        # Robot registrado pero sin mapa / recién arrancado
        "exploring",   # FSM: EXPLORING
        "saving_map",  # FSM: SAVING_MAP
        "planning",    # FSM: PLANNING
        "patrolling",  # FSM: PATROLLING
        "stopped",     # FSM: PATROL_STOPPED (en dock, patrulla detenida por el usuario)
    }

    curr_robot.estado_conexion = "online"
    if heartbeat.estado_operativo is not None:
        if heartbeat.estado_operativo not in VALID_OPERATIONAL_STATES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid estado_operativo '{heartbeat.estado_operativo}'. "
                    f"Allowed values: {sorted(VALID_OPERATIONAL_STATES)}"
                )
            )
        curr_robot.estado_operativo = heartbeat.estado_operativo

    db.commit()
    db.refresh(curr_robot)

    return curr_robot


#ROBOT --> SERVER (TELEMETRY)
def serve_telemetry(consumer: Consumer):
    """
    Endpoint to serve real-time telemetry from a specific robot and upload it to influxdb.
    Expected JSON payload example:
    {
        "robot_id": "RBT-01",
        "bateria": 85.5,
        "velocidad": 0.4,
        "pos_x": 1.25,
        "pos_y": 3.42
    """

    #=============================================================
    # Create InfluxDB client
    influx_client = InfluxDBClient(
        url=settings.influxdb_url,
        token=settings.influxdb_token,
        org=settings.influxdb_org
    )

    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    #=============================================================

    try:
        while True:
            msg = consumer.poll(1.0)

            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    print(f"Consumer Error (telemetry): {msg.error()}")
                    continue
            

            #==============================================================
            # Security check: Verify the token in the message headers to ensure it's from an authenticated robot

            headers = msg.headers()
            if not headers:
                print("MESSAGE DISCARDED: No headers found in Kafka message")
                continue

            headers_dict = {h[0]: h[1].decode('utf-8') if h[1] else None for h in headers}
            token_header = headers_dict.get("Authorization")

            if not token_header or not token_header.startswith("Bearer "):
                print("MESSAGE DISCARDED: Missing or invalid Authorization header in Kafka message")
                continue

            try:
                token_header = token_header.replace("Bearer ", "")
                robot_id_from_token = verificar_token(token_header)
            except Exception as e:
                print(f"Error verifying robot token: {e}")
                continue

            #==============================================================

            # Process the telemetry message
            try:
                telemetry_payload = json.loads(msg.value().decode('utf-8'))
            except json.JSONDecodeError:
                print("Error decoding JSON from Kafka message")
                continue

            robot_id = telemetry_payload.get("robot_id")
            robot_timestamp = telemetry_payload.get("timestamp")
            time_obj = datetime.datetime.fromtimestamp(robot_timestamp, tz=datetime.timezone.utc)
            
            if not robot_id:
                print("Invalid telemetry data received, missing robot_id")
                continue
            
            if robot_id != robot_id_from_token:
                print(f"Robot ID in message ({robot_id}) does not match robot ID from token ({robot_id_from_token}), discarding message")
                continue

            #==============================================================
            # Create a point for InfluxDB
            try:
                point = Point("robot_telemetry") \
                    .tag("robot_id", robot_id) \
                    .field("bateria", telemetry_payload.get("bateria", 0.0)) \
                    .field("bateria_voltaje", telemetry_payload.get("bateria_voltaje", 0.0)) \
                    .field("is_docked", telemetry_payload.get("is_docked", False)) \
                    .field("pos_x", telemetry_payload.get("pos_x", 0.0)) \
                    .field("pos_y", telemetry_payload.get("pos_y", 0.0)) \
                    .field("vel_linear", telemetry_payload.get("vel_linear", 0.0)) \
                    .field("vel_angular", telemetry_payload.get("vel_angular", 0.0)) \
                    .field("is_kidnapped", telemetry_payload.get("is_kidnapped", False)) \
                    .field("is_slipping", telemetry_payload.get("is_slipping", False)) \
                    .field("wheels_enabled", telemetry_payload.get("wheels_enabled", False)) \
                    .time(time_obj, WritePrecision.NS)
                
                write_api.write(bucket=settings.influxdb_bucket, org=settings.influxdb_org, record=point)

            except Exception as e:
                print(f"Error writing telemetry to InfluxDB: {e}")

    except Exception as e:
        print(f"Fatal Error in Kafka consumer loop (telemetry): {e}")
    
    finally:
        write_api.close()
        influx_client.close()
        consumer.close()

#ROBOT --> SERVER (INCIDENT DETECTION)
def detect_incident(consumer: Consumer):
    """
    Endpoint to detect real-time incidents through the robot's camera.

    Incidents come with this JSON structure:
    {
        "robot_id": "string",
        "bucket_name": "string",
        "video_filename": "string"
    }

    and this function creates an incident in the database with the received data. id, robot_id, bucket_name, video_filename, revisado (default False), created_at (timestamp)

     The robot sends the video to MinIO and then sends the bucket and object key to this endpoint.
     The server receives the bucket and object key and creates an incident in the database, which will be visible in the user's app.
     This endpoint is called by Kafka when a new message arrives in the 'incidents' topic.
     The Kafka consumer listens to the topic and calls this function for each new message.
     The function processes the message, extracts the data, and creates a new incident in the database.
     This way, we can handle incidents in real time without needing the robot to call an HTTP endpoint directly.
    """

    try:
        while True:
            msg = consumer.poll(1.0)

            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue  # Fin de la partición, sigue esperando
                else:
                    print(f"Consumer Error (incident): {msg.error()}")
                    continue
            
            #==============================================================

            headers = msg.headers()
            if not headers:
                print("MESSAGE DISCARDED: No headers found in Kafka message")
                continue

            headers_dict = {h[0]: h[1].decode('utf-8') if h[1] else None for h in headers}
            token_header = headers_dict.get("Authorization")

            if not token_header or not token_header.startswith("Bearer "):
                print("MESSAGE DISCARDED: Missing or invalid Authorization header in Kafka message")
                continue
            
            token_header = token_header.replace("Bearer ", "")

            try:
                robot_token = verificar_token(token_header)
            except Exception as e:
                print(f"Error verifying robot token: {e}")
                continue

            #==============================================================

            # Procesar el mensaje recibido
            try:
                incident_payload = json.loads(msg.value().decode('utf-8'))
            except json.JSONDecodeError:
                print("Error decoding JSON from Kafka message")
                continue

            robot_id = incident_payload.get("robot_id")
            bucket_name = incident_payload.get("bucket_name")
            video_filename = incident_payload.get("video_filename")

            if not robot_id or not bucket_name or not video_filename:
                print("Invalid incident data received, missing required fields")
                continue
            
            #this is a security check to ensure that the robot_id in the message matches the robot_id from the token, preventing spoofing
            if robot_id != robot_token:
                print(f"Robot ID in message ({robot_id}) does not match robot ID from token ({robot_token}), discarding message") #
                continue

            #==============================================================


            db: Session = SessionLocal()
            try:
                new_incident = Incidente(
                    robot_id=robot_id,
                    bucket_name=bucket_name,
                    video_filename=video_filename,
                    revisado=False
                )
                db.add(new_incident)
                db.commit()
            
            except Exception as e:
                db.rollback()
                print(f"Error saving incident to database: {e}")

            finally:
                db.close()

            #HERE WE CAN ADD LOGIC TO WARN THE USER IN REAL TIME THROUGH WEBSOCKETS OR PUSH NOTIFICATIONS

    except Exception as e:
        print(f"Fatal Error in Kafka consumer loop (incidents): {e}")

    finally:
        consumer.close()

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

#============================
# 5. USER ENDPOINTS
#============================

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
    token = generate_jwt_token(str(usuario.id))

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
            "/user/{robot_id}/delete",
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

#USER --> SERVER --> ROBOT
@app.put(
        "/user/{robot_id}/start-patrol",
        response_model=RobotRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Robots"]
        )
async def start_patrol(robot_id: str, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
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
    

    #ROBOT CAN ONLY START PATROLLING IF IT IS IN:
    #idle (never patrolled or just finished first boot)
    #stopped (patrol robot that was stopped by the user, now wants to resume)
    ALLOWED_STATES_FOR_START = {"idle", "stopped"}
    if robot.estado_operativo not in ALLOWED_STATES_FOR_START:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot start patrol: robot is currently '{robot.estado_operativo}'. "
                f"The robot must be in one of {ALLOWED_STATES_FOR_START} before patrol can be started."
            )
        )

    #logic to notify the robot in real time that it should start patrolling can be added here (kafka)
    
    producer : Producer = app.state.producer_robot_comms

    command_payload = {
        "robot_id": robot_id,
        "command": "start_patrol",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    try:
        producer.produce(
            topic=settings.kafka_robot_commands_topic,
            key=robot_id,
            value=json.dumps(command_payload).encode('utf-8'),
        )
        
        producer.flush(timeout=5.0)  # Trigger delivery of the message
    
    except Exception as e:
        print(f"Error sending START command to Kafka: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send command to robot"
        )

    # robot.estado_operativo = "patrolling"
    # db.commit()
    # db.refresh(robot)

    return robot

#USER --> SERVER --> ROBOT
@app.put(
        "/user/{robot_id}/stop-patrol",
        response_model=RobotRespuesta,
        status_code=status.HTTP_200_OK, 
        tags=["Robots"]
        )
async def stop_patrol(robot_id: str, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
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
    
    STOPPABLE_STATES = {"patrolling"}  # Define the states from which the robot can be stopped
    if robot.estado_operativo not in STOPPABLE_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot stop patrol: robot is currently '{robot.estado_operativo}'. "
                f"Only robots {STOPPABLE_STATES} can be stopped."
            )
        )

    #logic to notify the robot in real time that it should stop patrolling can be added here (kafka)

    producer : Producer = app.state.producer_robot_comms

    command_payload = {
        "robot_id": robot_id,
        "command": "stop_patrol",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    try:
        producer.produce(
            topic=settings.kafka_robot_commands_topic,
            key=robot_id,
            value=json.dumps(command_payload).encode('utf-8'),
        )
        
        producer.flush(timeout=5.0)  # Trigger delivery of the message
    except Exception as e:
        print(f"Error sending STOP command to Kafka: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send command to robot"
        )
    
    # robot.estado_operativo = "stopped"
    # db.commit()
    # db.refresh(robot)

    return robot

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

#USER --> SERVER
@app.get(
        "/user/{robot_id}/incidents",
        response_model=list[IncidenteRespuesta],
        status_code=status.HTTP_200_OK,
        tags=["Robots"]
        )
async def list_robot_incidents(robot_id: str,current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
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
    
    incidentes = db.query(Incidente).filter(Incidente.robot_id == robot_id).all()

    return incidentes

@app.get(
        "/user/incidents/{incident_id}/show-video",
        response_model=IncidenteURLRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Users"]
)
async def get_incident_video(id: UUID, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to get the video URL of a specific incident.
    """

    incident = db.query(Incidente).join(Robot).filter(Incidente.id == id, Robot.usuario_id == current_user.id).first()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found or you do not have permission to view it"
        )
    
    if not incident.bucket_name or not incident.video_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video information for this incident is incomplete"
        )
    
    # Generate a presigned URL for the video in MinIO with boto3

    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key
        )

        video_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': incident.bucket_name,
                'Key': incident.video_filename
                },
            ExpiresIn=3600  # URL expires in 1 hour
        )
    except Exception as e:
        print(f"Error generating presigned URL for incident video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate video URL"
        )

    return IncidenteURLRespuesta(video_url=video_url)

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

#================================
# ADMIN ENDPOINTS
#================================

@app.get(
        "/admin/robots",
        response_model=list[RobotRespuesta],
        status_code=status.HTTP_200_OK,
        tags=["Admin"]
)
async def admin_list_robots(current_admin: Usuario = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    Admin endpoint to list all robots in the system.
    """
    robots = db.query(Robot).all()
    return robots

@app.get(
        "/admin/robots/{robot_id}/incidents",
        response_model=list[IncidenteRespuesta],
        status_code=status.HTTP_200_OK,
        tags=["Admin"]
        )
async def admin_list_robot_incidents(
    robot_id: str,
    current_admin: Usuario = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to list all incidents for a specific robot.
    """
    incidents = db.query(Incidente).filter(Incidente.robot_id == robot_id).all()
    return incidents

@app.get(
        "/admin/users",
        response_model=list[UsuarioRespuesta],
        status_code=status.HTTP_200_OK,
        tags=["Admin"])
async def admin_list_users(current_admin: Usuario = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    Admin endpoint to list all users in the system.
    """
    users = db.query(Usuario).all()
    return users

@app.delete(
        "/admin/users/{user_id}/delete",
        status_code=status.HTTP_200_OK,
        tags=["Admin"]
)
async def admin_delete_user(
    user_id: int, 
    current_admin: Usuario = Depends(get_current_admin), 
    db: Session = Depends(get_db)
):
    """
    Endpoint para borrar un usuario del sistema por completo.
    (Esto borrará también sus robots e incidentes en cascada).
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    
    # Protección: Un admin no puede suicidarse digitalmente
    if user.id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes borrar tu propia cuenta de administrador")

    db.delete(user)
    db.commit()
    return {"status": "user_deleted", "user_id": user_id}

@app.delete(
        "/admin/robots/{robot_id}/delete",
        status_code=status.HTTP_200_OK,
        tags=["Admin"]
)
async def admin_delete_robot(
    robot_id: str, 
    current_admin: Usuario = Depends(get_current_admin), 
    db: Session = Depends(get_db)
):
    """
    Endpoint para que el Admin borre cualquier robot (sin importar de quién sea).
    """
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot no encontrado")

    db.delete(robot)
    db.commit()
    return {"status": "robot_deleted", "robot_id": robot_id}

@app.put(
        "/admin/users/{user_id}/grant",
        response_model=UsuarioRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Admin"]
)
async def admin_grant_permissions(
    user_id: int, 
    current_admin: Usuario = Depends(get_current_admin), 
    db: Session = Depends(get_db)
):
    """
    Ascender a un usuario normal al rango de Administrador.
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if user.rol == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario ya es administrador")

    user.rol = "admin"
    db.commit()
    db.refresh(user)
    
    return user

@app.put(
        "/admin/users/{user_id}/revoke",
        response_model=UsuarioRespuesta,
        status_code=status.HTTP_200_OK,
        tags=["Admin"]
)
async def admin_revoke_permissions(
    user_id: int, 
    current_admin: Usuario = Depends(get_current_admin), 
    db: Session = Depends(get_db)
):
    """
    Degradar a un Administrador al rango de usuario normal.
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if user.id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes revocar tus propios permisos de administrador")

    if user.rol == "user":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario ya tiene el rol base")

    user.rol = "user"
    db.commit()
    db.refresh(user)
    
    return user

if __name__ == "__main__":    
    print("🌐 Arrancando servidor FastAPI...")
    uvicorn.run(app, host="0.0.0.0", port=8000) 