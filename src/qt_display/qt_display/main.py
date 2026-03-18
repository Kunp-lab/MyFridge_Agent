import rclpy
from .display_node import DisplayNode

def main(args = None):
    rclpy.init(args=args)
    node = DisplayNode("DisplayNode")
    rclpy.spin(node= node)
    rclpy.shutdown
    