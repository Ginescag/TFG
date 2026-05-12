# Robot Workspace - Documentacion completa

Este documento describe el workspace ROS 2 del robot (robot_ws): arquitectura, tecnologias, estructura de paquetes, nodos, topicos, servicios, flujos de datos, algoritmia y configuracion con Docker.

## 1) Vision general

El workspace contiene los nodos que viven en el robot (o simulador) y que conectan ROS 2 con la infraestructura del backend. El objetivo es:

- Detectar incidentes con vision (YOLO) y enviar evidencia a MinIO y Kafka.
- Publicar telemetria periodica a Kafka.
- Orquestar patrulla autonoma (exploracion, guardado de mapa y rutas).
- Gestionar secretos y tokens JWT con un servicio ROS 2.

## 2) Tecnologias y dependencias

- ROS 2 Humble (rclpy).
- TurtleBot4/TurtleBot3 stacks y Nav2.
- OpenCV + cv_bridge para vision y video.
- Ultralytics YOLOv8 para deteccion.
- Kafka (confluent-kafka) para telemetria/incidentes.
- MinIO (boto3) para subida de videos.
- Requests para llamadas HTTP al backend.

## 3) Estructura del workspace

- robot_ws/docker-compose.yml: contenedor de desarrollo ROS 2.
- robot_ws/Dockerfile: imagen base con ROS 2 Humble y dependencias.
- robot_ws/.env: variables de entorno (Kafka, MinIO, backend, robot id).
- robot_ws/src/detect_incident: paquete ROS 2 de deteccion de incidentes.
- robot_ws/src/serve_telemetry: paquete ROS 2 de telemetria.
- robot_ws/src/secret_helper: paquete ROS 2 para secretos y JWT.
- robot_ws/src/patrol_nav: paquete ROS 2 para patrulla autonoma.

## 4) Docker y entorno

### docker-compose

El servicio `ros2_dev` monta el workspace local y habilita X11/Wayland para GUI (Gazebo, RViz). Usa `network_mode: host` para acceso directo a Kafka/MinIO/Backend desde el host.

Archivo: [robot_ws/docker-compose.yml](robot_ws/docker-compose.yml)

### Dockerfile

Basado en `osrf/ros:humble-desktop`. Instala:

- Herramientas basicas (pip, colcon, git).
- Paquetes TurtleBot 4/3, Gazebo, Nav2.
- Python deps: `confluent-kafka`, `requests`.

Archivo: [robot_ws/Dockerfile](robot_ws/Dockerfile)

### Variables de entorno

Archivo: [robot_ws/.env](robot_ws/.env)

- `MINIO_*`: acceso a almacenamiento de evidencias.
- `BACKEND_URL`: URL del backend FastAPI.
- `KAFKA_*`: broker y topicos.
- `ROBOT_ID`: identificador del robot.
- `DETECTION_CONFIDENCE_THRESHOLD`: umbral YOLO.
- `SECRET_PATH`: ruta local del secreto.

## 5) Paquete detect_incident

Archivo principal: [robot_ws/src/detect_incident/detect_incident/detect_incident.py](robot_ws/src/detect_incident/detect_incident/detect_incident.py)

### Nodo

- Nombre: `detect_incident_node`
- Suscripcion:
	- `/oakd/rgb/preview/image_raw` (sensor_msgs/Image)

### Flujo general

1) Convierte imagen ROS a OpenCV con `CvBridge`.
2) Ejecuta YOLOv8n para detectar personas.
3) Si detecta incidente, activa un buffer de frames y entra en cooldown.
4) Genera video local con OpenCV.
5) Sube video a MinIO.
6) Publica mensaje en Kafka con bucket y filename.

### Algoritmia y decisiones

- Modelo: `YOLO('yolov8n.pt')`.
- Clases objetivo: `['person']`.
- Umbral de confianza: `DETECTION_CONFIDENCE_THRESHOLD`.
- Buffer circular: `deque(maxlen=100)` para guardar frames recientes.
- Post-trigger: guarda 50 frames extra tras deteccion.
- Cooldown de 30s para evitar multiples incidentes continuos.

### Mensaje Kafka

- Topico: `KAFKA_INCIDENT_TOPIC`.
- Payload JSON:
	- `robot_id`, `bucket_name`, `video_filename`.
- Header: `Authorization: Bearer <JWT>` (pendiente de integrar via secret_helper en vez de ENV).

## 6) Paquete serve_telemetry

Archivo principal: [robot_ws/src/serve_telemetry/serve_telemetry/serve_telemetry.py](robot_ws/src/serve_telemetry/serve_telemetry/serve_telemetry.py)

### Nodo

- Nombre: `serve_telemetry_node`
- Suscripciones:
	- `/battery_state` (sensor_msgs/BatteryState)
	- `/odom` (nav_msgs/Odometry)
	- `/dock_status` (irobot_create_msgs/DockStatus)
	- `/kidnap_status` (irobot_create_msgs/KidnapStatus)
	- `/slip_status` (irobot_create_msgs/SlipStatus)
	- `/wheel_status` (irobot_create_msgs/WheelStatus)

### Telemetria enviada

Cada 1 segundo:

- `bateria`, `bateria_voltaje`
- `pos_x`, `pos_y`
- `vel_linear`, `vel_angular`
- `is_docked`, `is_kidnapped`, `is_slipping`, `wheels_enabled`
- `robot_id`, `timestamp`

### Kafka

- Topico: `KAFKA_TELEMETRY_TOPIC`.
- Header: `Authorization: Bearer <JWT>` (por ahora desde ENV).

## 7) Paquete secret_helper

Archivo principal: [robot_ws/src/secret_helper/secret_helper/secret_helper.py](robot_ws/src/secret_helper/secret_helper/secret_helper.py)

### Nodo

- Nombre: `secret_helper_node`
- Servicio ROS 2:
	- Nombre: `get_robot_token`
	- Tipo: `secret_helper/srv/GetToken`

Archivo del servicio: [robot_ws/src/secret_helper/srv/GetToken.srv](robot_ws/src/secret_helper/srv/GetToken.srv)

Campos:

- `success: bool`
- `token: string`
- `message: string`

### Algoritmia

- Lee el secreto local en `SECRET_PATH`.
- Si no existe, llama a `POST /robot/{robot_id}/first-boot` (TOFU) y guarda el secreto.
- Autentica con `POST /robot/{robot_id}/auth`.
- Refresca JWT cada hora.
- Expone el JWT via servicio ROS 2 para otros nodos.

### Flujo de autenticacion

1) `get_or_fetch_secret()` -> lectura local o first-boot.
2) `authenticate(secret)` -> obtiene `access_token`.
3) `get_token_callback()` -> sirve el JWT a otros nodos.

## 8) Paquete patrol_nav

Archivo principal: [robot_ws/src/patrol_nav/patrol_nav/patrol_nav.py](robot_ws/src/patrol_nav/patrol_nav/patrol_nav.py)

### Nodo

- Nombre: `patrol_orchestrator`
- Usa `nav2_simple_commander.BasicNavigator`.
- Suscripcion: `/odom` para detectar movimiento.
- Servicio: `/map_saver/save_map` (nav2_msgs/SaveMap).

### Maquina de estados

- `EXPLORING`: lanza explore_lite y espera a que el robot este inactivo.
- `SAVING_MAP`: guarda mapa en disco.
- `PLANNING`: genera waypoints a partir del mapa.
- `PATROLLING`: ejecuta patrulla ciclica.
- `PATROL_STOPPED`: regresa a docking y detiene.

### Algoritmia de planificacion

1) Lee mapa `.pgm` y `.yaml`.
2) Binariza para aislar espacio libre (umbral 250).
3) Erosiona para alejar el robot de paredes.
4) Construye rejilla con `grid_spacing_m`.
5) Convierte pixels a coordenadas en metros.
6) Genera ruta zig-zag para cubrir area.
7) Inserta pose de docking al inicio y final.

### Parametros clave

- `map_filepath`: ruta base para mapa guardado.
- `grid_spacing_m`: separacion entre waypoints.
- `explore_idle_secs`: tiempo de inactividad para finalizar exploracion.
- `explore_min_secs`: tiempo minimo de exploracion.
- `dock_x/y/yaw`: pose de docking.

## 9) Flujos end-to-end

### 9.1 Incident detection

1) `detect_incident_node` recibe imagen.
2) YOLO detecta persona.
3) Se crea video local.
4) Se sube a MinIO.
5) Se publica Kafka con metadata y JWT.
6) Backend crea incidente y genera URL firmada cuando el usuario lo solicita.

### 9.2 Telemetria

1) `serve_telemetry_node` lee topicos ROS.
2) Construye payload con estado actual.
3) Envia a Kafka cada 1s.
4) Backend escribe en InfluxDB.
5) Grafana visualiza.

### 9.3 Autenticacion del robot

1) `secret_helper_node` obtiene/guarda secreto.
2) Autentica contra backend y obtiene JWT.
3) Otros nodos consumen el JWT via servicio ROS 2.

## 10) Consideraciones y mejoras

- En `detect_incident` y `serve_telemetry` el JWT viene de ENV. Integrar servicio `secret_helper` para evitar variables expuestas.
- El modelo YOLO es `yolov8n` (ligero). Se puede parametrizar modelo/clases.
- El sistema de cooldown evita spam de incidentes, pero puede ajustar para escenarios de alta densidad.
- `PATROL_STOPPED` esta definido pero la transicion no se dispara desde afuera; puede integrarse con comando remoto.

## 11) Resumen

El workspace ROS 2 ofrece una capa robotica completa: vision para incidentes, telemetria en tiempo real, patrulla autonoma con mapeo, y autenticacion robusta con TOFU. Esta capa se integra con el backend via HTTP y Kafka, permitiendo control y observabilidad desde la app.
