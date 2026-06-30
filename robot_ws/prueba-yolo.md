# Prueba de detección YOLO en simulación

Runbook para montar el escenario de detección en el **simulador TurtleBot 4**
(Ignition Gazebo Fortress), mover el robot, **añadir objetos** (una persona, un
perro, etc.), **ver la cámara con los bounding boxes de YOLO** y recoger los números
que rellenan la tabla de métricas de detección de la memoria
(`tab:metricas-deteccion`) y la figura `fig:deteccion-sim`.

Léelo junto al `TEST_PLAN.md`: aquí no se repiten el levantado de infra ni la
construcción del workspace, solo lo específico de la prueba de YOLO.

---

## 0) Qué vamos a medir y por qué hace falta una herramienta aparte

El nodo de producción `detect_incident` (`src/detect_incident/detect_incident/
detect_incident.py`) **solo decide si hay una `person`** por encima del umbral
(`DETECTION_CONFIDENCE_THRESHOLD=0.5`) y, si la hay, dispara la incidencia (graba
clip, sube a MinIO, publica en Kafka). **No dibuja las cajas ni anota la confianza
ni el tiempo de inferencia.**

Por eso esta prueba usa **dos piezas complementarias**:

| Pieza | Para qué | Aporta a la tabla |
|---|---|---|
| `detect_incident` (nodo real) | Confirmar que la detección **dispara la incidencia** | Apariciones, TP/FN/FP, latencia de detección |
| `yolo_view.py` (visor, Sección 5) | **Ver** las cajas y **medir** confianza y tiempo de inferencia | Confianza media, tiempo de inferencia (ms/fotograma), FPS, *screenshot* de la figura |

El visor es **independiente y no invasivo**: corre el mismo `yolov8n.pt` sobre el
mismo tópico de cámara, pero **no modifica** el nodo de producción.

---

## 1) Prerrequisitos

Da por hechos los pasos 1 y 2 del `TEST_PLAN.md`:

- Contenedor `ros2_humble_dev` arriba y workspace compilado:
  ```bash
  cd /ruta/al/repo/robot_ws
  docker compose up -d
  docker exec -it ros2_humble_dev bash
  # dentro del contenedor:
  source /opt/ros/humble/setup.bash
  cd /robot_ws && colcon build --symlink-install && source install/setup.bash
  ```
- **`numpy<2`** dentro del contenedor (igual que en la Fase B; si no, `cv_bridge`
  peta con `_ARRAY_API not found`):
  ```bash
  pip3 install "numpy<2"     # -> numpy 1.26.4
  ```
- La GUI (Gazebo, RViz, ventana del visor) sale por **WSLg**: el `docker-compose.yml`
  ya monta `/mnt/wslg` + `/tmp/.X11-unix` y exporta `DISPLAY`/`WAYLAND_DISPLAY`, así
  que las ventanas gráficas funcionan sin pasos extra.

> **Qué NO hace falta para la prueba de detección pura (Secciones 2 a 6):** ni la
> infra (Kafka/MinIO) ni el backend. Solo se necesitan si además quieres comprobar el
> **extremo a extremo** (que la incidencia llega a la base de datos y a la app), que
> es la Sección 7.

> 💡 Todos los `ros2 ...` van **dentro del contenedor**. Abre varias terminales al
> mismo contenedor con `docker exec -it ros2_humble_dev bash` y, en cada una,
> `source /opt/ros/humble/setup.bash && source /robot_ws/install/setup.bash`.

---

## 2) Lanzar el mundo

Dos formas según lo que quieras probar.

### 2.A — Detección pura (recomendada para rellenar la tabla)

Levanta solo el simulador con el robot y la cámara, **sin Nav2 ni SLAM** (no hace
falta navegar para medir la detección; moverás el robot a mano en la Sección 3):

```bash
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
  world:=warehouse nav2:=false slam:=false rviz:=true
```

- `world:=warehouse` es el mundo por defecto del TB4 (interior con estanterías, buen
  fondo visual). Otras opciones: `maze` (el que usa la patrulla) y `depot`.
- `rviz:=true` abre RViz; útil para ver la cámara, pero el visor de la Sección 5 es
  el que dibuja las cajas de YOLO.

### 2.B — Integrada con patrulla autónoma

Si quieres que el robot patrulle solo y la persona aparezca durante la patrulla,
reutiliza el wrapper del proyecto (elige SLAM o localización según exista el mapa):

```bash
ros2 launch patrol_nav patrol_bringup.launch.py sim:=true
```

> Para medir la tabla es más cómodo el escenario **2.A**: controlas tú cuándo y dónde
> aparece la persona. El **2.B** sirve para la captura "en patrulla" de la figura.

**Comprobar que la cámara publica** (otra terminal):

```bash
ros2 topic echo /oakd/rgb/preview/image_raw --once   # debe volcar una cabecera de imagen
ros2 topic hz   /oakd/rgb/preview/image_raw           # frecuencia de fotogramas
```

---

## 3) Mover el robot

El robot acepta velocidades en **`/cmd_vel`** (sin namespace, igual que la cámara).

**Si arranca acoplado al dock, desacóplalo primero** (la base Create 3 inhibe el
avance mientras está en el dock):

```bash
ros2 action send_goal /undock irobot_create_msgs/action/Undock "{}"
```

**Teleoperación por teclado** (instala la herramienta la primera vez):

```bash
apt-get update && apt-get install -y ros-humble-teleop-twist-keyboard
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Controles: `i` avanzar, `,` retroceder, `j`/`l` girar, `k` parar; `q`/`z` suben/bajan
la velocidad. **La terminal del teleop debe tener el foco** para que lea las teclas.

**Alternativa sin teclado** (un empujón puntual hacia delante):

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.2}, angular: {z: 0.0}}"
```

Coloca el robot de modo que la persona quede dentro de su campo de visión frontal
(la OAK-D mira al frente).

---

## 4) Añadir objetos (persona, perro, etc.)

YOLOv8n reconoce las clases de **COCO** (incluye `person`, `dog`, `cat`, `chair`,
`tv`, etc.), pero recuerda que **`detect_incident` solo dispara con `person`**. El
visor de la Sección 5, en cambio, dibuja cajas para **cualquier** clase que detecte,
así que podrás ver al perro etiquetado aunque no genere incidencia.

### 4.A — Método visual (recomendado): Resource Spawner de la GUI

1. En la ventana de **Ignition Gazebo**, abre el menú de plugins (los tres puntos
   verticales, arriba a la derecha) y añade **"Resource Spawner"**.
2. En el panel, pestaña de **Fuel** (modelos online), busca un modelo de persona,
   por ejemplo **"Standing person"**, **"Casual female"** o algún **actor**. Para un
   animal, busca **"dog"** o similar (ver aviso de detectabilidad más abajo).
3. Haz clic en el modelo y luego clic en el mundo, **delante del robot**, para
   soltarlo. Repite para colocar varios o moverlos entre apariciones.

> La primera descarga de un modelo de Fuel tarda unos segundos (necesita internet).

### 4.B — Método por línea de comandos (alternativa)

Si prefieres reproducibilidad (misma posición exacta en cada repetición), spawnea por
CLI. Con `ros_gz_sim`:

```bash
ros2 run ros_gz_sim create -world warehouse -name persona1 \
  -x 2.0 -y 0.0 -z 0.0 \
  -file "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Standing person"
```

Si ese ejecutable no estuviera disponible en tu imagen, usa el servicio de Ignition
directamente:

```bash
ign service -s /world/warehouse/create \
  --reqtype ignition.msgs.EntityFactory --reptype ignition.msgs.Boolean \
  --timeout 2000 \
  --req 'sdf_filename: "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Standing person", name: "persona1", pose: {position: {x: 2.0, y: 0.0, z: 0.0}}'
```

(Cambia `warehouse` por el `world` que lanzaste, y las coordenadas `x,y` para
situarlo frente al robot.)

> ⚠️ **Detectabilidad honesta.** YOLOv8n se entrenó con **fotos reales**. Los modelos
> de **persona** de Fuel son suficientemente realistas y se detectan con fiabilidad;
> los de **animales** (perro, gato) son irregulares: según el modelo y la textura,
> YOLO puede no reconocerlos o hacerlo con confianza baja. Para la tabla de la memoria
> (que mide detección de **personas**), usa modelos de persona; el perro y demás sirven
> para ilustrar el visor multiclase, no como métrica fiable.

---

## 5) Ver la cámara con los bounding boxes de YOLO

Guarda este script como **`/robot_ws/yolo_view.py`** (el `/robot_ws` está montado
desde el repo, así que puedes crearlo en `robot_ws/yolo_view.py` desde Windows y
aparece dentro del contenedor). Suscribe la cámara, corre el mismo `yolov8n.pt`,
**dibuja las cajas con clase y confianza**, abre una ventana y **mide** el tiempo de
inferencia y la confianza para la tabla.

```python
#!/usr/bin/env python3
"""Visor YOLO no invasivo para la cámara del TB4 simulado.

Suscribe /oakd/rgb/preview/image_raw, corre yolov8n.pt, dibuja las cajas con
clase + confianza y muestra la ventana. Registra el tiempo de inferencia por
fotograma y la confianza de las detecciones para rellenar tab:metricas-deteccion.

Uso (dentro del contenedor, con el entorno sourceado):
    python3 /robot_ws/yolo_view.py
    python3 /robot_ws/yolo_view.py --classes person dog --conf 0.5 --csv /robot_ws/yolo_metrics.csv
"""
import argparse
import csv
import time

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from ultralytics import YOLO


class YoloViewer(Node):
    def __init__(self, args):
        super().__init__('yolo_viewer')
        self.args = args
        self.bridge = CvBridge()
        self.model = YOLO(args.model)
        self.names = self.model.names

        self.subscription = self.create_subscription(
            Image, args.topic, self.on_image, 10)

        # Acumuladores para el resumen final / tabla.
        self.frame_count = 0
        self.infer_ms_sum = 0.0
        self.conf_sum = 0.0          # suma de confianzas de las detecciones de interes
        self.det_count = 0           # nº de detecciones de interes
        self.frames_with_target = 0  # fotogramas con al menos una clase de interes
        self.t0 = time.time()

        self.csv_writer = None
        self.csv_file = None
        if args.csv:
            self.csv_file = open(args.csv, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(
                ['frame', 'stamp', 'infer_ms', 'n_det', 'max_conf', 'classes'])

        self.get_logger().info(
            f"Visor YOLO escuchando {args.topic} (modelo {args.model}, "
            f"conf>={args.conf}, clases={args.classes or 'todas'}). "
            "Pulsa 'q' en la ventana para salir.")

    def on_image(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        t = time.perf_counter()
        results = self.model(frame, conf=self.args.conf, verbose=False)
        infer_ms = (time.perf_counter() - t) * 1000.0

        r = results[0]
        n_det = 0
        max_conf = 0.0
        classes_seen = []
        for box in r.boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            label = self.names[cls_id]

            if self.args.classes and label not in self.args.classes:
                continue

            n_det += 1
            max_conf = max(max_conf, conf)
            classes_seen.append(label)
            self.conf_sum += conf
            self.det_count += 1

            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            color = (0, 0, 255) if label == 'person' else (0, 200, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{label} {conf:.2f}", (x1, max(0, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Estadisticas acumuladas.
        self.frame_count += 1
        self.infer_ms_sum += infer_ms
        if n_det > 0:
            self.frames_with_target += 1
        fps = self.frame_count / max(1e-6, (time.time() - self.t0))

        # HUD sobre la imagen.
        hud = f"infer {infer_ms:5.1f} ms | {fps:4.1f} FPS | det {n_det}"
        cv2.putText(frame, hud, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 0), 2)

        if self.csv_writer:
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            self.csv_writer.writerow(
                [self.frame_count, f"{stamp:.3f}", f"{infer_ms:.2f}",
                 n_det, f"{max_conf:.3f}", '|'.join(classes_seen)])

        cv2.imshow('YOLO viewer', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            rclpy.shutdown()

    def print_summary(self):
        mean_infer = self.infer_ms_sum / max(1, self.frame_count)
        mean_conf = self.conf_sum / max(1, self.det_count)
        fps = self.frame_count / max(1e-6, (time.time() - self.t0))
        self.get_logger().info(
            "\n===== RESUMEN (para tab:metricas-deteccion) =====\n"
            f"  fotogramas procesados      : {self.frame_count}\n"
            f"  fotogramas con deteccion   : {self.frames_with_target}\n"
            f"  detecciones (clase interes): {self.det_count}\n"
            f"  confianza media            : {mean_conf:.3f}\n"
            f"  tiempo de inferencia medio : {mean_infer:.1f} ms/fotograma\n"
            f"  FPS medios                 : {fps:.1f}\n"
            "=================================================")
        if self.csv_file:
            self.csv_file.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', default='/oakd/rgb/preview/image_raw')
    parser.add_argument('--model', default='/robot_ws/yolov8n.pt')
    parser.add_argument('--conf', type=float, default=0.5)
    parser.add_argument('--classes', nargs='*', default=['person'],
                        help="clases a contar/medir; vacio = todas")
    parser.add_argument('--csv', default=None,
                        help="ruta opcional para volcar metricas por fotograma")
    args = parser.parse_args()

    rclpy.init()
    node = YoloViewer(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.print_summary()
        node.destroy_node()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
```

**Lanzarlo** (dentro del contenedor, con el simulador y una persona ya en escena):

```bash
source /opt/ros/humble/setup.bash
python3 /robot_ws/yolo_view.py --csv /robot_ws/yolo_metrics.csv
```

- Aparece una ventana **"YOLO viewer"** con las cajas: **rojas** para `person`,
  **verdes** para el resto. Arriba se ve el HUD con `infer ms`, `FPS` y nº de
  detecciones.
- Para medir **solo personas** deja `--classes person` (por defecto). Para ver
  también el perro y demás: `--classes person dog cat` o `--classes` (vacío = todas).
- Al cerrar con **`q`** (o `Ctrl+C` en la terminal) imprime el **RESUMEN** con la
  confianza media, el tiempo de inferencia medio y los FPS, y deja el CSV por
  fotograma si lo pediste.

> Esta ventana es la **fuente del *screenshot*** de `fig:deteccion-sim` de la memoria
> (recorta la ventana con el robot detectando a la persona).

> **Alternativa sin script propio:** publicar un tópico anotado y verlo en
> `rqt_image_view`. Es más trabajo y no da las métricas, por eso aquí se usa el visor.

---

## 6) Escenario controlado y cómo rellenar la tabla de detección

Objetivo: obtener cada celda de `tab:metricas-deteccion`. Protocolo sugerido:

1. Lanza el mundo (Sección 2.A) y el **nodo real** `detect_incident` en una terminal:
   ```bash
   ros2 run detect_incident detect_incident_node
   ```
   (la primera vez descarga `yolov8n.pt` si no lo encuentra; necesita internet.)
2. En paralelo, lanza el **visor** (Sección 5) con `--csv` para las métricas de
   confianza y tiempo.
3. Define **N apariciones** de persona en posiciones/instantes conocidos: spawnea la
   persona delante del robot (o muévela / mueve el robot con teleop), déjala unos
   segundos en campo y retírala. Anota cada aparición.
4. Para cada aparición, registra si `detect_incident` la cazó (log
   **`Incident detected!`** y, tras el *cooldown*, evento en Kafka). Cuenta también
   los disparos sin persona real (falsos positivos).

**De dónde sale cada fila de la tabla:**

| Fila de `tab:metricas-deteccion` | Cómo se obtiene |
|---|---|
| Apariciones de persona (positivos reales) | N que definiste en el guion |
| Verdaderos positivos (VP) | Apariciones que dispararon `Incident detected!` |
| Falsos negativos (FN) | Apariciones que **no** dispararon |
| Falsos positivos (FP) | Disparos sin persona real delante |
| Precisión | `VP / (VP + FP)` |
| *Recall* | `VP / (VP + FN)` |
| Confianza media de detección | "confianza media" del RESUMEN del visor (o media del CSV) |
| Tiempo de inferencia | "tiempo de inferencia medio" del RESUMEN (ms/fotograma) |
| Latencia de detección | Tiempo desde que la persona entra en campo hasta `Incident detected!` |

> El **tiempo de inferencia** medido en el simulador corre sobre la **CPU del PC**
> (Torch CPU en el contenedor), no sobre el hardware del robot; conviene anotarlo así
> en la memoria. Las métricas de extremo a extremo van en la Sección 7.

---

## 7) (Opcional) Extremo a extremo: que la incidencia llegue al sistema

Para comprobar el flujo completo (lo de `tab:metricas-e2e`), levanta la infra y el
backend como en el `TEST_PLAN.md` (Sección 1) y observa el evento:

```bash
# Consumidor de incidencias (terminal en el host):
docker exec -it tfg_kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 --topic robot_incidents
```

Al detectar la persona, tras los ~50 fotogramas posteriores y el guardado del clip,
debe aparecer un mensaje
`{"robot_id":"RBT-01","bucket_name":"tfg-incidentes","video_filename":"incident_..._RBT-01.mp4"}`
y el `.mp4` en el bucket de MinIO (`http://localhost:9001`). La latencia
detección → registro → app se mide correlando esas marcas de tiempo (igual que la
Fase B del `TEST_PLAN.md`).

---

## 8) Checklist y problemas típicos

- [ ] **`numpy<2`** dentro del contenedor (si no, ni `detect_incident` ni el visor
      arrancan: `_ARRAY_API not found`).
- [ ] La **ventana del visor no aparece** → revisa que `DISPLAY`/`WAYLAND_DISPLAY`
      están exportados (los pone el compose) y que la GUI de Gazebo sí sale; es el
      mismo canal WSLg.
- [ ] **No detecta nada** → ¿la persona está realmente en el campo frontal y a
      distancia razonable?, ¿el modelo es realista (persona de Fuel, no un primitivo)?,
      ¿la confianza supera `--conf 0.5`? Baja el umbral para depurar (`--conf 0.25`).
- [ ] **El perro no se detecta** → esperable (modelos de animales poco realistas para
      YOLO); úsalo solo para ilustrar, no para la métrica.
- [ ] **`ros_gz_sim create` no existe** → usa el **Resource Spawner** de la GUI
      (Sección 4.A) o el `ign service` (Sección 4.B).
- [ ] **El teleop no responde** → la terminal de `teleop_twist_keyboard` debe tener el
      foco del teclado.
- [ ] **El robot no avanza** → puede estar acoplado: lanza la acción `/undock`.
- [ ] `ros2 topic hz /oakd/rgb/preview/image_raw` para confirmar que la cámara
      publica antes de culpar a YOLO.
