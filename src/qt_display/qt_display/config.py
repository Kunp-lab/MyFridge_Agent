from enum import Enum
import platform


def _get_broker_ip() -> str:
    machine = platform.machine().lower()
    if "arm" in machine or "aarch64" in machine:
        return "192.168.172.1"
    return "0.0.0.0"


class Setting(Enum):
    API_KEY = "726950d7799a42b793eb5320a4a96e57.XABR5f1gGMyM7ScB"
    BASE_URL = "https://api.z.ai/api/paas/v4/"
    BROKER_IP = _get_broker_ip()
    TONGUE_RECORD_ID = "user1"
    TOPIC_SEND = "tongue/predict"
    TOPIC_RECEIVE = "tongue/result/user1"
    IMAGE_PATH = "image.jpg"
