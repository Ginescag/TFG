# Backend TFG - Documentacion completa

Este documento describe en detalle el backend del TFG "Robot de patrulla": arquitectura, tecnologias, estructura de ficheros, modelos de datos, flujos de eventos, seguridad, algoritmia aplicada y el catalogo de endpoints. La implementacion esta basada en FastAPI e integra PostgreSQL, Kafka, MinIO, InfluxDB y Grafana.

## 1) Vision general y responsabilidades

El backend actua como orquestador entre tres actores principales:

- Aplicacion de usuario (Flutter): gestiona usuarios, robots, estado operativo y revisa incidentes.
- Robot (TurtleBot4): autentica, envia latidos, publica telemetria e incidentes.
- Infraestructura de datos: almacena estado relacional (PostgreSQL), telemetria temporal (InfluxDB) y ficheros de video (MinIO).

Objetivos clave:

- Autenticacion dual (usuarios humanos y robots) con JWT.
- Protocolo TOFU (Trust On First Use) para secret del robot.
- Procesamiento asincrono de telemetria e incidentes via Kafka.
- Emision de URLs firmadas para descargar videos de incidentes.

## 2) Tecnologias y librerias

- FastAPI: API asincrona y tipada.
- Uvicorn: servidor ASGI.
- SQLAlchemy + psycopg2: ORM y driver PostgreSQL.
- Alembic: migraciones (listado en requirements, no se usa en codigo actual).
- Kafka (confluent-kafka): mensajeria de telemetria e incidentes.
- InfluxDB 2.x: series temporales de telemetria.
- MinIO + boto3: almacenamiento de videos y URLs firmadas.
- PyJWT + passlib[bcrypt]: autenticacion y hashing.
- Pydantic + pydantic-settings: validacion de datos y configuracion.

## 3) Estructura de ficheros

Carpeta backend:

- backend/docker-compose.yml: infraestructura local (PostgreSQL, Kafka, InfluxDB, MinIO, Grafana).
- backend/init.sql: esquema SQL inicial (tablas e indices).
- backend/requirements.txt: dependencias del backend.
- backend/.env: variables de entorno (no versionar en produccion).
- backend/src/config.py: definicion de Settings y carga de .env.
- backend/src/database.py: motor SQLAlchemy, session factory y dependencia get_db.
- backend/src/models.py: modelos ORM (Usuario, Robot, Incidente).
- backend/src/schemas.py: esquemas Pydantic para requests/responses.
- backend/src/security.py: hashing, generacion de secretos y JWT.
- backend/src/dependencies.py: dependencias de autenticacion (usuario/robot/admin).
- backend/src/server.py: aplicacion FastAPI, endpoints y consumidores Kafka.
- backend/src/seeder.py: poblado de datos de ejemplo.

## 4) Configuracion y entorno

Archivo de entorno [.env](backend/.env) con:

- Configuracion de servidor (host/port y environment).
- Credenciales y URL de PostgreSQL.
- Broker y topicos Kafka.
- Endpoint y credenciales de MinIO.
- Credenciales y token de InfluxDB.
- Credenciales de Grafana.
- Clave secreta JWT y expiracion.

En [backend/src/config.py](backend/src/config.py) se define la clase Settings y se carga desde .env con Pydantic Settings.

## 5) Infraestructura con Docker Compose

El archivo [backend/docker-compose.yml](backend/docker-compose.yml) levanta:

- PostgreSQL 17 con init.sql.
- Zookeeper + Kafka.
- InfluxDB 2.7.
- MinIO (S3 compatible).
- Grafana (visualizacion sobre InfluxDB).
- init-kafka crea topicos en el arranque.

Los datos persisten en volumenes Docker (postgres_data, influxdb_data, minio_data, grafana_data).

## 6) Modelo de datos (PostgreSQL)

### Tablas y relaciones

- usuarios
	- id (PK), nombre, tlf, email (unique), password_hash, rol, created_at.
	- Relacion 1-N con robots.

- robots
	- id (PK string), usuario_id (FK usuarios), secret_hash, alias.
	- estado_conexion (online/offline) y estado_operativo (idle/patrolling/etc).
	- ultima_actividad, created_at.
	- Relacion 1-N con incidentes.

- incidentes
	- id (UUID), robot_id (FK robots).
	- bucket_name, video_filename, revisado, created_at.
	- Indices por (robot_id, created_at) y revisado=false.

Los modelos ORM estan en [backend/src/models.py](backend/src/models.py).

Notas de implementacion:

- Se usa UUID para incidentes para evitar enumeracion de IDs.
- Se configura cascade delete en relaciones, garantizando limpieza de robots e incidentes cuando se elimina un usuario.
- Existe un mismatch entre init.sql y el ORM: init.sql usa la columna file_name, mientras que el ORM usa video_filename. Si el esquema inicial se usa tal cual, conviene alinear el nombre para evitar errores en queries o inserciones.

## 7) Seguridad y autenticacion

### Hashing de contraseñas

En [backend/src/security.py](backend/src/security.py) se usa passlib con bcrypt:

- `get_password_hash(password)` devuelve hash irreversible.
- `verify_password(plain, hash)` valida contraseñas.

### JWT

- `generate_jwt_token(subject)` firma el token con `settings.secret_key` y `HS256`.
- `verificar_token(token)` valida firma y expiracion, y devuelve `sub`.
- El campo `sub` contiene el id del usuario (entero) o el id del robot (string).

### Autorizacion

Dependencias en [backend/src/dependencies.py](backend/src/dependencies.py):

- `get_current_user`: exige token valido y que `sub` sea numerico.
- `get_current_robot`: exige token valido y que `sub` no sea numerico.
- `get_current_admin`: requiere rol `admin`.

### TOFU (Trust On First Use)

Flujo:

1) Usuario da de alta el robot (`/user/new-robot`) sin secret.
2) Robot arranca por primera vez y llama a `/robot/{robot_id}/first-boot`.
3) Servidor genera un secret y lo devuelve solo una vez.
4) Robot usa ese secret en cada boot para pedir JWT en `/robot/{robot_id}/auth`.

## 8) Mensajeria y flujos asincronos (Kafka)

Hay dos consumidores en [backend/src/server.py](backend/src/server.py):

- `detect_incident`: consume del topico de incidentes. Cada mensaje genera un registro en PostgreSQL.
- `serve_telemetry`: consume telemetria y la escribe en InfluxDB.

Ambos consumidores validan el token JWT enviado en headers Kafka (`Authorization: Bearer ...`) y comparan el robot_id del mensaje con el `sub` del token. Esto evita spoofing en mensajes.

## 9) Algoritmia y logica principal

### 9.1 Latido del robot

El endpoint `/robot/heartbeat` actualiza estado de conexion y estado operativo, permitiendo a la app saber si el robot esta vivo. No se usa expiracion por tiempo; se actualiza el estado en cada latido.

### 9.2 Telemetria a InfluxDB

En `serve_telemetry`:

- Consume mensajes de Kafka.
- Valida token JWT y robot_id.
- Parseo JSON.
- Crea un `Point` con tags y fields (bateria, voltaje, posicion, velocidades, flags).
- Usa `WritePrecision.NS` y timestamp del robot.

Esto permite:

- Consultas temporales con alta resolucion.
- Dashboards en Grafana.

### 9.3 Registro de incidentes

En `detect_incident`:

- Consume mensajes de Kafka con `robot_id`, `bucket_name`, `video_filename`.
- Valida JWT y coherencia del robot_id.
- Inserta en PostgreSQL un incidente con `revisado=false`.
- Se deja el hook para notificaciones en tiempo real.

### 9.4 URLs firmadas para video

En `/user/incidents/{incident_id}/show-video`:

- Verifica que el incidente pertenece al usuario autenticado.
- Genera URL firmada con boto3 contra MinIO.
- Validez de 1 hora.

## 10) Esquemas Pydantic

Definidos en [backend/src/schemas.py](backend/src/schemas.py). Principales:

- Usuario: `UsuarioBase`, `UsuarioRegistro`, `UsuarioLogin`, `UsuarioRespuesta`, `UsuarioActualizar`, `UsuarioActualizarPassword`, `UsuarioJWTRespuesta`.
- Robot: `RobotAlta`, `RobotRespuesta`, `RobotFirstBootRespuesta`, `RobotAuthParams`, `RobotJWTRespuesta`, `RobotHeartbeat`, `robotRespuestaDelete`.
- Incidente: `IncidenteRespuesta`, `IncidenteURLRespuesta`.

## 11) Endpoints (catalogo completo)

Notas generales:

- Autenticacion via `Authorization: Bearer <token>`.
- `token` puede pertenecer a usuario o robot segun el endpoint.

### 11.1 Base

- `GET /`
	- Auth: no
	- Descripcion: confirma que la API esta levantada y expone el entorno activo.
	- Respuesta: mensaje y entorno.

- `GET /health`
	- Auth: no
	- Descripcion: chequeo rapido de configuraciones criticas (DB, Kafka, Influx, MinIO).
	- Respuesta: estado y flags de servicios configurados.

### 11.2 Robots

- `PUT /robot/heartbeat`
	- Auth: robot
	- Descripcion: actualiza el estado de conexion/operativo del robot en la BD.
	- Body: `RobotHeartbeat` (estado_operativo opcional).
	- Respuesta: `RobotRespuesta`.

- `POST /robot/{robot_id}/first-boot`
	- Auth: no
	- Descripcion: genera el secret inicial (TOFU) para un robot ya registrado.
	- Body: ninguno.
	- Respuesta: `RobotFirstBootRespuesta` (devuelve secret una vez).

- `POST /robot/{robot_id}/auth`
	- Auth: no
	- Descripcion: autentica al robot con su secret y devuelve un JWT.
	- Body: `RobotAuthParams` (secret_key).
	- Respuesta: `RobotJWTRespuesta`.

### 11.3 Usuarios

- `POST /user/register`
	- Auth: no
	- Descripcion: crea un usuario con credenciales y datos basicos.
	- Body: `UsuarioRegistro`.
	- Respuesta: `UsuarioRespuesta`.

- `POST /user/login`
	- Auth: no
	- Descripcion: valida credenciales y entrega un JWT de usuario.
	- Body: `UsuarioLogin`.
	- Respuesta: `UsuarioJWTRespuesta`.

- `GET /user/profile`
	- Auth: usuario
	- Descripcion: devuelve el perfil del usuario autenticado.
	- Respuesta: `UsuarioRespuesta`.

- `PUT /user/update-info`
	- Auth: usuario
	- Descripcion: actualiza datos del perfil tras validar la password actual.
	- Body: `UsuarioActualizar` (exige password).
	- Respuesta: `UsuarioRespuesta`.

- `PUT /user/update-password`
	- Auth: usuario
	- Descripcion: cambia la password verificando la anterior.
	- Body: `UsuarioActualizarPassword`.
	- Respuesta: `UsuarioRespuesta`.

- `GET /user/incidents`
	- Auth: usuario
	- Descripcion: lista todos los incidentes asociados al usuario (via sus robots).
	- Respuesta: lista de `IncidenteRespuesta`.

- `GET /user/incidents/{incident_id}/show-video`
	- Auth: usuario
	- Descripcion: genera URL firmada temporal para ver el video del incidente.
	- Respuesta: `IncidenteURLRespuesta`.

### 11.4 Robots asociados a usuario

- `POST /user/new-robot`
	- Auth: usuario
	- Descripcion: registra un robot en el sistema (sin secret hasta el first-boot).
	- Body: `RobotAlta`.
	- Respuesta: `RobotRespuesta`.

- `GET /user/robots`
	- Auth: usuario
	- Descripcion: lista los robots vinculados al usuario.
	- Respuesta: lista de `RobotRespuesta`.

- `DELETE /user/{robot_id}/delete`
	- Auth: usuario
	- Descripcion: elimina un robot del usuario y sus incidentes asociados.
	- Respuesta: `robotRespuestaDelete`.

- `PUT /user/{robot_id}/start-patrol`
	- Auth: usuario
	- Descripcion: cambia el estado operativo del robot a patrulla.
	- Respuesta: `RobotRespuesta` (estado_operativo="patrolling").

- `PUT /user/{robot_id}/stop-patrol`
	- Auth: usuario
	- Descripcion: detiene la patrulla y devuelve el robot a estado idle.
	- Respuesta: `RobotRespuesta` (estado_operativo="idle").

- `GET /user/{robot_id}/incidents`
	- Auth: usuario
	- Descripcion: lista incidentes de un robot concreto del usuario.
	- Respuesta: lista de `IncidenteRespuesta`.

### 11.5 Admin

- `GET /admin/robots`
	- Auth: admin
	- Descripcion: lista todos los robots del sistema.
	- Respuesta: lista de `RobotRespuesta`.

- `GET /admin/robots/{robot_id}/incidents`
	- Auth: admin
	- Descripcion: lista incidentes de cualquier robot.
	- Respuesta: lista de `IncidenteRespuesta`.

- `GET /admin/users`
	- Auth: admin
	- Descripcion: lista todos los usuarios registrados.
	- Respuesta: lista de `UsuarioRespuesta`.

- `DELETE /admin/users/{user_id}/delete`
	- Auth: admin
	- Descripcion: elimina un usuario y su arbol de robots/incidentes.
	- Respuesta: estado y user_id.

- `DELETE /admin/robots/{robot_id}/delete`
	- Auth: admin
	- Descripcion: elimina un robot aunque no pertenezca al admin.
	- Respuesta: estado y robot_id.

- `PUT /admin/users/{user_id}/grant`
	- Auth: admin
	- Descripcion: eleva un usuario a rol administrador.
	- Respuesta: `UsuarioRespuesta` con rol admin.

- `PUT /admin/users/{user_id}/revoke`
	- Auth: admin
	- Descripcion: degrada un admin a usuario base.
	- Respuesta: `UsuarioRespuesta` con rol user.

## 12) Flujos completos (end-to-end)

### 12.1 Alta de usuario y login

1) `POST /user/register`
2) `POST /user/login` -> se obtiene JWT
3) Se usa JWT para endpoints de usuario.

### 12.2 Alta de robot (TOFU)

1) Usuario registra robot con `POST /user/new-robot`.
2) Robot arranca y llama a `POST /robot/{robot_id}/first-boot`.
3) Robot guarda secret.
4) En cada boot, `POST /robot/{robot_id}/auth` para obtener JWT.
5) Robot usa JWT para `PUT /robot/heartbeat` y para publicar en Kafka.

### 12.3 Telemetria

1) Robot publica en Kafka (topico telemetria) con JWT en headers.
2) `serve_telemetry` valida y escribe en InfluxDB.
3) Grafana consume InfluxDB para dashboards.

### 12.4 Incidentes

1) Robot sube video a MinIO.
2) Robot publica mensaje en Kafka (topico incidentes) con bucket y filename.
3) `detect_incident` crea el incidente en PostgreSQL.
4) Usuario consulta lista con `GET /user/incidents`.
5) Usuario solicita video con `GET /user/incidents/{incident_id}/show-video` y recibe URL firmada.

## 13) Seeder de base de datos

El script [backend/src/seeder.py](backend/src/seeder.py) crea:

- Admin por defecto: admin@tfg.com / admin123
- Usuario normal: user@tfg.com / user123
- Robots RBT-01 y RBT-02 (uno con secret ya creado).
- Incidentes de ejemplo para RBT-01.

Este script es util para pruebas de UI y flujos.

## 14) Consideraciones y puntos finos

- El endpoint `/user/incidents/{incident_id}/show-video` usa parametro `id: UUID` en la funcion. Conviene mantener el nombre coherente (incident_id) para evitar confusion en el cliente.
- Los estados operativos son strings libres ("idle", "patrolling", etc). Se puede normalizar con enum para evitar typos.
- Se delega la notificacion a robot en `start-patrol/stop-patrol` (comentado). Puede integrarse via Kafka o WebSocket.
- En telemetria, la fecha se toma del timestamp enviado por el robot; si el reloj del robot es incorrecto, los datos quedaran desfasados.

## 15) Resumen

Este backend esta pensado como un hub de control y observabilidad. La capa HTTP gestiona usuarios/robots, mientras que Kafka desacopla la telemetria y los incidentes. La seguridad se apoya en JWT y en el modelo TOFU para robots. La combinacion PostgreSQL + InfluxDB + MinIO separa bien los tipos de datos: relacional, temporal y binario.
