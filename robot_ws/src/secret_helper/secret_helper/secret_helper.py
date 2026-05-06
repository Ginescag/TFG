import rclpy
from rclpy.node import Node
import os
import json
import requests
import threading
import time
from pathlib import Path

# Nota: Tendremos que editar package.xml y CMakeLists.txt para que se compile este .srv
from secret_helper.srv import GetToken

class SecretHelperNode(Node):
    def __init__(self):
        super().__init__('secret_helper_node')

        self.robot_id = os.getenv('ROBOT_ID')
        self.backend_url = os.getenv('BACKEND_URL')
        
        # Ruta donde guardaremos físicamente el secreto dentro del robot.
        # Puede ser un volumen de docker para que sea tolerante a reinicios del contenedor
        self.secret_file = Path(os.getenv('SECRET_PATH'))
        
        self.current_jwt = None
        self.is_ready = False
        
        # ROS 2 Service Server
        self.srv = self.create_service(GetToken, 'get_robot_token', self.get_token_callback)
        
        # Iniciamos el proceso de obtención/refresco del token en un Hilo separado
        # para no bloquear el bucle (spin) de ROS 2 si hay problemas de red.
        threading.Thread(target=self.auth_routine, daemon=True).start()

    def auth_routine(self):
        self.get_logger().info('Iniciando rutina de autenticación y gestión de secretos...')
        
        # 1. Aseguramos tener el secreto raíz (TOFU)
        secret = self.get_or_fetch_secret()
        if not secret:
            self.get_logger().error("No se pudo obtener el secreto raíz. Deteniendo proceso de Auth.")
            return

        # 2. Bucle infinito de autenticación y refresco (Proactivo)
        while rclpy.ok():
            jwt_token = self.authenticate(secret)
            
            if jwt_token:
                self.current_jwt = jwt_token
                self.is_ready = True
                self.get_logger().info("JWT obtenido/refrescado exitosamente.")
                
                # Dormimos el hilo durante un periodo (cada hora)
                time.sleep(3600)
            else:
                self.is_ready = False
                self.get_logger().warn("Fallo al autenticar. Reintentando en 10 segundos...")
                time.sleep(10)

    def get_or_fetch_secret(self):
        """Intenta leer el secreto local. Si no existe, llama al First Boot."""
        if self.secret_file.exists():
            with open(self.secret_file, 'r') as f:
                hidden_secret = f.read().strip()
            if hidden_secret:
                self.get_logger().info("Se encontró un secreto almacenado localmente.")
                return hidden_secret

        # Si no existe archivo, es nuestro First Boot
        self.get_logger().info("No hay secreto guardado. Intentando proceso de First Boot (TOFU)...")
        try:
            url = f"{self.backend_url}/robot/{self.robot_id}/first-boot"
            response = requests.post(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                new_secret = data.get("secret")
                
                if new_secret:
                    with open(self.secret_file, 'w') as f:
                        f.write(new_secret)
                    self.get_logger().info("Secreto raíz obtenido y guardado en disco con éxito.")
                    return new_secret
            else:
                self.get_logger().error(f"Fallo en First Boot: HTTP {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            self.get_logger().error(f"Error de red intentando First Boot: {e}")

        return None

    def authenticate(self, secret):
        """Llama al backend con el secreto raíz para obtener el JWT temporal de sesión."""
        self.get_logger().info("Contactando al backend para obtener JWT...")
        try:
            url = f"{self.backend_url}/robot/{self.robot_id}/auth"
            payload = {"secret_key": secret}
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            else:
                self.get_logger().error(f"Fallo de login (Auth): HTTP {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            self.get_logger().error(f"Error de red durante Auth: {e}")
            
        return None

    # ============== SERVICIO ROS 2 ==============
    def get_token_callback(self, request, response):
        """Callback for 'serve_telemetry' and 'detect_incident'."""
        if self.is_ready and self.current_jwt:
            response.success = True
            response.token = self.current_jwt
            response.message = "OK"
        else:
            response.success = False
            response.token = ""
            response.message = "El JWT aún no está disponible o la autenticación ha fallado."
            
        return response

def main(args=None):
    rclpy.init(args=args)
    node = SecretHelperNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()