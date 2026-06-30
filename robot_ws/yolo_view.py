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