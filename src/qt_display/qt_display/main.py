import rclpy
from .display_node import *
from .display_component import *
import threading

def update_ingredient(semaphore:threading.Semaphore,fridge:SmartFridgeUI,node:DisplayNode):
    with semaphore:
        for index in range(len(node.ingredient)):
            fridge.set_food_item(index//3,index%3,node.ingredient[index][0],node.ingredient[index][1],node.ingredient[index][2],node.ingredient[index][3])

def main(args = None):
    rclpy.init(args=args)
    node = DisplayNode("DisplayNode")
    app = QApplication(sys.argv)
    fridge = SmartFridgeUI()
    fridge.show()
    semaphore = threading.Semaphore(1)
    update_thread = threading.Thread(target=update_ingredient,args=[semaphore,fridge,node])
    ros_thread = RosThread(node)
    ros_thread.start()
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown

    