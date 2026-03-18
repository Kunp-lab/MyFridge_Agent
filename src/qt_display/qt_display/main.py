import rclpy
from .display_node import *
from .display_component import *
import threading

def main(args = None):
    rclpy.init(args=args)
    node = DisplayNode("DisplayNode")
    app = QApplication(sys.argv)
    fridge = SmartFridgeUI()
    fridge.show()
    ros_thread = RosThread(node)
    ros_thread.start()
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown

    