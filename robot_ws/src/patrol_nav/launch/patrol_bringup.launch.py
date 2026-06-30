"""Bringup de patrulla que autoselecciona el modo de Nav2 segun exista el mapa.

Regla: el estado del mapa guardado decide como se arranca.
  - Existe `<map_filepath>.yaml`  -> LOCALIZACION (map_server + AMCL) + patrol_nav use_localization:=true
  - No existe                     -> SLAM (explorar y mapear)        + patrol_nav use_localization:=false

Asi "como se lanza (SLAM o no)" no se pone a mano: se deriva del mapa. Tras un
`reinstall` que borra el mapa, el siguiente lanzamiento arranca en SLAM solo.

Argumento `sim`:
  - true  (por defecto): simulador Ignition (turtlebot4_ignition_bringup).
  - false: robot real (turtlebot4_navigation slam/localization + nav2); se asume que
    el bringup base del TB4 ya corre en la Raspberry Pi.

El nodo patrol_nav toma el resto de parametros (robot_id, kafka, server_url, ...) de sus
variables de entorno por defecto, por lo que aqui solo forzamos use_localization y
map_filepath, que deben ser coherentes con el `map:=` que se pasa a la localizacion.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _str_is_true(value):
    return str(value).lower() in ('true', '1', 'yes')


def _bringup(context, *args, **kwargs):
    sim = _str_is_true(LaunchConfiguration('sim').perform(context))
    world = LaunchConfiguration('world').perform(context)
    rviz = LaunchConfiguration('rviz').perform(context)
    map_filepath = LaunchConfiguration('map_filepath').perform(context)
    robot_id = LaunchConfiguration('robot_id').perform(context)

    map_yaml = f'{map_filepath}.yaml'
    map_exists = os.path.exists(map_yaml)

    if map_exists:
        print(f'[patrol_bringup] Saved map found ({map_yaml}) -> LOCALIZATION mode.')
    else:
        print(f'[patrol_bringup] No saved map ({map_yaml}) -> SLAM mode (will explore and map).')

    actions = []

    if sim:
        ign = os.path.join(
            get_package_share_directory('turtlebot4_ignition_bringup'),
            'launch', 'turtlebot4_ignition.launch.py')
        ign_args = {'nav2': 'true', 'rviz': rviz, 'world': world}
        if map_exists:
            ign_args.update({'localization': 'true', 'slam': 'false', 'map': map_yaml})
        else:
            ign_args.update({'localization': 'false', 'slam': 'true'})
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(ign),
            launch_arguments=ign_args.items()))
    else:
        nav_share = get_package_share_directory('turtlebot4_navigation')
        if map_exists:
            actions.append(IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(nav_share, 'launch', 'localization.launch.py')),
                launch_arguments={'map': map_yaml}.items()))
        else:
            actions.append(IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(nav_share, 'launch', 'slam.launch.py'))))
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav_share, 'launch', 'nav2.launch.py'))))

    if not map_exists:
        # En SLAM, patrol_nav guarda el mapa con /map_saver/save_map: el server debe estar vivo.
        actions.append(Node(
            package='nav2_map_server',
            executable='map_saver_server',
            name='map_saver',
            output='screen',
            parameters=[{'save_map_timeout': 5.0}],
        ))

    actions.append(Node(
        package='patrol_nav',
        executable='patrol_nav',
        name='patrol_orchestrator',
        output='screen',
        parameters=[{
            'use_localization': map_exists,
            'map_filepath': map_filepath,
            'robot_id': robot_id,
        }],
    ))

    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'sim', default_value='true',
            description='true para el simulador Ignition, false para el TB4 real'),
        DeclareLaunchArgument('world', default_value='maze'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument(
            'map_filepath', default_value='/robot_ws/src/mapa_patrulla',
            description='Ruta del mapa sin extension (.pgm/.yaml). Debe coincidir con map_filepath del nodo'),
        DeclareLaunchArgument(
            'robot_id', default_value=os.getenv('ROBOT_ID', 'RBT-01')),
        OpaqueFunction(function=_bringup),
    ])
