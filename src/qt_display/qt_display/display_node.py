from rclpy.node import Node
import sys
import threading
from sql_interface.srv import SQLOperation
import base64
import rclpy
import numpy as np
from PySide6.QtCore import QThread, Signal, QObject, Slot
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import String, Bool, UInt8MultiArray
from cv_bridge import CvBridge
import cv2
import os
from openai import OpenAI
from PySide6.QtGui import QImage
import json
from typing import List, Optional
from .config import Setting
import paho.mqtt.client as mqtt
import time
from datetime import datetime
import re


class DisplayNode(Node, QObject):
    data_updated = Signal(list)
    image_updated = Signal(QImage)
    reason_flag = Signal()
    recommend_updated = Signal(str)
    tongue_health_updated = Signal(str)
    food_recognition_updated = Signal(str)

    def __init__(self, name: str):
        """初始化显示节点并建立 ROS、LLM 与 MQTT 通道。"""
        Node.__init__(self, node_name=name)  # 先初始化 Node
        QObject.__init__(self)
        self.cv_bridge: CvBridge = CvBridge()
        self.image_temp: Optional[np.ndarray] = None
        self.get_logger().info("DisplayNode started")
        self.clients_sql = self.create_client(SQLOperation, "/sql_operation")
        self.timer = self.create_timer(1, self.timer_callback)
        self.subscriptions_image = self.create_subscription(
            CompressedImage, "/image", callback=self.ImageCallback, qos_profile=10
        )
        self.publishers_vlm_image_ = self.create_publisher(
            Image, "/vlm_image_topic", qos_profile=10
        )
        self.publishers_vlm_text_ = self.create_publisher(
            String, "/prompt_text", qos_profile=10
        )
        self.publishers_qdriver_control_ = self.create_publisher(
            Bool, "Qdriver/control", qos_profile=10
        )
        self.publishers_uart_data_ = self.create_publisher(
            UInt8MultiArray, "/uart/data", qos_profile=10
        )
        self.ingredient = [["", -1, [], []] for _ in range(9)]
        self.LLM_server = OpenAI(
            api_key=Setting.API_KEY.value,
            base_url=Setting.BASE_URL.value,
        )
        self.Ton_server = mqtt.Client()
        self.init_mqtt_connect()
        self.init_threads()

    @Slot(bool)
    def PublishQdriverControl(self, enabled: bool):
        """发布 Qdriver 启停控制指令。

        Args:
            enabled: `True` 表示启用，`False` 表示关闭。
        """
        msg = Bool()
        msg.data = bool(enabled)
        self.publishers_qdriver_control_.publish(msg)
        self.get_logger().info(
            f"已发布 Qdriver/control: {'true' if msg.data else 'false'}"
        )

    @Slot()
    def PublishStandbyUart(self):
        """向 MCU 发送待机指令包（功能码 `0xB2`）。"""
        self._publish_uart_packet(0xB2, [])

    def _publish_location_hint_uart(self, location: int):
        """向 MCU 发送位置提示指令。

        Args:
            location: UI 九宫格位置（1-9）。
        """
        mcu_location = self._map_ui_location_to_mcu_hint(location)
        if mcu_location is None:
            self.get_logger().warn(f"位置 {location} 无法映射到 MCU 冰箱编号，跳过 B0")
            return
        self._publish_uart_packet(0xB0, [mcu_location])

    def _publish_all_expiry_uart(self):
        """向 MCU 下发全部有效食材的保质期数据。"""
        payload = self._build_expiry_payload()
        self._publish_uart_packet(0xB1, payload)

    def _publish_uart_packet(self, func_code: int, payload: List[int]):
        """发布串口透传消息到 `/uart/data`。

        Args:
            func_code: 串口协议功能码。
            payload: 功能码后的数据字段（按 `uint8` 发送）。
        """
        msg = UInt8MultiArray()
        msg.data = [self._to_uint8(func_code)]
        msg.data.extend(self._to_uint8(item) for item in payload)
        self.publishers_uart_data_.publish(msg)
        self.get_logger().info(
            f"已发布 /uart/data: func=0x{func_code:02X}, payload={payload}"
        )

    def _build_expiry_payload(self) -> List[int]:
        """构建 MCU 保质期上报负载。

        Returns:
            长度为 7 的保质期数组，索引与 MCU 冰箱格映射一致。
        """
        payload = [0] * 7
        for idx, item in enumerate(self.ingredient, start=1):
            mapped_location = self._map_ui_location_to_mcu_expiry(idx)
            if mapped_location is None:
                continue

            expiry = item[1] if isinstance(item[1], int) else -1
            if expiry >= 0:
                payload[mapped_location - 1] = self._clamp_expiry_days(expiry)

        return payload

    def _map_ui_location_to_mcu_hint(self, location: int) -> Optional[int]:
        """将 UI 位置映射为 MCU 的提示位置编号。

        Args:
            location: UI 九宫格位置（1-9）。

        Returns:
            MCU 位置编号；无法映射时返回 `None`。
        """
        return {
            1: 1,
            2: 2,
            3: 3,
            4: 6,
            5: 5,
            6: 4,
            7: 7,
            8: 7,
            9: 7,
        }.get(location)

    def _map_ui_location_to_mcu_expiry(self, location: int) -> Optional[int]:
        """将 UI 位置映射为 MCU 保质期字段编号。

        Args:
            location: UI 九宫格位置（1-9）。

        Returns:
            MCU 字段编号；`B1` 仅支持 1-7，超出返回 `None`。
        """
        # B1 only has seven expiry fields; UI slots after 7 are intentionally ignored.
        return {
            1: 1,
            2: 2,
            3: 3,
            4: 6,
            5: 5,
            6: 4,
            7: 7,
        }.get(location)

    def _clamp_expiry_days(self, expiry_days: int) -> int:
        """将保质期天数限制到协议允许范围。"""
        return max(0, min(20, int(expiry_days)))

    def _to_uint8(self, value: int) -> int:
        """将整数收敛到 `uint8` 范围。"""
        return max(0, min(255, int(value)))

    def init_threads(self):
        """初始化任务并发控制所需的锁与状态变量。"""
        self._image_lock = threading.Lock()
        self._reasoning_lock = threading.Lock()
        self._reasoning_in_progress = False
        self._reasoning_thread = None
        self._reasoning_epoch = 0

        self._recommend_lock = threading.Lock()
        self._recommend_thread = None
        self._recommend_in_progress = False
        self._recommend_epoch = 0
        self._tongue_lock = threading.Lock()
        self._tongue_thread = None
        self._tongue_in_progress = False
        self._tongue_epoch = 0
        self._tongue_waiting_result = False
        self._tongue_ignore_result_count = 0
        self._location_lock = threading.Lock()
        self._location_cursor = 1
        self._inventory_refresh_lock = threading.Lock()
        self._inventory_refresh_epoch = 0
        self._inventory_refresh_pending = 0

    def init_mqtt_connect(self):
        """初始化 MQTT 连接并注册舌诊结果回调。"""
        def on_connect(client, userdata, flags, reason_code, properties=None):
            """MQTT 连接成功回调：订阅舌诊结果主题。"""
            self.get_logger().info(f"[*] 已连接到 Broker")
            client.subscribe(Setting.TOPIC_RECEIVE.value)
            self.get_logger().info(
                f"[*] 已订阅话题: {Setting.TOPIC_RECEIVE.value}，等待 AI 回复..."
            )

        def on_message(client, userdata, msg):
            """MQTT 消息回调：处理舌诊结果负载。"""
            self.get_logger().info(f"[√] 收到来自 {msg.topic} 的舌诊推送")
            self._handle_tongue_result_message(msg.payload)

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
        """接收压缩图像并更新界面显示缓存。

        Args:
            msg: ROS 压缩图像消息。
        """
        cv_image = self.cv_bridge.compressed_imgmsg_to_cv2(msg)
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        with self._image_lock:
            self.image_temp = rgb_image.copy()
        h, w, ch = rgb_image.shape
        qimage = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.image_updated.emit(qimage.copy())

    def timer_callback(self):
        """定时刷新库存数据，并在一轮结束后同步到界面和 MCU。"""
        if not self.clients_sql.wait_for_service(0.5):
            self.get_logger().warn("服务 /sql_operation 未上线，跳过本轮库存刷新")
            return

        with self._inventory_refresh_lock:
            if self._inventory_refresh_pending > 0:
                return

            self._inventory_refresh_epoch += 1
            refresh_epoch = self._inventory_refresh_epoch
            self._inventory_refresh_pending = 9

        for location in range(1, 10):
            self.SqlOpSend_(location, self.SymCallback_, refresh_epoch)

    def SqlOpSend_(self, location: int, callback, refresh_epoch: Optional[int] = None):
        """发起单格库存查询异步请求。

        Args:
            location: 查询位置（1-9）。
            callback: 请求完成后的回调函数。
            refresh_epoch: 当前刷新轮次标识；为空表示不参与轮次管理。
        """
        try:
            request = SQLOperation.Request()
            request.operation = 4
            request.location = location
            future = self.clients_sql.call_async(request)
            future.add_done_callback(
                lambda fut, epoch=refresh_epoch: callback(fut, epoch)
            )
        except Exception as e:
            self.get_logger().warn(f"查询位置 {location} 失败: {e}")
            if refresh_epoch is not None:
                self._finish_inventory_refresh_slot(refresh_epoch)

    def SymCallback_(self, future, refresh_epoch: Optional[int] = None):
        """处理库存查询返回并更新对应格位缓存。

        Args:
            future: 异步服务调用句柄。
            refresh_epoch: 刷新轮次标识，用于过滤过期结果。
        """
        try:
            if refresh_epoch is not None and not self._is_current_inventory_refresh(
                refresh_epoch
            ):
                return

            response = future.result()
            if 1 <= response.location <= 9:
                idx = response.location - 1
                if response.is_success:
                    self.ingredient[idx] = [
                        response.name,
                        response.expiry_date,
                        [response.nutritional_info],
                        [response.notes],
                    ]
                else:
                    self.ingredient[idx] = ["", -1, [], []]
        except Exception as e:
            self.get_logger().error(f"Service call failed: {e}")
        finally:
            if refresh_epoch is not None:
                self._finish_inventory_refresh_slot(refresh_epoch)

    def _is_current_inventory_refresh(self, refresh_epoch: int) -> bool:
        """判断给定轮次是否仍为当前库存刷新轮次。"""
        with self._inventory_refresh_lock:
            return refresh_epoch == self._inventory_refresh_epoch

    def _finish_inventory_refresh_slot(self, refresh_epoch: int):
        """标记一个库存格位刷新结束，并在整轮完成后触发发布。

        Args:
            refresh_epoch: 刷新轮次标识。
        """
        should_publish = False
        with self._inventory_refresh_lock:
            if refresh_epoch != self._inventory_refresh_epoch:
                return

            self._inventory_refresh_pending -= 1
            if self._inventory_refresh_pending <= 0:
                self._inventory_refresh_pending = 0
                should_publish = True

        if should_publish:
            self.data_updated.emit(self.ingredient[:])
            self._publish_all_expiry_uart()

    @Slot()
    def StartReasoning(self):
        """启动一次食材识别任务（含位置分配与状态提示）。"""
        with self._image_lock:
            if self.image_temp is None:
                self.get_logger().warn("暂无可识别图像，已跳过本次识别")
                return
            image_snapshot = self.image_temp.copy()

        with self._reasoning_lock:
            if self._reasoning_in_progress:
                self.get_logger().info("识别任务仍在进行中，忽略重复触发")
                return
            self._reasoning_in_progress = True
            self._reasoning_epoch += 1
            task_epoch = self._reasoning_epoch

        try:
            location = self._allocate_location()
        except Exception as e:
            with self._reasoning_lock:
                if self._reasoning_epoch == task_epoch:
                    self._reasoning_in_progress = False
            err_text = f"无法为本次识别分配位置：{e}"
            self.get_logger().error(err_text)
            self.food_recognition_updated.emit(err_text)
            return

        if not self._is_reasoning_active_epoch(task_epoch):
            return

        self.food_recognition_updated.emit(
            self._format_food_recognition_pending_text(location)
        )
        self._publish_location_hint_uart(location)

        self._reasoning_thread = threading.Thread(
            target=self._run_reasoning_task,
            args=(image_snapshot, location, task_epoch),
            daemon=True,
            name="food-reasoning",
        )
        self._reasoning_thread.start()

    @Slot()
    def StartRecommend(self):
        """启动一次营养与菜谱推荐任务。"""
        with self._recommend_lock:
            if self._recommend_in_progress:
                self.get_logger().info("推荐任务仍在进行中，忽略重复触发")
                return
            self._recommend_in_progress = True
            self._recommend_epoch += 1
            task_epoch = self._recommend_epoch

        self._recommend_thread = threading.Thread(
            target=self._run_recommend_task,
            args=(task_epoch,),
            daemon=True,
            name="food-recommend",
        )
        self._recommend_thread.start()

    @Slot()
    def StartTongueDiagnosis(self):
        """启动一次舌诊任务并等待 MQTT 结果回传。"""
        with self._image_lock:
            if self.image_temp is None:
                self.tongue_health_updated.emit("暂无可用于舌诊的图像，请先调整摄像头画面。")
                self.get_logger().warn("暂无可用于舌诊的图像")
                return
            image_snapshot = self.image_temp.copy()

        with self._tongue_lock:
            if self._tongue_in_progress:
                self.get_logger().info("舌诊任务仍在进行中，忽略重复触发")
                return
            self._tongue_in_progress = True
            self._tongue_waiting_result = False
            self._tongue_epoch += 1
            task_epoch = self._tongue_epoch

        self._tongue_thread = threading.Thread(
            target=self._run_tongue_task,
            args=(image_snapshot, task_epoch),
            daemon=True,
            name="tongue-diagnosis",
        )
        self._tongue_thread.start()

    @Slot()
    def CancelReasoning(self):
        """取消当前食材识别等待，后续同轮结果将忽略。"""
        with self._reasoning_lock:
            if not self._reasoning_in_progress:
                return
            self._reasoning_epoch += 1
            self._reasoning_in_progress = False
        self.get_logger().info("已取消食材识别等待，后续结果将忽略")

    @Slot()
    def CancelRecommend(self):
        """取消当前推荐等待，后续同轮结果将忽略。"""
        with self._recommend_lock:
            if not self._recommend_in_progress:
                return
            self._recommend_epoch += 1
            self._recommend_in_progress = False
        self.get_logger().info("已取消推荐等待，后续结果将忽略")

    @Slot()
    def CancelTongueDiagnosis(self):
        """取消当前舌诊等待，必要时忽略下一条结果消息。"""
        with self._tongue_lock:
            if not self._tongue_in_progress:
                return
            if self._tongue_waiting_result:
                self._tongue_ignore_result_count += 1
            self._tongue_epoch += 1
            self._tongue_in_progress = False
            self._tongue_waiting_result = False
        self.get_logger().info("已取消舌诊等待，后续结果将忽略")

    def _is_reasoning_active_epoch(self, epoch: int) -> bool:
        """判断食材识别轮次是否仍有效。"""
        with self._reasoning_lock:
            return self._reasoning_in_progress and self._reasoning_epoch == epoch

    def _is_recommend_active_epoch(self, epoch: int) -> bool:
        """判断推荐任务轮次是否仍有效。"""
        with self._recommend_lock:
            return self._recommend_in_progress and self._recommend_epoch == epoch

    def _is_tongue_active_epoch(self, epoch: int) -> bool:
        """判断舌诊任务轮次是否仍有效。"""
        with self._tongue_lock:
            return self._tongue_in_progress and self._tongue_epoch == epoch

    def _run_recommend_task(self, task_epoch: int):
        """后台执行推荐请求并回传文本结果。

        Args:
            task_epoch: 当前任务轮次标识。
        """
        try:
            result = self._request_recommend_result()
            if not self._is_recommend_active_epoch(task_epoch):
                return

            if result is None:
                self.recommend_updated.emit("暂未生成推荐，请稍后再试。")
                return

            self.recommend_updated.emit(self._format_recommend_result_text(result))
        except Exception as e:
            self.get_logger().error(f"推荐任务执行失败:{e}")
            if self._is_recommend_active_epoch(task_epoch):
                self.recommend_updated.emit("推荐任务执行失败，请稍后再试。")
        finally:
            with self._recommend_lock:
                if self._recommend_epoch == task_epoch:
                    self._recommend_in_progress = False

    def _run_tongue_task(self, image: np.ndarray, task_epoch: int):
        """后台执行舌诊图片发送流程。

        Args:
            image: 待发送的 RGB 图像。
            task_epoch: 当前任务轮次标识。
        """
        try:
            self._publish_tongue_image(image)
            if not self._is_tongue_active_epoch(task_epoch):
                return
            with self._tongue_lock:
                if self._tongue_epoch == task_epoch:
                    self._tongue_waiting_result = True
            self.tongue_health_updated.emit("舌诊图片已发送，正在等待健康检测结果......")
        except Exception as e:
            self.get_logger().error(f"舌诊任务执行失败:{e}")
            if self._is_tongue_active_epoch(task_epoch):
                self.tongue_health_updated.emit("健康检测发送失败，请稍后重试。")
            with self._tongue_lock:
                if self._tongue_epoch == task_epoch:
                    self._tongue_in_progress = False
                    self._tongue_waiting_result = False

    def _run_reasoning_task(self, image: np.ndarray, location: int, task_epoch: int):
        """后台执行食材识别与结果写库流程。

        Args:
            image: 待识别图像。
            location: 预分配冰箱位置。
            task_epoch: 当前任务轮次标识。
        """
        submitted = False
        try:
            result = self._request_reasoning_result(image)
            if not self._is_reasoning_active_epoch(task_epoch):
                return

            if result is None:
                self.food_recognition_updated.emit(
                    self._format_food_recognition_error_text(
                        location, "AI 推理失败，请稍后重试。"
                    )
                )
                return

            submitted = self._submit_reasoning_result(result, location, task_epoch)
        except Exception as e:
            self.get_logger().error(f"识别任务执行失败:{e}")
            if self._is_reasoning_active_epoch(task_epoch):
                error_text = (
                    "服务器过载"
                    if self._is_server_overloaded_error(e)
                    else "识别任务执行失败，请稍后再试。"
                )
                self.food_recognition_updated.emit(
                    self._format_food_recognition_error_text(
                        location, error_text
                    )
                )
        finally:
            with self._reasoning_lock:
                if (not submitted) and self._reasoning_epoch == task_epoch:
                    self._reasoning_in_progress = False

    def _is_server_overloaded_error(self, error: Exception) -> bool:
        """判断异常是否属于服务过载类错误（如 429）。"""
        status_code = getattr(error, "status_code", None)
        if status_code == 429:
            return True

        message = str(error).lower()
        return (
            " 429 " in f" {message} "
            or "error code: 429" in message
            or "temporarily overloaded" in message
            or "service may be temporarily overloaded" in message
            or "'code': '1305'" in message
            or '"code": "1305"' in message
        )

    def _submit_reasoning_result(self, result: dict, location: int, task_epoch: int):
        """提交识别结果到数据库服务。

        Args:
            result: 食材识别结构化结果。
            location: 写入位置。
            task_epoch: 当前任务轮次标识。

        Returns:
            `True` 表示请求已成功提交，`False` 表示轮次失效未提交。
        """
        if not self._is_reasoning_active_epoch(task_epoch):
            return False

        request = SQLOperation.Request()
        request.operation = 1
        request.name = result["名字"]
        request.expiry_date = int(result["保质期"])
        request.nutritional_info = result["营养价值"]
        request.notes = result["食用建议"]
        request.location = location

        future = self.clients_sql.call_async(request)
        future.add_done_callback(self.SymCallback_)
        future.add_done_callback(
            lambda fut, result_snapshot=dict(result), slot=location, epoch=task_epoch: self._food_submit_callback(
                fut, result_snapshot, slot, epoch
            )
        )
        self.get_logger().info(
            f"识别完成，已提交食材信息: {request.name}, location={request.location}"
        )
        return True

    def _food_submit_callback(self, future, result: dict, location: int, task_epoch: int):
        """处理食材识别写库回调并更新前端提示。

        Args:
            future: 写库异步调用句柄。
            result: 识别结果快照。
            location: 写入位置。
            task_epoch: 当前任务轮次标识。
        """
        try:
            if not self._is_reasoning_active_epoch(task_epoch):
                return

            response = future.result()
            if not response.is_success:
                self.food_recognition_updated.emit(
                    self._format_food_recognition_error_text(
                        location, "食材识别已完成，但写入数据库失败，请稍后重试。"
                    )
                )
                return

            self.food_recognition_updated.emit(
                self._format_food_recognition_text(result, location)
            )
        except Exception as e:
            self.get_logger().error(f"食材识别结果回调失败:{e}")
            self.food_recognition_updated.emit(
                self._format_food_recognition_error_text(
                    location, "食材识别已完成，但结果提示生成失败。"
                )
            )
        finally:
            with self._reasoning_lock:
                if self._reasoning_epoch == task_epoch:
                    self._reasoning_in_progress = False

    def _format_location_text(self, location: int) -> str:
        """将位置编号格式化为带行列信息的中文描述。"""
        row = ((location - 1) // 3) + 1
        col = ((location - 1) % 3) + 1
        return f"推荐放置位置：第 {location} 格（第 {row} 行，第 {col} 列）"

    def _format_food_recognition_pending_text(self, location: int) -> str:
        """生成食材识别进行中的界面提示文案。"""
        return (
            f"{self._format_location_text(location)}\n\n"
            "AI 正在推理中，请稍等..."
        )

    def _format_food_recognition_error_text(self, location: int, error_text: str) -> str:
        """生成食材识别失败的界面提示文案。"""
        return (
            f"{self._format_location_text(location)}\n\n"
            f"{error_text}"
        )

    def _format_food_recognition_text(self, result: dict, location: int) -> str:
        """生成食材识别成功的界面提示文案。"""
        name = str(result.get("名字", "未识别")).strip()
        expiry = str(result.get("保质期", "未识别")).strip()
        nutrition = str(result.get("营养价值", "未识别")).strip()
        notes = str(result.get("食用建议", "未识别")).strip()

        return (
            f"{self._format_location_text(location)}\n\n"
            f"识别完成：{name}\n"
            f"保质期：{expiry} 天\n"
            f"营养价值：{nutrition}\n"
            f"食用建议：{notes}"
        )

    def _refresh_ingredient_slots_from_db(self):
        """同步读取 1-9 号格位并刷新本地食材缓存。"""
        for location in range(1, 10):
            response = self._query_slot_by_location(location)
            if response is None:
                continue

            idx = location - 1
            if response.is_success:
                self.ingredient[idx] = [
                    response.name,
                    response.expiry_date,
                    [response.nutritional_info],
                    [response.notes],
                ]
            else:
                self.ingredient[idx] = ["", -1, [], []]

    def _query_slot_by_location(self, location: int):
        """按位置查询库存槽位数据。

        Args:
            location: 待查询位置（1-9）。

        Returns:
            查询成功返回服务响应对象；失败或超时返回 `None`。
        """
        if not self.clients_sql.wait_for_service(0.5):
            self.get_logger().warn(f"服务 /sql_operation 未上线,location={location}")
            return None

        request = SQLOperation.Request()
        request.operation = 4
        request.location = location
        future = self.clients_sql.call_async(request)

        timeout = time.time() + 1.5
        while not future.done() and time.time() < timeout:
            time.sleep(0.05)

        if not future.done():
            self.get_logger().warn(f"查询位置 {location} 超时")
            return None

        try:
            return future.result()
        except Exception as e:
            self.get_logger().error(f"查询位置 {location} 失败: {e}")
            return None

    def _allocate_location(self) -> int:
        """按游标轮转策略分配一个空闲格位。

        Returns:
            可用位置编号（1-9）。

        Raises:
            RuntimeError: 当九宫格已满时抛出异常。
        """
        with self._location_lock:
            empty_locations = []
            for idx, item in enumerate(self.ingredient, start=1):
                name = item[0].strip() if isinstance(item[0], str) else ""
                if not name:
                    empty_locations.append(idx)

            if not empty_locations:
                raise RuntimeError("九宫格位置已满，无法为新食材分配存储位置")

            for offset in range(9):
                candidate = ((self._location_cursor - 1 + offset) % 9) + 1
                if candidate in empty_locations:
                    self._location_cursor = (candidate % 9) + 1
                    return candidate

            chosen = empty_locations[0]
            self._location_cursor = (chosen % 9) + 1
            return chosen

    def _publish_tongue_image(self, image: np.ndarray):
        """将舌诊图像编码后发布到 MQTT 主题。

        Args:
            image: 待发送图像（RGB/BGR ndarray）。

        Raises:
            ValueError: 图像编码失败。
            RuntimeError: MQTT 发布失败。
        """
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        success, encoded = cv2.imencode(".jpg", image, encode_param)
        if not success:
            raise ValueError("舌诊图片编码失败")

        result = self.Ton_server.publish(
            Setting.TOPIC_SEND.value, payload=encoded.tobytes(), qos=0
        )
        result.wait_for_publish()
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT 发布失败，错误码: {result.rc}")

        self.get_logger().info(
            f"[*] 已将舌诊图像发送到 {Setting.TOPIC_SEND.value}，record_id={Setting.TONGUE_RECORD_ID.value}"
        )

    def _request_reasoning_result(self, image: np.ndarray):
        """调用视觉大模型获取食材识别结果。

        Args:
            image: 待识别图像。

        Returns:
            解析成功返回结果字典，失败返回 `None`。
        """
        system_prompt = """你是一个严格的食物分析助手。
        请严格只返回以下JSON格式,不要添加任何其他文字、解释或markdown:
        {
        "名字": "取常见食物名字，不要加修饰",
        "营养价值": "20个字以上",
        "食用建议": "20个字以上",
        "保质期": "假设今天放入这种食物，保质期大概为几天，单位为天,数据类型为int"
        }"""

        image_base64 = self.encode_opencv_image(image, format=".jpg", quality=85)

        response = self.LLM_server.chat.completions.create(
            model="gpt-5.5",  # 推荐快速模型
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
            max_tokens=4000,
            temperature=0.1,
        )

        try:
            raw_content = self._extract_message_content(response)
            if raw_content is None:
                self.get_logger().warn("模型未返回有效内容")
                return None

            result = self._parse_json_response(raw_content)
            result["保质期"] = int(result["保质期"])
            return result
        except Exception as e:
            self.get_logger().error(f"JSON 解析失败:{e}")
            return
        return None

    def _request_recommend_result(self):
        """调用大模型生成营养概括与菜谱推荐。

        Returns:
            推荐结果字典；无可用数据或失败时返回 `None`。
        """
        inventory_summary = self._build_inventory_summary()
        if inventory_summary == "当前冰箱中暂无可用食材数据。":
            self.get_logger().warn("暂无库存数据，无法生成推荐")
            return None

        current_context = self._build_hangzhou_context()
        health_guidance = self._build_health_diet_guidance()

        system_prompt = """你是一个严格的厨房营养与食谱推荐助手。
        请严格只返回以下JSON格式,不要添加任何其他文字、解释或markdown:
        {
        "近几天的营养状况概括": "如果没在传给你的数据里看到就说“未查询到”",
        "推荐食谱1": "根据冰箱里有的食材的基础，和当前的浙江杭州的节气环境温湿度，给出食谱，可以适当添加冰箱里未有的食材，但是要写明哪些没有需要购买",
        "推荐食谱2": "根据冰箱里有的食材的基础，和当前的浙江杭州的节气环境温湿度，给出食谱，可以适当添加冰箱里未有的食材，但是要写明哪些没有需要购买"
        }"""
        self.get_logger().info(f"{inventory_summary}\n\n\n{current_context}")
        response = self.LLM_server.chat.completions.create(
            model="gpt-5.5",  # 推荐快速模型
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"{current_context}\n"
                                "以下是基于健康状态整理的饮食关注点，请作为推荐的辅助参考。\n"
                                f"{health_guidance}\n"
                                "以下是冰箱中的现有食材信息，请结合这些内容给出推荐。\n"
                                f"{inventory_summary}\n"
                                "要求：\n"
                                "1. 优先使用已有且临近保质期的食材。\n"
                                "2. 推荐内容要明确哪些食材需要额外购买。\n"
                                "3. 近几天营养概括只能基于提供的数据，不要虚构体检或摄入记录。\n"
                                "4. 健康检测信息只能作为生活方式参考，不要输出医疗确诊表述。"
                            ),
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=4000,
            temperature=0.1,
        )

        try:
            raw_content = self._extract_message_content(response)
            if raw_content is None:
                self.get_logger().warn("模型未返回有效内容")
                return None

            result = self._parse_json_response(raw_content)
            nutrition_summary = str(result.get("近几天的营养状况概括", "")).strip()
            if (not nutrition_summary) or (nutrition_summary == "未查询到"):
                fallback_summary = self._resolve_nutrition_summary_with_health(
                    health_guidance
                )
                if fallback_summary != "未查询到":
                    result["近几天的营养状况概括"] = fallback_summary
                    self.get_logger().info(
                        "模型返回营养概括缺失，已使用健康检测摘要兜底填充。"
                    )
            return result
        except Exception as e:
            fallback_text = self._extract_message_content(response)
            self.get_logger().error(f"JSON 解析失败:{e}")
            if fallback_text:
                return {
                    "近几天的营养状况概括": "模型未按 JSON 返回，以下为原始内容",
                    "推荐食谱1": fallback_text.strip(),
                    "推荐食谱2": "请检查 prompt、模型能力或 base_url 接口格式。",
                }
            return None
        return None

    def _handle_tongue_result_message(self, payload: bytes):
        """处理 MQTT 推送的舌诊结果消息。

        Args:
            payload: MQTT 二进制消息体。
        """
        with self._tongue_lock:
            if self._tongue_ignore_result_count > 0:
                self._tongue_ignore_result_count -= 1
                self._tongue_waiting_result = False
                self._tongue_in_progress = False
                self.get_logger().info("舌诊结果已按取消请求忽略")
                return

            if not self._tongue_in_progress and not self._tongue_waiting_result:
                self.get_logger().info("收到舌诊结果，但当前无等待任务，已忽略")
                return

            self._tongue_waiting_result = False

        try:
            payload_text = payload.decode("utf-8")
            result_data = json.loads(payload_text)
            formatted_text, db_record = self._format_tongue_result(result_data)
            self._submit_health_status_result(db_record)
            self.tongue_health_updated.emit(formatted_text)
        except Exception as e:
            self.get_logger().error(f"处理舌诊 MQTT 结果失败:{e}")
            self.tongue_health_updated.emit("健康检测结果解析失败，请稍后重试。")
        finally:
            with self._tongue_lock:
                self._tongue_in_progress = False

    def _format_tongue_result(self, result_data: dict):
        """格式化舌诊原始结果，并生成写库记录。

        Args:
            result_data: 舌诊服务返回的 JSON 字典。

        Returns:
            二元组 `(formatted_text, db_record)`。
        """
        code = int(result_data.get("code", -1))
        detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = result_data.get("result") or {}

        if code != 1:
            summary = self._build_tongue_error_summary(code)
            formatted_text = (
                f"健康检测时间：{detected_at}\n"
                f"检测状态：图像不合规\n"
                f"结果说明：{summary}"
            )
            db_record = {
                "detected_at": detected_at,
                "health_status": "图像不合规",
                "health_summary": summary,
                "health_raw_json": json.dumps(result_data, ensure_ascii=False),
            }
            return formatted_text, db_record

        tongue_color_code = result.get("tongue_color", "未识别")
        coating_color_code = result.get("coating_color", "未识别")
        thickness_code = result.get("thickness", "未识别")
        rot_greasy_code = result.get("rot_greasy", "未识别")

        tongue_color = self._map_tongue_feature("tongue_color", tongue_color_code)
        coating_color = self._map_tongue_feature("coating_color", coating_color_code)
        thickness = self._map_tongue_feature("thickness", thickness_code)
        rot_greasy = self._map_tongue_feature("rot_greasy", rot_greasy_code)

        status = self._infer_health_status(
            tongue_color=tongue_color,
            coating_color=coating_color,
            thickness=thickness,
            rot_greasy=rot_greasy,
        )
        lifestyle_tip = self._build_health_lifestyle_tip(
            tongue_color=tongue_color,
            coating_color=coating_color,
            thickness=thickness,
            rot_greasy=rot_greasy,
        )
        summary = (
            f"舌色为{tongue_color}；舌苔颜色为{coating_color}；厚薄表现为{thickness}；"
            f"腻腐表现为{rot_greasy}。饮食参考：{lifestyle_tip}"
        )
        formatted_text = (
            f"健康检测时间：{detected_at}\n"
            f"检测结论：{status}\n"
            f"舌色：{tongue_color}\n"
            f"苔色：{coating_color}\n"
            f"厚薄：{thickness}\n"
            f"腻腐：{rot_greasy}\n"
            f"提示：{summary}"
        )
        db_record = {
            "detected_at": detected_at,
            "health_status": status,
            "health_summary": summary,
            "health_raw_json": json.dumps(result_data, ensure_ascii=False),
        }
        return formatted_text, db_record

    def _submit_health_status_result(self, result: dict):
        """将舌诊健康摘要写入数据库。

        Args:
            result: 健康状态记录字典。
        """
        if not self.clients_sql.wait_for_service(0.5):
            self.get_logger().warn("服务 /sql_operation 未上线，无法写入健康状态")
            return

        request = SQLOperation.Request()
        request.operation = 5
        request.detected_at = result["detected_at"]
        request.health_status = result["health_status"]
        request.health_summary = result["health_summary"]
        request.health_raw_json = result["health_raw_json"]

        future = self.clients_sql.call_async(request)
        future.add_done_callback(self._health_status_callback)

    def _health_status_callback(self, future):
        """处理健康状态写库异步回调并记录日志。"""
        try:
            response = future.result()
            if response.is_success:
                self.get_logger().info(
                    f"健康状态已写入数据库，id={response.id}, status={response.health_status}"
                )
            else:
                self.get_logger().warn(f"健康状态写库失败: {response.notes}")
        except Exception as e:
            self.get_logger().error(f"健康状态写库回调失败:{e}")

    def _query_recent_health_status(self, limit: int = 5):
        """查询最近健康状态历史。

        Args:
            limit: 最多返回的历史记录条数。

        Returns:
            健康历史列表；失败时返回空列表。
        """
        if not self.clients_sql.wait_for_service(0.5):
            self.get_logger().warn("服务 /sql_operation 未上线，无法查询健康状态")
            return []

        request = SQLOperation.Request()
        request.operation = 6
        request.query_limit = max(1, int(limit))
        future = self.clients_sql.call_async(request)

        timeout = time.time() + 3.0
        while not future.done() and time.time() < timeout:
            time.sleep(0.05)

        if not future.done():
            self.get_logger().warn("查询健康状态超时")
            return []

        try:
            response = future.result()
            if response is None:
                return []
            
            if not response.is_success:
                return []

            history_json = response.health_history_json.strip()
            if not history_json:
                return []
            return json.loads(history_json)
        except Exception as e:
            self.get_logger().error(f"解析健康状态历史失败:{e}")
            return []

    def _build_tongue_error_summary(self, code: int) -> str:
        """将舌诊错误码映射为可读提示文本。"""
        error_map = {
            201: "图片不符合采集要求，请确保舌头完整、清晰并位于画面中心。",
            202: "图片质量不足，请改善光线或重新拍摄后再试。",
        }
        return error_map.get(code, f"检测服务返回异常状态码 {code}。")

    def _infer_health_status(
        self, tongue_color: str, coating_color: str, thickness: str, rot_greasy: str
    ) -> str:
        """基于舌象要素推断健康状态标签。"""
        risk_tokens = ["青紫", "灰黑", "黄苔", "厚", "腻", "腐", "绛"]
        stable_tokens = ["淡红", "红舌", "白苔", "薄"]

        joined = f"{tongue_color}|{coating_color}|{thickness}|{rot_greasy}"
        if any(token in joined for token in risk_tokens):
            return "舌象需关注"
        if any(token in joined for token in stable_tokens):
            return "舌象相对平和"
        return "舌象有待复查"

    def _map_tongue_feature(self, field: str, value) -> str:
        """将舌诊特征编码转换为中文描述。

        Args:
            field: 特征字段名。
            value: 原始编码值。

        Returns:
            归一化后的中文描述文本。
        """
        mapping = {
            "tongue_color": {
                0: "淡白舌",
                1: "淡红舌",
                2: "红舌",
                3: "绛舌",
                4: "青紫舌",
            },
            "coating_color": {
                0: "白苔",
                1: "黄苔",
                2: "灰黑苔",
            },
            "thickness": {
                0: "舌苔偏薄",
                1: "舌苔偏厚",
            },
            "rot_greasy": {
                0: "舌苔腻",
                1: "舌苔腐",
            },
        }

        if field not in mapping:
            return str(value).strip() if str(value).strip() else "未识别"

        code = self._normalize_tongue_code(value)
        if code is None:
            text = str(value).strip()
            return text if text else "未识别"
        return mapping[field].get(code, f"未知编码({code})")

    def _normalize_tongue_code(self, value) -> Optional[int]:
        """将舌诊特征值归一化为整数编码。

        Args:
            value: 原始输入值。

        Returns:
            可解析时返回整数，否则返回 `None`。
        """
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)

        text = str(value).strip()
        if not text:
            return None
        if re.fullmatch(r"-?\d+", text):
            return int(text)
        return None

    def _build_health_lifestyle_tip(
        self, tongue_color: str, coating_color: str, thickness: str, rot_greasy: str
    ) -> str:
        """依据舌象信息生成温和饮食与生活方式建议。"""
        tips = []
        joined = f"{tongue_color}|{coating_color}|{thickness}|{rot_greasy}"

        if "黄苔" in joined or "灰黑苔" in joined:
            tips.append("近期饮食宜清淡，少辛辣油炸，多补充水分")
        if "舌苔偏厚" in joined or "舌苔腻" in joined or "舌苔腐" in joined:
            tips.append("可优先选择易消化、少油腻的食物，减轻饮食负担")
        if "淡白舌" in joined:
            tips.append("可适当搭配温和且含优质蛋白的食材")
        if "青紫舌" in joined or "绛舌" in joined:
            tips.append("避免过度辛燥刺激，饮食以平衡温和为主")

        if not tips:
            tips.append("整体饮食以规律、清爽、均衡搭配为主")
        return "；".join(tips)

    def _format_health_history_item(self, item: dict) -> str:
        """格式化单条健康历史记录为摘要文本。"""
        raw = item.get("health_raw_json")
        if isinstance(raw, dict):
            result = raw.get("result") or {}
            if result:
                tongue_color = self._map_tongue_feature(
                    "tongue_color", result.get("tongue_color")
                )
                coating_color = self._map_tongue_feature(
                    "coating_color", result.get("coating_color")
                )
                thickness = self._map_tongue_feature("thickness", result.get("thickness"))
                rot_greasy = self._map_tongue_feature(
                    "rot_greasy", result.get("rot_greasy")
                )
                return (
                    f"舌色为{tongue_color}；舌苔颜色为{coating_color}；"
                    f"厚薄表现为{thickness}；腻腐表现为{rot_greasy}"
                )

        summary = str(item.get("health_summary", "未查询到")).strip()
        return summary if summary else "未查询到"

    def _build_health_diet_guidance(self) -> str:
        """汇总近期健康检测记录并生成推荐辅助上下文。"""
        history = self._query_recent_health_status(limit=3)
        if not history:
            return "暂无健康检测数据，可按均衡饮食原则推荐。"

        guidance_lines = []
        for idx, item in enumerate(history, start=1):
            summary = self._format_health_history_item(item)
            guidance_lines.append(f"{idx}. {summary}")

        latest_summary = self._format_health_history_item(history[0])
        latest_raw = history[0].get("health_raw_json")
        extra_tip = "整体以清淡均衡为主。"
        if isinstance(latest_raw, dict):
            latest_result = latest_raw.get("result") or {}
            extra_tip = self._build_health_lifestyle_tip(
                tongue_color=self._map_tongue_feature(
                    "tongue_color", latest_result.get("tongue_color")
                ),
                coating_color=self._map_tongue_feature(
                    "coating_color", latest_result.get("coating_color")
                ),
                thickness=self._map_tongue_feature(
                    "thickness", latest_result.get("thickness")
                ),
                rot_greasy=self._map_tongue_feature(
                    "rot_greasy", latest_result.get("rot_greasy")
                ),
            )

        return (
            "最近健康状态记录：\n"
            f"{chr(10).join(guidance_lines)}\n"
            f"最新一次检测摘要：{latest_summary}\n"
            f"饮食关注点：{extra_tip}"
        )

    def _resolve_nutrition_summary_with_health(self, health_guidance: str) -> str:
        """从健康指导文本中提炼营养概括兜底内容。"""
        text = str(health_guidance).strip()
        if not text or "暂无健康检测数据" in text:
            return "未查询到"

        latest_match = re.search(r"最新一次检测摘要：(.+)", text)
        latest_summary = latest_match.group(1).strip() if latest_match else ""

        tip_match = re.search(r"饮食关注点：(.+)", text)
        diet_tip = tip_match.group(1).strip() if tip_match else ""

        if latest_summary and diet_tip:
            return f"{latest_summary}；饮食关注点：{diet_tip}"
        if latest_summary:
            return latest_summary
        if diet_tip:
            return f"饮食关注点：{diet_tip}"
        return "未查询到"

    def _extract_message_content(self, response) -> Optional[str]:
        """从模型响应对象中提取纯文本内容。

        Args:
            response: 模型 SDK 返回对象。

        Returns:
            提取到的文本；不存在时返回 `None`。
        """
        try:
            message = response.choices[0].message
        except Exception:
            return None

        content = getattr(message, "content", None)
        if isinstance(content, str):
            text = content.strip()
            return text if text else None

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_value = str(item.get("text", "")).strip()
                    if text_value:
                        text_parts.append(text_value)
            if text_parts:
                return "\n".join(text_parts)

        return None

    def _parse_json_response(self, raw_content: str) -> dict:
        """从模型文本中解析 JSON 对象。

        Args:
            raw_content: 模型返回原文。

        Returns:
            解析后的字典对象。

        Raises:
            ValueError: 未能解析出合法 JSON。
        """
        text = raw_content.strip()
        if not text:
            raise ValueError("模型返回内容为空")

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fenced_match:
            return json.loads(fenced_match.group(1).strip())

        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1).strip())

        raise ValueError(f"未找到合法 JSON，原始返回: {text[:200]}")

    def _build_inventory_summary(self) -> str:
        """将当前库存缓存整理为推荐提示文本。"""
        summary_lines = []
        for idx, item in enumerate(self.ingredient, start=1):
            name = item[0].strip() if isinstance(item[0], str) else ""
            if not name:
                continue

            expiry = item[1] if isinstance(item[1], int) else -1
            nutrition = self._normalize_text_field(item[2])
            notes = self._normalize_text_field(item[3])

            summary_lines.append(
                f"{idx}. 食材: {name}; 保质期: {expiry}天; 营养信息: {nutrition}; 备注: {notes}"
            )

        if not summary_lines:
            return "当前冰箱中暂无可用食材数据。"

        return "\n".join(summary_lines)

    def _normalize_text_field(self, value) -> str:
        """归一化文本字段，统一空值显示。"""
        if isinstance(value, list):
            text_parts = [str(item).strip() for item in value if str(item).strip()]
            return "；".join(text_parts) if text_parts else "未查询到"

        if value is None:
            return "未查询到"

        text = str(value).strip()
        return text if text else "未查询到"

    def _build_hangzhou_context(self) -> str:
        """生成杭州场景下的季节气候上下文描述。"""
        now = datetime.now()
        month = now.month
        day = now.day

        if month in (3, 4):
            season = "春季"
            climate = "体感偏湿润，适合清淡、温和、少油的搭配"
        elif month in (5, 6):
            season = "初夏"
            climate = "气温逐渐升高，适合清爽、补水、易消化的搭配"
        elif month in (7, 8, 9):
            season = "夏秋之交"
            climate = "偏闷热潮湿，适合少油腻、兼顾补水与开胃"
        else:
            season = "秋冬季"
            climate = "气温偏低，可适当选择温补、带热量的搭配"

        return (
            f"当前日期: {now.strftime('%Y-%m-%d')}。"
            f"用户所在场景按浙江杭州考虑，当前按{season}的一般节气与气候特征处理，"
            f"{climate}。如未提供实时温湿度，请明确按季节经验给出建议。"
        )

    def _format_recommend_result_text(self, result: dict) -> str:
        """格式化推荐结果为前端展示文本。"""
        nutrition = str(result.get("近几天的营养状况概括", "未查询到")).strip()
        recipe1 = str(result.get("推荐食谱1", "未查询到")).strip()
        recipe2 = str(result.get("推荐食谱2", "未查询到")).strip()

        return (
            f"近几天的营养状况概括：{nutrition}\n\n"
            f"推荐食谱1：{recipe1}\n\n"
            f"推荐食谱2：{recipe2}"
        )

    def encode_opencv_image(
        self, image: np.ndarray, format: str = ".jpg", quality: int = 85
    ) -> str:
        """将 OpenCV 图像编码为 base64 字符串。

        Args:
            image: OpenCV 图像（ndarray）。
            format: 输出格式，支持 `.jpg` 或 `.png`。
            quality: JPEG 压缩质量（1-100）。

        Returns:
            base64 编码后的图像字符串。

        Raises:
            ValueError: 图像编码失败。
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
        """初始化 ROS 工作线程。

        Args:
            node: 需要在子线程中 spin 的显示节点实例。
        """
        super().__init__()
        self.node = node
        self.daemon = True

    def run(self):
        """运行 ROS 事件循环。"""
        try:
            rclpy.spin(self.node)
        except:
            rclpy.shutdown
            sys.exit(0)

    def stop(self):
        """停止 ROS 并退出进程。"""
        rclpy.shutdown
        sys.exit(0)

    def getIngredient(self):
        """返回节点当前的食材缓存列表。"""
        if len(self.node.ingredient) != 0:
            return self.node.ingredient
        pass
