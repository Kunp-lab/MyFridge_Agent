#if !defined(__SQL_SERVER_NODE_HPP__)
#define __SQL_SERVER_NODE_HPP__

#include "example_interfaces/srv/add_two_ints.hpp"
#include "rclcpp/rclcpp.hpp"
#include <string>
namespace CreativeRobot
{
class SqlServer : public rclcpp::Node
{
  public:
    SqlServer();
    SqlServer(std::string nodeName);
    void init();

    ~SqlServer() = default;

  private:
    rclcpp::Service<example_interfaces::srv::AddTwoInts>::SharedPtr
        add_ints_server;
};
} // namespace CreativeRobot

#endif // __SQL_SERVER_NODE_HPP__
