#include <iostream>
#include <vector>
#include <cmath>
#include <thread>
#include <chrono>
#include <windows.h>
#include <format>

class SerialPort {
public:
    SerialPort(const std::string& port, int baudrate, int timeout_ms = 10) {
        // hSerial = CreateFileA(port.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
        hSerial = CreateFileA(port.c_str(), GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
        if (hSerial == INVALID_HANDLE_VALUE) {
            std::cerr << "无法打开串口: " << port << std::endl;
        }
        // 这里只简单设置波特率和超时，实际项目中应完善
        DCB dcbSerialParams = {0};
        dcbSerialParams.DCBlength = sizeof(dcbSerialParams);
        GetCommState(hSerial, &dcbSerialParams);
        dcbSerialParams.BaudRate = baudrate;
        dcbSerialParams.ByteSize = 8;
        dcbSerialParams.StopBits = ONESTOPBIT;
        dcbSerialParams.Parity = NOPARITY;
        SetCommState(hSerial, &dcbSerialParams);

        COMMTIMEOUTS timeouts = {0};
        timeouts.ReadIntervalTimeout = timeout_ms;
        timeouts.ReadTotalTimeoutConstant = timeout_ms;
        timeouts.ReadTotalTimeoutMultiplier = 0;
        timeouts.WriteTotalTimeoutConstant = timeout_ms;
        timeouts.WriteTotalTimeoutMultiplier = 0;
        SetCommTimeouts(hSerial, &timeouts);
    }

    ~SerialPort() {
        if (hSerial != INVALID_HANDLE_VALUE) {
            CloseHandle(hSerial);
        }
    }

    void write(const std::string& data) {
        DWORD bytesWritten;
        WriteFile(hSerial, data.c_str(), data.size(), &bytesWritten, NULL);
    }

    void read_all() {
        char buffer[256];
        DWORD bytesRead;
        while (ReadFile(hSerial, buffer, sizeof(buffer), &bytesRead, NULL) && bytesRead > 0) {
            // 这里简单丢弃读取内容
        }
    }

    bool is_open() const {
        return hSerial != INVALID_HANDLE_VALUE;
    }

    void close() {
        if (hSerial != INVALID_HANDLE_VALUE) {
            CloseHandle(hSerial);
            hSerial = INVALID_HANDLE_VALUE;
        }
    }

private:
    HANDLE hSerial;
};

class QD4310 {
public:
    QD4310(const std::string& port, int baudrate = 115200, int timeout_ms = 10)
        : ser(port, baudrate, timeout_ms) {
        ser.write("silent\n");
    }

    void enable() {
        ser.write("enable\n");
    }

    void disable() {
        ser.write("disable\n");
    }

    void set_speed(double speed) {
        ser.write("ctrl speed " + std::format("{:.4f}", speed) + "\n");
    }

    void set_angle(double angle) {
        ser.write("ctrl angle " + std::format("{:.4f}", angle) + "\n");
    }

    void close() {
        if (ser.is_open()) ser.close();
    }

private:
    SerialPort ser;
};

int main() {
    QD4310 qd4310_1("\\\\.\\COM28");
    qd4310_1.enable();

    float radius = 0.5;
    float two_pi = 2.0 * std::acos(-1.0);
    for (int i = 0; i < 20; ++i) {
        for (float j = 0.0; j < two_pi; j += 0.02) {
            qd4310_1.set_angle(radius * std::cos(j));
            std::this_thread::sleep_for(std::chrono::milliseconds(15));
        }
    }

    qd4310_1.disable();
    qd4310_1.close();
    return 0;
}
