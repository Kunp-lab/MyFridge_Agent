from enum import Enum
import platform


def _get_broker_ip() -> str:
    machine = platform.machine().lower()
    if "arm" in machine or "aarch64" in machine:
        return "192.168.137.1"
    return "0.0.0.0"


class Setting(Enum):
    API_KEY = "sk-7ZGr2wxHCXJuzT0boJPMlyBr1aQlNJL7kEIItZeeCB1eivZ7"
    BASE_URL = "https://chat.ekti.cc/v1"
    BROKER_IP = _get_broker_ip()
    TONGUE_RECORD_ID = "user1"
    TOPIC_SEND = "tongue/predict"
    TOPIC_RECEIVE = "tongue/result/user1"
    IMAGE_PATH = "image.jpg"
