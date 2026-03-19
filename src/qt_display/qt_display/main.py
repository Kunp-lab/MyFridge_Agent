import rclpy
from .display_node import *
from .display_component import *
import threading

def update_ingredient(semaphore:threading.Semaphore,fridge:SmartFridgeUI,node:DisplayNode,event:threading.Event):
    event.wait()
    with semaphore:
        for index in range(len(node.ingredient)):
            if (node.ingredient[index][0] != str and node.ingredient[index][1] != int and node.ingredient[index][2] != str and node.ingredient[index][3] != str):
                fridge.set_food_item(index//3,index%3,node.ingredient[index][0],node.ingredient[index][1],node.ingredient[index][2],node.ingredient[index][3])

def main(args = None):
    rclpy.init(args=args)
    semaphore = threading.Semaphore(1)
    sleep_event = threading.Event()
    node = DisplayNode("DisplayNode",sem=semaphore,sleep_event=sleep_event)
    app = QApplication(sys.argv)
    fridge = SmartFridgeUI()
    fridge.show()
    update_thread = threading.Thread(target=update_ingredient,args=[semaphore,fridge,node,sleep_event],daemon=True)
    ros_thread = RosThread(node)
    ros_thread.start()
    update_thread.start()

    try:
        sys.exit(app.exec())
        pass
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown

    