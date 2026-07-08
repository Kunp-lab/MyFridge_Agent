import os

from ament_index_python import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    test_mode = LaunchConfiguration("test_mode")
    enable_tongue_diagnosis = LaunchConfiguration("enable_tongue_diagnosis")
    tongue_model_dir = LaunchConfiguration("tongue_model_dir")
    tongue_yolo_score_threshold = LaunchConfiguration(
        "tongue_yolo_score_threshold"
    )
    usb_video_device = LaunchConfiguration("usb_video_device")

    declare_test_mode_arg = DeclareLaunchArgument(
        "test_mode",
        default_value="false",
        choices=["true", "false"],
        description="是否启用食材识别测试模式。",
    )
    declare_enable_tongue_diagnosis_arg = DeclareLaunchArgument(
        "enable_tongue_diagnosis",
        default_value="true",
        choices=["true", "false"],
        description="是否启动舌诊推理节点。",
    )
    declare_tongue_model_dir_arg = DeclareLaunchArgument(
        "tongue_model_dir",
        default_value=os.path.join(
            get_package_share_directory("tongue_diagnosis"),
            "bin",
        ),
        description="舌诊模型目录。",
    )
    declare_tongue_yolo_score_threshold_arg = DeclareLaunchArgument(
        "tongue_yolo_score_threshold",
        default_value="0.7",
        description="舌诊 YOLO26 分割置信度阈值。",
    )
    declare_usb_video_device_arg = DeclareLaunchArgument(
        "usb_video_device",
        default_value="/dev/video8",
        description="USB 摄像头设备路径。",
    )

    qt_display_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("qt_display"),
                "launch",
                "qtapp.launch.py",
            )
        ),
        launch_arguments={"test_mode": test_mode}.items(),
    )

    sql_server_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("sql_server"),
                "launch",
                "sql_server.launch.py",
            )
        )
    )

    connector_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("connector"),
                "launch",
                "connector.launch.py",
            )
        )
    )

    usb_cam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("hobot_usb_cam"),
                "launch",
                "hobot_usb_cam.launch.py",
            )
        ),
        launch_arguments={"usb_video_device": usb_video_device}.items(),
    )

    tongue_diagnosis_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("tongue_diagnosis"),
                "launch",
                "tongue_diagnosis.launch.py",
            )
        ),
        launch_arguments={
            "model_dir": tongue_model_dir,
            "yolo_score_threshold": tongue_yolo_score_threshold,
        }.items(),
        condition=IfCondition(enable_tongue_diagnosis),
    )

    return LaunchDescription(
        [
            declare_test_mode_arg,
            declare_enable_tongue_diagnosis_arg,
            declare_tongue_model_dir_arg,
            declare_tongue_yolo_score_threshold_arg,
            declare_usb_video_device_arg,
            connector_launch,
            sql_server_launch,
            usb_cam_launch,
            tongue_diagnosis_launch,
            qt_display_launch,
        ]
    )
