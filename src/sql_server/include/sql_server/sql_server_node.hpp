#if !defined(__SQL_SERVER_NODE_HPP__)
#define __SQL_SERVER_NODE_HPP__

#include "example_interfaces/srv/add_two_ints.hpp"
#include "rclcpp/rclcpp.hpp"
#include <sqlite3.h>
#include <string>

#define DB_ADRESS "/home/kunp/work/CreativeRobot/database/fridge_smart.db"
namespace CreativeRobot
{
class SqlServer : public rclcpp::Node
{
  public:
    SqlServer();
    SqlServer(std::string nodeName);
    void init();

    ~SqlServer();

  private:
    rclcpp::Service<example_interfaces::srv::AddTwoInts>::SharedPtr
        _search_server;
    sqlite3 *_db;
    int _rc;
    int search_callback(void *resp, int argc, char **argv, char **azColName);
};
} // namespace CreativeRobot

#endif // __SQL_SERVER_NODE_HPP__
