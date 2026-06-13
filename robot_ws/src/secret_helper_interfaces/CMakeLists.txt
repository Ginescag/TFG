cmake_minimum_required(VERSION 3.8)
project(secret_helper_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/GetToken.srv"
)

ament_package()
