#if !defined(__SQL_SERVER_NODE_HPP__)
#define __SQL_SERVER_NODE_HPP__

#include "rclcpp/rclcpp.hpp"
#include "sql_interface/srv/sql_operation.hpp"
#include "std_msgs/msg/int16_multi_array.hpp"
#include <memory>
#include <sqlite3.h>
#include <string>

#if defined(__x86_64__)
#define DB_ADRESS "/home/kunp/TrosWork/CreativeRobot/database/my_fridge"
#else
#define DB_ADRESS "/userdata/ros2_ws/CreativeRobot/database/my_fridge"
#endif
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
    rclcpp::Subscription<std_msgs::msg::Int16MultiArray>::SharedPtr
        _clock_subscriber;
    sqlite3 *_db;
    int _rc;

    void ensure_tables();
    bool execute_sql(const std::string &sql);
    void
    on_position_update(const std_msgs::msg::Int16MultiArray::SharedPtr msg);
    void on_clock_update(const std_msgs::msg::Int16MultiArray::SharedPtr msg);
    bool delete_ingredient_by_location(int location);
    bool apply_expiry_offset_to_all(int day_delta);
    bool increase_all_expiry_days(int day_delta);
    bool decrease_all_expiry_days_with_guard(int day_delta);
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
