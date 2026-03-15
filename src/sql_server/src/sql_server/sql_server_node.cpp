#include "sql_server/sql_server_node.hpp"
namespace CreativeRobot
{

SqlServer::SqlServer() : Node("SqlServer")
{
    RCLCPP_INFO(this->get_logger(), "SqlServer started\n");
    init();
}
SqlServer::SqlServer(std::string nodeName = "SqlServer") : Node(nodeName)
{
    RCLCPP_INFO(this->get_logger(), "SqlServer started\n");
    init();
}
void SqlServer::init()
{
    add_ints_server = this->create_service<example_interfaces::srv::AddTwoInts>(
        "add_two_ints_srv",
        [this](
            const std::shared_ptr<example_interfaces::srv::AddTwoInts::Request>
                req,
            std::shared_ptr<example_interfaces::srv::AddTwoInts::Response> resp)
        {
            RCLCPP_INFO(this->get_logger(), "a:%d, b:%d\n", req->a, req->b);
            resp->sum = req->a + req->b;
        });
}

} // namespace CreativeRobot