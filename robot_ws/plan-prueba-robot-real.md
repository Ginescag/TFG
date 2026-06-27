# Plan de prueba en el robot real (TurtleBot 4)

Este plan extiende el `TEST_PLAN.md` (que valida los nodos en **simulador**) a la
prueba sobre el **TurtleBot 4 físico**. La lógica de los nodos no cambia; lo que
cambia es el **hardware real** (base Create 3, cámara OAK-D, LiDAR) y, sobre todo,
la **red**: ahora el robot, la infraestructura/servidor y el móvil pueden estar
en máquinas distintas.

Léelo junto al `TEST_PLAN.md`: las verificaciones por nodo (Fases A a D) son las
mismas; aquí se detalla qué cambia al pasar a real.

---

## 1. Topología y dónde corre cada cosa

```
   TurtleBot 4 (Raspberry Pi 4, ROS 2 Humble)        PC (Windows + Docker)            Móvil
   - Create 3 (base, batería, odom, dock)            - Infra en Docker:               - APK Flutter
   - OAK-D (camara /oakd/rgb/...)                       Kafka, MinIO, InfluxDB,
   - LiDAR (/scan)                                      PostgreSQL, Grafana
   - Nodos: serve_telemetry, detect_incident,        - Backend FastAPI (:8000)
     secret_helper, patrol_nav
                    |                                         |                          |
                    +-------------------- router / red local (WiFi) -------------------+
```

**Recomendación:** ejecuta los **cuatro nodos en la Raspberry Pi del TB4** (ROS 2
Humble nativo), porque necesitan acceso directo a la cámara OAK-D y a los tópicos
de la base Create 3. La infraestructura (Kafka, MinIO, InfluxDB, PostgreSQL,
Grafana) y el backend siguen en el PC.

> En el simulador todo corría en el PC y el contenedor del robot se unía a la red
> Docker interna (`kafka:29092`, `host.docker.internal:8000`). Con el robot real
> en otra máquina, esas direcciones internas **ya no valen**: hay que usar la **IP
> de red local del PC**.

---

## 2. Prerrequisitos

**En el TurtleBot 4 (Raspberry Pi):**
- ROS 2 Humble instalado y funcionando, con la base Create 3 y la OAK-D operativas.
- Python con las dependencias de los nodos: `confluent-kafka`, `boto3`, `httpx`,
  `ultralytics`, `opencv`, `numpy<2` (mismo motivo que en `TEST_PLAN.md`:
  NumPy 2 rompe `cv_bridge`/`matplotlib` de Humble).
- Para `patrol_nav`: `nav2-simple-commander`, `irobot-create-msgs` y `explore_lite`
  compilado desde fuente (no hay binario apt para Humble), igual que la Fase D.
- El workspace compilado en la RPi: `colcon build --symlink-install`.

**En el PC (servidor):**
- Infra y backend levantados (`backend/`), accesibles desde la red local.
- El robot `RBT-01` insertado en la tabla `robots` (lo necesita `secret_helper`).
- Cortafuegos de Windows abierto para los puertos que el robot y el móvil deben
  alcanzar (ver sección 3).

**Red:**
- Robot, PC y móvil en la **misma red local**.
- Anota la **IP local del PC** (en Windows: `ipconfig`, normalmente algo como
  `192.168.1.50`). En adelante se referencia como `IP_PC`.

---

## 3. Cambios de red y configuración para el robot real

El robot deja de usar direcciones internas de Docker y pasa a usar `IP_PC`. Si
ejecutas los nodos **nativos en la RPi**, define estas variables de entorno en la
RPi (no en `.env.container`, que era para el contenedor del PC):

| Variable | En simulador (contenedor) | En robot real (nativo en la RPi) |
|---|---|---|
| `ROBOT_ID` | `RBT-01` | `RBT-01` |
| `KAFKA_BROKER_URL` | `kafka:29092` | `IP_PC:9094` |
| `MINIO_ENDPOINT` | `http://minio:9000` | `http://IP_PC:9000` |
| `BACKEND_URL` | `http://host.docker.internal:8000` | `http://IP_PC:8000` |
| `SERVER_URL` | `http://host.docker.internal:8000` | `http://IP_PC:8000` |
| `SECRET_PATH` | `/secrets/robot_token.txt` | ruta local en la RPi |
| `KAFKA_INCIDENT_TOPIC` | `robot_incidents` | `robot_incidents` |
| `KAFKA_TELEMETRY_TOPIC` | `robot_telemetry` | `robot_telemetry` |
| `KAFKA_ROBOT_COMMANDS_TOPIC` | `robot_commands` | `robot_commands` |
| `MINIO_BUCKET_NAME` | `tfg-incidentes` | `tfg-incidentes` |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5` | `0.5` |

**Cambio imprescindible en el servidor (Kafka):** por defecto Kafka anuncia el
*listener* del host como `PLAINTEXT_HOST://localhost:9094`. Un cliente remoto (la
RPi) que conecte a `IP_PC:9094` recibe de vuelta `localhost:9094` e intenta
reconectar contra **sí mismo**, y falla. Hay que **anunciar la IP del PC**. En
`backend/docker-compose.yml`, servicio `kafka`:

```yaml
KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://IP_PC:9094
```

(y recrear el contenedor: `docker compose up -d kafka`). Esto es lo que más se
olvida al pasar a distribuido.

**Cortafuegos del PC:** abre los puertos entrantes que el robot necesita:
`8000` (backend), `9094` (Kafka host), `9000` (MinIO). Para el móvil además
`3000` (Grafana) y `9000` (vídeo de MinIO).

**Red ROS 2 (DDS) en la RPi:** asegúrate de que tus nodos ven los tópicos reales
de la base y la cámara. Comparte `ROS_DOMAIN_ID` con la base Create 3 y la OAK-D,
y comprueba con `ros2 topic list` que aparecen `/battery_state`, `/odom`,
`/dock_status`, `/oakd/rgb/preview/image_raw` y `/scan`. La sincronización horaria
entre RPi y PC ayuda a evitar avisos.

---

## 4. Pruebas por nodo (adaptación de las Fases A a D a hardware real)

La verificación es la misma que en `TEST_PLAN.md`; la diferencia es que **la
entrada ya no se inyecta a mano**, viene del hardware real.

### Fase A. `serve_telemetry` (real)
- Lanza el nodo en la RPi. Ahora `/battery_state`, `/odom` y `/dock_status` los
  publica la **base Create 3 real**, no `ros2 topic pub`.
- Verifica en el PC: consumidor de `robot_telemetry` en Kafka muestra batería,
  posición y `is_docked` reales, y al mover el robot la posición cambia.
- Con el backend arriba, comprueba que la telemetría llega a InfluxDB y se ve en
  Grafana (requiere que el nodo firme los mensajes con el JWT, ver Fase C).

### Fase B. `detect_incident` (real)
- Lanza el nodo en la RPi (la primera vez descarga `yolov8n.pt`, necesita internet).
- La entrada es la **cámara OAK-D real** (`/oakd/rgb/preview/image_raw`). Ponte
  delante del robot para provocar una detección de `person`.
- Verifica: log `Incident detected!`, el clip sube a MinIO (`IP_PC:9000`,
  bucket `tfg-incidentes`) y aparece el evento en Kafka `robot_incidents`, que el
  backend convierte en incidencia visible en la app.
- Ojo al rendimiento: YOLOv8n sobre la CPU de la RPi va lento; mide los FPS reales.

### Fase C. `secret_helper` (real)
- Con `BACKEND_URL=http://IP_PC:8000`, el first-boot (TOFU) genera el secreto en
  la ruta local de la RPi, y `get_robot_token` entrega el JWT.
- Verifica conectividad desde la RPi: `curl -s -o /dev/null -w "%{http_code}\n" http://IP_PC:8000/docs`.
- Recuerda el pendiente de cableado: `serve_telemetry` y `detect_incident` deben
  pedir el JWT a este servicio para que el backend no descarte sus mensajes
  (`MESSAGE DISCARDED`).

### Fase D. `patrol_nav` (real)
- En vez del simulador, lanza la pila real del TB4: SLAM con el LiDAR real
  (`/scan`) y Nav2, más `map_saver_server`.
- Arranca `patrol_nav` y recorre los estados: EXPLORING (el robot se mueve de
  verdad, vigila el espacio físico), SAVING_MAP (genera `mapa_patrulla.pgm`),
  PLANNING (ruta de cobertura) y PATROLLING (recorre los waypoints reales).
- Comandos remotos: produce `start_patrol`/`stop_patrol` en `robot_commands`
  (desde el PC o desde la app) y comprueba que el robot reacciona y vuelve al dock.
- Heartbeat: con `server_url=http://IP_PC:8000`, el `estado_operativo` del robot
  se refleja en la base de datos y en la app.

> Seguridad física en pruebas reales: ten a mano el botón de parada o `stop_patrol`,
> empieza en un espacio despejado y con la batería cargada.

---

## 5. Checklist y problemas típicos

- [ ] `IP_PC` correcta y fija (reserva DHCP o IP estática para el PC).
- [ ] Kafka anunciando `PLAINTEXT_HOST://IP_PC:9094` (sin esto, el robot no
      conecta a Kafka aunque haga `ping` al PC).
- [ ] Cortafuegos del PC con `8000`, `9094`, `9000` abiertos (y `3000` para el móvil).
- [ ] `numpy<2` en la RPi (si no, `detect_incident` no arranca).
- [ ] `ROS_DOMAIN_ID` compartido y tópicos reales visibles (`ros2 topic list`).
- [ ] Robot `RBT-01` dado de alta en la base de datos antes del first-boot.
- [ ] JWT cableado (servicio `get_robot_token`) para que la telemetría llegue a Influx.
- [ ] `explore_lite` compilado desde fuente en la RPi para la Fase D.
