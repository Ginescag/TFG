import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

import cv2
import json
import boto3
import requests
from confluent_kafka import Producer
from ultralytics import YOLO
from collections import deque
import os
import time
import threading

class DetectIncidentNode(Node):

    def __init__(self):

        #subscribe to camera topic and mount CV bridge
        super().__init__('detect_incident_node')
        self.subscription = self.create_subscription(
            Image,
            '/oakd/rgb/preview/image_raw',
            self.image_callback,
            10
        )
        self.bridge = CvBridge()

        # Initialize YOLO model
        self.model = YOLO('yolov8n.pt')
    
        #init minIO conn with boto3
        #to add video to a bucket s3_client.upload_file('local_videoxxx.mp4', os.getenv('MINIO_BUCKET_NAME'), 'videoxxx.mp4')
        self.s3_client = boto3.client(
            's3',
            endpoint_url=os.getenv('MINIO_ENDPOINT'),
            aws_access_key_id=os.getenv('MINIO_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('MINIO_SECRET_KEY'),
        )

        #init Kafka producer
        self.kafkaProducer = Producer({'bootstrap.servers': os.getenv('KAFKA_BROKER_URL')})
        
        #init incident buffer to store recent frames in case we need to create a video
        self.incident_buffer = deque(maxlen=100)

        self.cooldown = False
        self.cooldown_time = 30
        self.timer = None
        
        self.post_trigger_counter = 0
        
        os.makedirs('tmp', exist_ok=True)

    def reset_cooldown(self):
        self.cooldown = False
        self.get_logger().info('Cooldown period ended. Ready to detect incidents again.')
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        self.incident_buffer.clear()

    def image_callback(self, msg):
        
        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        if self.cooldown:
            return

        self.incident_buffer.append(cv_image)

        if self.post_trigger_counter > 0:
            self.post_trigger_counter -= 1

            if self.post_trigger_counter == 0:
                timestamp = int(time.time())
                frames_copy = list(self.incident_buffer)
                
                # Start cooldown
                self.cooldown = True
                self.get_logger().info('Entering cooldown period...')
                self.timer = self.create_timer(self.cooldown_time, self.reset_cooldown)

                threading.Thread(
                    target=self.process_incident_io, 
                    args=(frames_copy, timestamp), 
                    daemon=True
                ).start()
        else:
            detected = self.detect_incident(cv_image)
            
            if detected:
                self.get_logger().info('Incident detected!')
                self.post_trigger_counter = 50

    def process_incident_io(self, frames, timestamp):
        # Save video of the incident
        base_filename = f'incident_{timestamp}_{os.getenv("ROBOT_ID")}.mp4'
        video_filename = f'tmp/{base_filename}'
        
        if frames:
            first_frame = frames[0]
            height, width = first_frame.shape[:2]
            fps = 10.0
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(video_filename, fourcc, fps, (width, height))
            for frame in frames:
                writer.write(frame)
            writer.release()

        # Upload video to MinIO
        self.s3_client.upload_file(video_filename, os.getenv('MINIO_BUCKET_NAME'), base_filename)
        os.remove(video_filename)

        # Send alert to Kafka
        incident_payload = {
            "robot_id": os.getenv("ROBOT_ID"),
            "bucket_name": os.getenv("MINIO_BUCKET_NAME"),
            "video_filename": base_filename
        }
        incident_headers = []

        # TENGO QUE CAMBIAR ESTO PARA QUE USE UN HELPER QUE TRABAJE CON LOS SECRETOS DEL ROBOT
        robot_token = os.getenv("ROBOT_JWT_TOKEN")
        if robot_token:
            incident_headers = [("Authorization", f"Bearer {robot_token}".encode("utf-8"))]
        self.kafkaProducer.produce(
            os.getenv("KAFKA_INCIDENT_TOPIC", "incidents"),
            value=json.dumps(incident_payload),
            headers=incident_headers
        )
        self.kafkaProducer.flush()

    def detect_incident(self, image):
        # Placeholder for actual incident detection logic
        # For demonstration, we will just return False
        target_classes = ['person']
        confidence_threshold = float(os.getenv('DETECTION_CONFIDENCE_THRESHOLD'))

        preds = self.model(image, stream=True, verbose=False)

        for p in preds:
            for box in p.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())

                if self.model.names[cls_id] in target_classes and conf >= confidence_threshold:
                    return True
        return False

def main(args=None):
    rclpy.init(args=args)
    node = DetectIncidentNode()
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