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

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import LaunchConfiguration


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

    return LaunchDescription(
        [
            declare_test_mode_arg,
            qt_display_node,
        ]
    )
