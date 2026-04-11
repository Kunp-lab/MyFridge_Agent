#include "connector/serial_port.hpp"
#include "rclcpp/rclcpp.hpp"
#include <atomic>
#include <mutex>
#include <string>
#include <thread>

class UartConnector : public rclcpp::Node
{
  public:
    UartConnector()
        : Node("uart_connector"), serial_("/dev/ttyACM0", 115200),
          running_(true)
    {
        serial_.setFrameFormat({0xA0, 0xB0}, {0xC0});
        serial_.setFunctionCodePosition(0);

        serial_.addFunctionHandler(
            0x01,
            [this](const std::vector<uint8_t> &packet)
            {
                RCLCPP_INFO(this->get_logger(),
                            "Function 0x01 packet received, len=%zu",
                            packet.size());
                std::lock_guard<std::mutex> lock(data_mutex_);
                latest_data_.assign(packet.begin(), packet.end());
            });

        serial_.addFunctionHandler(
            0x02,
            [this](const std::vector<uint8_t> &packet)
            {
                RCLCPP_INFO(this->get_logger(),
                            "Function 0x02 packet received, len=%zu",
                            packet.size());
                std::lock_guard<std::mutex> lock(data_mutex_);
                latest_data_.assign(packet.begin(), packet.end());
            });

        serial_.setCallback(
            [this](const std::vector<uint8_t> &packet)
            {
                RCLCPP_INFO(this->get_logger(),
                            "Unknown function packet received, len=%zu",
                            packet.size());
                std::lock_guard<std::mutex> lock(data_mutex_);
                latest_data_.assign(packet.begin(), packet.end());
            });

        // 初始化串口
        try
        {
            serial_.init();
            RCLCPP_INFO(this->get_logger(),
                        "Serial port initialized successfully");
        }
        catch (const std::exception &e)
        {
            RCLCPP_ERROR(this->get_logger(),
                         "Failed to initialize serial port: %s", e.what());
            throw;
        }

        // 创建定时器，每秒发布一次数据
        timer_ = this->create_wall_timer(
            std::chrono::seconds(1),
            std::bind(&UartConnector::publishData, this));
    }

    ~UartConnector() { serial_.shutdown(); }

  private:
    SerialPort serial_; // 假设设备和波特率
    std::atomic<bool> running_;
    std::mutex data_mutex_;
    std::vector<uint8_t> latest_data_;
    rclcpp::TimerBase::SharedPtr timer_;

    void publishData()
    {
        serial_.write("555");
        // std::lock_guard<std::mutex> lock(data_mutex_);
        // if (!latest_data_.empty())
        // {
        //     // 简单协议解析：假设格式 "CMD:DATA\n"
        //     // For binary data, just log the size or hex dump
        //     std::string hex_str;
        //     for (auto byte : latest_data_)
        //     {
        //         char buf[3];
        //         sprintf(buf, "%02X", byte);
        //         hex_str += buf;
        //     }
        //     RCLCPP_INFO(this->get_logger(), "Received binary data: %s",
        //                 hex_str.c_str());
        // }
    }
};

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    try
    {
        auto node = std::make_shared<UartConnector>();
        rclcpp::spin(node);
    }
    catch (const std::exception &e)
    {
        RCLCPP_ERROR(rclcpp::get_logger("uart_connector"), "Node failed: %s",
                     e.what());
    }
    rclcpp::shutdown();
    return 0;
}
