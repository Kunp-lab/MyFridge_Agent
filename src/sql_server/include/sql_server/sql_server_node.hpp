#if !defined(__SQL_SERVER_NODE_HPP__)
#define __SQL_SERVER_NODE_HPP__

#include "rclcpp/rclcpp.hpp"
#include "sql_interface/srv/sql_operation.hpp"
#include "std_msgs/msg/int16_multi_array.hpp"
#include <memory>
#include <sqlite3.h>
#include <string>

#define DB_ADRESS "/home/kunp/TrosWork/CreativeRobot/database/my_fridge"
namespace CreativeRobot
{
class SqlServerNode : public rclcpp::Node
{
  public:
    SqlServerNode();
    SqlServerNode(std::string nodeName);
    void init();

    ~SqlServerNode();

  private:
    rclcpp::Service<sql_interface::srv::SQLOperation>::SharedPtr _sql_server;
    rclcpp::Subscription<std_msgs::msg::Int16MultiArray>::SharedPtr
        _pos_subscriber;
    sqlite3 *_db;
    int _rc;

    void ensure_tables();
    bool execute_sql(const std::string &sql);
    void on_position_update(const std_msgs::msg::Int16MultiArray::SharedPtr msg);
    bool update_last_added_ingredient_location(int location);
    bool delete_ingredient_by_location(int location);
};

enum class Operation : uint8_t
{
    APPEND = 1,
    DELETE = 2,
    MODIFY = 3,
    SELECT = 4,
    APPEND_HEALTH_STATUS = 5,
    SELECT_RECENT_HEALTH_STATUS = 6
};

struct SqlData
{
    Operation op;
    uint32_t id;
    std::string name;
    std::string category;
    uint32_t expiry_date;
    uint32_t location;
    float calories_per_unit;
    std::string nutritional_info;
    std::string notes;
    std::string detected_at;
    std::string health_status;
    std::string health_summary;
    std::string health_raw_json;
    std::string health_history_json;
    bool is_success;
};
} // namespace CreativeRobot

#endif // __SQL_SERVER_NODE_HPP__
