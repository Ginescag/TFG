# imagen oficial de ROS 2 Humble
FROM osrf/ros:humble-desktop

# Configuramos la terminal
SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

# 1 Herramientas básicas de compilación y Python
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    nano \
    git \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# 2 Paquetes oficiales del TurtleBot 4 y su simulador
RUN apt-get update && apt-get install -y \
    ros-humble-turtlebot4-simulator \
    ros-humble-turtlebot4-desktop \
    ros-humble-turtlebot4-navigation2 \
    ros-humble-turtlebot4-viz \
    && rm -rf /var/lib/apt/lists/*

# 3. Librerías de Python para tu Bridge (FastAPI + Kafka)
RUN pip3 install confluent-kafka requests --break-system-packages

# 4. Preparar el Workspace
WORKDIR /robot_ws
RUN mkdir -p src

# 5. Automatizar los sources para que los comandos de ROS 2 funcionen al abrir la terminal
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc