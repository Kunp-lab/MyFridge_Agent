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
from typing import Optional
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
        Node.__init__(self, node_name=name)  # 先初始化 Node
        QObject.__init__(self)
        self.cv_bridge: CvBridge = CvBridge()
        self.image_temp: Optional[np.ndarray] = None
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
        self.init_threads()

    def init_threads(self):
        self._image_lock = threading.Lock()
        self._reasoning_lock = threading.Lock()
        self._reasoning_in_progress = False
        self._reasoning_thread = None

        self._recommend_lock = threading.Lock()
        self._recommend_thread = None
        self._recommend_in_progress = False
        self._tongue_lock = threading.Lock()
        self._tongue_thread = None
        self._tongue_in_progress = False
        self._location_lock = threading.Lock()
        self._location_cursor = 1

    def init_mqtt_connect(self):
        def on_connect(client, userdata, flags, reason_code, properties=None):
            self.get_logger().info(f"[*] 已连接到 Broker")
            client.subscribe(Setting.TOPIC_RECEIVE.value)
            self.get_logger().info(
                f"[*] 已订阅话题: {Setting.TOPIC_RECEIVE.value}，等待 AI 回复..."
            )

        def on_message(client, userdata, msg):
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
        cv_image = self.cv_bridge.compressed_imgmsg_to_cv2(msg)
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        with self._image_lock:
            self.image_temp = rgb_image.copy()
        h, w, ch = rgb_image.shape
        qimage = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.image_updated.emit(qimage.copy())

    def timer_callback(self):
        for location in range(9):
            self.SqlOpSend_(location + 1, self.SymCallback_)
            self.data_updated.emit(self.ingredient[:])

    def SqlOpSend_(self, location: int, callback):
        try:
            if not self.clients_sql.wait_for_service(0.5):
                self.get_logger().warn(f"服务 /sql_operation 未上线,location={location}")
                return
            request = SQLOperation.Request()
            request.operation = 4
            request.location = location
            future = self.clients_sql.call_async(request)
            future.add_done_callback(callback=callback)
        except Exception as e:
            self.get_logger().warn(f"查询位置 {location} 失败: {e}")

    def SymCallback_(self, future):
        try:
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

    @Slot()
    def StartReasoning(self):
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

        self._reasoning_thread = threading.Thread(
            target=self._run_reasoning_task,
            args=(image_snapshot,),
            daemon=True,
            name="food-reasoning",
        )
        self._reasoning_thread.start()

    @Slot()
    def StartRecommend(self):
        with self._recommend_lock:
            if self._recommend_in_progress:
                self.get_logger().info("推荐任务仍在进行中，忽略重复触发")
                return
            self._recommend_in_progress = True

        self._recommend_thread = threading.Thread(
            target=self._run_recommend_task,
            daemon=True,
            name="food-recommend",
        )
        self._recommend_thread.start()

    @Slot()
    def StartTongueDiagnosis(self):
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

        self._tongue_thread = threading.Thread(
            target=self._run_tongue_task,
            args=(image_snapshot,),
            daemon=True,
            name="tongue-diagnosis",
        )
        self._tongue_thread.start()

    def _run_recommend_task(self):
        try:
            result = self._request_recommend_result()
            if result is None:
                self.recommend_updated.emit("暂未生成推荐，请稍后再试。")
                return

            self.recommend_updated.emit(self._format_recommend_result_text(result))
        except Exception as e:
            self.get_logger().error(f"推荐任务执行失败:{e}")
            self.recommend_updated.emit("推荐任务执行失败，请稍后再试。")
        finally:
            with self._recommend_lock:
                self._recommend_in_progress = False

    def _run_tongue_task(self, image: np.ndarray):
        try:
            self._publish_tongue_image(image)
            self.tongue_health_updated.emit("舌诊图片已发送，正在等待健康检测结果......")
        except Exception as e:
            self.get_logger().error(f"舌诊任务执行失败:{e}")
            self.tongue_health_updated.emit("健康检测发送失败，请稍后重试。")
            with self._tongue_lock:
                self._tongue_in_progress = False

    def _run_reasoning_task(self, image: np.ndarray):
        try:
            result = self._request_reasoning_result(image)
            if result is None:
                return

            self._submit_reasoning_result(result)
        except Exception as e:
            self.get_logger().error(f"识别任务执行失败:{e}")
        finally:
            with self._reasoning_lock:
                self._reasoning_in_progress = False

    def _submit_reasoning_result(self, result: dict):
        self._refresh_ingredient_slots_from_db()
        location = self._allocate_location()
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
            lambda fut, result_snapshot=dict(result), slot=location: self._food_submit_callback(
                fut, result_snapshot, slot
            )
        )
        self.get_logger().info(
            f"识别完成，已提交食材信息: {request.name}, location={request.location}"
        )

    def _food_submit_callback(self, future, result: dict, location: int):
        try:
            response = future.result()
            if not response.is_success:
                self.food_recognition_updated.emit("食材识别已完成，但写入数据库失败，请稍后重试。")
                return

            self.food_recognition_updated.emit(
                self._format_food_recognition_text(result, location)
            )
        except Exception as e:
            self.get_logger().error(f"食材识别结果回调失败:{e}")
            self.food_recognition_updated.emit("食材识别已完成，但结果提示生成失败。")

    def _format_food_recognition_text(self, result: dict, location: int) -> str:
        row = ((location - 1) // 3) + 1
        col = ((location - 1) % 3) + 1
        name = str(result.get("名字", "未识别")).strip()
        expiry = str(result.get("保质期", "未识别")).strip()
        nutrition = str(result.get("营养价值", "未识别")).strip()
        notes = str(result.get("食用建议", "未识别")).strip()

        return (
            f"识别完成：{name}\n"
            f"保质期：{expiry} 天\n"
            f"营养价值：{nutrition}\n"
            f"食用建议：{notes}\n"
            f"推荐放置位置：第 {location} 格（第 {row} 行，第 {col} 列）"
        )

    def _refresh_ingredient_slots_from_db(self):
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
        inventory_summary = self._build_inventory_summary()
        if inventory_summary == "当前冰箱中暂无可用食材数据。":
            self.get_logger().warn("暂无库存数据，无法生成推荐")
            return None

        current_context = self._build_hangzhou_context()
        health_summary = self._build_recent_health_summary()

        system_prompt = """你是一个严格的厨房营养与食谱推荐助手。
        请严格只返回以下JSON格式,不要添加任何其他文字、解释或markdown:
        {
        "近几天的营养状况概括": "如果没在传给你的数据里看到就说“未查询到”",
        "推荐食谱1": "根据冰箱里有的食材的基础，和当前的浙江杭州的节气环境温湿度，给出食谱，可以适当添加冰箱里未有的食材，但是要写明哪些没有需要购买",
        "推荐食谱2": "根据冰箱里有的食材的基础，和当前的浙江杭州的节气环境温湿度，给出食谱，可以适当添加冰箱里未有的食材，但是要写明哪些没有需要购买"
        }"""
        self.get_logger().info(f"{inventory_summary}\n\n\n{current_context}")
        response = self.LLM_server.chat.completions.create(
            model="glm-4.6v",  # 推荐快速模型
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"{current_context}\n"
                                "以下是用户最近几次健康检测摘要，请仅基于提供内容酌情参考，不要夸大为医疗诊断。\n"
                                f"{health_summary}\n"
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

        tongue_color = str(result.get("tongue_color", "未识别")).strip()
        coating_color = str(result.get("coating_color", "未识别")).strip()
        thickness = str(result.get("thickness", "未识别")).strip()
        rot_greasy = str(result.get("rot_greasy", "未识别")).strip()

        status = self._infer_health_status(
            tongue_color=tongue_color,
            coating_color=coating_color,
            thickness=thickness,
            rot_greasy=rot_greasy,
        )
        summary = (
            f"舌色{tongue_color}；舌苔{coating_color}；厚薄表现为{thickness}；"
            f"腻腐表现为{rot_greasy}。"
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
            if not response.is_success:
                return []

            history_json = response.health_history_json.strip()
            if not history_json:
                return []
            return json.loads(history_json)
        except Exception as e:
            self.get_logger().error(f"解析健康状态历史失败:{e}")
            return []

    def _build_recent_health_summary(self) -> str:
        history = self._query_recent_health_status(limit=5)
        if not history:
            return "最近暂无健康检测记录。"

        lines = []
        for idx, item in enumerate(history, start=1):
            detected_at = str(item.get("detected_at", "未知时间")).strip()
            health_status = str(item.get("health_status", "未识别")).strip()
            health_summary = str(item.get("health_summary", "未查询到")).strip()
            lines.append(
                f"{idx}. 时间: {detected_at}; 状态: {health_status}; 摘要: {health_summary}"
            )
        return "\n".join(lines)

    def _build_tongue_error_summary(self, code: int) -> str:
        error_map = {
            201: "图片不符合采集要求，请确保舌头完整、清晰并位于画面中心。",
            202: "图片质量不足，请改善光线或重新拍摄后再试。",
        }
        return error_map.get(code, f"检测服务返回异常状态码 {code}。")

    def _infer_health_status(
        self, tongue_color: str, coating_color: str, thickness: str, rot_greasy: str
    ) -> str:
        normalized = " ".join(
            [
                tongue_color.lower(),
                coating_color.lower(),
                thickness.lower(),
                rot_greasy.lower(),
            ]
        )
        risk_tokens = ["purple", "yellow", "thick", "greasy", "腻", "腐", "dark", "black"]
        stable_tokens = ["pink", "red", "light red", "white", "thin", "normal", "none"]

        if any(token in normalized for token in risk_tokens):
            return "舌象需关注"
        if any(token in normalized for token in stable_tokens):
            return "舌象相对平和"
        return "舌象有待复查"

    def _extract_message_content(self, response) -> Optional[str]:
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
        if isinstance(value, list):
            text_parts = [str(item).strip() for item in value if str(item).strip()]
            return "；".join(text_parts) if text_parts else "未查询到"

        if value is None:
            return "未查询到"

        text = str(value).strip()
        return text if text else "未查询到"

    def _build_hangzhou_context(self) -> str:
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
