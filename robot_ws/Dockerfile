# imagen oficial de ROS 2 Humble
FROM osrf/ros:humble-desktop

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

# 1. Herramientas básicas
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    nano \
    git \
    iputils-ping \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 2. Paquetes TurtleBot 4 + TurtleBot 3 + Gazebo
RUN apt-get update && apt-get install -y \
    ros-humble-turtlebot4-simulator \
    ros-humble-turtlebot4-desktop \
    ros-humble-turtlesim \
    ros-humble-turtlebot4-navigation \
    ros-humble-turtlebot4-viz \
    ros-humble-turtlebot3 \
    ros-humble-turtlebot3-simulations \
    ros-humble-turtlebot3-gazebo \
    ros-humble-gazebo-ros-pkgs \
    qtwayland5 \
    && rm -rf /var/lib/apt/lists/*

# 3. Librerías Python
RUN pip3 install confluent-kafka requests

# 4. Workspace
WORKDIR /robot_ws
RUN mkdir -p src

# 5. Source automático
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && \
    echo "export TURTLEBOT3_MODEL=burger" >> ~/.bashrc