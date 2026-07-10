# Resultados de las pruebas — Conexión y pruebas con el TurtleBot 4 real

**Fecha:** 1 de julio de 2026 · **Última actualización:** 3 de julio de 2026
**Objetivo:** conectar el PC de desarrollo (Windows 10) al TurtleBot 4 real por la red WiFi `Xiaomi Robot` y probar el ciclo de patrulla autónoma (`patrol_nav` + resto de nodos del proyecto) contra el robot físico, reutilizando la pila de backend (Kafka/MinIO/Postgres/Influx/Grafana) y el contenedor ROS 2 Humble del proyecto.

**✅ ESTADO ACTUAL (3 jul): HITO 2 ALCANZADO (parcial).** El bringup completo (SLAM + Nav2 + map_saver + patrol_nav) arranca contra el robot real; el orquestador recibe `start_patrol` vía Kafka y la FSM transita a `EXPLORING` lanzando `explore_lite`. **Validados además `secret_helper` (TOFU + token) y `serve_telemetry` (telemetría real en Grafana/Influx).** Pendientes por hardware: `detect_incident` end-to-end (fallo intermitente del driver de la OAK-D + batería crítica, §3.21–3.22) y el ciclo FSM completo hasta `PATROLLING` (§4). Matriz de validación detallada en §4.1; runbook con checklist previa en §5.

**Datos fijos del montaje:**

| Parámetro | Valor |
|---|---|
| WiFi del robot | `Xiaomi Robot` / pass `turtlebot4` (red **aislada, sin internet**) |
| IP de la RPi (robot) | `192.168.31.191` (SSH: `ubuntu` / `turtlebot4`) |
| Discovery server del robot | FastDDS, **server ID 1**, puerto 11811, escucha en `0.0.0.0` |
| Namespace del robot | `/turtlebot4` |
| `ROS_DOMAIN_ID` | `0` |
| RMW de los nodos del robot | `rmw_fastrtps_cpp` (FastDDS) |

---

## 1. Arquitectura final que ha funcionado

```
Windows 10 (host)
└── VirtualBox VM · Ubuntu 22.04 · adaptador en MODO PUENTE sobre la WiFi
    ├── chrony (host VM) ──sincroniza──▶ robot 192.168.31.191 (fuente NTP)
    ├── backend/docker-compose (postgres, kafka:9094, minio:9000, influx, grafana)
    ├── backend FastAPI (venv python3.10, uvicorn :8000)
    └── contenedor ros2_robot (imagen propia, --network host)
        ├── fast-discovery-server -i 0 -p 11811   (discovery LOCAL, ID 0)
        ├── patrol_bringup_real.launch.py  (SLAM/Nav2/map_saver ns=turtlebot4)
        └── nodos del proyecto (patrol_nav, secret_helper, serve_telemetry, detect_incident)
```

**Variables de entorno ganadoras del contenedor** (costaron todo el día):

```bash
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ROS_DOMAIN_ID=0
ROS_DISCOVERY_SERVER="127.0.0.1:11811;192.168.31.191:11811"   # ID0=local, ID1=robot (¡posicional!)
ROS_SUPER_CLIENT=True
# + tras reiniciar el daemon: sleep 8 antes de ros2 topic list
```

> Alternativa equivalente: el script oficial `configure_discovery.sh` (en `practica_3_2526-main/Parte_2/`) genera `/etc/turtlebot4_discovery/setup.bash` con exactamente esta configuración (respondiendo: domain 0, server ID 0 = `127.0.0.1:11811`, server ID 1 = `192.168.31.191:11811`). Ojo: pone `ROS_SUPER_CLIENT=True` solo en shells interactivas (`[ -t 0 ]`) y no conoce el workspace del proyecto (hay que añadir a mano `source /robot_ws/install/setup.bash`). En el contenedor (sin sudo) requiere un shim: `printf '#!/bin/bash\nexec "$@"\n' > /usr/local/bin/sudo && chmod +x /usr/local/bin/sudo`. En la práctica el runbook de §5 usa los exports manuales, que son igual de válidos y más explícitos.

---

## 2. Tabla resumen de problemas

| # | Problema | Causa raíz | Estado |
|---|---|---|---|
| 1 | WSL2 no alcanza al robot (ping/TCP fallan) | NAT de WSL2 (172.28.x), sin ruta a 192.168.31.x; Windows 10 no soporta `networkingMode=mirrored` | ✅ Resuelto (VM bridged) |
| 2 | chrony en WSL no sincroniza con el robot | Refclock `PHC0` de Hyper-V (stratum 1) domina; `makestep` → `500 Failure` (reloj controlado por el hipervisor) | ✅ Resuelto (chrony en la VM) |
| 3 | VirtualBox instaló Ubuntu solo (usuario `vboxuser`, francés) | Instalación desatendida automática de VirtualBox 7 | ✅ Resuelto (reinstalación manual) |
| 4 | Guest Additions no integraban | Faltaban `build-essential`, `dkms`, `linux-headers` | ✅ Resuelto |
| 5 | Carpeta compartida no aparece / errores al copiar | Automount no aplicado; symlinks del `venv` dan "Error de protocolo" en vboxsf; `getcwd` tras `rm -rf` del cwd | ✅ Resuelto (mount manual + copiar sin `venv`) |
| 6 | `ros2 topic list` vacío desde el PC | **Tres causas encadenadas** (ver 3.6): faltaba `ROS_SUPER_CLIENT`, server **ID 1** (`;` inicial), y CycloneDDS en la shell del robot (pista falsa) | ✅ Resuelto → SLAM+teleop OK |
| 7 | Backend no conecta a Kafka (`192.168.0.67:9094 timeout`) | `KAFKA_ADVERTISED_LISTENERS` hardcodeado a la IP de casa en `backend/docker-compose.yml` | ✅ Resuelto (`localhost`) |
| 8 | `.env` del backend con IP de casa | `MINIO_ENDPOINT`/`GRAFANA_URL` hardcodeados | ✅ Resuelto (`localhost`) |
| 9 | `ros-humble-explore-lite` no existe en apt | `explore_lite` (m-explore-ros2) no se publica como binario para Humble | ✅ Resuelto (compilado desde fuente) |
| 10 | Nodos del proyecto sordos ante el robot real | Código escrito para el simulador: topics globales (`/odom`, `/oakd/...`) vs namespace `/turtlebot4` del robot | ✅ Resuelto (parámetro `namespace` + launch real) |
| 11 | El bringup arrancó en LOCALIZACIÓN en vez de SLAM | Quedaba un `mapa_patrulla.pgm/.yaml` viejo de la simulación | ✅ Resuelto (borrar mapa) |
| 12 | Nav2 colgado: `Waiting for service .../get_state`, bonds fallan a los 4 s | Descubrimiento de ~12 nodos locales **a través del discovery server del robot por WiFi** → latencia enorme | ✅ Resuelto (discovery server **local** ID 0 + lista dual) |
| 13 | Sin super client los nodos no reciben el TF del robot | Un client "normal" del discovery server no recibe de forma fiable los topics del robot | ✅ Resuelto (re-añadir `ROS_SUPER_CLIENT=True` junto al server local) |
| 14 | **`/turtlebot4/scan` no llega** → slam no publica `map` → Nav2 no activa → patrol_nav no arranca | Confirmado en el lab: en Humble el TB4 **apaga el RPLIDAR y la OAK-D al estar acoplado en el dock** (power saver) | ✅ Resuelto (**undock ANTES del bringup**, ver §3.14) |
| 15 | SLAM descarta todos los scans: `Message Filter dropping message... timestamp earlier than all the data in the transform cache` (cola > 1900, colapsa el sistema) | **Desfase de reloj entre las 3 fuentes**: RPi (sella `/scan`), base Create 3 (sella `/odom`/`/tf`) y la VM. Agravante: las Guest Additions de VirtualBox re-imponen la hora de Windows y pisan a chrony | ✅ Resuelto (restart NTP del Create 3 + `GetHostTimeDisabled` en VBox + `chronyc makestep`, ver §3.15) |
| 16 | `Server map_saver was unable to be reached after 4.00s by bond` → bringup abortado | Bonds de Nav2 con timeout de 4 s, insuficiente con la latencia de servicios en el robot real | ✅ Resuelto (`bond_timeout: 15.0` en el launch, ver §3.16) |
| 17 | `Failed to change state for node: planner_server ... async_send_request failed` → `lifecycle_manager_navigation` aborta el bringup | Intermitente; NO es CPU (89 % idle, load 0.4-0.7 verificado). Probable congestión puntual de descubrimiento/servicios DDS | ⚠️ **Workaround** (reintento in-place con `manage_nodes`, ver §3.16) |
| 18 | Base Create 3 congelada: botón físico de undock sin efecto, `dock_status` no responde | Firmware del Create 3 bloqueado (ocurrió tras varias horas de pruebas y reinicios) | ✅ Procedimiento de recuperación (ver §3.17) |
| 19 | `secret_helper` muere al arrancar: `FileNotFoundError: '/secrets/robot_token.txt'` | El contenedor se lanza con `--rm` → al apagar la VM se destruyó; el nuevo se creó sin el volumen `-v ~/robot_ws/secrets:/secrets` | ✅ Resuelto (`mkdir` + volumen en el `docker run`, ver §3.18) |
| 20 | Tras corregir los relojes **con el stack corriendo**: mapa corrupto ("patas de araña" en RViz) y `Extrapolation Error ... into the past` en el planner | El salto de reloj envenena todo lo sellado antes del ajuste: buffers TF (solo ~10 s de historia), mapa de SLAM y goals pendientes de explore | ✅ Resuelto (reinicio limpio del stack; **regla: relojes primero, bringup después**, ver §3.19) |
| 21 | `detect_incident` suscrito a la cámara con QoS RELIABLE por defecto | Código heredado del simulador; en sensores lo correcto es `qos_profile_sensor_data` (BEST_EFFORT). *No era el bloqueante real* (la OAK-D del TB4 publica RELIABLE), pero era frágil | ✅ Corregido en código (ver §3.20) |
| 22 | La OAK-D no publica imágenes: `Publisher count: 0/1` pero sin datos, ni siquiera en la propia RPi | **El driver DepthAI a veces no carga al reiniciar `turtlebot4.service`**: el journal del boot malo no tiene ni `Camera ready!` y `turtlebot4_node` grita `Service oakd/start_camera unavailable` | ✅ Diagnóstico y recuperación (reiniciar el servicio hasta ver `Camera ready!`, ver §3.21) |
| 23 | Cascada de fallos raros: botón de encendido no responde, base congelada, driver de cámara que no carga | **Batería crítica** (anillo del Create 3 en rojo) tras horas de pruebas sin volver al dock | ⚠️ Lección operativa: comprobar batería al inicio de cada sesión (ver §3.23) |
| 24 | Run limpia (relojes a 0 s verificados) y AUN ASÍ drops continuos de `/scan` durante toda la sesión → mapa a trompicones, explore sin completar goals | **Jitter de transporte bajo carga, MEDIDO**: de 7,86 Hz / σ 7 ms (baseline) a 0,6 Hz / σ 2,8 s con el bringup activo; huecos de hasta 16 s > buffer TF (10 s). No es ancho de banda (~0,5 Mbps) ni relojes ni CPU | ⚠️ Limitación del banco de pruebas (VM+bridge WiFi), cuantificada en §3.22 |

---

## 3. Detalle de los problemas y sus soluciones

### 3.1 WSL2 → callejón sin salida para el robot real
- **Síntoma:** `ping 192.168.31.191` sin respuesta; test TCP a puertos 22/8080 → `FAIL`; `ip route` solo muestra `172.28.32.0/20`.
- **Causa:** WSL2 usa NAT; el robot no puede alcanzar la IP interna de WSL (imprescindible para el retorno DDS) y WSL no tiene ruta a la subred del robot. `networkingMode=mirrored` **no existe en Windows 10** (el propio WSL lo revirtió: *"Versión 19045 de Windows no tiene las características necesarias"*).
- **Solución:** VM VirtualBox Ubuntu 22.04 con **adaptador puente** sobre la tarjeta WiFi (+ modo promiscuo "Permitir todo"). La VM obtiene IP `192.168.31.x` propia y el robot puede responder.
- **Lección:** para DDS con robots reales hace falta estar *en* la LAN del robot, no detrás de un NAT.

### 3.2 chrony
- **En WSL:** el refclock `PHC0` (reloj del hipervisor, stratum 1, error de ns) domina la selección y `makestep` devuelve `500 Failure`. El modelo "el PC sigue al robot" es inviable en WSL.
- **En la VM:** funcionó a la primera con la config suministrada (`server 192.168.31.191 iburst prefer`, pools comentados). Resultado: `^*` sobre el robot, offset < 1 ms (`chronyc tracking` → Reference ID = robot).
- **Pendiente opcional:** desactivar la sincronización de hora de VirtualBox para que no compita con chrony:
  `VBoxManage setextradata "<VM>" "VBoxInternal/Devices/VMMDev/0/Config/GetHostTimeDisabled" 1` (con la VM apagada).
- **Recordatorio:** tras cambios de hora, en el Create 3 (web `192.168.31.191:8080`) → *Beta Features → Restart NTP*.

### 3.3–3.5 VM, Guest Additions y carpeta compartida
- Instalación desatendida de VirtualBox → reinstalar eligiendo idioma/usuario propios.
- Guest Additions: `sudo apt install -y build-essential dkms linux-headers-$(uname -r)` antes de ejecutar el CD; `sudo usermod -aG vboxsf $USER`; reboot.
- Carpeta compartida `TFG`: montar con `sudo mount -t vboxsf TFG ~/compartida`. Para persistencia añadir a `/etc/fstab`:
  `TFG /home/gines/compartida vboxsf nofail,uid=1000,gid=1000 0 0`
- **Copiar el backend SIN el venv** (symlinks rotos en vboxsf): `rsync -a --exclude venv ~/compartida/backend/ ~/backend/` y recrear el venv en la VM.

### 3.6 El misterio del `ros2 topic list` vacío (tres capas)
1. **`ROS_SUPER_CLIENT=True` faltante:** con discovery server, la CLI/daemon solo ve el grafo completo si es super client.
2. **Server ID incorrecto:** el robot ejecuta `fast-discovery-server -i 1 -p 11811` (verificado en `/usr/sbin/discovery`). `ROS_DISCOVERY_SERVER` es **posicional por ID**: para el ID 1 hay que escribir `";192.168.31.191:11811"` (con `;` inicial). Sin él, el cliente busca un server ID 0 y el emparejamiento falla en silencio.
3. **Pista falsa de CycloneDDS:** la shell interactiva de la RPi tenía `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`, por lo que **ni el propio robot "veía" sus topics** (Cyclone ignora el discovery server y no ve a FastDDS). Los *nodos* del robot sí usan FastDDS (verificado con `/proc/<pid>/environ`). Diagnóstico definitivo: `ros2 doctor --report | grep -i middleware`.
- Además: tras `ros2 daemon stop; ros2 daemon start`, **esperar ~8 s** antes de `ros2 topic list`.
- **Resultado:** topics visibles → SLAM manual + RViz + teleop funcionaron (Hito 1 ✅, el robot se movió y mapeó).

### 3.7–3.8 IPs de casa hardcodeadas
- `backend/docker-compose.yml`: `KAFKA_ADVERTISED_LISTENERS: ...PLAINTEXT_HOST://192.168.0.67:9094` → el cliente conectaba al bootstrap `localhost:9094` pero Kafka lo redirigía a la IP de casa → timeouts. Cambiado a `localhost:9094` y recreados `kafka` + `init-kafka` (los tópicos se pierden al recrear: no hay volumen).
- `backend/.env`: `MINIO_ENDPOINT` y `GRAFANA_URL` → `localhost`.
- **Lección:** en la VM todo va por `localhost:<puerto publicado>` porque el contenedor ROS usa `--network host`.

### 3.9 explore_lite
- No existe `ros-humble-explore-lite` en apt. Solución: `git clone https://github.com/robo-friends/m-explore-ros2.git` en `robot_ws/src` y `colcon build`. Compila `explore_lite` + `explore_lite_msgs` (warnings de `multirobot_map_merge` inofensivos).

### 3.10 Adaptación de namespace (sim ↔ real)
- Cambios de código (retrocompatibles, parámetro `namespace`, por defecto `''` = simulador):
  - `patrol_nav.py`: `BasicNavigator(namespace=...)`, `odom`, `dock_status`, acciones `undock`/`dock`, servicio `map_saver/save_map` prefijados con `_robot_name()`.
  - `serve_telemetry.py`: las 6 suscripciones (battery/odom/dock/kidnap/slip/wheel) prefijadas.
  - `detect_incident.py`: cámara `oakd/rgb/preview/image_raw` prefijada.
  - `secret_helper.py`: sin cambios (no toca topics del robot).
- Nuevo launch **`patrol_bringup_real.launch.py`**: SLAM (o localización si hay mapa) + Nav2 + `map_saver` con lifecycle manager, todo bajo `namespace:=turtlebot4`, y `patrol_nav` con `namespace:=/turtlebot4`.
- Lanzamiento de los nodos sueltos en robot real: `--ros-args -p namespace:=/turtlebot4` (secret_helper sin namespace).

### 3.11 Mapa viejo → modo localización
- El launch autodetecta el modo según exista `<map_filepath>.yaml`. Un mapa viejo de simulación hizo arrancar AMCL/map_server. Borrar `mapa_patrulla.pgm/.yaml` para forzar SLAM. (El comando `reinstall` del propio patrol_nav hace esto en operación.)

### 3.12–3.13 Latencia de descubrimiento y visibilidad (la clave del día)
- **Con un solo discovery server (el del robot):** los ~12 nodos locales de Nav2 hacían TODO su descubrimiento por WiFi → `get_state` tardaba segundos, el *bond* (timeout 4 s) fallaba (`Server map_saver was unable to be reached after 4.00s`), bringup abortado.
- **Fix:** levantar un **discovery server local** en el contenedor (`fast-discovery-server -i 0 -p 11811`) y apuntar los nodos a ambos: `ROS_DISCOVERY_SERVER="127.0.0.1:11811;192.168.31.191:11811"`. Es exactamente la config de la sección 2 de `comandos_turtlebot4.md`. Resultado: Nav2 configura y activa en segundos, bonds conectan.
- **Pero sin super client los nodos no recibían el TF del robot** (`Invalid frame ID "odom"`). Con el server local ya en marcha, **re-añadir `ROS_SUPER_CLIENT=True`** dio a los nodos la visibilidad del robot sin recuperar la lentitud: TF del robot fluyendo a 12–17 Hz, `use_sim_time=False` verificado, endpoints de `/turtlebot4/tf` correctamente emparejados (publishers del robot + listeners de Nav2).
- **Trampa recurrente de variables cruzadas:** si la terminal del discovery server *local* hereda `ROS_DISCOVERY_SERVER` apuntando a la RPi, el servidor entra en conflicto y los nodos locales dejan de recibir el TF del robot. **Siempre `unset ROS_DISCOVERY_SERVER` (y `ROS_DOMAIN_ID`) en esa terminal antes de arrancar `fast-discovery-server`.** Este fue el origen de una recaída del `Invalid frame ID "odom"` que costó horas re-diagnosticar.

### 3.14 Confirmado en el lab: power-saver del dock (hipótesis A de la antigua §4)
- Verificado con el robot físico: acoplado en el dock, el RPLIDAR no gira y `/turtlebot4/scan` no publica; al desacoplarlo, el láser arranca y SLAM empieza a construir el mapa.
- **Regla operativa adoptada:** desacoplar el robot **antes** de lanzar el bringup (a mano o con `ros2 action send_goal /turtlebot4/undock irobot_create_msgs/action/Undock "{}"`). Sin esto, Nav2 nunca activa (necesita el frame `map` que SLAM solo produce con láser) y `patrol_nav` se queda esperando a `bt_navigator` para siempre — el conflicto de arranque descrito en la antigua §4 ("Implicación de diseño").
- La solución robusta en código (que `patrol_nav` haga undock antes de `waitUntilNav2Active()`) sigue pendiente como mejora; de momento el runbook lo resuelve operativamente.

### 3.15 Desincronización de relojes: hay TRES relojes, no dos (y VirtualBox sabotea)
- **Síntoma:** `Message Filter dropping message: frame 'rplidar_link' ... the timestamp on the message is earlier than all the data in the transform cache`. SLAM descarta todos los scans, la cola crece (>1900) y el sistema colapsa aunque todo lo demás esté bien.
- **Diagnóstico clave:** no basta con sincronizar VM↔RPi. El robot tiene **dos relojes internos independientes**: la RPi (que sella `/scan`) y la base **Create 3** (que sella `/odom` y `/tf`). Pueden desincronizarse *entre sí* aunque la VM esté perfecta. Comprobación rápida: comparar `odom.header.stamp.sec` con `date +%s` en la VM — deben coincidir a 0-1 s.
- **Agravante descubierto:** las Guest Additions de VirtualBox re-imponen periódicamente la hora del host Windows en la VM (Host Time Sync), deshaciendo el trabajo de chrony a mitad de ejecución. Es la causa de que el desfase "volviera" tras haberlo corregido.
- **Además:** el slewing de NTP converge demasiado despacio para offsets grandes; para el Create 3 la vía rápida es reiniciarlo (fuerza resync instantáneo al arrancar). Tras un reboot del Create 3 se verificó diff de 0 s exactos.
- **Fix completo (en orden):**
  1. *Una sola vez, con la VM apagada, en Windows:* `VBoxManage setextradata "<nombre-VM>" "VBoxInternal/Devices/VMMDev/0/Config/GetHostTimeDisabled" 1` (ya no es "pendiente opcional": es **obligatorio**).
  2. En la RPi: `sudo systemctl restart chrony`.
  3. En el Create 3 (web `192.168.31.191:8080`): *Beta Features → Restart NTP*; si el offset es grande, reiniciar el Create 3 directamente.
  4. En la VM: `sudo systemctl restart chrony && sudo chronyc makestep`.

### 3.16 Estabilidad del lifecycle de Nav2 en el robot real
- **map_saver / bonds (resuelto):** los bonds de Nav2 tienen timeout por defecto de 4 s, insuficiente en el robot real. Fix en código: `bond_timeout: 15.0` en los parámetros del `lifecycle_manager_map_saver` de [patrol_bringup_real.launch.py](robot_ws/src/patrol_nav/launch/patrol_bringup_real.launch.py) (tras editar: `rsync` al VM + `colcon build --packages-select patrol_nav` + re-source).
- **planner_server (workaround):** intermitentemente el `lifecycle_manager_navigation` aborta con `Failed to change state for node: planner_server. Exception: planner_server/get_state service client: async_send_request failed`. Descartado que sea CPU (4 cores, 89 % idle, 2.2 GB libres, load 0.4-0.7 durante el fallo). **No relanzar el bringup**: los nodos ya configurados se conservan; basta reintentar in-place:
  ```bash
  ros2 service call /turtlebot4/lifecycle_manager_navigation/manage_nodes \
    nav2_msgs/srv/ManageLifecycleNodes "{command: 0}"   # 0 = STARTUP
  ```
  Repetir hasta que complete (cada intento avanza más porque no reconfigura lo ya hecho). Pendiente de investigar la causa raíz si se vuelve frecuente (candidata: reducir el nº de super clients para descongestionar el descubrimiento).

### 3.17 Recuperación de la base Create 3 congelada
- **Síntoma:** el botón físico de undock no responde y `ros2 topic echo /turtlebot4/dock_status --once` se queda colgado sin respuesta → la base está bloqueada.
- **Recuperación (de menos a más invasivo):**
  1. Web del Create 3 (`192.168.31.191:8080`) → *Restart Application*.
  2. Si no responde: power-cycle físico (mantener el botón central ~7 s hasta apagar, esperar, encender, esperar ~2 min).
  3. Después, en la RPi: `sudo systemctl restart turtlebot4.service` para re-registrar el stack completo.
- Bonus: tras el reboot el reloj del Create 3 queda perfectamente sincronizado (ver §3.15).

### 3.18 Contenedor efímero (`--rm`): `/secrets` desaparecido
- **Síntoma:**
  ```
  FileNotFoundError: [Errno 2] No such file or directory: '/secrets/robot_token.txt'
  ```
- **Causa:** el contenedor se lanza con `docker run --rm` → al apagar la VM se destruyó, y el recreado no llevaba el volumen `-v $HOME/robot_ws/secrets:/secrets`. Todo lo que vive en el filesystem del contenedor (y no en un volumen) muere con él; lo que va por bind mount (`/robot_ws`: código, `install/`, explore_lite compilado, mapas) sobrevive.
- **Fix:** `mkdir -p ~/robot_ws/secrets` en el host y **siempre** incluir el volumen en el `docker run`. Con el volumen, el token TOFU persiste entre sesiones (que es el sentido del modelo Trust-On-First-Use); sin él, el robot repite el first-boot en cada arranque.

### 3.19 NUNCA resincronizar relojes con el stack corriendo
- **Qué pasó:** con el bringup y explore en marcha, se detectó desfase de relojes y se corrigió (Restart NTP del Create 3). Los relojes quedaron bien… pero el sistema quedó peor:
  ```
  [planner_server] Extrapolation Error: Requested time 1783089326.77 but the earliest data
                   is at time 1783089507.62 (≈181 s de hueco)
  ```
  y el mapa en RViz apareció corrupto (rayas radiales atravesando paredes: scans registrados con tiempos incoherentes).
- **Por qué:** el buffer de TF solo guarda ~10 s de historia; los goals de explore y medio mapa de SLAM quedaron sellados "en el pasado" respecto al reloj corregido → intransformables.
- **Regla operativa (para la memoria):** el ajuste de relojes corrige el futuro pero envenena todo lo sellado en el pasado. **Relojes primero, bringup después, siempre.** Si hay que resincronizar, se tira el stack (Ctrl-C), se corrigen relojes, se verifica (`odom.sec` vs `date +%s` a 0-1 s) y se relanza de cero.

### 3.20 QoS de la cámara en `detect_incident` (bug latente sim→real)
- Revisando por qué no llegaban imágenes se encontró que `detect_incident` se suscribía con QoS por defecto (**RELIABLE**, depth 10). Para topics de sensor lo canónico es `qos_profile_sensor_data` (BEST_EFFORT): un suscriptor best_effort empareja con publishers reliable **y** best_effort; uno reliable solo con reliable.
- Curiosamente **no era el bloqueante aquí**: la OAK-D del TB4 publica RELIABLE (verificado con `ros2 topic info --verbose`), así que habría emparejado. Pero en el simulador u otras cámaras (best_effort) habría fallado en silencio. Corregido en `detect_incident.py` (import `qos_profile_sensor_data` + usarlo en la suscripción) y recompilado.
- **Trampa de diagnóstico aprendida:** no inferir la QoS del publisher a partir de la de otros suscriptores; pedirla siempre con `ros2 topic info <topic> --verbose`.

### 3.21 La OAK-D tiene DOS modos de fallo distintos
**Modo 1 — power-saver del dock (esperado, documentado):** acoplado, el `turtlebot4_node` llama a `oakd/stop_camera`; al desacoplar, a `oakd/start_camera`. Ciclo visible en el journal:
  ```
  [turtlebot4_node] OAKD stopped  → oakd/stop_camera service available, sending request
  [turtlebot4_node] OAKD started  → oakd/start_camera service available, sending request
  ```
**Modo 2 — el driver DepthAI no carga en un arranque dado (fallo intermitente):** tras un `systemctl restart turtlebot4.service`, el componente `oakd` puede no cargarse en absoluto. Firma en el journal del boot malo: **no existe ninguna línea de DepthAI** (ni `Load Library`, ni `MXID`, ni `Camera ready!`) y el turtlebot4_node repite:
  ```
  [turtlebot4_node] [ERROR] Service oakd/start_camera unavailable.
  ```
  El `/turtlebot4/oakd_container` aparece en `ros2 node list` pero es un contenedor vacío. Consecuencia: el topic existe (lo advertisa el resto del grafo) pero `Publisher count: 0` y cero frames **incluso en la propia RPi** — lo que descartó QoS y transporte WiFi como causas.
- **Diagnóstico en 5 s:** `journalctl -u turtlebot4.service -b --no-pager | grep -i 'camera ready'` — si no aparece en el boot actual, el driver no está.
- **Recuperación:** `sudo systemctl restart turtlebot4.service` y re-comprobar (a veces hacen falta varios intentos); en el peor caso, power-cycle completo del robot **con batería sana**. Boot bueno de referencia:
  ```
  [turtlebot4.oakd] Camera with MXID: 18443010E10E5F0E00 and Name: 1.1.1 connected!
  [turtlebot4.oakd] USB SPEED: SUPER · Device type: OAK-D-LITE · Camera ready!
  ```

**Modo 3 — componente cargado pero COLGADO (el peor: veredicto final de la sesión).** El driver carga (`Camera ready!` en el journal) y al desacoplar el `turtlebot4_node` envía `start_camera`… pero el componente no responde: ni "Starting camera", ni error, ni frames. Evidencia recogida (con batería al 30 %, recién cargada):
  ```
  17:06:42 [turtlebot4_node] OAKD started
  17:06:43 [turtlebot4_node] oakd/start_camera service available, sending request
           → (ninguna respuesta del componente oakd; compárese con el ciclo sano,
              donde cada petición produce un "[turtlebot4.oakd] Stopping/Starting camera.")
  ```
  - `ros2 service call /turtlebot4/oakd/start_camera std_srvs/srv/Trigger "{}"` → **se queda sin respuesta** (un Trigger sano contesta en ms).
  - `ros2 topic hz .../rgb/preview/camera_info` (mensaje de bytes, descarta tamaño/transporte) → **silencio, también en la propia RPi**.
  - Contraste: el RPLIDAR completó su ciclo (`start_motor service completed`) en el mismo undock — el fallo es exclusivo del subsistema cámara.
  Conclusión: cuelgue interno del driver DepthAI / firmware de la OAK-D-LITE, intermitente, no atribuible al software del proyecto.

### 3.22 Jitter de transporte medido: la causa de los drops de scan bajo carga (evidencia cuantitativa)
- **Contexto:** en la run limpia final (relojes verificados a 0 s ANTES de lanzar), los `Message Filter dropping message ... earlier than all the data in the transform cache` persistieron durante toda la sesión → ya no podía ser desfase de relojes. Se midió la entrega de `/turtlebot4/scan` en la VM con `ros2 topic hz --window 50` en dos condiciones:

| Métrica | Baseline (solo robot publicando) | Bajo carga (bringup completo) | Degradación |
|---|---|---|---|
| Frecuencia media | **7,86 Hz** (estable) | **0,60–1,25 Hz** | ~13× |
| Desviación típica inter-mensaje | **6–8 ms** | **2,5–2,8 s** | **~400×** |
| Hueco máximo entre scans | 0,144 s | **16,12 s** | ~110× |

- Complementario (`ros2 topic bw`): mensajes de **8,71 KB** a ~63–69 KB/s (~0,5 Mbps) → **NO es saturación de ancho de banda** (irrisorio para WiFi). La degradación aparece solo con el stack completo → contención de la capa de transporte/virtualización bajo carga (DDS reliable con reintentos, decenas de endpoints, bridge de VirtualBox).
- **Mecanismo causal cerrado:** el buffer de TF retiene ~10 s; un scan que llega con 16 s de retraso encuentra todo el buffer "más nuevo" que él → exactamente el error observado (`timestamp earlier than all the data in the transform cache`) → SLAM privado de láser → mapa a trompicones → explore_lite no completa goals.
- **Descartes previos que apuntalan la conclusión:** relojes (verificados a 0 s justo antes), CPU (89 % idle medido en fallo análogo), configuración DDS/QoS (TF y topics pequeños fluyendo, Nav2 activó, FSM transitó).
- **Conclusión (para la memoria):** el software del proyecto es funcionalmente correcto; la validación completa del ciclo de patrulla quedó limitada por una degradación del transporte **medida** (13× frecuencia, 400× jitter, huecos > buffer TF), atribuible al banco de pruebas (VM VirtualBox + bridge WiFi), no al código. Mitigaciones futuras: PC nativo en la LAN del robot, red cableada, aumentar `transform_tolerance`/colas, o ejecutar los nodos pesados en la propia RPi.
- Detalle ilustrativo: bajo carga, el propio `topic hz` necesitó dos intentos y >10 s para el primer mensaje, con el robot publicando a 7,9 Hz reales.

### 3.23 Batería crítica: el desestabilizador silencioso
- Tras ~horas de pruebas sin volver al dock, el anillo del Create 3 quedó en **rojo** (batería crítica). Efectos observados, todos desconcertantes hasta ver el patrón común:
  - El botón central **no encendía** el robot (hubo que ponerlo en el dock, que lo enciende solo al detectar corriente).
  - La base se **congeló** (botón de undock sin efecto, `dock_status` colgado) → Restart Application desde la web.
  - El driver de la OAK-D **fallaba al cargar** (modo 2 de §3.21) — la cámara consume bastante por USB al inicializar y con la batería en las últimas la alimentación no da.
- **Lección operativa:** comprobar la batería **al principio de cada sesión** y vigilarla durante:
  ```bash
  ros2 topic echo /turtlebot4/battery_state --field percentage --once
  ```
  Por debajo de ~30 %, los fallos raros dejan de ser diagnósticos fiables. El robot publica la batería incluso docked (el power-saver solo apaga lidar/cámara).

---

## 4. Estado de validación en el robot real (3 jul) — base para la sección de resultados

El antiguo "problema actual" de esta sección (`/turtlebot4/scan` no llegaba) quedó **resuelto y verificado en el lab**: eran dos causas superpuestas — el power-saver del dock (§3.14) y la desincronización de relojes RPi↔Create 3↔VM agravada por VirtualBox (§3.15).

### 4.1 Matriz de validación por componente

| Componente | Estado | Evidencia / motivo |
|---|---|---|
| Conectividad VM↔robot (bridged + dual discovery server + super client) | ✅ **Validado** | Topics del robot visibles, TF a 12–17 Hz, SLAM+teleop (Hito 1) |
| Sincronización de relojes (chrony + Create 3 + VBox aislado) | ✅ **Validado** | `odom.sec` == `date +%s` (diff 0 s); RPi↔VM a 10 ms por SSH |
| Bringup completo (SLAM + Nav2 + map_saver + patrol_nav) | ✅ **Validado** | `bt_navigator` activo; nodos lifecycle arriba (con el workaround §3.16 cuando toca) |
| Orquestación por Kafka (backend → `start_patrol` → FSM) | ✅ **Validado** | `patrol_nav`: `IDLE → EXPLORING`, `explore_lite` lanzado |
| **`secret_helper`** (TOFU + servicio `get_robot_token`) | ✅ **Validado** | First boot completado contra el backend; token persistido en `/secrets` (tras fix §3.18) |
| **`serve_telemetry`** (robot → Kafka → Influx → Grafana) | ✅ **Validado** | Telemetría real (batería/odom/dock) visible en el dashboard de Grafana; datos generados moviendo el robot por teleop |
| **`detect_incident`** (cámara → YOLO → MinIO + Kafka) | ❌ **Bloqueado por hardware (veredicto confirmado)** | Re-test con batería recargada y `Camera ready!` verificado: el componente oakd quedó colgado internamente (modo 3, §3.21) — `start_camera` sin respuesta, `camera_info` en silencio incluso en la propia RPi. El nodo del proyecto quedó verificado hasta donde el hardware permitió: arranque, carga YOLO local, suscripción con QoS correcta (§3.20), conexión MinIO/Kafka/secret_helper. Descartadas por capas: QoS, transporte DDS/WiFi, power-saver, alimentación |
| Exploración autónoma sostenida (`EXPLORING` completo) | ⚠️ **Parcial — limitado por transporte (cuantificado)** | explore_lite se lanzó y Nav2 activó en la run limpia final, pero `/scan` llegaba degradado: 7,86 Hz→0,6 Hz, jitter ×400, huecos de 16 s > buffer TF (medición en §3.22). El mapa crecía a trompicones y explore no completaba goals. Limitación del banco de pruebas (VM+WiFi), no del software |
| Ciclo FSM completo (`SAVING_MAP → PLANNING → PATROLLING`) | ⏳ **No ejercitado** | Requiere completar una exploración; nunca se llegó a la fase de guardado de mapa en el robot real. El `bond_timeout: 15.0` del map_saver está aplicado pero sin validar end-to-end (una vez apareció también `change_state service is not available!` — vigilar) |
| RViz remoto (`turtlebot4_viz`) | ✅ **Validado** | Mapa y sensores visibles en vivo desde la VM (fue lo que destapó el mapa corrupto de §3.19) |

### 4.2 Por qué no se pudo probar lo pendiente (argumentario para la memoria)

Las dos pruebas incompletas **no fallaron por defectos del software del proyecto**, sino por limitaciones operativas del hardware compartido de laboratorio:

1. **`detect_incident` end-to-end:** la OAK-D-LITE presentó fallos intermitentes en dos variantes: el driver DepthAI que no se instancia en algunos arranques (§3.21 modo 2) y, tras recargar batería y verificar `Camera ready!`, un **cuelgue interno del componente** que no responde a `start_camera` ni publica `camera_info` ni siquiera en la propia RPi (§3.21 modo 3 — veredicto final). El diagnóstico se hizo **descartando capas**: QoS (verificada con `topic info --verbose`), transporte DDS/WiFi (el fallo se reproduce localmente en la RPi), power-saver del dock (ciclo `stop/start_camera` verificado en el journal), estado del driver (`Camera ready!`) y alimentación (reproducido tras recarga y power-cycle). El fallo queda aislado en el subsistema cámara (hardware/firmware), ajeno al software del proyecto. El nodo quedó verificado hasta donde el hardware permitió: arranque, carga del modelo YOLO en local (sin internet), suscripción con QoS correcta y conexión con MinIO/Kafka/secret_helper.
2. **Ciclo completo de patrulla:** la exploración se interrumpió por causas diagnosticadas y ajenas a la FSM: desfase de relojes corregido en caliente (§3.19), batería crítica (§3.23) y, en la run limpia final, la **degradación de transporte medida y cuantificada en §3.22** (frecuencia de `/scan` de 7,86 Hz a 0,6 Hz bajo carga, jitter ×400, huecos de 16 s que exceden el buffer TF de 10 s). La FSM demostró las transiciones `IDLE → EXPLORING` con lanzamiento efectivo de explore_lite y Nav2 completamente activo; el cuello de botella quedó aislado en la capa de transporte del banco de pruebas (VM VirtualBox + bridge WiFi), no en el software del proyecto.

### 4.3 Flecos abiertos (técnica)

1. **Deriva de reloj en ejecuciones largas.** Mitigada con `GetHostTimeDisabled=1` (VM `ubuntu22`) + `chronyc makestep`; vigilar en la próxima sesión larga.
2. **Aborto intermitente de `lifecycle_manager_navigation` en `planner_server`** (§3.16). Workaround estable (reintento `manage_nodes`); causa raíz sin identificar.
3. **Mejora de código pendiente:** `undock` automático antes de `waitUntilNav2Active()` en patrol_nav (hoy es paso manual del runbook, §3.14). Buena discusión de diseño para la memoria.
4. **Fallo intermitente del driver OAK-D** (§3.21): sin causa raíz confirmada (sospecha: estado USB sucio entre reinicios + alimentación con batería baja). Detección y recuperación documentadas.

---

## 5. Runbook de arranque definitivo (validado 3 jul)

> Preparación (con internet, WiFi normal): imagen construida, backend levantado, venv hecho.
> Pruebas (WiFi `Xiaomi Robot`, sin internet): todo lo de abajo, **en este orden estricto**.

### Checklist previa (5 min que ahorran horas)

```bash
# 1. BATERÍA — por debajo de ~30 % nada de lo que falle es diagnóstico fiable (§3.23)
ros2 topic echo /turtlebot4/battery_state --field percentage --once

# 2. RELOJES — los TRES, JUSTO antes de lanzar (no vale de hace media hora), stack parado (§3.19)
ssh ubuntu@192.168.31.191 'date +%s.%N'; date +%s.%N        # RPi vs VM (deben diferir < 1 s)
ros2 topic echo /turtlebot4/odom --field header.stamp --once; date +%s   # Create 3 vs VM

# 3. CÁMARA — si la sesión usa detect_incident: verificar que el driver cargó en este boot (§3.21)
ssh ubuntu@192.168.31.191 "journalctl -u turtlebot4.service -b --no-pager | grep -i 'camera ready'"
```

Si falla el 2 → §3.15 (Restart NTP / reboot del Create 3) **antes** de lanzar nada.
Si falla el 3 → `sudo systemctl restart turtlebot4.service` en la RPi y re-comprobar.

### Paso 0 — Aislar el reloj de VirtualBox (solo 1 vez, en Windows, con la VM apagada)

```cmd
cd "C:\Program Files\Oracle\VirtualBox"
VBoxManage setextradata "ubuntu22" "VBoxInternal/Devices/VMMDev/0/Config/GetHostTimeDisabled" 1
```

> El nombre de la VM es `ubuntu22` (el que aparece en la lista de VirtualBox). Requiere la VM apagada; comprobar con `VBoxManage getextradata "ubuntu22" "VBoxInternal/Devices/VMMDev/0/Config/GetHostTimeDisabled"` → debe dar `Value: 1`.

### Paso 1 — Infraestructura base (Terminal 1, host VM)

```bash
# Forzar hora correcta contra la RPi
sudo systemctl restart chrony
sudo systemctl enable chrony
sudo chronyc makestep

# Levantar backend
cd ~/backend && docker compose up -d
source venv/bin/activate && uvicorn src.server:app --host 0.0.0.0 --port 8000
```

> Si SLAM descarta scans por timestamps (§3.15): comprobar `odom.header.stamp.sec` vs `date +%s`; si difieren, *Restart NTP* en la web del Create 3 (`192.168.31.191:8080`) o reiniciar el Create 3.

### Paso 2 — Servidor DDS local (Terminal 2, dentro del contenedor)

```bash
# ¡CRÍTICO eliminar las variables heredadas! (ver §3.13, trampa de variables cruzadas)
unset ROS_DISCOVERY_SERVER
unset ROS_DOMAIN_ID
fast-discovery-server -i 0 -p 11811
# dejar corriendo
```

### Paso 3 — Preparar robot y bringup (Terminal 3, dentro del contenedor)

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

# Configuración DDS estricta
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=0
export ROS_DISCOVERY_SERVER="127.0.0.1:11811;192.168.31.191:11811"
export ROS_SUPER_CLIENT=True

# Limpiar caché de ROS 2
ros2 daemon stop; ros2 daemon start
sleep 8

# Desacoplar el robot para encender el láser (si está en el dock — ver §3.14)
ros2 action send_goal /turtlebot4/undock irobot_create_msgs/action/Undock "{}"

# Borrar mapa anterior si queremos empezar de cero
rm -f /robot_ws/src/mapa_patrulla.{pgm,yaml}

# Lanzar bringup
ros2 launch patrol_nav patrol_bringup_real.launch.py robot_id:=RBT-01
```

> Si aborta con `Failed to change state for node: planner_server` (§3.16), **NO relanzar**; en otra terminal (con los mismos exports):
> ```bash
> ros2 service call /turtlebot4/lifecycle_manager_navigation/manage_nodes \
>   nav2_msgs/srv/ManageLifecycleNodes "{command: 0}"
> ```
> y repetir hasta que active `bt_navigator`.

### Paso 4 — Nodos del proyecto (Terminal 4, dentro del contenedor)

```bash
source install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=0
export ROS_DISCOVERY_SERVER="127.0.0.1:11811;192.168.31.191:11811"
export ROS_SUPER_CLIENT=True

ros2 run secret_helper secret_helper_node &
ros2 run serve_telemetry serve_telemetry_node --ros-args -p namespace:=/turtlebot4 &
ros2 run detect_incident detect_incident_node --ros-args -p namespace:=/turtlebot4 &
```

### Paso 5 — Opcional: visualización (Terminal 5, dentro del contenedor)

```bash
source install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="127.0.0.1:11811;192.168.31.191:11811"
export ROS_SUPER_CLIENT=True

ros2 launch turtlebot4_viz view_robot.launch.py namespace:=/turtlebot4
```

### Paso 6 — Disparar la patrulla (Terminal 6, host VM)

```bash
docker exec -i tfg_kafka kafka-console-producer --bootstrap-server kafka:29092 \
  --topic robot_commands <<< '{"robot_id":"RBT-01","command":"start_patrol"}'
```

Secuencia esperada de la FSM: `IDLE → UNDOCKING (si docked) → EXPLORING (explore_lite) → SAVING_MAP → PLANNING → PATROLLING`.

### Notas y troubleshooting

- La `.env.robot` apunta todo a `localhost` (kafka `9094`, minio `9000`, backend `8000`) — válido gracias a `--network host`.
- `detect_incident` también depende de la OAK-D → **apagada cuando el robot está docked** (mismo power-saver que el lidar).
- **Base Create 3 congelada** (undock físico no responde, `dock_status` colgado): recuperación en §3.17.
- **Topics del robot desaparecen:** en la RPi, `sudo systemctl restart turtlebot4.service`.
- **El contenedor es efímero (`--rm`):** al apagar la VM desaparece; se recrea con el mismo `docker run` (la imagen y `/robot_ws` persisten). No olvidar el volumen `-v $HOME/robot_ws/secrets:/secrets` o `secret_helper` muere con `FileNotFoundError` (§3.18). El robot enciende poniéndolo en el dock si el botón no responde (batería baja).
- **La cámara no publica:** comprobar journal (`grep 'camera ready'`, §3.21) y batería (§3.23) ANTES de sospechar de QoS o de la red — hoy costó una tarde llegar a eso.
- **NUNCA corregir relojes con el stack corriendo** (§3.19): Ctrl-C, corregir, verificar, relanzar.
- Tras editar el launch de `patrol_nav`: `rsync` del `robot_ws` a la VM + `colcon build --packages-select patrol_nav` + re-`source install/setup.bash`.

---

## 6. DOSSIER FINAL DE LA SESIÓN DE PRUEBAS REALES (3 de julio de 2026)

> **Propósito de esta sección:** documento autocontenido con TODA la información resultante de la campaña de pruebas con el TurtleBot 4 real, pensado para redactar la sección de "Resultados en robot real" de la memoria del TFG sin necesitar contexto adicional. Incluye el banco de pruebas exacto, los resultados validados con su evidencia, los no validados con su causa raíz diagnosticada, todas las métricas cuantitativas tomadas, los cambios de código realizados, y el argumentario defendible con sus matices.

### 6.1 Banco de pruebas (setup experimental exacto)

| Elemento | Detalle |
|---|---|
| Robot | TurtleBot 4 (ROS 2 Humble): base iRobot Create 3 + Raspberry Pi 4 (`192.168.31.191`) + RPLIDAR + cámara OAK-D-LITE (MXID `18443010E10E5F0E00`, USB 3 "SUPER") |
| Red | WiFi `Xiaomi Robot`, aislada, sin internet, subred `192.168.31.0/24` |
| PC de desarrollo | Windows 10 Pro (sin soporte WSL2 mirrored) → **VM VirtualBox `ubuntu22`** (Ubuntu 22.04) con adaptador **puente** sobre la WiFi (IP propia en la subred del robot) |
| Sincronía de hora | chrony en la VM siguiendo a la RPi (`server 192.168.31.191 iburst prefer`); sincronización de hora de VirtualBox **desactivada** (`GetHostTimeDisabled=1`); Create 3 sincroniza por NTP contra la RPi |
| Middleware | FastDDS (`rmw_fastrtps_cpp`), `ROS_DOMAIN_ID=0`, namespace `/turtlebot4` |
| Descubrimiento | **Dual discovery server**: servidor del robot (ID 1, `192.168.31.191:11811`) + servidor local en el contenedor (ID 0, `127.0.0.1:11811`), con `ROS_SUPER_CLIENT=True` en todos los nodos locales |
| Contenedor ROS | Imagen propia `ros2_robot:latest`, `docker run --rm --network host`, workspace por bind mount `/robot_ws`, secretos en volumen `/secrets` |
| Backend | docker compose en la VM: Postgres, Kafka (`localhost:9094`), MinIO (`:9000`), InfluxDB, Grafana (`:3000`) + FastAPI con uvicorn (`:8000`) |
| Nodos del proyecto | `patrol_nav` (orquestador FSM), `serve_telemetry`, `detect_incident` (YOLOv8n local), `secret_helper` (TOFU/JWT), `explore_lite` (compilado de fuente, m-explore-ros2) |
| Stack de navegación | slam_toolbox (sync) + Nav2 completo + map_saver_server, todo bajo `namespace:=turtlebot4`, lanzado por `patrol_bringup_real.launch.py` |

### 6.2 Resultados VALIDADOS (con su evidencia)

1. **Conectividad y descubrimiento VM↔robot.** Topics del robot visibles desde la VM, TF del robot fluyendo a 12–17 Hz, acciones (`undock`/`dock`) y servicios del robot invocables. Evidencia: sesiones de `ros2 topic list/echo/hz`, Hito 1 (SLAM manual + RViz + teleop, el robot se movió y mapeó).
2. **Sincronización de relojes a nivel de milisegundos.** Medido RPi↔VM por SSH simultáneo: **10 ms** de diferencia (`1783087850.165` vs `.175`). Create 3↔VM tras reboot: **0 s** (`odom.header.stamp.sec` == `date +%s`). El modelo "PC sigue al robot vía chrony + Create 3 vía NTP + VBox aislado" funciona.
3. **Bringup completo de navegación en robot real.** slam_toolbox registró el sensor lidar; Nav2 configuró y activó los 7 servidores (controller, smoother, planner, behavior, bt_navigator, waypoint_follower, velocity_smoother) hasta `Managed nodes are active` y `Nav2 is ready for use!`; map_saver como lifecycle node con su manager. Log de referencia: run del 3 jul 17:38 (arranque completo en ~100 s incluyendo esperas de TF).
4. **Orquestación completa backend→robot.** Comando `{"robot_id":"RBT-01","command":"start_patrol"}` publicado en Kafka (`robot_commands`) desde el backend → `patrol_nav` lo consume → FSM transita `IDLE → EXPLORING` → lanza `explore_lite` como subproceso → explore espera el costmap. Observado en **dos runs distintas**. Heartbeat del orquestador activo hacia la API (`http://localhost:8000`, cada 10 s).
5. **`secret_helper` end-to-end.** Proceso TOFU (Trust On First Use) completado contra el backend real: obtención del token JWT en el first boot, persistencia en `/secrets/robot_token.txt` (tras corregir el volumen), servicio `get_robot_token` disponible para el resto de nodos.
6. **`serve_telemetry` end-to-end.** Telemetría real del robot (batería, odometría, dock, kidnap, slip, wheel) fluyendo robot→nodo→Kafka→InfluxDB→**dashboard de Grafana** (visualizado en vivo). Datos de movimiento generados por teleoperación (`teleop_twist_keyboard` con remap a `/turtlebot4/cmd_vel`).
7. **Construcción de mapa real (parcial).** El costmap estático creció de 156×181 a 159×183 celdas a 0,05 m/px durante la exploración (≈7,9×9,2 m de entorno mapeado), demostrando el pipeline scan→SLAM→map→costmap, aunque a ritmo degradado (ver 6.4).
8. **RViz remoto** (`turtlebot4_viz view_robot.launch.py`) mostrando mapa, sensores y pose en vivo desde la VM.

### 6.3 Resultados NO validados y su CAUSA RAÍZ diagnosticada

**A. `detect_incident` end-to-end (cámara→YOLO→MinIO+Kafka) — bloqueado por hardware.**
- El nodo del proyecto quedó verificado hasta donde el hardware permitió: arranca, carga YOLOv8n **en local sin internet** (`yolov8n.pt` en el workspace), se suscribe con QoS correcta, conecta con MinIO/Kafka/secret_helper. **Nunca recibió un frame que procesar.**
- Autopsia de la cámara OAK-D-LITE (cronología con logs en §3.21):
  - Boot 15:53 — driver DepthAI carga y conecta: `Camera with MXID ... connected!`, `USB SPEED: SUPER`, `Camera ready!`. Ciclo del power-saver correcto (`stop_camera`/`start_camera` al acoplar/desacoplar).
  - Boot 16:03 — **el componente DepthAI no se instancia en absoluto** (ni una línea suya en el journal); `turtlebot4_node` repite `Service oakd/start_camera unavailable`.
  - Boot 16:20 — driver carga bien de nuevo (`Camera ready!`).
  - 17:06 (desacoplado, batería cargando) — `start_camera` se envía… y el componente **no responde**: ni log de respuesta, ni `success`, la llamada directa `ros2 service call .../start_camera` se queda colgada, `camera_info` (mensaje diminuto) tampoco publica **ni siquiera en la propia RPi**.
- **Descartes realizados (en orden):** QoS (verificada con `topic info --verbose`; el publisher del robot es RELIABLE y emparejaría), transporte WiFi (el fallo se reproduce en la RPi, sin red), power-saver del dock (ciclo verificado en journal), carga del driver (verificado `Camera ready!`), alimentación (reproducido tras recarga y power-cycle completo).
- **Veredicto:** fallo intermitente del subsistema cámara (componente DepthAI que unas veces no carga y otras se cuelga sin atender servicios), **ajeno al software del proyecto**. Hardware compartido de laboratorio.

**B. Ciclo FSM completo `EXPLORING → SAVING_MAP → PLANNING → PATROLLING` — no ejercitado, limitado por transporte (medido).**
- En la run limpia final (relojes verificados a 0 s justo antes, batería recargada), Nav2 activó y la FSM lanzó explore, pero los `/scan` llegaban tan degradados a la VM que slam_toolbox descartaba la mayoría (`Message Filter dropping message ... timestamp earlier than all the data in the transform cache` + `queue is full` de forma continua durante ~6 min) → el mapa crecía a trompicones → explore_lite no completaba goals → nunca se alcanzó la condición de fin de exploración (idle 180 s tras mínimo 900 s).
- La causa se midió (sección 6.4): no eran relojes (verificados), ni CPU (89 % idle medido en fallo análogo), ni ancho de banda (~0,5 Mbps), sino **jitter de entrega bajo carga** en la capa VM/bridge/DDS.

### 6.4 MÉTRICAS cuantitativas tomadas (todas)

**a) Jitter de entrega de `/turtlebot4/scan` en la VM** (`ros2 topic hz --window 50`, 3 jul ~19:50):

| Métrica | Baseline (solo robot publicando) | Bajo carga (bringup Nav2+SLAM activo) | Factor |
|---|---|---|---|
| Frecuencia media | **7,86 Hz** (estable 7,85–8,12) | **0,60–1,25 Hz** | ÷13 |
| Intervalo mínimo | 0,111–0,116 s | 0,010–0,015 s (ráfagas) | — |
| Intervalo máximo | 0,144 s (régimen); 0,327 s (transitorio inicial) | **16,120 s** | ×110 |
| Desviación típica | **6–8 ms** | **2,5–2,8 s** | **×400** |
| Nota | — | el propio `topic hz` tardó >10 s y 2 intentos en recibir el primer mensaje | — |

**b) Caudal del scan** (`ros2 topic bw`): mensajes de **8,71 KB constantes**, 50,9–69,9 KB/s (≈**0,5 Mbps**, ~7–8 msg/s) → descarta saturación de ancho de banda; la WiFi soporta órdenes de magnitud más.

**c) Relojes:**
- RPi↔VM (SSH simultáneo): **10 ms** de offset.
- Create 3↔VM tras reboot de la base: **0 s** (epoch idéntico).
- Episodio de desfase detectado: scan (RPi) ~4–5 s por detrás del odom (Create 3) — corregido con restart de chrony/NTP + reboot del Create 3.
- Corrección en caliente (PROHIBIDA a posteriori): dejó un hueco de **181 s** entre el goal pendiente y el buffer TF (`Requested time 1783089326.78, earliest 1783089507.63`) y un mapa corrupto.
- Transitorio normal de arranque (inofensivo, se autoresuelve): 0,03 s (`432.985` vs `433.011`).

**d) Recursos de la VM durante fallo del lifecycle (descarte de CPU):** 4 cores, **89 % idle**, 2,2 GB RAM libre, load average 0,43–0,72.

**e) Tiempos de arranque observados:** bringup completo hasta `Nav2 is ready for use!` ≈ **100 s** (incluye ~50 s de espera de TF `odom` y ~40 s de espera del frame `map` del primer scan aceptado); driver DepthAI: conexión en ~3 s + pipeline en ~2 s cuando carga bien.

**f) Buffer de TF de Nav2:** ~10 s de historia → cualquier retraso de entrega > 10 s produce descarte garantizado del mensaje (mecanismo exacto del error observado, dado el hueco máximo medido de 16,12 s).

**g) Mapa construido:** de 156×181 a 159×183 celdas @ 0,05 m/px en ~5 min de exploración degradada.

### 6.5 Cambios de código realizados DURANTE la campaña (commits de la sesión)

1. **`patrol_bringup_real.launch.py`** (nuevo, pre-sesión + fix in-situ): bringup real con namespace, y `bond_timeout: 15.0` en el lifecycle manager del map_saver (los bonds de 4 s por defecto expiraban con la latencia real).
2. **`detect_incident.py`**: suscripción de cámara cambiada de QoS por defecto (RELIABLE, depth 10) a `qos_profile_sensor_data` — bug latente sim→real detectado durante el diagnóstico (no era el bloqueante, pero fallaría en silencio con cámaras BEST_EFFORT).
3. **Parametrización por `namespace`** en `patrol_nav`, `serve_telemetry`, `detect_incident` (pre-sesión, validada hoy en real).
4. **Workaround operativo** (sin código): reintento in-place del bringup de Nav2 vía `ros2 service call .../lifecycle_manager_navigation/manage_nodes "{command: 0}"` cuando `planner_server` aborta con `async_send_request failed` (intermitente, causa raíz abierta).

### 6.6 Mejoras identificadas y NO implementadas (trabajo futuro justificado)

1. **Undock automático antes de `waitUntilNav2Active()`** en patrol_nav: conflicto de diseño detectado — Nav2 no puede activar sin láser, y el láser está apagado en el dock; hoy se resuelve operativamente (undock manual pre-bringup).
2. **Periodo de estabilización antes de lanzar explore_lite** (~10 s tras `map` disponible): la sugerencia del tutor, reencuadrada — un timeout de *lookup* de TF no cura extrapolaciones "into the past", pero un retardo de arranque sí evita los transitorios.
3. **`transform_tolerance` de los costmaps** (hoy 0,2 s): elevarlo amortiguaría el jitter moderado (no los huecos de 16 s).
4. **Mitigaciones del transporte** (la mejora de fondo): PC nativo en la LAN del robot (sin virtualización), enlace cableado, o ejecutar los nodos pesados (SLAM/Nav2) en la propia RPi dejando en el PC solo la supervisión.
5. **Investigar la causa raíz** del aborto intermitente de `planner_server` y del cuelgue del componente DepthAI (candidatos: congestión de descubrimiento con super clients; estado USB sucio entre reinicios del servicio).

### 6.7 Catálogo completo de problemas (24) — índice temático

*Detalle individual en §2 (tabla) y §3 (análisis). Agrupados por naturaleza para la redacción:*

- **Entorno/virtualización (5):** WSL2 inviable para DDS (#1), chrony bloqueado por Hyper-V (#2), instalación VirtualBox (#3-4), carpetas compartidas/symlinks (#5), contenedor efímero y volúmenes (#19).
- **Red/DDS (5):** descubrimiento posicional por ID y super client (#6), latencia de descubrimiento con un solo server → dual server local (#12-13), variables cruzadas en la terminal del server local (#3.13-bis), **jitter de transporte bajo carga — medido (#24)**.
- **Tiempo (3):** tres relojes independientes RPi/Create3/VM (#15), VirtualBox pisando a chrony (#15), resincronizar en caliente envenena TF/mapa/goals (#20).
- **Hardware del robot (4):** power-saver del dock apaga lidar+cámara (#14), Create 3 congelado (#18), driver DepthAI intermitente (#22), batería crítica como desestabilizador transversal (#23).
- **Configuración heredada (3):** IPs de casa hardcodeadas en compose/.env (#7-8), mapa viejo forzando modo localización (#11), explore_lite sin binario en Humble (#9).
- **Software propio — bugs reales encontrados (3):** topics sin namespace para el robot real (#10), QoS RELIABLE en cámara (#21), bonds de 4 s insuficientes (#16).
- **Nav2 (1):** aborto intermitente de planner_server con workaround (#17).

### 6.8 Argumentario para la memoria (claims defendibles + matices obligatorios)

**Se puede afirmar:**
- La arquitectura completa (backend cloud-like + orquestador FSM + Nav2 + robot físico) **funciona en hardware real**: quedó demostrada la cadena de mando completa Kafka→FSM→Nav2→actuadores y la de datos robot→telemetría→Influx/Grafana, más la de seguridad (TOFU/JWT).
- Las partes no validadas por completo tienen **causa raíz diagnosticada y medida, externa al software del proyecto**: (a) cámara con fallo intermitente de driver/hardware — autopsia con logs; (b) exploración limitada por degradación del transporte **cuantificada** (÷13 frecuencia, ×400 jitter, huecos 16 s > buffer TF 10 s, con ancho de banda descartado a 0,5 Mbps).
- La metodología fue sistemática: cada fallo se aisló por descarte de capas con evidencia (24 problemas catalogados, 21 resueltos, 2 con workaround, 1 aislado como hardware).

**Matices que la redacción DEBE respetar (rigor):**
- La medición de jitter es **N=1, ilustrativa** — el contraste (un orden de magnitud) hace robusta la conclusión cualitativa, pero no es una caracterización estadística.
- No se separó experimentalmente la contribución de VirtualBox vs la WiFi al jitter → decir "capa de transporte del banco de pruebas (virtualización + bridge WiFi)" sin repartir culpas; proponer el experimento discriminante (PC nativo) como trabajo futuro.
- El ciclo `SAVING_MAP→PLANNING→PATROLLING` en real no se ejercitó: apoyarse en su validación en simulación y en que las fases previas (las de mayor riesgo de integración) sí se demostraron en real.
- Escribir "los datos son **consistentes con** un problema de jitter de transporte" (no "se demostró que la red era el problema").

### 6.9 Evidencias disponibles para la redacción

- Este documento completo (`resultados-test.md`): tablas, logs cortos por problema, runbook reproducible con checklist.
- Capturas de terminal de la sesión (en el historial del chat/equipo): salidas íntegras de `ros2 topic hz` baseline y bajo carga, `ros2 topic bw`, journals de la RPi (boots bueno/malo de la cámara), logs completos del bringup, capturas de RViz (incluido el mapa corrupto "patas de araña" del incidente de relojes — muy ilustrativa como figura).
- Captura del dashboard de Grafana con telemetría real.
- Código en `robot_ws/src/` con los cambios de la sesión (bond_timeout, QoS).

---

## 7. Referencias

- Manual TB4 — Sensores (power saver del lidar/cámara al estar docked): https://turtlebot.github.io/turtlebot4-user-manual/software/sensors.html
- Issue conocido "scan data not available" (auto-standby del rplidar): https://github.com/turtlebot/turtlebot4/issues/150
- Issue "not publishing /scan": https://github.com/turtlebot/turtlebot4/issues/614
- Config chrony oficial del TB4: https://raw.githubusercontent.com/turtlebot/turtlebot4_setup/humble/etc/turtlebot4/chrony.conf
- m-explore-ros2 (explore_lite para ROS 2): https://github.com/robo-friends/m-explore-ros2
