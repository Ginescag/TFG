# 🛠️ Tech Stack - Robot de Patrulla Indoor (TFG)

Este documento detalla el conjunto de tecnologías y servicios utilizados en el desarrollo del sistema de vigilancia autónoma.

## 🤖 1. Robótica y Edge AI (TurtleBot 4)
* **Sistema Operativo:** Ubuntu 22.04 LTS (Raspberry Pi 4)
* **Middleware:** ROS 2 (Humble Hawksbill)
* **Navegación:** Nav2 (SlamToolbox para mapeo, Nav2 para planificación de rutas)
* **Visión:** YOLOv8 (Inferencia en tiempo real para detección de intrusos/mascotas)
* **Comunicación Interna:** Tópicos, Acciones y Servicios de ROS 2

## 🐳 2. Infraestructura y Servicios (Docker)
* **Orquestación:** Docker Compose (Entorno de desarrollo unificado)
* **Base de Datos Relacional:** PostgreSQL 16 (Persistencia de usuarios, configuración y registros históricos)
* **Message Broker:** Apache Kafka (Protocolo de eventos para desacoplar el robot del servidor)
* **Object Storage:** MinIO (Almacenamiento compatible con S3 para clips de vídeo y fotos de alertas)
* **Time-Series DB:** InfluxDB 2.7 (Telemetría de alta frecuencia: batería, CPU, latencia, posición)
* **Visualización:** Grafana (Dashboards de estado operativo y métricas de rendimiento)

## 🧠 3. Servidor / Backend
* **Lenguaje:** Python 3.10+
* **Framework:** FastAPI (Arquitectura asíncrona para alta concurrencia)
* **ORM:** SQLAlchemy 2.0 (Mapeo objeto-relacional asíncrono)
* **Seguridad:** JWT (JSON Web Tokens) con algoritmo HS256 y cifrado de contraseñas Bcrypt
* **Validación de Datos:** Pydantic V2 (Esquemas de datos estrictos)

## 📱 4. Panel de Control (Frontend)
* **Framework:** Flutter (Dart)
* **Plataformas:** Web (Prioritario) y compilación nativa para Android/iOS
* **Comunicación en Tiempo Real:** WebSockets (Notificaciones push de alertas)
