from rclpy.node import Node
import sys
import threading
from sql_interface.srv import SQLOperation
import base64
import rclpy
import numpy as np
from PySide6.QtCore import QThread, Signal, QObject, Slot
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
import os
from openai import OpenAI
from PySide6.QtGui import QImage
import json
from .config import Setting
import paho.mqtt.client as mqtt
import time


class DisplayNode(Node, QObject):
    data_updated = Signal(list)
    image_updated = Signal(QImage)
    reason_flag = Signal()

    def __init__(self, name: str):
        Node.__init__(self, node_name=name)  # 先初始化 Node
        QObject.__init__(self)
        self.cv_bridge: CvBridge = CvBridge()
        self.image_temp: np.ndarray
        self.get_logger().info("DisplayNode started")
        self.clients_sql = self.create_client(SQLOperation, "/sql_operation")
        self.timer = self.create_timer(3, self.timer_callback)
        self.subscriptions_image = self.create_subscription(
            CompressedImage, "/image", callback=self.ImageCallback, qos_profile=10
        )
        self.publishers_vlm_image_ = self.create_publisher(
            Image, "/vlm_image_topic", qos_profile=10
        )
        self.publishers_vlm_text_ = self.create_publisher(
            String, "/prompt_text", qos_profile=10
        )
        self.ingredient = [["", -1, [], []] for _ in range(9)]
        self.LLM_server = OpenAI(
            api_key=Setting.API_KEY.value,
            base_url=Setting.BASE_URL.value,
        )
        self.Ton_server = mqtt.Client()
        self.init_mqtt_connect()

    def init_mqtt_connect(self):
        def on_connect(client, userdata, flags, reason_code, properties=None):
            self.get_logger().info(f"[*] 已连接到 Broker")
            # 连接成功后立刻订阅结果话题
            client.subscribe(Setting.TOPIC_RECEIVE.value)
            self.get_logger().info(
                f"[*] 已订阅话题: {Setting.TOPIC_RECEIVE.value}，等待 AI 回复..."
            )

        def on_message(client, userdata, msg):
            self.get_logger().info(f"\n[√] 收到来自 {msg.topic} 的推送:")
            self.get_logger().info(f"内容: {msg.payload.decode()}")
            # 收到结果后，可以安全退出
            client.disconnect()

        self.Ton_server.on_connect = on_connect
        self.Ton_server.on_message = on_message
        try:
            self.Ton_server.connect(Setting.BROKER_IP.value, 1883, 60)
        except Exception as e:
            self.get_logger().error(f"[!] 无法连接: {e}")
            sys.exit(1)
            return
        self.Ton_server.loop_start()
        self.get_logger().info("[*] 正在建立连接...")
        retry_count = 0
        while not self.Ton_server.is_connected() and retry_count < 10:
            time.sleep(0.5)
            retry_count += 1

        if not self.Ton_server.is_connected():
            self.get_logger().info("[!] 连接超时，请检查网络或防火墙！")
            return

        # --- 现在连接已经是 True 了 ---
        self.get_logger().info(f"[*] 连接状态: {self.Ton_server.is_connected()}")

    def ImageCallback(self, msg):
        cv_image = self.cv_bridge.compressed_imgmsg_to_cv2(msg)
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        self.image_temp = rgb_image
        h, w, ch = rgb_image.shape
        qimage = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.image_updated.emit(qimage.copy())

    def timer_callback(self):
        for id in range(9):  # id 从 0 到 8，对应 request.id = id+1 ?
            self.SqlOpSend_(id + 1)
            self.data_updated.emit(self.ingredient[:])

    def SqlOpSend_(self, id: int):
        try:
            if not self.clients_sql.wait_for_service(0.5):
                self.get_logger().warn(f"服务 /sql_operation 未上线,id={id}")
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
            if 1 <= response.id <= 9:
                idx = response.id - 1
                if 0 <= idx < 9:
                    self.ingredient[idx] = [
                        response.name,
                        response.expiry_date,
                        [response.nutritional_info],  # 注意：你原来用了列表
                        [response.notes],
                    ]
            else:
                pass
        except Exception as e:
            self.get_logger().error(f"Service call failed: {e}")

    @Slot()
    def StartReasoning(self):
        if self.image_temp is None:
            return

        system_prompt = """你是一个严格的食物分析助手。
        请严格只返回以下JSON格式,不要添加任何其他文字、解释或markdown:
        {
        "名字": "取常见食物名字",
        "营养价值": "10个字以上",
        "食用建议": "10个字以上",
        "保质期": "假设今天放入这种食物，保质期大概为几天，单位为天,数据类型为int"
        }"""

        image_base64 = self.encode_opencv_image(
            self.image_temp, format=".jpg", quality=85
        )

        response = self.LLM_server.chat.completions.create(
            model="glm-4.6v-flash",  # 推荐快速模型
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "分析图片中的食物，按要求输出四个信息",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=400,
            temperature=0.1,
        )

        try:
            if response.choices[0].message.content is None:
                return
            result = json.loads(response.choices[0].message.content.strip())
            request = SQLOperation.Request()
            request.operation = 1
            request.name = result["名字"]
            request.expiry_date = result["保质期"]
            request.nutritional_info = result["营养价值"]
            request.notes = result["食用建议"]
            future = self.clients_sql.call_async(request)
            future.add_done_callback(self.SqlOpCallback_)
            return result
        except Exception as e:
            self.get_logger().error(f"JSON 解析失败:{e}")
            return None

    def encode_opencv_image(
        self, image: np.ndarray, format: str = ".jpg", quality: int = 85
    ) -> str:
        """
        把 OpenCV 图像 (numpy array) 直接转为 base64
        format: ".jpg" 或 ".png"
        quality: jpg 压缩质量 (1-100)，越低越小越快
        """
        if format.lower() == ".png":
            success, encoded = cv2.imencode(".png", image)
        else:
            # jpg 压缩更快、数据量更小，推荐用于 API 调用
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            success, encoded = cv2.imencode(".jpg", image, encode_param)

        if not success:
            raise ValueError("图像编码失败")

        buffer_bytes = encoded.tobytes()
        return base64.b64encode(buffer_bytes).decode("utf-8")


class RosWorker(QThread):
    data_updated = Signal(list)

    def __init__(self, node: DisplayNode):
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
