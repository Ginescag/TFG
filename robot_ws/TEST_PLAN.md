# Plan de pruebas de los nodos ROS 2 (`robot_ws`)

Runbook paso a paso para lanzar, probar y verificar los 4 nodos del workspace:
`serve_telemetry`, `detect_incident`, `secret_helper` y `patrol_nav`.

---

## 0) Estado actual — ESTÁS AQUÍ (2026-06-09)

Resumen de lo ya verificado en este entorno y la siguiente acción pendiente:

- **Infra (Sección 1):** ✅ levantada y verificada.
  - Tópicos Kafka creados: `robot_commands`, `robot_incidents`, `robot_telemetry`.
  - Bucket MinIO `tfg-incidentes` creado (`init-minio` terminó con *"Bucket listo"*).
- **Contenedor ROS (Sección 2):** ✅ imagen reconstruida y `ros2_humble_dev` arriba.
  - Deps **verificadas** en la imagen: `irobot-create-msgs` + `nav2-simple-commander` (apt, `dpkg ii`)
    y `torch`/`ultralytics`/`boto3`/`httpx`/`confluent-kafka` (pip).
  - **Variables inyectadas vía `env_file: .env.container`** → **no hay que exportar nada a mano** (11 vars OK).
  - **`/secrets` montado como volumen** (`./secrets:/secrets`) → el token de `secret_helper` persiste.
- **Workspace compilado:** ✅ `colcon build --symlink-install` → **5 paquetes OK**
  (`serve_telemetry`, `detect_incident`, `patrol_nav`, `secret_helper`, `secret_helper_interfaces`).
  Los avisos *clock skew* de `secret_helper_interfaces` son inofensivos (bind-mount de Windows).
  `ros-humble-image-publisher` ya instalado en el contenedor (lo usa la Fase B).
- **Fase A (`serve_telemetry`):** ✅ **PROBADA** — publica telemetría en Kafka `robot_telemetry`
  cada 1 s y los callbacks de `/battery_state` y `/odom` actualizan el JSON.
  - ℹ️ La ingesta en **InfluxDB NO forma parte de la Fase A**. Requiere el **backend FastAPI en `:8000`**
    (es quien consume Kafka `robot_telemetry` y escribe en Influx) **y** un JWT válido en `ROBOT_JWT_TOKEN`
    (si falta, el backend descarta el mensaje por no traer header `Authorization`). Queda ligado a la
    **Fase C + backend arriba**.
- **Fase B (`detect_incident`):** ✅ **PROBADA** — detecta `person` (YOLOv8n, conf ≥ 0.5), graba el
  clip, lo sube a MinIO (`tfg-incidentes`) y publica en Kafka `robot_incidents`.
  - ⚠️ **Fix de entorno obligatorio:** la imagen trae **NumPy 2**, incompatible con `cv_bridge`/`matplotlib`
    de Humble (`_ARRAY_API not found` / `numpy.core.multiarray failed to import`). Solución aplicada en el
    contenedor: **`pip3 install "numpy<2"`** (→ `numpy 1.26.4`). El aviso de que `opencv-python` pide
    `numpy>=2` es **cosmético**: el nodo corre igual. **PENDIENTE:** fijar `numpy<2` en el `Dockerfile`
    para que el próximo `docker compose build` nazca correcto (si no, reaparece el fallo).
- **Fase C (`secret_helper`):** ✅ **PROBADA** — first-boot (TOFU) genera el secreto y lo guarda en
  `secrets/robot_token.txt`, el auth devuelve un JWT y el servicio `get_robot_token` lo entrega
  (`success=True`). Requiere **backend en `:8000`** + `RBT-01` insertado en la tabla `robots`.
  - 🔌 **PENDIENTE de cableado:** `serve_telemetry` y `detect_incident` aún leen el JWT de la env var
    `ROBOT_JWT_TOKEN` (vacía) → por eso el backend descarta su telemetría (`MESSAGE DISCARDED`). El
    diseño previsto es que **llamen al servicio `get_robot_token`** para obtener el JWT y meterlo en el
    header `Authorization` de Kafka (ver TODO en `detect_incident.py:125`). **Hasta cablearlo, la ingesta
    en InfluxDB no se completa.**
- **Solo la Fase D añade un paso extra:** compilar `explore_lite` **desde fuente** (no hay binario
  apt para Humble; se clona en `src/` y se compila con `colcon`).

> **👉 Siguiente acción inmediata:** **Fase D (`patrol_nav`).** Es la más pesada: (1) compilar
> `explore_lite` desde fuente en `src/` (no hay binario apt para Humble), (2) lanzar el simulador TB4
> con SLAM+Nav2, (3) tener `map_saver_server` vivo, (4) arrancar `patrol_nav`. `numpy<2` ya está
> aplicado en el contenedor (⚠️ no rehagas el `build` sin fijarlo antes en el Dockerfile). Pasos
> detallados abajo en la Fase D.

---

## 1) Levantar la infraestructura (Kafka + MinIO) y verificarla

Desde `backend/` (ahí está el compose con Kafka, Zookeeper, MinIO y la creación de tópicos):

```bash
cd ../backend
docker compose up -d zookeeper kafka init-kafka minio init-minio
docker compose ps
```

**Comprobar Kafka (tópicos creados):**

```bash
docker exec -it tfg_kafka kafka-topics --bootstrap-server kafka:29092 --list
# Debes ver: robot_incidents, robot_telemetry, robot_commands
```

**Bucket de MinIO:** lo crea automáticamente el servicio `init-minio` (mismo patrón que
`init-kafka` para los tópicos). No hay que crearlo a mano. Verificar que existe:

```bash
docker logs tfg_init_minio          # debe terminar en "Bucket listo. Me apago."
# o por consola web: http://localhost:9001  (minioadmin / minioadmin) → bucket "tfg-incidentes"
```

> El nombre real de la red lo confirmas con `docker network ls | grep backend`
> (suele ser `backend_default`).

---

## 2) Construir el contenedor ROS y el workspace

```bash
cd ../robot_ws
docker compose build
docker compose up -d
docker exec -it ros2_humble_dev bash
```

Las dependencias (`boto3`, `ultralytics`, `httpx`, `torch`/`torchvision` por pip;
`irobot-create-msgs`, `nav2-simple-commander` por apt) están en el `Dockerfile`.
`image-publisher` es solo para pruebas y se instala aparte.

> ⚠️ **NumPy 2 rompe ROS Humble.** `ultralytics` arrastra `numpy 2.x` y `opencv-python` 4.13, pero
> `cv_bridge`/`matplotlib` de Humble están compilados contra `numpy 1.x` → `_ARRAY_API not found` al
> arrancar `detect_incident` (Fase B). **Fix:** `pip3 install "numpy<2"` dentro del contenedor (→ 1.26.4).
> Pendiente fijarlo en el `Dockerfile` (paso 3) para que persista entre rebuilds.

> ℹ️ **Rebuild completo (recomendado):** el `docker compose build` desde cero instala de una vez
> todas las dependencias de las Fases A–D. Reparto por fase de las que se suelen olvidar:
> - `irobot-create-msgs` (apt) → **Fase A**: `serve_telemetry` importa `DockStatus`/`KidnapStatus`/… y
>   se suscribe a `/dock_status`. Sin él, el nodo ni arranca.
> - `nav2-simple-commander` (apt) → **Fase D**: `patrol_nav` usa `BasicNavigator`/`TaskResult`.
> - `explore_lite` → **Fase D**, y **no va por apt**: se compila desde fuente (ver Fase D).
>
> El paso lento del build es descargar `torch`/`torchvision` CPU (~192 MB) + `ultralytics`.

> ⚠️ **`explore_lite` NO se instala por apt** (no existe el binario `ros-humble-explore-lite`
> para Humble). Solo lo usa `patrol_nav` (Fase D) y se compila desde fuente. Las fases A–C
> no lo necesitan; los pasos de clonado + build están en la Fase D.

**Dentro del contenedor**, compila:

```bash
source /opt/ros/humble/setup.bash

# solo para inyectar imágenes en la Fase B (herramienta de prueba)
apt-get update && apt-get install -y ros-humble-image-publisher

cd /robot_ws
colcon build --symlink-install
source install/setup.bash
```

**Comprobar que el build encontró los paquetes:**

```bash
ros2 pkg list | grep -E "detect_incident|serve_telemetry|secret_helper|secret_helper_interfaces|patrol_nav"
ros2 pkg executables detect_incident serve_telemetry patrol_nav
```

> 💡 **Si lanzas `ros2 ...` con `docker exec ... bash -lc`** (no interactivo) puede fallar con
> *"command not found"*: ese modo **no lee `~/.bashrc`** (donde está el `source /opt/ros/humble/setup.bash`).
> Soluciones: usa `docker exec -it ros2_humble_dev bash` (interactivo, sí sourcea), o
> `docker exec ros2_humble_dev bash -c "source /opt/ros/humble/setup.bash && ros2 ..."`.

> **Conectividad a Kafka/MinIO (ya resuelta en el compose):** el `docker-compose.yml` del robot
> **ya no usa `network_mode: host`**. Une el contenedor a la red externa `backend_default` (la de la
> infra) y carga las variables de los nodos desde `.env.container`:
> ```yaml
> networks: [infra]              # infra → external: backend_default
> env_file: [.env.container]     # ROBOT_ID, KAFKA_BROKER_URL=kafka:29092, MINIO_ENDPOINT=http://minio:9000, ...
> volumes:
>   - ./secrets:/secrets         # token JWT de secret_helper (persistente)
> ```
> Por tanto **NO hace falta el `docker run --network backend_default` separado**: se direcciona por
> nombre de servicio (`kafka`, `minio`) usando directamente el contenedor `ros2_humble_dev`. Para la
> GUI del simulador (Fase D) este mismo compose ya monta `/mnt/wslg` + `/tmp/.X11-unix` y exporta
> `DISPLAY`/`WAYLAND_DISPLAY`, así que **la Fase D usa el mismo contenedor** (no requiere `network_mode: host`).

**Variables de entorno — ya NO hay que exportar nada.** El compose las carga desde `.env.container`
(`env_file`). Compruébalo dentro del contenedor:

```bash
env | grep -E "ROBOT_ID|KAFKA_BROKER_URL|MINIO_ENDPOINT|BACKEND_URL|SERVER_URL|SECRET_PATH" | sort
```

Ese fichero (`robot_ws/.env.container`, **ignorado por git**) ya tiene las direcciones de **red
interna**. Tu `.env` de Windows **no se usa** dentro del contenedor.

> ⚠️ **NO hagas `source .env` dentro del contenedor.** Los nodos leen con `os.getenv(...)` y tu `.env`
> está escrito para ejecutar **desde Windows** (todo `localhost`). Dentro del contenedor `localhost` es
> el **propio contenedor** → rompería las 3 conexiones. Por eso `.env.container` usa direcciones internas:
>
> | Variable | `.env` (Windows) | `.env.container` (dentro del contenedor) |
> |---|---|---|
> | `KAFKA_BROKER_URL` | `localhost:9094` | `kafka:29092` |
> | `MINIO_ENDPOINT` | `http://localhost:9000` | `http://minio:9000` |
> | `BACKEND_URL` / `SERVER_URL` | `http://localhost:8000` | `http://host.docker.internal:8000` |
>
> Motivo de los dos puertos de Kafka: el broker anuncia dos *listeners* (`PLAINTEXT://kafka:29092`
> interno, `PLAINTEXT_HOST://localhost:9094` para el host). El cliente se reconecta a la dirección
> **anunciada**, por eso no son intercambiables.
>
> El backend FastAPI **no es un contenedor de `backend_default`** (corre en Windows en `:8000`), por
> eso desde el contenedor se alcanza vía `host.docker.internal` (DNS de Docker Desktop), no `localhost`.

> 💡 Para cambiar un valor luego: edita `.env.container` y `docker compose up -d` (recrea el
> contenedor). **No hace falta `build`.** Variable opcional: `ROBOT_JWT_TOKEN` (la leen
> `serve_telemetry`/`detect_incident` para incrustar el JWT en sus mensajes; déjala vacía si no la usas).

---

## Fase A — `serve_telemetry` (la más fácil) — ✅ PROBADA

**Objetivo:** confirmar que publica telemetría en Kafka cada 1 s y que refleja los tópicos ROS.

**Lanzar** (terminal 1, dentro del contenedor con el entorno cargado):

```bash
ros2 run serve_telemetry serve_telemetry_node
```

**Comprobar la salida en Kafka** (terminal 2 — un consumidor):

```bash
docker exec -it tfg_kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 --topic robot_telemetry
# Deberías ver un JSON por segundo con bateria, pos_x, is_docked, etc.
```

**Probar que los callbacks actualizan el estado** (terminal 3, dentro del contenedor):

```bash
ros2 topic pub /battery_state sensor_msgs/msg/BatteryState '{percentage: 0.8, voltage: 14.0}' -r 2
ros2 topic pub /odom nav_msgs/msg/Odometry '{pose: {pose: {position: {x: 1.5, y: 2.0}}}, twist: {twist: {linear: {x: 0.3}}}}' -r 2
```

**Verificación:** en el consumidor Kafka, `bateria` debe pasar a `80.0`, `pos_x` a `1.5`,
`vel_linear` a `0.3`. ✅

---

## Fase B — `detect_incident` — ✅ PROBADA

**Objetivo:** ante una imagen con persona, detecta → graba vídeo → sube a MinIO → publica en Kafka.

**Lanzar el nodo** (terminal 1):

```bash
ros2 run detect_incident detect_incident_node
# Primera vez: descarga yolov8n.pt (necesita internet)
```

**Inyectar imágenes** (terminal 2) — usa una imagen que contenga una persona, remapeada al tópico
que el nodo escucha:

```bash
ros2 run image_publisher image_publisher_node /ruta/a/imagen_con_persona.jpg \
  --ros-args -r image_raw:=/oakd/rgb/preview/image_raw
```

**Consumidor Kafka de incidentes** (terminal 3):

```bash
docker exec -it tfg_kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 --topic robot_incidents
```

**Verificación:**
- Log del nodo: `Incident detected!` y luego `Entering cooldown period...`.
- Tras ~50 frames, en Kafka aparece
  `{"robot_id":"RBT-01","bucket_name":"tfg-incidentes","video_filename":"incident_..._RBT-01.mp4"}`.
- En MinIO (http://localhost:9001) el bucket `tfg-incidentes` contiene el `.mp4`. ✅
- Para comprobar que **no** dispara: publica una imagen sin personas → no debe loguear detección.

---

## Fase C — `secret_helper` — ✅ PROBADA

> El servicio ya está en su propio paquete `secret_helper_interfaces` (creado al arreglar el
> hallazgo #2). El nodo importa `from secret_helper_interfaces.srv import GetToken`. Solo hay
> que compilar y probar.

```bash
cd /robot_ws && colcon build --symlink-install && source install/setup.bash
ros2 interface show secret_helper_interfaces/srv/GetToken   # comprobar que existe
```

**Prerrequisitos (ya resueltos por el compose):** `BACKEND_URL=http://host.docker.internal:8000` viene
del `env_file`, y `/secrets` es un **volumen** (`./secrets:/secrets`), así que **no hay que exportar ni
crear nada**. Lo único que debes garantizar tú: el **backend FastAPI corriendo en Windows** en `:8000`
con `/robot/{id}/first-boot` y `/robot/{id}/auth`. Verifica conectividad desde el contenedor:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://host.docker.internal:8000/docs   # ¿responde el backend?
```

**Lanzar y probar:**

```bash
ros2 run secret_helper secret_helper_node            # terminal 1
ros2 service list | grep get_robot_token             # terminal 2: el servicio aparece
ros2 service call /get_robot_token secret_helper_interfaces/srv/GetToken '{}'
```

**Verificación:** la respuesta trae `success: true` y un `token` no vacío una vez autenticado
(logs: `JWT obtenido/refrescado exitosamente`). Si el backend no está, `success: false` con
mensaje de error → confirma el manejo de fallos. ✅

> 🔌 **Pendiente de integración (no bloquea la Fase C, pero sí la ingesta en Influx):**
> `serve_telemetry` y `detect_incident` deben **llamar a este servicio `get_robot_token`** para obtener
> el JWT e incrustarlo en el header `Authorization` de sus mensajes Kafka. Hoy leen `ROBOT_JWT_TOKEN`
> (vacía) → el backend los descarta (`MESSAGE DISCARDED`). Ver TODO en `detect_incident.py:125`.

---

## Fase D — `patrol_nav` (integración con simulador)

**Objetivo:** máquina de estados completa (exploración → guardar mapa → planificar → patrullar)
+ comandos Kafka + heartbeat.

> Esta fase usa el **mismo contenedor `ros2_humble_dev`** (el compose ya monta WSLg para la GUI; no
> requiere `network_mode: host`). `nav2-simple-commander` e `irobot-create-msgs` ya están en la imagen;
> el único paso extra de esta fase es compilar `explore_lite` desde fuente (abajo). Lanza el simulador
> TB4 **antes** que `patrol_nav` (el nodo bloquea en `waitUntilNav2Active()`).

**Prerrequisito — compilar `explore_lite` desde fuente** (solo esta fase lo usa). Dentro del
contenedor, clónalo en el workspace y reconstruye:

```bash
cd /robot_ws/src
git clone https://github.com/robo-friends/m-explore-ros2.git
cd /robot_ws
colcon build --symlink-install
source install/setup.bash
ros2 pkg list | grep explore_lite     # debe aparecer
```

**Terminal 1 — simulador TB4 con SLAM + Nav2:**

```bash
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
  slam:=true nav2:=true rviz:=true
```

**Terminal 2 — map_saver_server** (el nodo llama a `/map_saver/save_map`, hay que tenerlo vivo):

```bash
ros2 run nav2_map_server map_saver_server --ros-args -p save_map_timeout:=5.0
```

**Terminal 3 — el orquestador de patrulla:**

```bash
# KAFKA_BROKER_URL=kafka:29092 ya viene del compose (no exportar)
ros2 run patrol_nav patrol_nav \
  --ros-args -p robot_id:=RBT-01 -p explore_min_secs:=30.0 -p explore_idle_secs:=10.0
```

**Comprobaciones por estado:**
- **EXPLORING:** logs `Starting autonomous exploration (explore_lite)...`; el robot se mueve en Gazebo/RViz.
- **SAVING_MAP:** `Map saved successfully` y aparecen `src/mapa_patrulla.pgm` + `.yaml`.
- **PLANNING:** `N patrol points were generated.`
- **PATROLLING:** el robot recorre los waypoints (visible en RViz).

**Probar comandos remotos por Kafka** (terminal 4) — producir a `robot_commands`:

```bash
docker exec -it tfg_kafka kafka-console-producer --bootstrap-server kafka:29092 --topic robot_commands
> {"robot_id":"RBT-01","command":"stop_patrol"}
> {"robot_id":"RBT-01","command":"start_patrol"}
```

**Verificación:** `stop_patrol` → log `Returning to dock` y el robot vuelve al dock
(`PATROL_STOPPED`); `start_patrol` → `Resuming patrol`. ✅

**(Opcional) Heartbeat al backend:** lanza con
`-p server_url:=http://host.docker.internal:8000 -p robot_jwt:=<token>` (el backend corre en Windows;
desde el contenedor es `host.docker.internal`, no `localhost`) y comprueba en el backend que
`estado_operativo` cambia (`exploring`, `patrolling`, `stopped`...). `patrol_nav` llama a
`POST {server_url}/robot/heartbeat`.

> **Atajo si no quieres explorar:** coloca un `mapa_patrulla.pgm`+`.yaml` previo en `/robot_ws/src/`
> y arranca el nodo directamente; aun así el estado inicial es `EXPLORING`, por lo que para saltar
> a patrulla tendrías que ajustar el estado inicial en el código.

---

## 3) Checklist final

> Deps ya en la imagen y variables vía `env_file` → la columna "Arranca" asume imagen reconstruida +
> `colcon build` hecho. Solo falta lo externo a la imagen (backend, simulador, `explore_lite`).

| Nodo | Arranca | Entrada inyectable | Salida verificable |
|------|---------|--------------------|--------------------|
| `serve_telemetry` | ✅ **PROBADO** | `ros2 topic pub` battery/odom | ✅ JSON en Kafka `robot_telemetry` |
| `detect_incident` | ✅ **PROBADO** (req. `numpy<2`) | `image_publisher` con persona | ✅ `.mp4` en MinIO + msg en `robot_incidents` |
| `secret_helper` | ✅ **PROBADO** (backend `:8000` + robot en BD) | servicio `get_robot_token` | ✅ `service call` devuelve token (JWT) |
| `patrol_nav` | ⚠️ requiere **simulador + Nav2 + `explore_lite`** | comandos Kafka `robot_commands` | movimiento en Gazebo + mapa guardado |
