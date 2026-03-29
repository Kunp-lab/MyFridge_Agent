import rclpy
from .display_node import *
from .display_component import *

def main(args = None):
    rclpy.init(args=args)
    node = DisplayNode("DisplayNode")
    app = QApplication(sys.argv)
    fridge = SmartFridgeUI(node=node)
    fridge.show()
    
    try:
        sys.exit(app.exec())
        pass
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown

    