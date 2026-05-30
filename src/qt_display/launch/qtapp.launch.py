# Copyright (c) 2024，D-Robotics.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import TextSubstitution
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python import get_package_share_directory
from ament_index_python.packages import get_package_prefix


def generate_launch_description():
    test_mode = LaunchConfiguration("test_mode")
    declare_test_mode_arg = DeclareLaunchArgument(
        "test_mode",
        default_value="false",
        choices=["true", "false"],
        description="是否启用食材识别测试模式。true=跳过云端推理，延迟2秒返回本地固定结果",
    )

    qt_display_node = Node(
        package="qt_display",
        executable="qt_display_node",
        output="screen",
        parameters=[{"test_mode": ParameterValue(test_mode, value_type=bool)}],
    )

    sql_server_node = Node(
            package="sql_server",
            executable="sql_server_node",
            output="screen",
        )
    
    connector_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("connector"), "launch/connector.launch.py"
            )
        )
    )

    usb_cam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("hobot_usb_cam"), "launch/hobot_usb_cam.launch.py"
            )
        )
    )

    return LaunchDescription(
        [
            declare_test_mode_arg,
            connector_launch,
            qt_display_node,
            sql_server_node,
            usb_cam_launch,
        ]
    )
