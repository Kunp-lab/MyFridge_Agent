import serial
import time
import numpy as np


class QD4310:
    def __init__(self, port):
        self.ser = serial.Serial(port, baudrate=115200, timeout=0.005)
        self.ser.write(f"silent\n".encode())

    def enable(self):
        """发送使能指令"""
        self.ser.write(f"enable\n".encode())

    def disable(self):
        """发送失能指令"""
        self.ser.write(f"disable\n".encode())

    def set_current(self, current):
        """设置电流 (A)"""
        self.ser.write(f"ctrl current {current}\n".encode())

    def set_speed(self, speed):
        """设置速度 (rpm)"""
        self.ser.write(f"ctrl speed {speed}\n".encode())

    def set_low_speed(self, low_speed):
        """设置速度 (rpm)"""
        self.ser.write(f"ctrl speed {low_speed}\n".encode())

    def set_angle(self, angle):
        """设置角度 (rad)"""
        self.ser.write(f"ctrl angle {angle}\n".encode())

    def close(self):
        """关闭串口连接"""
        self.ser.close()


if __name__ == "__main__":
    qd4310_1 = QD4310('COM28')
    qd4310_1.enable()
    radius = 0.5
    for i in range(20):
        for j in np.arange(0, 2 * np.pi, 0.02):
            qd4310_1.set_angle(radius * np.cos(j))
            time.sleep(0.04)
    qd4310_1.disable()
    qd4310_1.close()
