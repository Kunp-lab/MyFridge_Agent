#include "ament_index_cpp/get_package_share_directory.hpp"
#include "connector/serial_port.hpp"
#include "opencv2/imgcodecs.hpp"
#include "opencv2/imgproc.hpp"
#include "opencv2/objdetect.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/compressed_image.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <exception>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

class QD4310
{
  public:
    QD4310(const std::string &port, int baudrate = 115200)
        : ser_(port, baudrate)
    {
        ser_.init();
        ser_.write("silent\n");
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    void enable()
    {
        ser_.write("enable\n");
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    void disable()
    {
        ser_.write("disable\n");
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    void set_speed(double speed)
    {
        char buf[256];
        std::snprintf(buf, sizeof(buf), "ctrl speed %.4f\n", speed);
        ser_.write(std::string(buf));
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    void set_angle(double angle)
    {
        char buf[256];
        std::snprintf(buf, sizeof(buf), "ctrl angle %.4f\n", angle);
        ser_.write(std::string(buf));
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    void close() { ser_.shutdown(); }

  private:
    SerialPort ser_;
};

class QDriverNode : public rclcpp::Node
{
  public:
    QDriverNode() : Node("qdriver_node")
    {
        serial_port_ =
            this->declare_parameter<std::string>("serial_port", "/dev/ttyACM0");
        baudrate_ = this->declare_parameter<int>("baudrate", 115200);
        image_topic_ =
            this->declare_parameter<std::string>("image_topic", "/image");
        pid_p_ = this->declare_parameter<double>("pid_p", -10);
        deadband_ratio_ =
            this->declare_parameter<double>("deadband_ratio", 0.05);
        max_speed_ = this->declare_parameter<double>("max_speed", 25.0);
        min_speed_ = this->declare_parameter<double>("min_speed", -25.0);
        face_min_size_ = this->declare_parameter<int>("face_min_size", 60);
        command_interval_ms_ =
            this->declare_parameter<int>("command_interval_ms", 50);
        confidence_min_ =
            this->declare_parameter<double>("confidence_min", 0.0);
        confidence_max_ =
            this->declare_parameter<double>("confidence_max", 10.0);
        face_cascade_path_ =
            this->declare_parameter<std::string>("face_cascade_path", "");

        if (!load_face_detector())
        {
            throw std::runtime_error(
                "Failed to load Haar cascade for face detection. "
                "Set parameter 'face_cascade_path'.");
        }

        qd_ = std::make_unique<QD4310>(serial_port_, baudrate_);
        qd_->enable();

        subscription_image_ =
            this->create_subscription<sensor_msgs::msg::CompressedImage>(
                image_topic_, rclcpp::SensorDataQoS(),
                [this](sensor_msgs::msg::CompressedImage::ConstSharedPtr msg)
                    -> void { image_callback(msg); });

        RCLCPP_INFO(this->get_logger(),
                    "QDriverNode started. topic=%s kp=%.3f deadband=%.3f "
                    "max_speed=%.3f min_speed=%.3f conf_range=[%.2f, %.2f] "
                    "cascade=%s",
                    image_topic_.c_str(), pid_p_, deadband_ratio_, max_speed_,
                    min_speed_, confidence_min_, confidence_max_,
                    face_cascade_path_.c_str());
    }

    ~QDriverNode() override
    {
        if (!qd_)
        {
            return;
        }

        try
        {
            qd_->set_speed(0.0);
            qd_->disable();
            qd_->close();
        }
        catch (const std::exception &e)
        {
            RCLCPP_ERROR(this->get_logger(), "Stop motor failed: %s", e.what());
        }
    }

  private:
    bool load_face_detector()
    {
        std::vector<std::string> candidate_paths;
        if (!face_cascade_path_.empty())
        {
            candidate_paths.push_back(face_cascade_path_);
        }

        try
        {
            const std::string share_dir =
                ament_index_cpp::get_package_share_directory("connector");
            candidate_paths.push_back(
                share_dir + "/assets/haarcascade_frontalface_default.xml");
        }
        catch (const std::exception &e)
        {
            RCLCPP_WARN(this->get_logger(),
                        "Failed to query package share path: %s", e.what());
        }

        candidate_paths.push_back("/usr/share/opencv4/haarcascades/"
                                  "haarcascade_frontalface_default.xml");
        candidate_paths.push_back("/usr/share/opencv/haarcascades/"
                                  "haarcascade_frontalface_default.xml");

        for (const auto &path : candidate_paths)
        {
            if (path.empty())
            {
                continue;
            }

            if (face_detector_.load(path))
            {
                face_cascade_path_ = path;
                return true;
            }
        }

        return false;
    }

    void image_callback(sensor_msgs::msg::CompressedImage::ConstSharedPtr msg)
    {
        if (!qd_ || msg->data.empty())
        {
            return;
        }

        cv::Mat encoded(1, static_cast<int>(msg->data.size()), CV_8UC1,
                        const_cast<unsigned char *>(msg->data.data()));
        cv::Mat frame = cv::imdecode(encoded, cv::IMREAD_COLOR);
        if (frame.empty())
        {
            RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 2000,
                                 "Decode CompressedImage failed");
            return;
        }

        cv::Mat gray;
        cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);
        cv::equalizeHist(gray, gray);

        std::vector<cv::Rect> faces;
        std::vector<int> reject_levels;
        std::vector<double> level_weights;
        face_detector_.detectMultiScale(
            gray, faces, reject_levels, level_weights, 1.1, 5, 0,
            cv::Size(face_min_size_, face_min_size_), cv::Size(), true);

        if (faces.empty())
        {
            publish_motor_speed(0.0);
            return;
        }

        size_t selected_face_index = 0;
        for (size_t i = 1; i < faces.size(); ++i)
        {
            if (faces[i].area() > faces[selected_face_index].area())
            {
                selected_face_index = i;
            }
        }
        const cv::Rect &face = faces[selected_face_index];
        const double face_confidence =
            selected_face_index < level_weights.size()
                ? level_weights[selected_face_index]
                : 0.0;
        const double face_confidence_norm =
            normalize_confidence(face_confidence);

        const double frame_center_x = static_cast<double>(frame.cols) * 0.5;
        if (frame_center_x <= 0.0)
        {
            return;
        }

        const double face_center_x =
            static_cast<double>(face.x) + static_cast<double>(face.width) * 0.5;
        double error_norm = (face_center_x - frame_center_x) / frame_center_x;
        error_norm = std::clamp(error_norm, -1.0, 1.0);

        // P-only control uses absolute error magnitude. Direction is handled
        // separately by checking whether the face is left or right.
        const double abs_error = std::abs(error_norm);
        double speed_command = 0.0;
        if (abs_error > deadband_ratio_)
        {
            double speed_mag = pid_p_ * abs_error;
            speed_mag = std::clamp(speed_mag, -max_speed_, max_speed_);
            if (speed_mag > 0.0 && speed_mag < min_speed_)
            {
                speed_mag = min_speed_;
            }

            speed_command = (error_norm > 0.0) ? speed_mag : -speed_mag;
        }

        publish_motor_speed(speed_command);

        RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
                             "face_center_x=%.1f frame_center_x=%.1f "
                             "error=%.3f cmd=%.3f confidence=%.3f(raw=%.3f)",
                             face_center_x, frame_center_x, error_norm,
                             speed_command, face_confidence_norm,
                             face_confidence);
    }

    double normalize_confidence(double raw_confidence) const
    {
        if (confidence_max_ <= confidence_min_)
        {
            return 0.0;
        }
        const double norm = (raw_confidence - confidence_min_) /
                            (confidence_max_ - confidence_min_);
        return std::clamp(norm, 0.0, 1.0);
    }

    void publish_motor_speed(double speed)
    {
        const auto now = this->now();
        const double elapsed_ms =
            has_sent_command_ ? (now - last_command_time_).seconds() * 1000.0
                              : static_cast<double>(command_interval_ms_);

        if (has_sent_command_ &&
            elapsed_ms < static_cast<double>(command_interval_ms_))
        {
            return;
        }

        if (has_sent_command_ && std::abs(speed - last_speed_command_) < 1e-3)
        {
            return;
        }

        qd_->set_speed(speed);
        last_speed_command_ = speed;
        last_command_time_ = now;
        has_sent_command_ = true;
    }

    std::unique_ptr<QD4310> qd_;
    cv::CascadeClassifier face_detector_;

    std::string serial_port_;
    int baudrate_{115200};
    std::string image_topic_;
    std::string face_cascade_path_;
    double pid_p_{20.0};
    double deadband_ratio_{0.05};
    double max_speed_{25.0};
    double min_speed_{1.0};
    int face_min_size_{60};
    int command_interval_ms_{50};
    double confidence_min_{0.0};
    double confidence_max_{10.0};

    bool has_sent_command_{false};
    double last_speed_command_{0.0};
    rclcpp::Time last_command_time_;

    rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr
        subscription_image_;
};

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    try
    {
        auto node = std::make_shared<QDriverNode>();
        rclcpp::spin(node);
    }
    catch (const std::exception &e)
    {
        RCLCPP_ERROR(rclcpp::get_logger("qdriver_node"), "Node failed: %s",
                     e.what());
    }
    rclcpp::shutdown();
    return 0;
}
