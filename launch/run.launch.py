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
from launch.substitutions import TextSubstitution
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python import get_package_share_directory
from ament_index_python.packages import get_package_prefix


def generate_launch_description():

    llama_node = Node(
        package="hobot_llamacpp",
        executable="hobot_llamacpp",
        output="screen",
        parameters=[
            {"feed_type": 1},
            {"is_shared_mem_sub": 1},
            {"llm_threads": 6},
            {"user_prompt": LaunchConfiguration("llamacpp_user_prompt")},
            {"system_prompt": LaunchConfiguration("llamacpp_system_prompt")},
            {"pre_infer": LaunchConfiguration("llamacpp_advance")},
            {
                "cute_words": "好的,让我看看;没问题,我想想;容我思考片刻;小事一桩;收到,我的主人"
            },
            {
                "text_msg_pub_topic_name": LaunchConfiguration(
                    "llamacpp_text_msg_pub_name"
                )
            },
            {
                "ros_string_sub_topic_name": LaunchConfiguration(
                    "llamacpp_prompt_msg_sub_name"
                )
            },
            {"model_type": LaunchConfiguration("llamacpp_model_type")},
            {"model_file_name": LaunchConfiguration("llamacpp_vit_model_file_name")},
            {"llm_model_name": LaunchConfiguration("llamacpp_gguf_model_file_name")},
        ],
        arguments=["--ros-args", "--log-level", "warn"],
    )

    return LaunchDescription(
        [
            # 启动llamacpp pkg
            llama_node,
        ]
    )
