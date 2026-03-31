from rclpy.node import Node
import sys
import threading
from sql_interface.srv import SQLOperation
import rclpy
import numpy as np
from PySide6.QtCore import QThread, Signal,QObject,Slot
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import cv2
from PySide6.QtGui import QImage

class DisplayNode(Node,QObject):
    data_updated = Signal(list)
    image_updated = Signal(QImage)
    reason_flag = Signal()
    def __init__(self, name: str):
        Node.__init__(self, node_name=name)      # 先初始化 Node
        QObject.__init__(self)
        self.cv_bridge:CvBridge = CvBridge()
        self.image_temp:np.ndarray
        self.get_logger().info("DisplayNode started")
        self.clients_sql = self.create_client(SQLOperation, "/sql_operation")
        self.timer = self.create_timer(0.5, self.timer_callback)
        self.subscriptions_image =          self.create_subscription(CompressedImage,"/image",callback=self.ImageCallback,qos_profile=10)        
        self.publishers_ = self.create_publisher(CompressedImage,"/image",qos_profile=10)
        self.ingredient = [ ["", -1, [], []] for _ in range(9) ]

    def ImageCallback(self,msg):
        cv_image = self.cv_bridge.compressed_imgmsg_to_cv2(msg)
        self.image_temp = cv_image
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        qimage = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.image_updated.emit(qimage.copy())
        
    def timer_callback(self):
        for id in range(9):   # id 从 0 到 8，对应 request.id = id+1 ?
            self.SqlOpSend_(id + 1)
            self.data_updated.emit(self.ingredient[:])

    def SqlOpSend_(self, id: int):
        try:
            if not self.clients_sql.wait_for_service(0.5):
                self.get_logger().warn(f"服务 /sql_operation 未上线，id={id}")
                return
            request = SQLOperation.Request()
            request.operation = 4
            request.id = id
            future = self.clients_sql.call_async(request)
            future.add_done_callback(self.SqlOpCallback_)
        except:
            self.get_logger().warn("error")
        pass

    def SqlOpCallback_(self, future):
        try:
            response = future.result()
            # 更新本地数据
            idx = response.id - 1
            if 0 <= idx < 9:
                self.ingredient[idx] = [
                    response.name,
                    response.expiry_date,
                    [response.nutritional_info],   # 注意：你原来用了列表
                    [response.notes]
                ]
        except Exception as e:
            self.get_logger().error(f"Service call failed: {e}")

    @Slot()
    def StartReasoning(self):
        if self.image_temp is None:
            return
        self.get_logger().info("start reasoning")
        
        
        
        pass

class RosWorker(QThread):
    data_updated = Signal(list)
    def __init__(self,node:DisplayNode):
        super().__init__()
        self.node = node
        self.daemon = True

    def run(self):
        try:            
            rclpy.spin(self.node)
        except:
            rclpy.shutdown
            sys.exit(0)

    def stop(self):
        rclpy.shutdown
        sys.exit(0)

    def getIngredient(self):
        if len(self.node.ingredient) != 0:
            return self.node.ingredient
        pass