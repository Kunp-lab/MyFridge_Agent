#include "opencv2/core/mat.hpp"
#include "rclcpp/rclcpp.hpp"
#include "websocket/websocket.h"

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    auto nh_ = std::make_shared<rclcpp::Node>("websockt");

    return 0;
}
