# 🧪 Plan de Pruebas de Integración — Robot de Patrulla (TFG)

Plan end-to-end para arrancar **toda** la aplicación (infraestructura Docker → backend → frontend → robot ROS 2) en orden y validar que las tres patas se comunican correctamente, **manejando el sistema como un usuario normal desde la app Flutter** y **sin usar el seeder**.

> **Sin seeder:** los datos de prueba (usuario y robot) se crean **a mano desde la app Flutter**:
> el usuario se **registra** en la pantalla de login y **da de alta su robot** desde la pantalla *Robots*.
> Como consecuencia, el backend y el frontend deben estar arriba **antes** de poder crear esos datos
> (de ahí el nuevo orden de fases). No hay usuario admin por defecto: ver el **Apéndice A** si quieres probar los flujos de administrador.

> **Entorno asumido:** Windows 11 + Docker Desktop (backend WSL2) + Flutter en el host.
> El `venv` del backend del repo es Linux (`backend/venv/lib/python3.12`), así que el backend se arranca desde **WSL/bash**. Si prefieres Windows nativo, recrea el venv con PowerShell (ver nota en la Fase 2).

---

## 0. Arquitectura y mapa de puertos

| Componente | Dónde corre | Puerto host | Dirección interna (red docker) |
|---|---|---|---|
| PostgreSQL | Docker (`tfg_postgres`) | `5432` | `postgres:5432` |
| Kafka | Docker (`tfg_kafka`) | `9094` | `kafka:29092` |
| Zookeeper | Docker (`tfg_zookeeper`) | — | `zookeeper:2181` |
| InfluxDB | Docker (`tfg_influxdb`) | `8086` | `influxdb:8086` |
| MinIO (API / consola) | Docker (`tfg_minio`) | `9000` / `9001` | `minio:9000` |
| Grafana | Docker (`tfg_grafana`) | `3000` | `grafana:3000` |
| **Backend FastAPI** | Host / WSL | `8000` | `host.docker.internal:8000` |
| **Frontend Flutter** | Host (Chrome/Windows) | — | usa `http://localhost:8000` |
| **Robot ROS 2** | Docker (`ros2_humble_dev`) | — | red `backend_default` |

**Flujo de eventos:**
```
Robot (ROS2)  --kafka robot_telemetry-->  Backend  --> InfluxDB --> Grafana
Robot (ROS2)  --kafka robot_incidents-->  Backend  --> PostgreSQL + MinIO --> Frontend
Frontend      --REST /start-patrol-->     Backend  --kafka robot_commands--> Robot
Robot (ROS2)  --REST PUT /robot/heartbeat-> Backend --> PostgreSQL (estado online/operativo)
```

**Detalle de red importante:** el `docker-compose.yml` del robot se conecta a la red externa `backend_default`. Esa red la **crea el compose del backend** (nombre de proyecto = carpeta `backend`). Por eso **la infra del backend debe levantarse antes** que el contenedor del robot.

---

## 1. Pre-requisitos y configuración (una sola vez)

### 1.1 Crear los `.env` a partir de las plantillas

```bash
# backend
cp backend/.env.example backend/.env
# robot (nodos en host/bash, no usado en este plan pero requerido por el repo)
cp robot_ws/.env.example robot_ws/.env
# robot dentro del contenedor → ya existe robot_ws/.env.container
```

### 1.2 Coherencia de credenciales (CRÍTICO)

Las mismas credenciales se usan desde varios sitios. Rellena `backend/.env` para que **cuadre** con `robot_ws/.env.container`:

| Variable en `backend/.env` | Valor que debe coincidir | Por qué |
|---|---|---|
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | `minioadmin` / `minioadmin` (igual que `.env.container`) | El robot sube vídeos a MinIO con esas claves; el backend genera la URL firmada con las mismas |
| `MINIO_BUCKET_NAME` | `tfg-incidentes` | Bucket donde el robot sube y el backend lee |
| `INFLUXDB_TOKEN` | El mismo token en compose y backend (un único `.env`) | El backend escribe telemetría con ese token |
| `SECRET_KEY` | genera uno: `python -c "import secrets; print(secrets.token_hex(32))"` | Firma/verifica los JWT del robot y del usuario |
| `KAFKA_*_TOPIC` | `robot_incidents` / `robot_telemetry` / `robot_commands` | Deben ser idénticos a `.env.container` |

> Nota: `backend/.env` usa direcciones **`localhost`** (backend en el host). `robot_ws/.env.container` usa direcciones **internas** (`kafka:29092`, `minio:9000`, `host.docker.internal:8000`). Es correcto que sean distintas.

### 1.3 Elige el ID del robot de prueba

En este plan **no hay robots sembrados**: tú das de alta el robot desde la app en la Fase 4 y eliges su ID (campo *Robot ID (QR)*). Usaremos **`RBT-01`** como ejemplo. Lo único imprescindible es que **ese mismo ID** sea el que use el robot físico/simulado.

Por eso, antes de arrancar el robot (Fase 5), asegúrate de que en `robot_ws/.env.container`:
```ini
ROBOT_ID=RBT-01
```
y de que **`robot_ws/secrets/robot_token.txt` no existe** (si existe, bórralo para forzar un *First Boot* / TOFU limpio):
```bash
rm -f robot_ws/secrets/robot_token.txt
```

> El alta del robot desde la app lo deja con `secret_hash = NULL` (pendiente de TOFU). Al arrancar, el robot hará el ciclo completo first-boot → auth → JWT → heartbeat/telemetría.

---

## 2. Orden de arranque (resumen)

```
Fase 1: docker compose up infra (backend/)   → postgres, kafka, influx, minio, grafana
Fase 2: backend FastAPI (uvicorn)            → API + consumidores Kafka
Fase 3: frontend Flutter                     → arranca la app
Fase 4: registro + alta de robot EN LA APP   → sustituye al seeder (usuario + robot)
Fase 5: robot ROS 2 (contenedor + sim + nodos) → TOFU, navegación, telemetría
Fase 6: escenarios de integración            → los tests propiamente dichos
```

> ⚠️ Cambio respecto a versiones anteriores: como el usuario y el robot se crean **desde la app**, el backend (Fase 2) y el frontend (Fase 3) van **antes** de poblar los datos (Fase 4).

---

## 3. Fase 1 — Infraestructura (Docker)

```powershell
# PowerShell, desde la raíz del repo
cd backend
docker compose up -d
```

Esto levanta postgres, zookeeper, kafka, influxdb, minio, grafana y los jobs efímeros `init-kafka` (crea los tópicos) e `init-minio` (crea el bucket). El `init.sql` se ejecuta **automáticamente** al inicializar postgres por primera vez y crea las tablas `usuarios`, `robots`, `incidentes` (vacías).

### ✅ Verificaciones Fase 1

```powershell
docker compose ps                     # todos "running"/"healthy"
```
```bash
# Tópicos creados
docker exec tfg_kafka kafka-topics --bootstrap-server kafka:29092 --list
#   → robot_commands, robot_incidents, robot_telemetry

# Tablas creadas (deben estar vacías: sin seeder)
docker exec -it tfg_postgres psql -U postgres -d mydb -c "\dt"
#   → usuarios, robots, incidentes

# Bucket creado (consola web)
#   http://localhost:9001  (login: minioadmin / minioadmin) → bucket "tfg-incidentes"

# Grafana arriba
#   http://localhost:3000  (admin / <GF_ADMIN_PASSWORD>)
```

> Si los tópicos o el bucket no aparecen, revisa los logs de los jobs init:
> `docker logs tfg_init_kafka` · `docker logs tfg_init_minio`

---

## 4. Fase 2 — Backend FastAPI

```bash
cd backend
source venv/bin/activate
uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
```

> **Windows nativo (sin WSL):** el venv del repo es Linux. Recréalo:
> ```powershell
> cd backend
> python -m venv venv
> .\venv\Scripts\Activate.ps1
> pip install -r requirements.txt
> uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
> ```

En el arranque, el `startup_event` crea los **consumidores Kafka** (incidentes + telemetría) y el **productor de comandos**. En la consola deberías ver `Iniciando recursos del servidor...` y ningún error de conexión a `localhost:9094`.

### ✅ Verificaciones Fase 2
```bash
curl http://localhost:8000/health
# → {"status":"ok","database_configured":true,"minio_configured":true,
#    "kafka_configured":true,"influxdb_configured":true}

curl http://localhost:8000/
# → {"mensaje":"¡Servidor FastAPI operativo!","entorno":"development"}
```
Swagger interactivo: **http://localhost:8000/docs**

---

## 5. Fase 3 — Frontend Flutter

El frontend apunta a `http://localhost:8000` (`flutter_frontend/lib/src/config/app_config.dart`), válido para web/Windows en el mismo host.

```powershell
cd flutter_frontend
flutter pub get
flutter run -d chrome        # web (prioritario), o:  flutter run -d windows
```

### ✅ Verificación Fase 3
- La app abre en la pantalla **Start using the app** con las pestañas **Login** / **Register**.
- Aún no inicies sesión: primero hay que crear la cuenta (Fase 4).

---

## 6. Fase 4 — Crear usuario y robot **desde la app** (sustituye al seeder)

Esta fase reemplaza al antiguo `python -m src.seeder`. Todo se hace por la UI, como lo haría un usuario real.

### 6.1 Registrar el usuario

1. En la pantalla inicial, pestaña **Register** (*Create an account*).
2. Rellena **Full Name**, **Email**, **Password** y **Phone (opcional)**. Ej.: `Ginés Piloto` / `user@tfg.com` / `user123`.
3. Pulsa **Create Account**. La app llama a `POST /user/register` y, si va bien, hace **login automático** (`POST /user/login`) y entra a **Home (WARDEN)**.

### 6.2 Dar de alta el robot

1. Menú lateral (drawer) → **Robots**.
2. Botón inferior **Add robot** → diálogo *Nuevo robot*.
3. **Robot ID (QR):** `RBT-01` (el mismo ID que pondrás en `robot_ws/.env.container`).
   **Alias:** p. ej. `TurtleBot Salón`.
   > El botón *Scan QR* es un placeholder ("QR Scan pending"); introduce el ID a mano.
4. **Save** → la app llama a `POST /user/new-robot`. El robot queda con `secret_hash = NULL` (pendiente de TOFU), `estado_conexion = offline`, `estado_operativo = idle`.

### ✅ Verificaciones Fase 4
- **En la app:** Home y Robots muestran **RBT-01** (`offline`, el robot aún no arrancó).
- **En BD** (usuario creado + robot pendiente de TOFU):
  ```bash
  docker exec -it tfg_postgres psql -U postgres -d mydb \
    -c "select id, alias, estado_conexion, estado_operativo, secret_hash is null as pendiente_tofu from robots;"
  #   RBT-01 → estado_conexion=offline, estado_operativo=idle, pendiente_tofu = t

  docker exec -it tfg_postgres psql -U postgres -d mydb \
    -c "select id, email, rol from usuarios;"
  #   → tu usuario con rol = 'user'
  ```

---

## 7. Fase 5 — Robot ROS 2 (contenedor + simulación + nodos)

> Requisito: la Fase 1 ya creó la red `backend_default`. Confírmalo:
> `docker network ls | findstr backend_default`
> Y recuerda: `ROBOT_ID=RBT-01` en `robot_ws/.env.container` y `secrets/robot_token.txt` borrado (ver 1.3).

### 7.1 Construir y entrar al contenedor

```powershell
cd robot_ws
docker compose up -d --build
docker exec -it ros2_humble_dev bash
```

### 7.2 (Dentro del contenedor) compilar el workspace

```bash
cd /robot_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### 7.3 Lanzar la simulación (Terminal R1)

> ⚠️ El repo **no fija** un launch propio de simulación. Estos son los comandos estándar de TurtleBot 4 (Ignition) con Nav2 + SLAM, de los que depende `patrol_nav` (espera a `bt_navigator`). **Ajusta el mundo/parámetros a tu setup.**

```bash
# Terminal R1 — simulación + navegación + SLAM
# Bajo WSLg HAY QUE forzar render por software: si no, Gazebo crashea al
# inicializar la cámara RGBD (Ogre::UnimplementedException, ver Troubleshooting).
export LIBGL_ALWAYS_SOFTWARE=1
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
    slam:=true nav2:=true rviz:=true world:=depot   # 'depot' o 'maze' = más ligeros que 'warehouse'
```

> 🐢 **Primer arranque:** Gazebo descarga el mundo desde Fuel (warehouse/estanterías,
> varios minutos con la ventana en negro). Queda cacheado en `~/.ignition/fuel/`, así que
> los siguientes arranques son rápidos. Si tras el `export` la simulación va muy lenta,
> usa un mundo ligero (`world:=depot`/`world:=maze`) y, si hace falta, desactiva la cámara OAK-D.

Verifica que el árbol de comportamiento de Nav2 y el servicio de guardado de mapa están vivos:
```bash
ros2 node list        | grep bt_navigator        # debe existir
ros2 service list     | grep /map_saver/save_map  # lo usa patrol_nav al guardar el mapa
```
> **Importante:** `patrol_nav` llama a `/map_saver/save_map` en su fase `SAVING_MAP`. Ese servicio lo
> da `map_saver_server`, que es un **lifecycle node**: no basta con lanzarlo, hay que **activarlo**, y
> debe estar **activo ANTES** de que `patrol_nav` llegue a guardar (si no, se cuelga en
> *"Waiting for map_saver service..."*).
>
> Forma recomendada (un `lifecycle_manager` lo arranca, lo activa solo y lo mantiene vivo):
> ```bash
> ros2 run nav2_map_server map_saver_server --ros-args -p use_sim_time:=true &
> ros2 run nav2_lifecycle_manager lifecycle_manager --ros-args \
>   -p node_names:='[map_saver]' -p autostart:=true -p use_sim_time:=true
> ```
> Forma manual (activar a mano):
> ```bash
> ros2 run nav2_map_server map_saver_server &
> ros2 lifecycle set /map_saver configure && ros2 lifecycle set /map_saver activate
> ```
> Confirma con `ros2 service list | grep /map_saver/save_map` (debe aparecer).
> Alternativa one-shot e independiente de `patrol_nav`: `ros2 run nav2_map_server map_saver_cli -f ~/mapa`.

### 7.4 Lanzar los 4 nodos del proyecto (una terminal por nodo)

Abre nuevas shells con `docker exec -it ros2_humble_dev bash` y en cada una:
`cd /robot_ws && source install/setup.bash`.

**Orden recomendado** (primero `secret_helper`, que obtiene el JWT que los demás consumen):

> ⚠️ **Nombres de ejecutables:** los `entry_points` reales llevan sufijo `_node`
> (`secret_helper_node`, `serve_telemetry_node`, `detect_incident_node`); solo `patrol_nav`
> va sin sufijo. Usar el nombre del paquete a secas da *"No executable found"*.

```bash
# Terminal R2 — secret_helper (TOFU + auth + cachea el JWT, servicio get_robot_token)
# Déjalo corriendo: se queda spinning sirviendo el JWT. Si lo cierras (Ctrl+C),
# los demás nodos se quedan sin token.
ros2 run secret_helper secret_helper_node
```
```bash
# Terminal R3 — patrol_nav (FSM, heartbeat, consume robot_commands)
# Lánzalo DESPUÉS de tener el map_saver activo (ver 7.3).
# Los explore_* van inflados para compensar el RTF bajo del render por software: con RTF
# bajo el robot avanza lento y la exploración se daría por terminada antes de tiempo
# ("Exploration completed (idle detected)"). Defaults ya subidos en el código
# (idle 180 / min 900); aquí van explícitos para poder calibrarlos sin recompilar.
ros2 run patrol_nav patrol_nav --ros-args \
  -p robot_id:=RBT-01 \
  -p server_url:=http://host.docker.internal:8000 \
  -p kafka_broker_url:=kafka:29092 \
  -p kafka_robot_commands_topic:=robot_commands \
  -p explore_idle_secs:=180.0 \
  -p explore_min_secs:=900.0
```
```bash
# Terminal R4 — serve_telemetry (publica telemetría a Kafka con el JWT)
ros2 run serve_telemetry serve_telemetry_node
```
```bash
# Terminal R5 — detect_incident (YOLO sobre la cámara → MinIO + Kafka)
# Es el nodo MÁS pesado (YOLO en CPU). Lánzalo el ÚLTIMO y vigila RAM/CPU:
# sobre el Gazebo en software puede agotar recursos y tumbar Docker (ver Troubleshooting).
ros2 run detect_incident detect_incident_node
```

> 💡 `scripts/42_robot_run.sh` automatiza esta fase: lanza los 4 nodos en segundo plano
> dentro del contenedor (logs en `robot_ws/log/*.log`). **No** levanta la simulación (7.3),
> que debe estar ya corriendo.

### ✅ Verificaciones Fase 5 (la prueba TOFU + heartbeat)

1. **`secret_helper`** (Terminal R2) debe loguear:
   `No hay secreto guardado. Intentando proceso de First Boot (TOFU)...` →
   `Secreto raíz obtenido y guardado en disco con éxito.` →
   `JWT obtenido/refrescado exitosamente.`
2. El fichero del secreto persiste: `cat /secrets/robot_token.txt`.
3. **Backend:** verás peticiones a `POST /robot/RBT-01/first-boot`, `POST /robot/RBT-01/auth` y luego `PUT /robot/heartbeat`.
4. **Estado en BD** pasa a `online`:
   ```bash
   docker exec -it tfg_postgres psql -U postgres -d mydb \
     -c "select id, estado_conexion, estado_operativo from robots where id='RBT-01';"
   #   → online / idle
   ```
5. **Frontend:** en Home/Robots, RBT-01 aparece **online** (la pantalla Home refresca sola cada 5 s).

---

## 8. Fase 6 — Escenarios de prueba de integración

> Recorrido como **usuario normal** por la app. Cada caso indica el gesto en la UI y el endpoint que dispara.

### Caso 6.1 — Telemetría → InfluxDB → Grafana
- **Acción:** con `serve_telemetry` corriendo, la telemetría fluye cada 1 s.
- **Verificar el flujo Kafka:**
  ```bash
  docker exec tfg_kafka kafka-console-consumer --bootstrap-server kafka:29092 \
    --topic robot_telemetry --max-messages 3
  # → JSON con robot_id, bateria, pos_x, pos_y, ...
  ```
- **Verificar en Grafana desde la app:** Robots → tarjeta de RBT-01 → icono **stats** (`insights`), que llama a `GET /user/RBT-01/dashboard-url` y abre Grafana en el navegador. Alternativa directa:
  `http://localhost:3000/d/<grafana_dashboard_uid>/robot-telemetry?var-robot_id=RBT-01`
- **Esperado:** se ven series de batería/posición para `RBT-01`.
- **Nota de seguridad:** la telemetría sin cabecera `Authorization` válida se descarta en el backend. Si no aparece nada en Influx, casi seguro `secret_helper` aún no había entregado el JWT cuando arrancó `serve_telemetry` (espera ~10 s y reintenta).

### Caso 6.2 — Start Patrol (Frontend → Backend → Robot)
- **Acción:** en **Home (WARDEN)**, sobre la tarjeta de RBT-01, activa el **switch** (ON). Eso llama a `PUT /user/RBT-01/start-patrol`.
  - El backend valida que el estado sea `idle` o `stopped` y publica en `robot_commands`.
  - La tarjeta muestra `PREPARING` mientras mapea y `PATROLLING` cuando ya patrulla (la app avisa con un snackbar al pasar a `patrolling`).
- **Verificar el comando en Kafka:**
  ```bash
  docker exec tfg_kafka kafka-console-consumer --bootstrap-server kafka:29092 \
    --topic robot_commands --max-messages 1
  # → {"robot_id":"RBT-01","command":"start_patrol",...}
  ```
- **Esperado en `patrol_nav` (R3):** la FSM avanza
  `IDLE → EXPLORING` (lanza `explore_lite`) `→ SAVING_MAP → PLANNING → PATROLLING`.
- **Verificar transición de estado** (el heartbeat es la fuente de verdad): la pantalla Home refresca sola; o consulta la BD; `estado_operativo` debe ir cambiando `exploring → saving_map → planning → patrolling`:
  ```bash
  docker exec -it tfg_postgres psql -U postgres -d mydb \
    -c "select estado_operativo from robots where id='RBT-01';"
  ```

### Caso 6.3 — Detección de incidente (Robot → MinIO + Kafka → Backend → Frontend)
- **Acción:** provoca una detección de persona delante de la cámara del robot. En la simulación, inserta un **modelo/actor humano** en el mundo Gazebo frente al robot. (`detect_incident` corre YOLOv8n sobre `/oakd/rgb/preview/image_raw` con umbral `DETECTION_CONFIDENCE_THRESHOLD=0.5`).
- **Esperado en `detect_incident` (R5):** `Incident detected!` → graba clip → sube a MinIO → publica en `robot_incidents` (cooldown de 30 s entre incidentes).
- **Verificar artefactos:**
  ```bash
  # Vídeo en MinIO (consola http://localhost:9001 → bucket tfg-incidentes), o:
  docker exec tfg_kafka kafka-console-consumer --bootstrap-server kafka:29092 \
    --topic robot_incidents --max-messages 1
  # → {"robot_id":"RBT-01","bucket_name":"tfg-incidentes","video_filename":"incident_..._RBT-01.mp4"}

  # Incidente persistido en BD
  docker exec -it tfg_postgres psql -U postgres -d mydb \
    -c "select robot_id, video_filename, revisado from incidentes where robot_id='RBT-01';"
  ```
- **Verificar en Frontend:** drawer → **Incidents** (`GET /user/incidents`) muestra el nuevo incidente. Pulsa **View details** → **View video** (`GET /user/incidents/{id}/show-video`): genera una **URL firmada de MinIO** y debe **reproducirse** (es un clip real subido por el robot). El botón *Notify the police* es un placeholder ("Alert to the police pending").

### Caso 6.4 — Stop Patrol
- **Pre-condición:** RBT-01 en `patrolling`.
- **Acción:** Home → desactiva el **switch** de RBT-01 (OFF) → `PUT /user/RBT-01/stop-patrol`. El backend solo lo permite si está `patrolling`.
- **Esperado:** `patrol_nav` → `PATROL_STOPPED` (cancela navegación y vuelve al dock); `estado_operativo` → `stopped` en BD y frontend.
  > Si intentas apagar el switch mientras está `PREPARING` (mapeando), la app muestra el diálogo *"El robot aún no está listo"* porque el backend responde **409** (solo se puede parar desde `patrolling`).

### Caso 6.5 — Reinstall (borrar mapa y volver a IDLE)
- **Acción:** Robots → tarjeta de RBT-01 → icono **reinstall** (`settings_backup_restore`) → confirma en el diálogo → `PUT /user/RBT-01/reinstall`.
- **Esperado:** `patrol_nav` borra `mapa_patrulla.pgm/.yaml`, limpia waypoints y vuelve a `IDLE`; `estado_operativo` → `idle`. Tras esto, un nuevo *Start patrol* repite el ciclo completo (exploración incluida).

### Caso 6.6 — Renombrar robot (alias)
- **Acción:** Robots → tarjeta de RBT-01 → icono **editar** (`edit`) → cambia el alias → `PUT /user/RBT-01/alias`.
- **Esperado:** la tarjeta refleja el nuevo alias; persiste en BD.

### Caso 6.7 — Validaciones de transición de estado (caminos negativos)
- *Start patrol* mientras está `exploring/planning/patrolling` → backend responde **409 Conflict** (solo se permite desde `idle`/`stopped`).
- *Stop patrol* mientras NO está `patrolling` → **409 Conflict** (la app lo muestra como el diálogo "El robot aún no está listo").
- Controlar un robot de otro usuario (probable solo vía API/Swagger, no por la UI) → **403 Forbidden**.

### Caso 6.8 — Perfil de usuario
- Drawer → **Profile**. Comprueba `GET /user/profile`, **update info** (`PUT /user/update-info`, requiere password actual) y **update password** (`PUT /user/update-password`, valida longitud ≥ 6 y que sea distinta).

### Caso 6.9 — Borrar robot
- **Acción:** Robots → tarjeta de RBT-01 → icono **borrar** (`delete_outline`) → `DELETE /user/RBT-01/delete`.
- **Esperado:** desaparece de la lista; en BD se borra el robot y, en cascada, sus incidentes.
  > Si vas a seguir probando, vuelve a darlo de alta (Fase 4) o no lo borres hasta el final.

---

## 9. Matriz de cobertura (checklist)

| # | Escenario | REST / Topic | Componentes implicados | OK |
|---|---|---|---|---|
| 1 | Health + arranque | `GET /health` | Backend + infra | ☐ |
| 2 | Registro usuario (app) | `POST /user/register` (+ login) | Front → Backend → PG | ☐ |
| 3 | Alta de robot (app) | `POST /user/new-robot` | Front → Backend → PG | ☐ |
| 4 | TOFU first boot | `POST /robot/{id}/first-boot` | Robot → Backend → PG | ☐ |
| 5 | Auth robot (JWT) | `POST /robot/{id}/auth` | Robot → Backend | ☐ |
| 6 | Heartbeat / online | `PUT /robot/heartbeat` | Robot → Backend → PG | ☐ |
| 7 | Telemetría | topic `robot_telemetry` | Robot → Kafka → Backend → Influx → Grafana | ☐ |
| 8 | Start patrol (switch Home) | `PUT /user/{id}/start-patrol` | Front → Backend → Kafka → Robot | ☐ |
| 9 | FSM completa | — | Robot (explore→map→plan→patrol) | ☐ |
| 10 | Incidente real + ver vídeo | topic `robot_incidents` · `GET /user/incidents/{id}/show-video` | Robot → MinIO+Kafka → Backend → PG → Front | ☐ |
| 11 | Stop patrol (switch Home) | `PUT /user/{id}/stop-patrol` | Front → Backend → Kafka → Robot | ☐ |
| 12 | Reinstall | `PUT /user/{id}/reinstall` | Front → Backend → Kafka → Robot | ☐ |
| 13 | Alias robot | `PUT /user/{id}/alias` | Front → Backend → PG | ☐ |
| 14 | Perfil usuario | `PUT /user/update-info` · `/update-password` | Front → Backend → PG | ☐ |
| 15 | Borrar robot | `DELETE /user/{id}/delete` | Front → Backend → PG | ☐ |

---

## 10. Troubleshooting rápido

| Síntoma | Causa probable | Solución |
|---|---|---|
| No puedo registrarme / "Email already registered" | Ya creaste ese usuario en una corrida anterior | Usa otro email o borra la fila en `usuarios` (o `docker compose down -v` para empezar de cero) |
| El robot no aparece tras "Add robot" | El alta falló o el ID ya existía | Revisa el snackbar de error; comprueba en BD `select * from robots;` |
| Robot no autentica / heartbeat 401 | El `ROBOT_ID` del robot no coincide con el dado de alta, o quedaba un secreto viejo | Pon el **mismo ID** en `.env.container` y borra `secrets/robot_token.txt` (TOFU limpio) |
| `health` con `kafka_configured` false o backend casca al arrancar | Backend levantado antes que Kafka | Espera a que `tfg_kafka` esté healthy y reinicia el backend |
| Telemetría no llega a Influx | `serve_telemetry` arrancó antes de tener JWT | Espera ~10 s (refresco de token) o reinicia el nodo |
| `patrol_nav` colgado en "Waiting for Nav2" | Sim/Nav2 no levantó `bt_navigator` | Revisa el launch de la Fase 7.3 |
| Robot no recibe comandos | `ROBOT_ID` no coincide con el del comando, o broker mal | Confirma `RBT-01` en `.env.container` y `kafka:29092` |
| Contenedor robot no levanta (red) | `backend_default` no existe | Levanta primero `backend/` con docker compose |
| El switch de Home no para el robot | El robot aún está `PREPARING` (mapeando) | Solo se puede parar desde `patrolling`; espera al snackbar "ya está patrullando" |
| Gazebo se cierra solo (`Ogre::UnimplementedException ... GL3PlusTextureGpu::copyTo`) | El driver GL de WSLg no soporta el render de la cámara RGBD | `export LIBGL_ALWAYS_SOFTWARE=1` **antes** del `ros2 launch` (Fase 7.3) |
| Simulación muy lenta | Render por software (CPU) | Mundo ligero (`world:=depot`/`maze`) y/o desactivar la cámara OAK-D |
| `ros2 run ... ` → *No executable found* | Falta el sufijo `_node` en el ejecutable | Usa `secret_helper_node` / `serve_telemetry_node` / `detect_incident_node` (`patrol_nav` va sin sufijo) |
| `Package '...' not found` al lanzar un nodo | Terminal sin el overlay sourceado | `source /opt/ros/humble/setup.bash && source install/setup.bash` (desde `/robot_ws`) |
| First-boot `Connection refused host.docker.internal:8000` | El backend (Fase 2) no está arriba | Arranca `uvicorn` antes del robot |
| First-boot `HTTP 404 - Robot not yet registered` | El robot no está dado de alta (Fase 4) | Regístralo en la app antes de arrancar el robot |
| `docker exec` corta con `500 Internal Server Error` / la sesión se cae | WSL2/Docker sin recursos (sim en software + YOLO) | Lanza `detect_incident` el último; usa mundo ligero; sube la RAM de WSL2 en `~/.wslconfig` |
| Grafana "No data" aunque InfluxDB sí tiene datos (Data Explorer los ve) | Datasource duplicado/sin URL en el volumen `grafana_data` | Recrear el contenedor: `docker compose up -d --force-recreate grafana` (o borrar el datasource sin URL); el bueno es el `default` con `http://influxdb:8086` |
| `patrol_nav` colgado en "Waiting for map_saver service..." | `map_saver_server` lanzado pero **no activado** (lifecycle) | Actívalo (`lifecycle set /map_saver configure`+`activate`) o usa `nav2_lifecycle_manager` con `autostart:=true`, **antes** de `patrol_nav` (ver 7.3) |
| El robot explora muy poco y "Exploration completed (idle detected)" salta enseguida | RTF bajo (render software) + `patrol_nav` mide en tiempo real → cree que el robot está quieto | Sube `explore_idle_secs`/`explore_min_secs` (p. ej. 180/900); alternativa más robusta: lanzar `patrol_nav` con `use_sim_time:=true` |
| Tras lanzar Gazebo headless (`gz_args:='-s'`): no existe el frame `map`, `/scan` vacío, costmaps sin mapa | Bajo WSLg los sensores GPU (lidar/cámara) **no renderizan** sin el contexto del GUI | No usar headless en este entorno; lanzar con GUI (`rviz:=true` para visualizar) |

---

## 11. Teardown

```powershell
# Parar robot (y borrar contenedor)
cd robot_ws ; docker compose down

# Parar backend (Ctrl+C en uvicorn) y la infra
cd ..\backend ; docker compose down
#   añade -v para borrar también los volúmenes (postgres/influx/minio/grafana) y empezar de cero:
#   docker compose down -v
```

---

## Apéndice A — Probar los flujos de Admin (opcional)

Sin seeder **no existe ningún usuario administrador**, y no hay endpoint público para crear uno. Si quieres probar la sección de admin, **promueve a admin un usuario ya registrado** con un `UPDATE` directo en Postgres:

```bash
docker exec -it tfg_postgres psql -U postgres -d mydb \
  -c "update usuarios set rol='admin' where email='user@tfg.com';"
```

Vuelve a **iniciar sesión** en la app (el rol se lee al hacer login). En el drawer aparecerá la entrada **Admin**.

Escenarios de admin a cubrir:
- `GET /admin/robots`, `GET /admin/users`, `GET /admin/robots/{id}/incidents`.
- **grant/revoke** rol a un usuario (`PUT /admin/users/{id}/grant` · `/revoke`) y **delete** robot/usuario.
- Caminos negativos: un admin no puede borrarse a sí mismo ni revocarse sus propios permisos → **400**.

> Para grant/revoke necesitarás un **segundo usuario** (regístralo desde otra sesión o en incógnito) sobre el que operar.
