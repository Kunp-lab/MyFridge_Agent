#include "sql_server/sql_server_node.hpp"
namespace CreativeRobot
{
SqlServerNode::SqlServerNode() : Node("SqlServerNode")
{
    RCLCPP_INFO(this->get_logger(), "SqlServerNode started\n");
    init();
}
SqlServerNode::SqlServerNode(std::string nodeName = "SqlServerNode")
    : Node(nodeName)
{
    RCLCPP_INFO(this->get_logger(), "SqlServerNode started\n");
    init();
}
SqlServerNode::~SqlServerNode() { sqlite3_close(_db); }
void SqlServerNode::init()
{
    // sqlite init
    _rc = sqlite3_open(DB_ADRESS, &_db);
    if (_rc)
    {
        RCLCPP_ERROR(this->get_logger(), "Can't open database: %s\n",
                     sqlite3_errmsg(_db));
        exit(0);
    }
    else
    {
        RCLCPP_INFO(this->get_logger(), "Opened database successfully\n");
    }

    // rclcpp init
    _sql_server = this->create_service<sql_interface::srv::SQLOperation>(
        "/sql_operation",
        [this](const std::shared_ptr<sql_interface::srv::SQLOperation::Request>
                   req,
               std::shared_ptr<sql_interface::srv::SQLOperation::Response> resp)
        {   //init
            char *sql;
            char *zErrMsg = 0;
            SqlData data{};
            switch (static_cast<Operation>(req->operation))
            {
            case Operation::APPEND:
                data.op = Operation::APPEND;
                data.id = req->id;
                data.name = req->name;
                data.category = req->category;
                data.expiry_date = req->expiry_date;
                data.location = req->location;
                data.calories_per_unit = req->calories_per_unit;
                data.notes = req->notes;
                data.nutritional_info = req->calories_per_unit;
                /* code */
                break;
            
            default:
                break;
            }
            sql = "SELECT * from ingredients";
            
            //get request
            // this->_rc =
            //     sqlite3_exec(this->_db, sql, &SqlServerNode::sqlCallback,
            //                  (void *)&data, &zErrMsg);
            // if (this->_rc != SQLITE_OK)
            // {
            //     RCLCPP_ERROR(this->get_logger(), "SQL error: %s\n", zErrMsg);
            //     sqlite3_free(zErrMsg);
            // }
            // else
            // {
            //     RCLCPP_DEBUG(this->get_logger(),
            //                  "Operation done successfully\n");
            // }
            RCLCPP_INFO(this->get_logger(), "name:%s你好,nutritional_info:%.2f",req->name,req->nutritional_info);

            //set respond
        });
}

// int SqlServerNode::sqlCallback(void *data, int argc, char **argv,
//                                char **azColName)
// {
//     auto *data_stru = static_cast<SqlData *>(data);
//     if (data_stru->mode == "search")
//     {
//         for (int i = 0; i < argc; i++)
//         {
//             printf("%s = %s\n", azColName[i], argv[i] ? argv[i] : "NULL");
//         }
//         printf("\n");
//         data_stru->sum = data_stru->a + data_stru->b + 5;
//     }
//     return 0;
// }

} // namespace CreativeRobot