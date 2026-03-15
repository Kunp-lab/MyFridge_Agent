#include <sql_server/sql_server_node.hpp>

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<CreativeRobot::SqlServer>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
