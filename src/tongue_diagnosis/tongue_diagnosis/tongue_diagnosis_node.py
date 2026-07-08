"""
Tongue Diagnosis Main Node

This node receives tongue images via ROS2, performs:
1. YOLO26 segmentation to extract tongue region
2. 4D ResNet classification (color, coating, thickness, greasiness)
3. Publishes results via ROS2 with format compatible with PC backend

Topics:
  - Subscribe: /tongue_diagnosis/input_image (sensor_msgs/CompressedImage)
  - Publish: /tongue_diagnosis/result (std_msgs/String - JSON format)
"""

import logging
import json
import sys
import os
import threading
from datetime import datetime
from typing import Dict, Optional, Any

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
from cv_bridge import CvBridge

# Import model modules
from .yolov26seg import YOLO26Seg, YOLO26SegConfig
from .resnet import ResNet, ResNetConfig


class TongueDiagnosisNode(Node):
    """
    Main node for tongue diagnosis inference on RDK X5.
    
    Responsibilities:
    - Subscribe to /tongue_diagnosis/input_image for incoming CompressedImage
    - Execute YOLO26 segmentation + 4x ResNet classification
    - Publish results to /tongue_diagnosis/result as JSON String
    """

    def __init__(self):
        super().__init__('tongue_diagnosis_node')
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="[%(name)s] [%(asctime)s.%(msecs)03d] [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        self.logger = logging.getLogger("TongueDiagnosis")
        self.cv_bridge = CvBridge()
        
        # Declare and get parameters
        self.declare_parameter('model_dir', './bin')
        self.declare_parameter('yolo_score_threshold', 0.7)
        self.declare_parameter('input_image_topic', '/tongue_diagnosis/input_image')
        self.declare_parameter('output_result_topic', '/tongue_diagnosis/result')
        
        self.model_dir = self.get_parameter('model_dir').value
        self.yolo_score_threshold = self.get_parameter('yolo_score_threshold').value
        self.input_topic = self.get_parameter('input_image_topic').value
        self.output_topic = self.get_parameter('output_result_topic').value
        
        self.get_logger().info(
            f"Initializing TongueDiagnosisNode"
        )
        self.get_logger().info(f"  Input topic: {self.input_topic}")
        self.get_logger().info(f"  Output topic: {self.output_topic}")
        
        # Initialize models
        self._init_models()
        
        # Initialize ROS2 pub/sub
        self._init_ros2_interface()

    def _init_models(self):
        """Initialize YOLO26 segmentation and 4x ResNet classification models."""
        try:
            # YOLO26 Segmentation Model
            yolo_config = YOLO26SegConfig(
                model_path=os.path.join(self.model_dir, "yolo_seg2_bayese_640x640_nv12.bin"),
                classes_num=1,
                score_thres=self.yolo_score_threshold,
                resize_type=1,
            )
            self.yolo_model = YOLO26Seg(yolo_config)
            self.get_logger().info("✅ YOLO26 segmentation model loaded")
            
            # ResNet Models for 4D classification
            self.resnet_models = {
                'tongue_color': ResNet(ResNetConfig(
                    model_path=os.path.join(self.model_dir, "tongue_color_bayese_224x224_nv12.bin"),
                    resize_type=1
                )),
                'coating_color': ResNet(ResNetConfig(
                    model_path=os.path.join(self.model_dir, "tongue_coat_color_bayese_224x224_nv12.bin"),
                    resize_type=1
                )),
                'thickness': ResNet(ResNetConfig(
                    model_path=os.path.join(self.model_dir, "thickness_bayese_224x224_nv12.bin"),
                    resize_type=1
                )),
                'rot_greasy': ResNet(ResNetConfig(
                    model_path=os.path.join(self.model_dir, "rot_and_greasy_bayese_224x224_nv12.bin"),
                    resize_type=1
                )),
            }
            self.get_logger().info("✅ ResNet classification models loaded (4x)")
            
        except Exception as e:
            self.get_logger().error(f"❌ Failed to load models: {e}")
            raise

    def _init_ros2_interface(self):
        """Initialize ROS2 publisher and subscriber."""
        # Subscriber for compressed images
        self.image_subscription = self.create_subscription(
            CompressedImage,
            self.input_topic,
            self._on_image_received,
            qos_profile=10
        )
        self.image_subscription  # Prevent unused variable warning
        self.get_logger().info(f"✅ Subscribed to {self.input_topic}")
        
        # Publisher for results
        self.result_publisher = self.create_publisher(
            String,
            self.output_topic,
            qos_profile=10
        )
        self.get_logger().info(f"✅ Publisher created for {self.output_topic}")

    def _on_image_received(self, msg: CompressedImage):
        """
        ROS2 callback when compressed image is received.
        
        Args:
            msg: CompressedImage message from display node
        """
        self.get_logger().info(f"[ROS2] Received image, size: {len(msg.data)} bytes")
        
        try:
            # Process image in background thread to avoid blocking ROS2 callbacks
            thread = threading.Thread(
                target=self._process_tongue_image,
                args=(msg.data,),
                daemon=True
            )
            thread.start()
        except Exception as e:
            self.get_logger().error(f"[ROS2] Error processing message: {e}")

    def _process_tongue_image(self, image_bytes: bytes):
        """
        Process incoming tongue image through inference pipeline.
        
        Pipeline:
        1. Decode image
        2. YOLO26 segmentation
        3. Extract masked region
        4. 4x ResNet classification
        5. Format and publish results
        """
        try:
            # Decode image
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if image is None:
                raise ValueError("Failed to decode image")
            
            self.get_logger().info(f"Image decoded: shape={image.shape}")
            
            # YOLO26 Segmentation
            xyxy, score, cls, masks = self.yolo_model.predict(image)
            
            if masks.shape[0] == 0:
                self.get_logger().warn("No tongue detected in image")
                self._publish_result(
                    record_id="unknown",
                    code=201,
                    result=None,
                    error="No tongue detected"
                )
                return
            
            # Extract masked region
            masked_image = cv2.bitwise_and(image, image, mask=masks[0].astype(np.uint8))
            self.get_logger().info(f"Tongue region extracted, mask shape={masks[0].shape}")
            
            # 4D Classification
            results = self._run_4d_classification(masked_image)
            
            # Publish results
            self._publish_result(
                record_id="user1",  # TODO: Extract from MQTT topic if available
                code=1,
                result=results
            )
            
        except Exception as e:
            self.get_logger().error(f"Error processing tongue image: {e}")
            self._publish_result(
                record_id="unknown",
                code=202,
                result=None,
                error=str(e)
            )

    def _run_4d_classification(self, masked_image: np.ndarray) -> Dict[str, int]:
        """
        Run 4D ResNet classification on masked tongue image.
        
        Returns:
            Dict with keys: tongue_color, coating_color, thickness, rot_greasy
            Each value is the predicted class index.
        """
        try:
            results = {}
            
            # Run each ResNet model
            for model_name, model in self.resnet_models.items():
                pred_result = model(masked_image)
                
                # Extract class index (models return top-k predictions)
                if isinstance(pred_result, dict):
                    class_idx = pred_result.get('top_1', [0])[0]
                elif isinstance(pred_result, (list, tuple)):
                    class_idx = int(pred_result[0]) if len(pred_result) > 0 else 0
                else:
                    class_idx = int(pred_result)
                
                results[model_name] = class_idx
                self.get_logger().info(f"  {model_name}: class {class_idx}")
            
            self.get_logger().info(f"✅ Classification complete: {results}")
            return results
            
        except Exception as e:
            self.get_logger().error(f"❌ Classification failed: {e}")
            raise

    def _publish_result(
        self,
        record_id: str,
        code: int,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        Publish diagnosis results via ROS2.
        
        Format:
        {
            "record_id": str,
            "code": 1 (success) | 201/202 (error),
            "result": {
                "tongue_color": 0-4,
                "coating_color": 0-2,
                "thickness": 0-1,
                "rot_greasy": 0-1
            }
        }
        """
        if code == 1 and result:
            payload = {
                "record_id": record_id,
                "code": code,
                "result": {
                    "tongue_color": result.get('tongue_color', -1),
                    "coating_color": result.get('coating_color', -1),
                    "thickness": result.get('thickness', -1),
                    "rot_greasy": result.get('rot_greasy', -1),
                }
            }
        else:
            payload = {
                "record_id": record_id,
                "code": code,
                "error": error or "Unknown error"
            }
        
        payload_json = json.dumps(payload)
        
        try:
            msg = String()
            msg.data = payload_json
            self.result_publisher.publish(msg)
            self.get_logger().info(f"✅ Published result to {self.output_topic}")
        except Exception as e:
            self.get_logger().error(f"❌ Failed to publish result: {e}")

    def destroy_node(self):
        """Cleanup on node shutdown."""
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = TongueDiagnosisNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
