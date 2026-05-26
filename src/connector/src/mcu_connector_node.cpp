#include "connector/serial_port.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/float32.hpp"
#include "std_msgs/msg/float32_multi_array.hpp"
#include "std_msgs/msg/int16_multi_array.hpp"
#include "std_msgs/msg/u_int8_multi_array.hpp"
#include <atomic>
#include <mutex>
#include <string>
#include <thread>

class MCUConnector : public rclcpp::Node
{
  public:
    MCUConnector()
        : Node("uart_connector"), serial_("/dev/ttyS1", 115200), running_(true)
    {
        ros2_init();
        serial_init();
    }

    ~MCUConnector() { serial_.shutdown(); }

    void ros2_init()
    {
        publisher_dht11_ =
            this->create_publisher<std_msgs::msg::Float32MultiArray>(
                "/env/dht11", 10);
        timer_ = this->create_wall_timer(
            std::chrono::seconds(1),
            std::bind(&MCUConnector::publishData, this));
        publisher_pos_ = this->create_publisher<std_msgs::msg::Int16MultiArray>(
            "/env/pos", 10);
        publisher_clock_ =
            this->create_publisher<std_msgs::msg::Int16MultiArray>("/env/clock",
                                                                   10);
        _uart_data_subscriber =
            this->create_subscription<std_msgs::msg::UInt8MultiArray>(
                "/uart/data", 10,
                [this](const std_msgs::msg::UInt8MultiArray::SharedPtr msg)
                {
                    auto data = msg->data;
                    try
                    {
                        if (data.empty())
                        {
                            RCLCPP_WARN(this->get_logger(),
                                        "Ignore empty /uart/data message");
                            return;
                        }

                        auto func_code = data.front();
                        data.erase(data.begin());
                        size_t sent = serial_.writePacket(func_code, data);
                        RCLCPP_INFO(
                            this->get_logger(),
                            "Sent UART packet: header 0xA0, func_code 0x%02X, "
                            "payload size %zu, tail 0xC0, size: %zu",
                            func_code, data.size(), sent);
                    }
                    catch (const std::exception &e)
                    {
                        RCLCPP_ERROR(this->get_logger(),
                                     "Failed to send packet: %s", e.what());
                    }
                });
    }

    void serial_init()
    {
        // Set receive frame format: header 0xB0, tail 0xC0
        serial_.setRxFrameFormat({0xA0}, {0xC0});
        serial_.setFunctionCodePosition(0);

        // Set transmit frame format: header 0xA0, tail 0xC0
        serial_.setTxFrameFormat({0xA0}, {0xC0});

        serial_.addFunctionHandler(
            0xB3, // 时间
            [this](const std::vector<uint8_t> &packet)
            {
                RCLCPP_INFO(this->get_logger(),
                            "Function Code 0xB3 packet received, len=%zu",
                            packet.size());
                if (packet.size() != 1)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 " Function Code 0xB3 packet received error");
                    return;
                }

                std::lock_guard<std::mutex> lock(clock_data_mutex_);
                clock_data_[1] = clock_data_[0]; // set old
                clock_data_[0] = packet[0];      // set new
                std_msgs::msg::Int16MultiArray msg;
                msg.data.resize(1);
                auto dist = clock_data_[1] - clock_data_[0];
                if (std::abs(dist) > 200)
                {
                    clock_data_[1] = clock_data_[0];
                }
                msg.data[0] = clock_data_[1] - clock_data_[0];
                this->publisher_clock_->publish(msg);
            });

        serial_.addFunctionHandler(
            0xB2, // 温湿度
            [this](const std::vector<uint8_t> &packet)
            {
                RCLCPP_INFO(this->get_logger(),
                            "Function Code 0xB2 packet received, len=%zu",
                            packet.size());
                if (packet.size() != 8)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 " Function Code 0xB2 packet received error");
                    return;
                }

                std::lock_guard<std::mutex> lock(dht11_data_mutex_);
                FloatConverter temperature_fc{};
                temperature_fc.ucharfmt.assign(packet.begin(),
                                               packet.begin() + 4);
                dht11_data_[0] = temperature_fc.floatfmt;

                FloatConverter humidity_fc{};
                humidity_fc.ucharfmt.assign(packet.begin() + 4,
                                            packet.begin() + 8);
                dht11_data_[1] = humidity_fc.floatfmt;
            });

        serial_.addFunctionHandler(
            0xB1, // 压力
            [this](const std::vector<uint8_t> &packet)
            {
                RCLCPP_INFO(this->get_logger(),
                            "Function Code 0xB1 packet received, len=%zu",
                            packet.size());
                if (packet.size() != 7)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 " Function Code 0xB1 packet received error");
                    return;
                }
                std::lock_guard<std::mutex> lock(position_data_mutex_);
                now_position_data_.swap(last_position_data_);
                for (size_t i = 0; i < 7; i++)
                    now_position_data_[i] = packet[i];
            });

        serial_.setDefaultHandler(
            [this](const std::vector<uint8_t> &packet)
            {
                RCLCPP_INFO(this->get_logger(),
                            "Unknown Function Code packet received, len=%zu",
                            packet.size());
                return;
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
    }

  private:
    SerialPort serial_; // 假设设备和波特率
    std::atomic<bool> running_;
    std::mutex data_mutex_;
    std::vector<uint8_t> latest_data_;
    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::Subscription<std_msgs::msg::UInt8MultiArray>::SharedPtr
        _uart_data_subscriber;
    std::shared_ptr<rclcpp::Publisher<std_msgs::msg::Float32MultiArray>>
        publisher_dht11_;
    std::shared_ptr<rclcpp::Publisher<std_msgs::msg::Int16MultiArray>>
        publisher_pos_;
    std::shared_ptr<rclcpp::Publisher<std_msgs::msg::Int16MultiArray>>
        publisher_clock_;
    std::vector<float> dht11_data_ = std::vector<float>(2, 0);
    std::mutex dht11_data_mutex_;
    std::mutex clock_data_mutex_;
    std::mutex position_data_mutex_;
    std::vector<int> clock_data_ = std::vector<int>(2, 0);
    std::vector<int> last_position_data_ = std::vector<int>(7, 0);
    std::vector<int> now_position_data_ = std::vector<int>(7, 0);
    void publishData()
    {

        // Example: Send packet with header 0xA0, func_code 0x01,
        // payload "a",
        // tail 0xC0
        // try
        // {
        //     size_t sent = serial_.writePacket(0x01, "a");
        //     RCLCPP_INFO(this->get_logger(),
        //                 "Sent packet with header 0xA0, func_code 0x01,
        //                 payload "
        //                 "'a', tail 0xC0, size: %zu",
        //                 sent);
        // }
        // catch (const std::exception &e)
        // {
        //     RCLCPP_ERROR(this->get_logger(), "Failed to send packet: %s",
        //                  e.what());
        // }

        // send data of dht11
        // std_msgs::msg::Float32MultiArray msg;
        // msg.data.resize(dht11_data_.size());
        // std::copy(dht11_data_.begin(), dht11_data_.end(), msg.data.begin());
        // publisher_dht11_->publish(msg);

        // send data of position
        std::vector<int> append_list{};
        std::vector<int> delete_list{};

        for (size_t i = 0; i < last_position_data_.size(); i++)
        {
            auto temp = last_position_data_[i] - now_position_data_[i];
            if (temp == 1)
            {
                delete_list.push_back(i);
            }
            else if (temp == -1)
            {
                append_list.push_back(i);
            }
        }
        std::copy(now_position_data_.begin(), now_position_data_.end(),
                  last_position_data_.begin());

        for (auto item : append_list)
        {
            std_msgs::msg::Int16MultiArray msg;
            msg.data.resize(2);
            msg.data[0] = 1;
            msg.data[1] = item + 1;
            publisher_pos_->publish(msg);
            RCLCPP_INFO(this->get_logger(), "append %d,%d", msg.data[0],
                        msg.data[1]);
        }

        for (auto item : delete_list)
        {
            std_msgs::msg::Int16MultiArray msg;
            msg.data.resize(2);
            msg.data[0] = -1;
            msg.data[1] = item + 1;
            publisher_pos_->publish(msg);
            RCLCPP_INFO(this->get_logger(), "delete %d,%d", msg.data[0],
                        msg.data[1]);
        }
    }
};

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    try
    {
        auto node = std::make_shared<MCUConnector>();
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
