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
        {
            resp->is_success = false;
            resp->notes = "操作失败";

            sqlite3_stmt *stmt = nullptr;
            int rc;

            switch (static_cast<Operation>(req->operation))
            {
            case Operation::APPEND:
            {
                // INSERT 新食材（id 由 AUTOINCREMENT 自动生成）
                const char *sql = R"SQL(
                    INSERT INTO ingredients (
                        name,
                        category,
                        expiry_date,
                        location,
                        calories_per_unit,
                        nutritional_info,
                        notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                )SQL";

                rc = sqlite3_prepare_v2(_db, sql, -1, &stmt, nullptr);
                if (rc != SQLITE_OK)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 "Prepare APPEND failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                    break;
                }

                // 绑定参数（顺序必须和 SQL 中的 ? 对应）
                sqlite3_bind_text(stmt, 1, req->name.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_text(stmt, 2, req->category.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_int(stmt, 3, req->expiry_date);
                sqlite3_bind_text(stmt, 4, req->location.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_double(stmt, 5, req->calories_per_unit);
                sqlite3_bind_text(stmt, 6, req->nutritional_info.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_text(stmt, 7, req->notes.c_str(), -1,
                                  SQLITE_TRANSIENT);

                rc = sqlite3_step(stmt);
                if (rc != SQLITE_DONE)
                {
                    RCLCPP_ERROR(this->get_logger(), "APPEND failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                }
                else
                {
                    resp->is_success = true;
                    resp->id =
                        static_cast<uint32_t>(sqlite3_last_insert_rowid(_db));
                    resp->name = req->name;
                    resp->category = req->category;
                    resp->expiry_date = req->expiry_date;
                    resp->location = req->location;
                    resp->calories_per_unit = req->calories_per_unit;
                    resp->nutritional_info = req->nutritional_info;
                    resp->notes = req->notes;
                    RCLCPP_INFO(this->get_logger(),
                                "APPEND success, new id: %u, name: %s",
                                resp->id, req->name.c_str());
                }
                sqlite3_finalize(stmt);
                break;
            }

            case Operation::DELETE:
            {
                // DELETE 根据 location 删除
                const char *sql = "DELETE FROM ingredients WHERE location = ?;";

                rc = sqlite3_prepare_v2(_db, sql, -1, &stmt, nullptr);
                if (rc != SQLITE_OK)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 "Prepare DELETE failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                    break;
                }

                sqlite3_bind_text(stmt, 1, req->location.c_str(), -1,
                                  SQLITE_TRANSIENT);
                rc = sqlite3_step(stmt);
                if (rc != SQLITE_DONE)
                {
                    RCLCPP_ERROR(this->get_logger(), "DELETE failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                }
                else
                {
                    int changes = sqlite3_changes(_db);
                    resp->is_success = (changes > 0);
                    resp->notes =
                        changes > 0 ? "删除成功" : "未找到要删除的记录";
                    RCLCPP_INFO(this->get_logger(), "DELETE affected rows: %d",
                                changes);
                }
                sqlite3_finalize(stmt);
                break;
            }

            case Operation::MODIFY:
            {
                // UPDATE 根据 id 修改
                const char *sql =
                    "UPDATE ingredients SET "
                    "name = ?, category = ?, expiry_date = ?, location = ?, "
                    "calories_per_unit = ?, nutritional_info = ?, notes = ? "
                    "WHERE id = ?;";

                rc = sqlite3_prepare_v2(_db, sql, -1, &stmt, nullptr);
                if (rc != SQLITE_OK)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 "Prepare MODIFY failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                    break;
                }

                sqlite3_bind_text(stmt, 1, req->name.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_text(stmt, 2, req->category.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_int(stmt, 3, req->expiry_date);
                sqlite3_bind_text(stmt, 4, req->location.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_double(stmt, 5, req->calories_per_unit);
                sqlite3_bind_text(stmt, 6, req->nutritional_info.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_text(stmt, 7, req->notes.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_int(stmt, 8, req->id);

                rc = sqlite3_step(stmt);
                if (rc != SQLITE_DONE)
                {
                    RCLCPP_ERROR(this->get_logger(), "MODIFY failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                }
                else
                {
                    int changes = sqlite3_changes(_db);
                    resp->is_success = (changes > 0);
                    resp->notes =
                        changes > 0 ? "修改成功" : "未找到要修改的记录";
                    RCLCPP_INFO(this->get_logger(), "MODIFY affected rows: %d",
                                changes);
                }
                sqlite3_finalize(stmt);
                break;
            }

            case Operation::SELECT:
            {
                // SELECT 根据 id 查询单条记录
                const char *sql =
                    "SELECT id, name, category, expiry_date, location, "
                    "calories_per_unit, nutritional_info, notes "
                    "FROM ingredients WHERE id = ?;";

                rc = sqlite3_prepare_v2(_db, sql, -1, &stmt, nullptr);
                if (rc != SQLITE_OK)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 "Prepare SELECT failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                    break;
                }
                sqlite3_bind_int(stmt, 1, req->id);

                rc = sqlite3_step(stmt);
                if (rc == SQLITE_ROW)
                {
                    resp->id = sqlite3_column_int(stmt, 0);
                    resp->name = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 1));
                    resp->category = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 2));
                    resp->expiry_date = sqlite3_column_int(stmt, 3);
                    resp->location = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 4));
                    resp->calories_per_unit =
                        static_cast<float>(sqlite3_column_double(stmt, 5));
                    resp->nutritional_info = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 6));
                    resp->notes = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 7));
                    resp->is_success = true;
                    RCLCPP_INFO(this->get_logger(),
                                "SELECT success: id=%u, name=%s", resp->id,
                                resp->name.c_str());
                }
                else
                {
                    resp->notes = "未找到记录";
                    RCLCPP_INFO(this->get_logger(),
                                "SELECT no record found for id: %u", req->id);
                }
                sqlite3_finalize(stmt);
                break;
            }

            default:
                RCLCPP_ERROR(this->get_logger(), "未知的操作类型: %d",
                             req->operation);
                resp->notes = "无效的操作类型";
                break;
            }

            // 可选：记录请求日志（调试用）
            RCLCPP_INFO(this->get_logger(),
                        "处理完成 - 操作:%d, name:%s, nutritional_info:%.2f",
                        req->operation, req->name.c_str(),
                        req->nutritional_info);
        });
}

} // namespace CreativeRobot