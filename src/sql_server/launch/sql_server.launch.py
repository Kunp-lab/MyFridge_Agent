from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="sql_server",
                executable="sql_server_node",
                name="sql_server",
                output="screen",
            )
        ]
    )
