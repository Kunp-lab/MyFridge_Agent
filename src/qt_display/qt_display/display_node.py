from rclpy.node import Node
from .display_component import *
import threading
from sql_interface.srv import SQLOperation
import rclpy
import numpy as np

class DisplayNode(Node):
    def __init__(self,name:str,sem:threading.Semaphore,sleep_event:threading.Event) -> None:
        super().__init__(node_name=name)
        self.get_logger().info("DisplayNode started")
        self.init()
        self.ingredient = [[str,int,[str],[str]] for _ in range(9)]
        self.sem:threading.Semaphore = sem
        self.sleep_event:threading.Event = sleep_event
        pass
    
    def testSetEnv(self):
        pass 

    def init(self):
        self.clients_sql = self.create_client(SQLOperation,"/sql_operation")
        self.timer = self.create_timer(0.5,self.timer_callback)

    def timer_callback(self):
        for id in range(9):  
            self.SqlOpSend_(id)

    def SqlOpCallback_(self, result_future):
        response = SQLOperation.Response()
        response = result_future.result()
        with self.sem:
            self.ingredient[response.id-1][0] =response.name
            self.ingredient[response.id-1][1] =response.expiry_date
            self.ingredient[response.id-1][2] =[response.nutritional_info]
            self.ingredient[response.id-1][3] =[response.notes]
            self.sleep_event.set()

    
    def SqlOpSend_(self, id):
        while rclpy.ok() and self.clients_sql.wait_for_service(1)==False:
            self.get_logger().info(f"等待服务端上线....")
            
        request = SQLOperation.Request()
        request.operation = 4
        request.id = id 
        self.clients_sql.call_async(request).add_done_callback(self.SqlOpCallback_)

class RosThread(threading.Thread):
    def __init__(self,node:DisplayNode):
        super().__init__()
        self.node = node
        self.daemon = True

    def run(self):
        rclpy.spin(self.node)

    def getIngredient(self):
        if len(self.node.ingredient) != 0:
            return self.node.ingredient
        pass