import json
import math
import os
import subprocess
from collections import deque

import httpx

import cv2
import numpy as np
import rclpy
import yaml
from confluent_kafka import Consumer, KafkaError, KafkaException
from geometry_msgs.msg import PoseStamped
from nav2_msgs.srv import SaveMap
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from nav_msgs.msg import Odometry
from rclpy.node import Node

from secret_helper_interfaces.srv import GetToken

class PatrolOrchestrator(Node):
    def __init__(self):
        super().__init__('patrol_orchestrator')
        self.navigator = BasicNavigator()

        self.declare_parameter('map_filepath', '/robot_ws/src/mapa_patrulla')
        self.declare_parameter('grid_spacing_m', 2.0)
        self.declare_parameter('explore_idle_secs', 20.0)
        self.declare_parameter('explore_min_secs', 120.0)
        self.declare_parameter('dock_x', 0.0)
        self.declare_parameter('dock_y', 0.0)
        self.declare_parameter('dock_yaw', 0.0)
        self.declare_parameter('robot_id', os.getenv('ROBOT_ID', ''))
        self.declare_parameter('kafka_broker_url', os.getenv('KAFKA_BROKER_URL', ''))
        self.declare_parameter('kafka_robot_commands_topic', os.getenv('KAFKA_ROBOT_COMMANDS_TOPIC', 'robot_commands'))
        self.declare_parameter('server_url', os.getenv('SERVER_URL', ''))
        self.declare_parameter('heartbeat_interval_secs', 10.0)

        self.map_filepath = self.get_parameter('map_filepath').value
        self.grid_spacing_m = float(self.get_parameter('grid_spacing_m').value)
        self.explore_idle_secs = float(self.get_parameter('explore_idle_secs').value)
        self.explore_min_secs = float(self.get_parameter('explore_min_secs').value)
        self.dock_pose = self.create_pose(
            float(self.get_parameter('dock_x').value),
            float(self.get_parameter('dock_y').value),
            float(self.get_parameter('dock_yaw').value)
        )
        self.robot_id = str(self.get_parameter('robot_id').value).strip()
        self.kafka_broker_url = str(self.get_parameter('kafka_broker_url').value).strip()
        self.kafka_robot_commands_topic = str(self.get_parameter('kafka_robot_commands_topic').value).strip()
        self.server_url = str(self.get_parameter('server_url').value).strip().rstrip('/')
        self.heartbeat_interval_secs = float(self.get_parameter('heartbeat_interval_secs').value)

        # Token JWT gestionado por secret_helper (servicio get_robot_token), cacheado.
        self.token_client = self.create_client(GetToken, 'get_robot_token')
        self.current_token = None

        self.state = 'EXPLORING'
        self.waypoints_queue = deque()
        self.explore_process = None
        self.save_map_client = self.create_client(SaveMap, '/map_saver/save_map')
        self.save_map_future = None
        self.last_move_time = None
        self.last_pose = None
        self.explore_start_time = None
        self.active_task = None

        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
 
        # Canonical vocabulary shared with the server.
        # Each internal FSM state maps to the exact string accepted by the heartbeat.
        self.FSM_TO_OPERATIVO = {
            'EXPLORING':      'exploring',
            'SAVING_MAP':     'saving_map',
            'PLANNING':       'planning',
            'PATROLLING':     'patrolling',
            'PATROL_STOPPED': 'stopped',
        }

        self.command_consumer = None
        if not self.robot_id:
            self.get_logger().error('Robot ID is missing. Set parameter robot_id or env ROBOT_ID.')
        if self.kafka_broker_url and self.kafka_robot_commands_topic and self.robot_id:
            self.command_consumer = Consumer({
                'bootstrap.servers': self.kafka_broker_url,
                'group.id': f'patrol_command_group_{self.robot_id}',
                'auto.offset.reset': 'latest'
            })
            self.command_consumer.subscribe([self.kafka_robot_commands_topic])
        else:
            self.get_logger().error('Kafka command consumer not started due to missing config.')

        self.get_logger().info('Waiting for Nav2 (bt_navigator) to become active...')
        # En modo SLAM no existe amcl, y slam_toolbox corre sin lifecycle gestionable
        # (no expone get_state). El gate real para enviar goals es bt_navigator, así que
        # esperamos solo a él. Con localizer='bt_navigator', waitUntilNav2Active espera a
        # bt_navigator y se salta _waitForInitialPose (que solo corre si localizer=='amcl').
        self.navigator.waitUntilNav2Active(localizer='bt_navigator')

        self.timer = self.create_timer(1.0, self.state_machine)
        self.command_timer = self.create_timer(0.5, self.poll_command_topic)
        # Refresco no bloqueante del token (secret_helper ya refresca cada hora).
        self.token_timer = self.create_timer(10.0, self._refresh_token)

        if self.server_url:
            self.heartbeat_timer = self.create_timer(self.heartbeat_interval_secs, self.send_heartbeat)
            self.get_logger().info(f'Heartbeat enabled → {self.server_url} every {self.heartbeat_interval_secs}s')
        else:
            self.heartbeat_timer = None
            self.get_logger().warn('Heartbeat disabled: SERVER_URL not set. Server DB will not reflect real robot state.')

    def _refresh_token(self):
        if not self.token_client.service_is_ready():
            return
        future = self.token_client.call_async(GetToken.Request())
        future.add_done_callback(self._on_token)

    def _on_token(self, future):
        try:
            resp = future.result()
        except Exception as e:
            self.get_logger().warn(f'Token service call failed: {e}')
            return
        if resp.success:
            self.current_token = resp.token
        else:
            self.get_logger().warn(f'secret_helper not ready: {resp.message}')

    def create_pose(self, x, y, yaw):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.navigator.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        return pose

    def odom_callback(self, msg: Odometry):
        now = self.get_clock().now()
        if self.last_move_time is None:
            self.last_move_time = now
            self.last_pose = msg.pose.pose.position
            return

        dx = msg.pose.pose.position.x - self.last_pose.x
        dy = msg.pose.pose.position.y - self.last_pose.y
        if math.hypot(dx, dy) > 0.05:
            self.last_move_time = now
            self.last_pose = msg.pose.pose.position

    def get_estado_operativo(self) -> str:
        """
        Translates the internal FSM state to the string the server expects.
        """
        return self.FSM_TO_OPERATIVO.get(self.state, 'idle')

    def send_heartbeat(self):
        """
        Calls PUT /robot/heartbeat with the current FSM operational state.
        It is the source of truth that keeps the server DB synchronized
        with what the robot is actually doing.
        """
        if self.current_token is None:
            self.get_logger().debug('Heartbeat skipped: token not available yet from secret_helper.')
            return

        estado = self.get_estado_operativo()
        try:
            response = httpx.put(
                f'{self.server_url}/robot/heartbeat',
                json={'estado_operativo': estado},
                headers={'Authorization': f'Bearer {self.current_token}'},
                timeout=5.0
            )
            if response.status_code == 200:
                self.get_logger().debug(f'Heartbeat OK → estado_operativo={estado}')
            else:
                self.get_logger().warn(
                    f'Heartbeat rejected by server: {response.status_code} {response.text}'
                )
        except httpx.TimeoutException:
            self.get_logger().warn('Heartbeat timeout: server did not respond in 5s')
        except httpx.RequestError as e:
            self.get_logger().warn(f'Heartbeat request error: {e}')

    def state_machine(self):
        if self.state == 'EXPLORING':
            self.run_exploration()
            
        elif self.state == 'SAVING_MAP':
            self.save_map()
            
        elif self.state == 'PLANNING':
            self.generate_waypoints_from_map()
            
        elif self.state == 'PATROLLING':
            self.run_patrol_cycle()
        elif self.state == 'PATROL_STOPPED':
            self.run_patrol_stopped()

    def poll_command_topic(self):
        if self.command_consumer is None:
            return

        try:
            msg = self.command_consumer.poll(0.1)
        except KafkaException as exc:
            self.get_logger().error(f'Kafka poll error: {exc}')
            return

        if msg is None:
            return

        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                self.get_logger().warn(f'Kafka message error: {msg.error()}')
            return

        try:
            payload = json.loads(msg.value().decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            self.get_logger().warn('Invalid JSON command payload. Ignoring message.')
            return

        robot_id = payload.get('robot_id')
        command = payload.get('command')

        if robot_id != self.robot_id:
            return

        if command == 'start_patrol':
            self.handle_start_patrol()
        elif command == 'stop_patrol':
            self.handle_stop_patrol()

    def handle_start_patrol(self):
        if self.state == 'PATROL_STOPPED':
            self.get_logger().info('Received start_patrol. Resuming patrol.')
            self.active_task = None
            self.state = 'PATROLLING'
        elif self.state == 'PATROLLING':
            # Idempotent: already patrolling, nothing to do.
            self.get_logger().info('start_patrol received but robot is already PATROLLING. Ignoring.')
        else:
            # States EXPLORING / SAVING_MAP / PLANNING: the robot is not yet ready.
            # The server should have validated this, but we defend here too.
            self.get_logger().warn(
                f'start_patrol ignored: robot is in state {self.state} and cannot start patrol yet. '
                f'Wait until the robot reaches PATROL_STOPPED before issuing start_patrol.'
            )

    def handle_stop_patrol(self):
        if self.state != 'PATROL_STOPPED':
            self.get_logger().info('Received stop_patrol. Returning to dock.')
            if self.explore_process is not None:
                self.explore_process.terminate()
                self.explore_process = None
            # Bug fix: clear any pending map-save future so it does not remain
            # orphaned when SAVING_MAP is interrupted mid-flight.
            if self.save_map_future is not None:
                self.get_logger().warn('Map save interrupted by stop_patrol. Discarding pending future.')
                self.save_map_future = None
            self.state = 'PATROL_STOPPED'
        else:
            self.get_logger().info('stop_patrol ignored; already stopped.')

    def destroy_node(self):
        if self.command_consumer is not None:
            self.command_consumer.close()
        super().destroy_node()

    # --- PHASE 1: AUTONOMOUS EXPLORATION ---
    def run_exploration(self):
        if self.explore_process is None:
            self.get_logger().info('Starting autonomous exploration (explore_lite)...')
            self.explore_process = subprocess.Popen(
                ['ros2', 'launch', 'explore_lite', 'explore.launch.py']
            )
            self.explore_start_time = self.get_clock().now()
            if self.last_move_time is None:
                self.last_move_time = self.get_clock().now()

        now = self.get_clock().now()
        explore_elapsed = (now - self.explore_start_time).nanoseconds / 1e9
        idle_elapsed = (now - self.last_move_time).nanoseconds / 1e9

        if explore_elapsed >= self.explore_min_secs and idle_elapsed >= self.explore_idle_secs:
            self.get_logger().info('Exploration completed (idle detected). Stopping explore_lite.')
            self.explore_process.terminate()
            self.explore_process = None
            self.state = 'SAVING_MAP'

    # --- PHASE 2: MAP SAVING ---
    def save_map(self):
        if not self.save_map_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for map_saver service...')
            return

        if self.save_map_future is None:
            self.get_logger().info('Saving the generated map...')
            req = SaveMap.Request()
            req.map_topic = 'map'
            req.map_url = self.map_filepath
            req.image_format = 'pgm'
            req.map_mode = 'trinary'
            req.free_thresh = 0.25
            req.occupied_thresh = 0.65
            self.save_map_future = self.save_map_client.call_async(req)
            return

        if self.save_map_future.done():
            if self.save_map_future.result() is not None:
                self.get_logger().info('Map saved successfully.')
                self.state = 'PLANNING'
            else:
                self.get_logger().error('Failed to save the map.')
            self.save_map_future = None

    # --- PHASE 3: WAYPOINT EXTRACTION (Basic CPP) ---
    def generate_waypoints_from_map(self):
        self.get_logger().info('Generating patrol route from the image...')
        img_path = f"{self.map_filepath}.pgm"
        yaml_path = f"{self.map_filepath}.yaml"
        
        if not os.path.exists(img_path):
            self.get_logger().error("Physical map not found.")
            return

        # 1. Read map parameters.
        with open(yaml_path, 'r') as f:
            map_data = yaml.safe_load(f)
            resolution = map_data['resolution']
            origin_x = map_data['origin'][0]
            origin_y = map_data['origin'][1]

        # 2. Computer Vision: Find free tiles (white).
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        free_space_thresh = 250
        _, binary = cv2.threshold(img, free_space_thresh, 255, cv2.THRESH_BINARY)
        
        # Erode to separate the robot from the walls.
        kernel = np.ones((5,5), np.uint8)
        safe_binary = cv2.erode(binary, kernel, iterations=2)

        # 3. Create a waypoint grid (e.g., a point every 2 meters).
        grid_spacing_pixels = max(1, int(self.grid_spacing_m / resolution))
        
        waypoints = []
        for y in range(0, safe_binary.shape[0], grid_spacing_pixels):
            # Alternate loop for a "snake" or "zig-zag" sweep effect.
            x_range = range(0, safe_binary.shape[1], grid_spacing_pixels)
            if (y // grid_spacing_pixels) % 2 != 0:
                x_range = reversed(x_range)
                
            for x in x_range:
                if safe_binary[y, x] == 255: # If space is safe.
                    # Map pixel to real coordinate in meters in ROS 2.
                    real_x = origin_x + (x * resolution)
                    # In ROS, the Y axis is inverted relative to images.
                    real_y = origin_y + ((img.shape[0] - y) * resolution)
                    waypoints.append(self.create_pose(real_x, real_y, 0.0))

        if not waypoints:
            self.get_logger().error('No safe waypoints could be generated from the map.')
            return

        self.waypoints_queue.clear()
        self.waypoints_queue.append(self.dock_pose)
        self.waypoints_queue.extend(waypoints)
        self.waypoints_queue.append(self.dock_pose)
        self.get_logger().info(f'{len(waypoints)} patrol points were generated.')
        
        self.state = 'PATROLLING'

    # --- PHASE 4: PATROL CYCLE ---
    def run_patrol_cycle(self):
        if self.active_task is None:
            self.get_logger().info('Starting patrol cycle with NavigateThroughPoses.')
            route = []
            for _ in range(len(self.waypoints_queue)):
                pose = self.waypoints_queue.popleft()
                route.append(pose)
                self.waypoints_queue.append(pose)
            self.navigator.goThroughPoses(route)
            self.active_task = 'patrol'
            return

        if not self.navigator.isTaskComplete():
            return

        result = self.navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            self.get_logger().info('Patrol cycle finished. Restarting...')
        elif result == TaskResult.CANCELED:
            self.get_logger().warn('Patrol canceled. Restarting...')
        else:
            self.get_logger().error('Patrol failed. Restarting...')

        self.active_task = None

    def run_patrol_stopped(self):
        if self.active_task != 'return_to_dock':
            if self.active_task is not None:
                self.get_logger().info('Patrol stopped by user. Canceling active navigation task.')
                self.navigator.cancelTask()
                # Bug fix: Nav2 processes cancellations asynchronously. We must wait
                # for the current task to actually finish (CANCELED or FAILED) before
                # issuing goToPose, otherwise the two commands race inside Nav2.
                # isTaskComplete() returns True once the result (any result) is available.
                if not self.navigator.isTaskComplete():
                    self.get_logger().info('Waiting for active task to be canceled before returning to dock...')
                    return  # Come back next timer tick (1 s) and check again

            self.get_logger().info('Returning to dock before stopping patrol.')
            self.navigator.goToPose(self.dock_pose)
            self.active_task = 'return_to_dock'
            return

        if not self.navigator.isTaskComplete():
            return

        result = self.navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            self.get_logger().info('Dock reached. Patrol is stopped.')
        elif result == TaskResult.CANCELED:
            self.get_logger().warn('Return to dock canceled. Patrol is stopped anyway.')
        else:
            self.get_logger().error('Failed to reach dock. Patrol is stopped anyway.')

        self.active_task = None

def main(args=None):
    rclpy.init(args=args)
    node = PatrolOrchestrator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()