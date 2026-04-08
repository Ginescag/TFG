# 🛡️ Autonomous Indoor Patrol Robot with TurtleBot 4 (TB4)

> **Bachelor's Thesis (TFG) - Computer Engineering / Robotics**
>
> An event-driven, autonomous indoor surveillance system utilizing ROS 2, Edge AI (YOLOv8), and a modern web stack for real-time monitoring and incident management.

## 📖 Overview

This project implements a comprehensive indoor patrol and surveillance system using a **TurtleBot 4**. The robot is capable of navigating autonomously through a mapped building, detecting specific targets (intruders, pets, or misplaced objects) using lightweight artificial intelligence, and alerting a centralized web dashboard in real-time. 

Instead of a monolithic approach, this system uses a decoupled, event-driven architecture (via Kafka/MQTT) to ensure scalability, security, and hardware efficiency.

## ✨ Key Features

* **🤖 Autonomous Navigation:** Leverages **SLAM** for mapping and **Nav2** for semantic waypoint patrolling and dynamic obstacle avoidance.
* **👁️ Edge AI Perception:** Integrates **YOLOv8n** to detect people and pets in real-time, coupled with a multi-object tracking algorithm (e.g., ByteTrack) to assign unique IDs.
* **⚡ Event-Driven Architecture:** Uses **Kafka/MQTT** as a message broker to decouple the physical robot (ROS 2) from the web backend, minimizing network polling and saving battery.
* **📹 Live Streaming & Clip Storage:** Streams real-time video via WebRTC/WebSockets and automatically records and uploads incident clips to an S3-compatible Object Storage (**MinIO**).
* **🌐 Centralized Web Dashboard:** A React/Vue frontend that allows users to monitor the robot's status, view the live camera feed, send manual commands (Standby/Patrol), and review the incident history.
* **📊 Telemetry & Metrics:** Ingests high-frequency hardware metrics into **InfluxDB** and visualizes them using **Grafana** (battery levels, network latency, detection confidence).

## 🏗️ System Architecture

The project is structured as a Monorepo, divided into four main logical blocks:

1. **`robot_ws/` (Hardware & Edge):** ROS 2 Humble workspace running on the TurtleBot 4 (Raspberry Pi). Handles hardware interfaces, Nav2, YOLOv8 inference, and the IoT Bridge node.
2. **`infra/` (Data Layer):** Dockerized infrastructure containing PostgreSQL (relational data), Kafka (message broker), MinIO (media storage), and InfluxDB (time-series metrics).
3. **`backend/` (Control Plane):** A FastAPI/Node.js server that consumes Kafka events, handles business logic, persists data, and serves the REST API and WebSockets.
4. **`frontend/` (User Interface):** A modern SPA (Single Page Application) for the security personnel dashboard.

## 📂 Repository Structure

```text
tfg-robot-patrulla/
│
├── docs/                 # Architecture diagrams, API specs, and thesis documents
├── infra/                # Docker Compose files for DBs, Kafka, and MinIO
├── backend/              # API Server, DB ORM, and Kafka consumers
├── frontend/             # Web application (React/Vue)
└── robot_ws/             # ROS 2 Colcon workspace (TurtleBot 4 code)
    └── src/
        ├── tb4_patrol/   # Navigation and waypoint logic
        ├── tb4_vision/   # Camera capture and YOLOv8 inference
        └── tb4_bridge/   # IoT translation node (ROS 2 <-> Kafka)
