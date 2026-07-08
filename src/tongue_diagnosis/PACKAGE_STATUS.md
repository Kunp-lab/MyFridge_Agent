# tongue_diagnosis 包创建完成

## 📦 包结构概览

```
src/tongue_diagnosis/
├── bin/                                    # 5个量化模型 (121MB总)
│   ├── yolo_seg2_bayese_640x640_nv12.bin         # YOLO26分割模型 (3.9MB)
│   ├── tongue_color_bayese_224x224_nv12.bin      # ResNet - 舌质色分类
│   ├── tongue_coat_color_bayese_224x224_nv12.bin # ResNet - 舌苔色分类
│   ├── thickness_bayese_224x224_nv12.bin         # ResNet - 厚度分类
│   └── rot_and_greasy_bayese_224x224_nv12.bin    # ResNet - 腻腐分类
│
├── launch/
│   └── tongue_diagnosis.launch.py          # ROS2 launch配置
│
├── tongue_diagnosis/                       # Python包源代码
│   ├── __init__.py                         # 包初始化
│   ├── tongue_diagnosis_node.py            # 主节点（265行）
│   ├── yolov26seg.py                       # YOLO26分割模块（已迁移）
│   ├── resnet.py                           # ResNet分类模块（已迁移）
│   └── utils.py                            # 工具函数
│
├── resource/                               # ROS2资源
├── package.xml                             # 包元数据
├── setup.py                                # Python安装配置
├── setup.cfg                               # Python构建配置
└── README.md                               # 详细文档
```

## ✅ 已完成的工作

### 1. 包结构初始化
- [x] 创建ROS2 Python包框架
- [x] 配置setup.py/setup.cfg/package.xml
- [x] 声明entry_point: tongue_diagnosis_node

### 2. 模型文件迁移
- [x] 复制5个量化.bin模型文件
- [x] 复制yolov26seg.py（YOLO26分割模块）
- [x] 复制resnet.py（ResNet分类模块）

### 3. 主节点实现
- [x] TongueDiagnosisNode - 主ROS2节点
- [x] MQTT连接与话题订阅（tongue/predict）
- [x] 图像解码和预处理
- [x] YOLO26分割执行
- [x] 4个ResNet模型并行推理
- [x] MQTT结果发布（tongue/result/{record_id}）

### 4. Launch配置
- [x] tongue_diagnosis.launch.py
- [x] 支持参数化配置（broker_ip, broker_port等）

### 5. 文档
- [x] README.md - 完整使用指南
- [x] 代码注释和类型提示

## 🔄 MQTT通信架构

```
Display节点（RDK）              tongue_diagnosis节点
─────────────────────          ─────────────────────

调用 StartTongueDiagnosis()
    ↓ 拍摄舌象图像
    ↓ 编码为JPEG
    ↓ MQTT发布到 tongue/predict
                               ↓ 订阅 tongue/predict
                               ↓ on_message回调触发
                               ↓ _process_tongue_image()
                               ├─ 图像解码
                               ├─ YOLO26分割
                               ├─ 提取masked region
                               ├─ 4x ResNet分类
                               ├─ 格式化结果JSON
                               ↓ MQTT发布到 tongue/result/{record_id}
    
    ↓ on_message接收舌诊结果
    ↓ 显示到Qt界面
```

## 📋 后续工作清单

### Phase 1: 基础功能验证（已完成）
- [x] 包结构创建
- [x] 模型文件迁移
- [x] 主节点框架实现

### Phase 2: 集成与测试（待进行）
- [ ] 修改display_node.py发送逻辑（从PC-MQTT改为RDK本地MQTT）
- [ ] 在RDK上运行包进行推理测试
- [ ] 验证4个ResNet的推理结果
- [ ] 性能基准测试（推理时间、内存占用）

### Phase 3: 优化与部署（待进行）
- [ ] RDK多核BPU调度优化
- [ ] 错误处理和日志完善
- [ ] 健康检测（心跳、模型加载状态）

## 🚀 快速使用

### 构建
```bash
cd ~/TrosWork/CreativeRobot
colcon build --packages-select tongue_diagnosis
source install/setup.bash
```

### 运行
```bash
# 默认参数（本地MQTT broker）
ros2 launch tongue_diagnosis tongue_diagnosis.launch.py

# 自定义broker地址
ros2 launch tongue_diagnosis tongue_diagnosis.launch.py broker_ip:=192.168.x.x
```

## 📝 关键代码位置

- **主节点初始化**: tongue_diagnosis_node.py::TongueDiagnosisNode.__init__()
- **模型加载**: tongue_diagnosis_node.py::_init_models()
- **MQTT连接**: tongue_diagnosis_node.py::_init_mqtt_client()
- **推理流程**: tongue_diagnosis_node.py::_process_tongue_image()
- **4D分类**: tongue_diagnosis_node.py::_run_4d_classification()
- **结果发布**: tongue_diagnosis_node.py::_publish_result()

## 💡 技术细节

### 推理管道
1. **输入**: MQTT接收原始JPEG二进制
2. **解码**: cv2.imdecode() → BGR图像
3. **分割**: YOLO26Seg.predict() → 舌头mask
4. **分类**: 
   - ResNet(tongue_color): 5分类 (0-4)
   - ResNet(coating_color): 3分类 (0-2)
   - ResNet(thickness): 2分类 (0-1)
   - ResNet(rot_greasy): 2分类 (0-1)
5. **输出**: JSON格式MQTT发布

### 多线程设计
- MQTT接收线程：独立运行，避免阻塞
- 推理线程：后台执行，支持并发处理多张图像

### 错误处理
- 图像解码失败 → code=202
- 舌头未检测 → code=201
- 推理成功 → code=1

---

**编译状态**: ✅ 编译通过  
**测试状态**: ⏳ 待在RDK上验证  
**备份状态**: ✅ git标签v1.0-base
