#ifndef PID_CONTROLLER_HPP
#define PID_CONTROLLER_HPP

#include <algorithm>
#include <string>

class PIDController
{
public:
    struct Config
    {
        double kp, ki, kd, max_i, max_out;
        std::string mod;
    };

    PIDController(const Config &cfg) : cfg_(cfg) {}

    double update(double error, double dt)
    {
        if (cfg_.mod == "位置式")
        {
            if (dt <= 0.0)
                return last_out_;

            // P
            double p_out = cfg_.kp * error;
            // I
            iterm_ += error * dt;
            iterm_ = std::clamp(iterm_, -cfg_.max_i, cfg_.max_i);
            // D
            double d_out = cfg_.kd * (error - last_error_) / dt;

            last_error_ = error;
            last_out_ = std::clamp(p_out + (cfg_.ki * iterm_) + d_out, -cfg_.max_out, cfg_.max_out);
            return last_out_;
        }
        else if (cfg_.mod == "增量式")
        {
            // 1. 安全检查：避免周期异常导致的除零或跳变
            if (dt <= 0.0)
                return last_out_;

            // 2. 计算各阶差分
            double error_delta = error - last_error_;                    // 一阶差分 (用于P)
            double error_2delta = error - 2 * last_error_ + prev_error_; // 二阶差分 (用于D)

            // 3. 计算增量 delta_out
            // P项：比例作用于误差变化量
            double p_out = cfg_.kp * error_delta;
            // I项：积分作用于当前误差
            double i_out = cfg_.ki * error * dt;
            // D项：微分作用于误差变化率的变化（二阶导数）
            double d_out = cfg_.kd * error_2delta / dt;

            double delta_out = p_out + i_out + d_out;

            // 4. 状态更新（在限幅前更新，保证历史数据的连续性）
            prev_error_ = last_error_;
            last_error_ = error;

            // 5. 双重限幅策略
            // A. 步进限幅：防止单次增量过大冲击机械结构

            // B. 输出限幅：防止执行器（电机/舵机）超程
            last_out_ = std::clamp(last_out_ + delta_out, -cfg_.max_out, cfg_.max_out);

            return last_out_;
        }
        else
        {
            // 未知模式，返回0
            return 0.0;
        }
    }

    double get_iterm() const { return iterm_; }

private:
    Config cfg_;
    double iterm_{0.0}, last_error_{0.0}, last_out_{0.0}, prev_error_{0.0};
};

#endif