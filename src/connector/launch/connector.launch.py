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
from launch.substitutions import LaunchConfiguration, TextSubstitution
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python import get_package_share_directory
from ament_index_python.packages import get_package_prefix
import os

def generate_launch_description():
    # config_file_path = os.path.join(
    #     get_package_prefix('hobot_usb_cam'),
    #     "lib/hobot_usb_cam/config/usb_camera_calibration.yaml")
    # print("config_file_path is ", config_file_path)

    return LaunchDescription([
        Node(
            package='connector',
            executable='mcu_connector_node',
            name='hobot_usb_cam',
        ),
        Node(
            package='connector',
            executable='qdriver_connector_node',
            name='hobot_usb_cam',            
        )
    ])
