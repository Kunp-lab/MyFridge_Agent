#include "sql_server/sql_server_node.hpp"
#include <sstream>
#include <utility>
#include <vector>

namespace
{
std::string escape_json_string(const std::string &value)
{
    std::string escaped;
    escaped.reserve(value.size());
    for (const char ch : value)
    {
        switch (ch)
        {
        case '"':
            escaped += "\\\"";
            break;
        case '\\':
            escaped += "\\\\";
            break;
        case '\n':
            escaped += "\\n";
            break;
        case '\r':
            escaped += "\\r";
            break;
        case '\t':
            escaped += "\\t";
            break;
        default:
            escaped += ch;
            break;
        }
    }
    return escaped;
}
} // namespace

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

    ensure_tables();

    _pos_subscriber = this->create_subscription<std_msgs::msg::Int16MultiArray>(
        "/env/pos", 10,
        std::bind(&SqlServerNode::on_position_update, this,
                  std::placeholders::_1));
    _clock_subscriber = this->create_subscription<std_msgs::msg::Int16MultiArray>(
        "/env/clock", 10,
        std::bind(&SqlServerNode::on_clock_update, this,
                  std::placeholders::_1));

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
                sqlite3_bind_int(stmt, 4, static_cast<int>(req->location));
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
                // DELETE 根据 location 编号删除
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

                sqlite3_bind_int(stmt, 1, static_cast<int>(req->location));
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
                sqlite3_bind_int(stmt, 4, static_cast<int>(req->location));
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
                // SELECT 根据位置编号查询单条记录
                const char *sql =
                    "SELECT id, name, category, expiry_date, location, "
                    "calories_per_unit, nutritional_info, notes "
                    "FROM ingredients WHERE location = ?;";

                rc = sqlite3_prepare_v2(_db, sql, -1, &stmt, nullptr);
                if (rc != SQLITE_OK)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 "Prepare SELECT failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                    break;
                }
                sqlite3_bind_int(stmt, 1, static_cast<int>(req->location));

                rc = sqlite3_step(stmt);
                if (rc == SQLITE_ROW)
                {
                    resp->id = sqlite3_column_int(stmt, 0);
                    resp->name = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 1));
                    resp->category = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 2));
                    resp->expiry_date = sqlite3_column_int(stmt, 3);
                    resp->location = sqlite3_column_int(stmt, 4);
                    resp->calories_per_unit =
                        static_cast<float>(sqlite3_column_double(stmt, 5));
                    resp->nutritional_info = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 6));
                    resp->notes = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 7));
                    resp->is_success = true;
                    RCLCPP_INFO(this->get_logger(),
                                "SELECT success: location=%u, name=%s",
                                resp->location, resp->name.c_str());
                }
                else
                {
                    resp->location = req->location;
                    resp->notes = "未找到记录";
                    RCLCPP_INFO(this->get_logger(),
                                "SELECT no record found for location: %u",
                                req->location);
                }
                sqlite3_finalize(stmt);
                break;
            }

            case Operation::APPEND_HEALTH_STATUS:
            {
                const char *sql = R"SQL(
                    INSERT INTO health_status_history (
                        detected_at,
                        health_status,
                        health_summary,
                        health_raw_json
                    ) VALUES (?, ?, ?, ?);
                )SQL";

                rc = sqlite3_prepare_v2(_db, sql, -1, &stmt, nullptr);
                if (rc != SQLITE_OK)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 "Prepare APPEND_HEALTH_STATUS failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                    break;
                }

                sqlite3_bind_text(stmt, 1, req->detected_at.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_text(stmt, 2, req->health_status.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_text(stmt, 3, req->health_summary.c_str(), -1,
                                  SQLITE_TRANSIENT);
                sqlite3_bind_text(stmt, 4, req->health_raw_json.c_str(), -1,
                                  SQLITE_TRANSIENT);

                rc = sqlite3_step(stmt);
                if (rc != SQLITE_DONE)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 "APPEND_HEALTH_STATUS failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                }
                else
                {
                    resp->is_success = true;
                    resp->id =
                        static_cast<uint32_t>(sqlite3_last_insert_rowid(_db));
                    resp->detected_at = req->detected_at;
                    resp->health_status = req->health_status;
                    resp->health_summary = req->health_summary;
                    resp->health_raw_json = req->health_raw_json;
                    resp->notes = "健康状态记录写入成功";
                }
                sqlite3_finalize(stmt);
                break;
            }

            case Operation::SELECT_RECENT_HEALTH_STATUS:
            {
                const uint32_t limit = req->query_limit == 0 ? 5 : req->query_limit;
                const char *sql = R"SQL(
                    SELECT id, detected_at, health_status, health_summary, health_raw_json
                    FROM health_status_history
                    ORDER BY datetime(detected_at) DESC, id DESC
                    LIMIT ?;
                )SQL";

                rc = sqlite3_prepare_v2(_db, sql, -1, &stmt, nullptr);
                if (rc != SQLITE_OK)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 "Prepare SELECT_RECENT_HEALTH_STATUS failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                    break;
                }

                sqlite3_bind_int(stmt, 1, static_cast<int>(limit));

                std::ostringstream history_stream;
                history_stream << "[";
                bool has_rows = false;
                bool first = true;

                while ((rc = sqlite3_step(stmt)) == SQLITE_ROW)
                {
                    const auto row_id = sqlite3_column_int(stmt, 0);
                    const char *detected_at = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 1));
                    const char *health_status = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 2));
                    const char *health_summary = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 3));
                    const char *health_raw_json = reinterpret_cast<const char *>(
                        sqlite3_column_text(stmt, 4));

                    if (!has_rows)
                    {
                        resp->id = row_id;
                        resp->detected_at = detected_at ? detected_at : "";
                        resp->health_status = health_status ? health_status : "";
                        resp->health_summary = health_summary ? health_summary : "";
                        resp->health_raw_json = health_raw_json ? health_raw_json : "";
                        has_rows = true;
                    }

                    if (!first)
                    {
                        history_stream << ",";
                    }
                    first = false;
                    history_stream << "{"
                                   << "\"id\":" << row_id << ","
                                   << "\"detected_at\":\""
                                   << escape_json_string(detected_at ? detected_at : "")
                                   << "\","
                                   << "\"health_status\":\""
                                   << escape_json_string(health_status ? health_status : "")
                                   << "\","
                                   << "\"health_summary\":\""
                                   << escape_json_string(health_summary ? health_summary : "")
                                   << "\","
                                   << "\"health_raw_json\":"
                                   << (health_raw_json ? health_raw_json : "\"\"")
                                   << "}";
                }

                history_stream << "]";

                if (rc != SQLITE_DONE)
                {
                    RCLCPP_ERROR(this->get_logger(),
                                 "SELECT_RECENT_HEALTH_STATUS failed: %s",
                                 sqlite3_errmsg(_db));
                    resp->notes = sqlite3_errmsg(_db);
                }
                else if (has_rows)
                {
                    resp->is_success = true;
                    resp->health_history_json = history_stream.str();
                    resp->notes = "查询最近健康状态成功";
                }
                else
                {
                    resp->health_history_json = "[]";
                    resp->notes = "未找到健康状态记录";
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
                        "处理完成 - 操作:%d, name:%s, nutritional_info:%s",
                        req->operation, req->name.c_str(),
                        req->nutritional_info.c_str());
        });
}

void SqlServerNode::on_position_update(
    const std_msgs::msg::Int16MultiArray::SharedPtr msg)
{
    if (!msg || msg->data.size() < 2)
    {
        RCLCPP_WARN(this->get_logger(),
                    "Ignore /env/pos message: invalid data size");
        return;
    }

    const int action = static_cast<int>(msg->data[0]);
    const int location = static_cast<int>(msg->data[1]);

    if (action < 0)
    {
        if (!delete_ingredient_by_location(location))
        {
            RCLCPP_WARN(this->get_logger(),
                        "No ingredient deleted for location %d", location);
        }
    }
    else if (action > 0)
    {
        RCLCPP_DEBUG(this->get_logger(),
                     "Ignore /env/pos add event at location=%d", location);
    }
    else
    {
        RCLCPP_WARN(this->get_logger(),
                    "Ignore /env/pos message: unknown action=%d", action);
    }
}

void SqlServerNode::on_clock_update(
    const std_msgs::msg::Int16MultiArray::SharedPtr msg)
{
    if (!msg || msg->data.empty())
    {
        RCLCPP_WARN(this->get_logger(),
                    "Ignore /env/clock message: invalid data size");
        return;
    }

    const int day_delta = static_cast<int>(msg->data[0]);
    if (day_delta == 0)
    {
        RCLCPP_INFO(this->get_logger(),
                    "/env/clock delta is 0 day, nothing to update");
        return;
    }

    if (!apply_expiry_offset_to_all(day_delta))
    {
        RCLCPP_ERROR(this->get_logger(),
                     "Failed to apply /env/clock delta=%d to ingredients",
                     day_delta);
    }
}

bool SqlServerNode::apply_expiry_offset_to_all(int day_delta)
{
    if (day_delta > 0)
    {
        return increase_all_expiry_days(day_delta);
    }
    if (day_delta < 0)
    {
        return decrease_all_expiry_days_with_guard(day_delta);
    }
    return true;
}

bool SqlServerNode::increase_all_expiry_days(int day_delta)
{
    sqlite3_stmt *stmt = nullptr;
    const char *sql = "UPDATE ingredients SET expiry_date = expiry_date + ?;";

    int rc = sqlite3_prepare_v2(_db, sql, -1, &stmt, nullptr);
    if (rc != SQLITE_OK)
    {
        RCLCPP_ERROR(this->get_logger(),
                     "Prepare increase_all_expiry_days failed: %s",
                     sqlite3_errmsg(_db));
        return false;
    }

    sqlite3_bind_int(stmt, 1, day_delta);
    rc = sqlite3_step(stmt);
    const bool done = (rc == SQLITE_DONE);
    const int changes = done ? sqlite3_changes(_db) : 0;
    sqlite3_finalize(stmt);

    if (!done)
    {
        RCLCPP_ERROR(this->get_logger(),
                     "Increase expiry days failed: %s", sqlite3_errmsg(_db));
        return false;
    }

    RCLCPP_INFO(this->get_logger(),
                "Applied +%d day(s) to all ingredients, affected rows=%d",
                day_delta, changes);
    return true;
}

bool SqlServerNode::decrease_all_expiry_days_with_guard(int day_delta)
{
    sqlite3_stmt *select_stmt = nullptr;
    const char *select_sql = "SELECT id, expiry_date FROM ingredients;";

    int rc = sqlite3_prepare_v2(_db, select_sql, -1, &select_stmt, nullptr);
    if (rc != SQLITE_OK)
    {
        RCLCPP_ERROR(this->get_logger(),
                     "Prepare decrease select failed: %s",
                     sqlite3_errmsg(_db));
        return false;
    }

    std::vector<std::pair<int, int>> planned_updates;
    while ((rc = sqlite3_step(select_stmt)) == SQLITE_ROW)
    {
        const int id = sqlite3_column_int(select_stmt, 0);
        const int expiry = sqlite3_column_int(select_stmt, 1);
        int next_expiry = expiry + day_delta;
        if (next_expiry < 0)
        {
            next_expiry = 0;
        }

        if (next_expiry != expiry)
        {
            planned_updates.emplace_back(id, next_expiry);
        }
    }

    if (rc != SQLITE_DONE)
    {
        RCLCPP_ERROR(this->get_logger(),
                     "Read ingredients for decrease failed: %s",
                     sqlite3_errmsg(_db));
        sqlite3_finalize(select_stmt);
        return false;
    }
    sqlite3_finalize(select_stmt);

    if (planned_updates.empty())
    {
        RCLCPP_INFO(this->get_logger(),
                    "Applied %d day(s), no ingredient expiry needs update",
                    day_delta);
        return true;
    }

    if (!execute_sql("BEGIN TRANSACTION;"))
    {
        return false;
    }

    sqlite3_stmt *update_stmt = nullptr;
    const char *update_sql =
        "UPDATE ingredients SET expiry_date = ? WHERE id = ?;";
    rc = sqlite3_prepare_v2(_db, update_sql, -1, &update_stmt, nullptr);
    if (rc != SQLITE_OK)
    {
        RCLCPP_ERROR(this->get_logger(),
                     "Prepare decrease update failed: %s",
                     sqlite3_errmsg(_db));
        execute_sql("ROLLBACK;");
        return false;
    }

    for (const auto &item : planned_updates)
    {
        sqlite3_reset(update_stmt);
        sqlite3_clear_bindings(update_stmt);
        sqlite3_bind_int(update_stmt, 1, item.second);
        sqlite3_bind_int(update_stmt, 2, item.first);

        rc = sqlite3_step(update_stmt);
        if (rc != SQLITE_DONE)
        {
            RCLCPP_ERROR(this->get_logger(),
                         "Decrease update failed for id=%d: %s", item.first,
                         sqlite3_errmsg(_db));
            sqlite3_finalize(update_stmt);
            execute_sql("ROLLBACK;");
            return false;
        }
    }
    sqlite3_finalize(update_stmt);

    if (!execute_sql("COMMIT;"))
    {
        execute_sql("ROLLBACK;");
        return false;
    }

    RCLCPP_INFO(this->get_logger(),
                "Applied %d day(s) to ingredients with zero guard, "
                "affected rows=%zu",
                day_delta, planned_updates.size());
    return true;
}

bool SqlServerNode::delete_ingredient_by_location(int location)
{
    sqlite3_stmt *stmt = nullptr;
    const char *sql = "DELETE FROM ingredients WHERE location = ?;";

    int rc = sqlite3_prepare_v2(_db, sql, -1, &stmt, nullptr);
    if (rc != SQLITE_OK)
    {
        RCLCPP_ERROR(this->get_logger(),
                     "Prepare delete_ingredient_by_location failed: %s",
                     sqlite3_errmsg(_db));
        return false;
    }

    sqlite3_bind_int(stmt, 1, location);
    rc = sqlite3_step(stmt);
    const bool done = (rc == SQLITE_DONE);
    const int changes = done ? sqlite3_changes(_db) : 0;
    sqlite3_finalize(stmt);

    if (!done)
    {
        RCLCPP_ERROR(this->get_logger(),
                     "Delete ingredient by location failed: %s",
                     sqlite3_errmsg(_db));
        return false;
    }

    if (changes == 0)
    {
        RCLCPP_WARN(this->get_logger(),
                    "No ingredient found at location=%d", location);
        return false;
    }

    RCLCPP_INFO(this->get_logger(),
                "Deleted %d ingredient(s) at location=%d", changes, location);
    return true;
}

bool SqlServerNode::execute_sql(const std::string &sql)
{
    char *err_msg = nullptr;
    const int rc = sqlite3_exec(_db, sql.c_str(), nullptr, nullptr, &err_msg);
    if (rc != SQLITE_OK)
    {
        RCLCPP_ERROR(this->get_logger(), "Execute SQL failed: %s",
                     err_msg ? err_msg : sqlite3_errmsg(_db));
        sqlite3_free(err_msg);
        return false;
    }
    return true;
}

void SqlServerNode::ensure_tables()
{
    execute_sql(R"SQL(
        CREATE TABLE IF NOT EXISTS health_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TEXT NOT NULL,
            health_status TEXT NOT NULL,
            health_summary TEXT NOT NULL,
            health_raw_json TEXT NOT NULL
        );
    )SQL");

    execute_sql(R"SQL(
        CREATE INDEX IF NOT EXISTS idx_health_status_detected_at
        ON health_status_history (detected_at DESC, id DESC);
    )SQL");
}

} // namespace CreativeRobot
