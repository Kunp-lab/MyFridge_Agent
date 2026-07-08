[English](/home/kunp/TrosWork/CreativeRobot/README.md) | [简体中文](/home/kunp/TrosWork/CreativeRobot/README_cn.md)

# CreativeRobot

`CreativeRobot` 是一个基于 ROS2 的智能膳食管理机器人项目。  
它的目标是把冰箱库存管理、食材识别、舌象检测、营养建议和设备联动整合成一套可以实际运行的完整系统。

当前项目采用更标准的 ROS2 启动分层方式：

- `creative_robot_bringup` 作为整机级启动入口
- 每个功能包保留自己的局部 `launch`
- 根目录推荐工作流以整机 bringup 为中心，而不是从某个单一应用包里拉起全部节点

## 系统能做什么

CreativeRobot 面向一个实际的智能冰箱使用场景：

- 记录冰箱中的食材
- 识别摄像头画面中的食物
- 管理格位位置和保质期
- 对舌象图像进行分析，并生成轻量级健康提示
- 将冰箱库存和近期健康状态结合起来生成饮食建议
- 通过 ROS2 协调界面、数据库、摄像头、MCU 和电机相关节点

## 功能包说明

### `src/creative_robot_bringup`

这是整个机器人的顶层启动包。

职责：

- 负责启动完整的应用栈
- 统一包含主要功能包的 `launch` 文件
- 集中管理整机级启动参数，例如测试模式、是否启用舌诊、舌诊模型目录、舌诊阈值和 USB 摄像头设备路径

如果你想用一条命令启动整机，这就是对应的入口包。

### `src/qt_display`

这是项目的主交互层，也是最核心的功能包之一。

职责：

- 提供基于 Qt 的图形界面
- 订阅摄像头图像并刷新实时界面
- 触发食材识别流程
- 触发营养推荐流程
- 发起舌象检测请求
- 接收舌象检测结果并格式化展示
- 通过 `/sql_operation` 与数据库服务通信
- 发布 UART 桥接命令给 MCU 侧逻辑

从实际业务角度看，这个包就是整个系统的业务中心：用户交互、图像驱动流程、推荐逻辑和健康结果展示都汇聚在这里。

### `src/sql_server`

这个包提供基于 SQLite 的数据库服务层。

职责：

- 打开并管理项目数据库
- 对外提供 `/sql_operation` ROS2 服务
- 存储和查询冰箱库存记录
- 存储近期健康状态历史
- 响应部分环境和格位事件，更新持久化数据

它是系统中的持久化核心。

### `src/sql_interface`

这个包定义了数据库服务使用的接口协议。

职责：

- 提供 `SQLOperation.srv`
- 定义界面层和数据库服务层共享的请求/响应字段
- 作为应用逻辑与持久化逻辑之间的协议边界

这个包本身不承载业务逻辑，但它对于保持系统解耦非常重要。

### `src/connector`

这是 ROS2 和下位机硬件之间的设备桥接包。

职责：

- 处理 MCU 串口通信
- 发布环境和格位相关话题，例如位置变化和时钟增量
- 订阅 `/uart/data`，向串口发送数据包
- 管理 QDriver 电机相关控制逻辑

这个包承担的是软件系统与外部硬件之间的连接职责。

### `src/hobot_usb_cam`

这个包负责 USB 摄像头图像采集。

职责：

- 打开配置好的 USB 视频设备
- 发布上层功能需要的 ROS2 图像话题
- 作为 Qt 界面、食材识别和舌象检测的统一视觉输入源

在当前项目中，摄像头图像流是多个业务流程的共同上游依赖。

### `src/tongue_diagnosis`

这个包实现舌象检测推理流程。

职责：

- 订阅 `/tongue_diagnosis/input_image`
- 解码输入的压缩图像
- 执行舌体区域分割
- 执行四个分类分支：舌色、苔色、厚薄、腻腐
- 将结构化 JSON 结果发布到 `/tongue_diagnosis/result`

这个包仍然支持单独运行，但在正常使用中一般由 `creative_robot_bringup` 统一启动。

### `database/`

这个目录保存项目的数据库相关资源。

包括：

- SQLite 数据库文件
- SQL schema
- 仓库中已有的数据库侧 build / install / log 运行产物

在这个项目里，`database/` 不是演示目录，而是真实的数据边界。

## 系统架构

从高层看，系统运行流程大致如下：

1. `hobot_usb_cam` 发布摄像头图像
2. `qt_display` 订阅图像流并更新界面
3. `qt_display` 触发识别、推荐和舌诊流程
4. `sql_server` 持久化库存和健康状态数据
5. `connector` 在 ROS2 和 MCU / UART 之间做桥接
6. `tongue_diagnosis` 处理舌象图像并返回结构化结果

## 主要话题与服务

### 话题

- `/image`
  作为主摄像头图像话题，被界面层消费。

- `/tongue_diagnosis/input_image`
  由 `qt_display` 在发起舌诊任务时发布。

- `/tongue_diagnosis/result`
  由 `tongue_diagnosis` 在推理完成后发布。

- `/uart/data`
  由界面层发布 UART 数据包，交给 MCU 桥接层处理。

- `/env/pos`
  用于冰箱格位 / 位置相关状态更新。

- `/env/clock`
  用于时间增量类更新，可能影响保质期逻辑。

### 服务

- `/sql_operation`
  由 `sql_server` 提供，接口定义位于 `sql_interface/srv/SQLOperation.srv`

典型用途包括：

- 新增库存记录
- 删除或修改格位记录
- 按位置查询库存
- 写入健康状态记录
- 查询最近健康状态历史

## 快速开始

### 1. 编译

```bash
cd ~/TrosWork/CreativeRobot
colcon build
source install/setup.bash
```

### 2. 启动整机

```bash
ros2 launch creative_robot_bringup bringup.launch.py
```

这条命令会启动主要运行栈：

- `qt_display`
- `sql_server`
- `connector`
- `hobot_usb_cam`
- `tongue_diagnosis`

## 常用启动参数

启用测试模式：

```bash
ros2 launch creative_robot_bringup bringup.launch.py test_mode:=true
```

临时关闭舌象检测：

```bash
ros2 launch creative_robot_bringup bringup.launch.py enable_tongue_diagnosis:=false
```

指定自定义舌诊模型目录：

```bash
ros2 launch creative_robot_bringup bringup.launch.py tongue_model_dir:=/your/model/bin
```

指定其他 USB 摄像头设备：

```bash
ros2 launch creative_robot_bringup bringup.launch.py usb_video_device:=/dev/video0
```

查看全部 bringup 参数：

```bash
ros2 launch creative_robot_bringup bringup.launch.py --show-args
```

## 运行关系

- `hobot_usb_cam` 提供图像流
- `qt_display` 消费图像并驱动用户可见的业务流程
- `qt_display` 通过 `/sql_operation` 与 `sql_server` 通信
- `connector` 负责 ROS2 与 UART / MCU 之间的桥接
- `tongue_diagnosis` 负责舌象分析的推理路径
- 健康结果会写回数据库，并继续参与后续推荐逻辑

## 数据与持久化

数据库相关文件：

- 数据库文件：`database/my_fridge`
- schema 文件：`database/schema.sql`

当前运行中最关键的持久化表包括：

- `ingredients`
- `health_status_history`

如果要修改 schema、迁移脚本或持久化数据，强烈建议先备份数据库。

## 关键配置文件

- 整机启动入口：`src/creative_robot_bringup/launch/bringup.launch.py`
- 界面启动入口：`src/qt_display/launch/qtapp.launch.py`
- 数据库服务启动入口：`src/sql_server/launch/sql_server.launch.py`
- 设备桥接启动入口：`src/connector/launch/connector.launch.py`
- 舌诊启动入口：`src/tongue_diagnosis/launch/tongue_diagnosis.launch.py`
- 云端 / 模型相关配置：`src/qt_display/qt_display/config.py`

## 环境说明

- 推荐 ROS2 发行版：Humble
- 项目是 Python / C++ 混合工作区
- 舌诊部分依赖 RDK X5 相关运行时和 `.bin` 模型文件
- 默认 USB 摄像头设备为 `/dev/video8`

## 实际建议

- 日常运行优先使用 `creative_robot_bringup`
- 部署到新环境时，优先检查摄像头设备路径、舌诊模型目录、云端配置和数据库文件权限
