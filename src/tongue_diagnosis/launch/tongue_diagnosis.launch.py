import os
from launch import LaunchDescription
from launch.substitutions import TextSubstitution
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    default_model_dir = os.path.join(
        get_package_share_directory('tongue_diagnosis'),
        'bin',
    )

    # Launch arguments with defaults
    model_dir_arg = DeclareLaunchArgument(
        'model_dir',
        default_value=TextSubstitution(text=default_model_dir),
        description='Directory containing quantized model bin files'
    )
    
    yolo_score_arg = DeclareLaunchArgument(
        'yolo_score_threshold',
        default_value='0.7',
        description='YOLO26 confidence threshold'
    )
    
    # Tongue diagnosis node
    tongue_diagnosis_node = Node(
        package='tongue_diagnosis',
        executable='tongue_diagnosis_node',
        name='tongue_diagnosis_node',
        parameters=[
            {'model_dir': LaunchConfiguration('model_dir')},
            {'yolo_score_threshold': LaunchConfiguration('yolo_score_threshold')},
            {'input_image_topic': '/tongue_diagnosis/input_image'},
            {'output_result_topic': '/tongue_diagnosis/result'},
        ],
        output='screen',
    )
    
    return LaunchDescription([
        model_dir_arg,
        yolo_score_arg,
        tongue_diagnosis_node,
    ])
