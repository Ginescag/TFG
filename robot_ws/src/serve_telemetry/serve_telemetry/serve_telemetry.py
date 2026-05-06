import rclpy
from rclpy.node import Node
import json
import os
import time
from confluent_kafka import Producer

# IMPORTAMOS LOS TIPOS DE MENSAJES
from sensor_msgs.msg import BatteryState
from nav_msgs.msg import Odometry
from irobot_create_msgs.msg import DockStatus, KidnapStatus, SlipStatus, WheelStatus

class ServeTelemetryNode(Node):
    def __init__(self):
        super().__init__('serve_telemetry_node')
        
        # 1. Inicializar Kafka
        self.kafkaProducer = Producer({'bootstrap.servers': os.getenv('KAFKA_BROKER_URL')})
        self.topic = os.getenv('KAFKA_TELEMETRY_TOPIC')
        self.robot_id = os.getenv('ROBOT_ID')

        # 2. Diccionario de estado interno (se actualizará con los callbacks)
        self.current_state = {
            "bateria": 0.0,
            "bateria_voltaje": 0.0,
            "is_docked": False,
            "pos_x": 0.0,
            "pos_y": 0.0,
            "vel_linear": 0.0,
            "vel_angular": 0.0,
            "is_kidnapped": False,
            "is_slipping": False,
            "wheels_enabled": True
        }

        # 3. SUSCRIPCIONES
        self.sub_battery = self.create_subscription(
            BatteryState, '/battery_state', self.battery_callback, 10)
            
        self.sub_odom = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)
            
        self.sub_dock = self.create_subscription(
            DockStatus, '/dock_status', self.dock_callback, 10)
            
        self.sub_kidnap = self.create_subscription(
            KidnapStatus, '/kidnap_status', self.kidnap_callback, 10)
            
        self.sub_slip = self.create_subscription(
            SlipStatus, '/slip_status', self.slip_callback, 10)
            
        self.sub_wheel = self.create_subscription(
            WheelStatus, '/wheel_status', self.wheel_callback, 10)

        # 4. Temporizador de envío
        self.timer = self.create_timer(1.0, self.publish_telemetry)

    # --- CALLBACKS PARA ACTUALIZAR EL ESTADO ---
    def battery_callback(self, msg):
        self.current_state["bateria"] = msg.percentage * 100.0
        self.current_state["bateria_voltaje"] = msg.voltage

    def odom_callback(self, msg):
        self.current_state["pos_x"] = msg.pose.pose.position.x
        self.current_state["pos_y"] = msg.pose.pose.position.y
        self.current_state["vel_linear"] = msg.twist.twist.linear.x
        self.current_state["vel_angular"] = msg.twist.twist.angular.z

    def dock_callback(self, msg):
        self.current_state["is_docked"] = msg.is_docked

    def kidnap_callback(self, msg):
        self.current_state["is_kidnapped"] = msg.is_kidnapped

    def slip_callback(self, msg):
        self.current_state["is_slipping"] = msg.is_slipping

    def wheel_callback(self, msg):
        self.current_state["wheels_enabled"] = msg.wheels_enabled

    # --- FUNCIÓN QUE ENVÍA A KAFKA ---
    def publish_telemetry(self):
        payload = {
            "robot_id": self.robot_id,
            "timestamp": time.time()
        }
        payload.update(self.current_state)

        # this is handled by secret handler, needs to be changed
        headers = []
        robot_token = os.getenv("ROBOT_JWT_TOKEN")
        if robot_token:
            headers = [("Authorization", f"Bearer {robot_token}".encode("utf-8"))]

        try:
            self.kafkaProducer.produce(
                self.topic,
                value=json.dumps(payload),
                headers=headers
            )
            self.kafkaProducer.poll(0)
        except Exception as e:
            self.get_logger().error(f'Error enviando telemetría a Kafka: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = ServeTelemetryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.kafkaProducer.flush()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()