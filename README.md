# Dart 2025 Trajectory Detection System

实时飞镖轨迹检测与追踪系统，基于工业相机和OpenCV开发，用于树莓派3B+平台。

## 树莓派性能监控（开发者备忘）

### 检查供电状态
```bash
vcgencmd get_throttled
```

**输出含义**：
- `0x0` - 从未欠压（正常）
- `0x50000` - 曾经欠压
- `0x50005` - 曾经 + 现在都在欠压（需要更换电源）

### 实时监控CPU频率
```bash
watch -n 1 vcgencmd measure_clock arm
```

**说明**：
- 欠压会导致CPU降频，影响检测性能
- 建议使用5V/3A以上的电源适配器
- USB相机会增加功耗，确保供电充足

## 功能特性

- 🎯 **红色飞镖头实时检测**：基于HSV颜色空间的红色发光物体识别
- 📊 **轨迹追踪**：自动记录飞镖移动路径，绘制红色轨迹线
- 🎬 **视频录制**：支持实时录制检测过程为MP4格式
- ⚡ **性能优化**：
  - 检测分辨率降低50%，提升处理速度
  - 显示窗口缩放至320x240，优化显示性能
  - 自动选择相机最小分辨率preset
  - 约10 FPS实时帧率（树莓派3B+）
- 🎮 **起始点触发**：设置起始圆，只有飞镖经过时才开始追踪
- 🔄 **镜像翻转**：视频左右镜像显示

## 硬件要求

- **主控**：Raspberry Pi 3B+（或更高性能的树莓派）
- **相机**：MV-SUA133GC（迈德威视USB3.0工业相机）
  - 分辨率：1280x1024（自动降至最小preset）
  - 接口：USB 3.0
  - 彩色相机
- **系统**：Linux (Raspbian/Raspberry Pi OS)

## 软件依赖

```bash
# Python 3
sudo apt-get install python3 python3-pip

# OpenCV
pip3 install opencv-python==4.6.0
pip3 install numpy

# 工业相机SDK (mvsdk)
# 请从迈德威视官网下载并安装对应的Linux SDK
```

## 项目结构

```
dart_vision/
├── dart_detector.py              # 主程序：飞镖检测与轨迹追踪
├── dart_detector_config.json     # 配置文件：起始点坐标
├── python_demo/                  # 相机SDK示例代码
│   ├── mvsdk.py                  # 相机SDK Python接口
│   ├── cv_grab.py                # OpenCV采集示例
│   └── ...                       # 其他示例
├── Camera/                       # 相机配置文件夹
│   └── Data/                     # 相机标定数据
├── output/                       # 输出文件夹
│   └── videos/                   # 录制的视频文件
├── docs/                         # 文档文件夹
├── archive/                      # 归档/旧代码
└── README.md                     # 本文档
```

## 快速开始

### 1. 安装依赖

确保已安装OpenCV和相机SDK：

```bash
cd /home/rickxu/dart_vision
pip3 install opencv-python numpy
```

### 2. 运行程序

```bash
sudo python3 dart_detector.py
```

> **注意**：需要sudo权限以访问USB相机设备

### 3. 操作说明

**键盘控制**：
- `q` - 退出程序
- `s` - 保存当前检测结果截图
- `r` - 开始/停止录制视频
- `c` - 清空轨迹和起始点

**运行流程**：
1. 程序启动后自动在右下角（画面85%位置）创建起始圆（黄色）
2. 飞镖进入起始圆范围（半径50像素）时，圆圈变绿，开始追踪
3. 红色轨迹线自动记录飞镖头移动路径（最多保存100个点）
4. 按 `r` 键可录制整个过程，视频保存在 `output/videos/` 目录

## 检测参数

### 颜色检测（HSV空间）
```python
# 红色范围1: 0-10°
lower_red1 = [0, 100, 100]
upper_red1 = [10, 255, 255]

# 红色范围2: 170-180°
lower_red2 = [170, 100, 100]
upper_red2 = [180, 255, 255]
```

### 物体过滤
```python
min_area = 300        # 最小面积（像素²）
max_area = 10000      # 最大面积
aspect_ratio < 15.0   # 长宽比阈值（排除极端细长物体）
```

### 起始点配置
```python
start_point_radius = 50    # 触发半径（像素）
default_position = (85%, 85%)  # 默认位置（右下角）
```

## 配置文件

`dart_detector_config.json` 保存起始点坐标：

```json
{
  "start_point": [272, 218]
}
```

- 按 `c` 键会清空配置并重新在右下角创建
- 程序启动时自动加载上次的起始点位置

## 性能调优

### 树莓派3B+优化建议

1. **降低相机分辨率**：程序自动选择最小preset
2. **检测分辨率**：已设置为实际分辨率的1/2
3. **显示分辨率**：固定320x240窗口
4. **录制帧率**：固定10 FPS，避免加速问题

### 预期性能
- **实时FPS**：~10 FPS
- **启动时间**：<5秒
- **检测延迟**：<100ms

## 输出文件

### 视频文件
- **格式**：MP4 (mp4v编码)
- **帧率**：10 FPS
- **分辨率**：相机原始分辨率
- **命名**：`dart_video_YYYYMMDD_HHMMSS.mp4`
- **位置**：`output/videos/`

### 截图文件
- **格式**：JPG
- **命名**：`dart_YYYYMMDD_HHMMSS.jpg`
- **位置**：当前目录

## 故障排查

### 相机未找到
```
错误：未找到相机！
```
**解决**：
- 检查USB连接
- 确认相机电源
- 使用sudo运行：`sudo python3 dart_detector.py`

### 启动慢/卡顿
**解决**：
- 已优化启动流程，移除冗余打印
- 确保树莓派散热良好
- 关闭其他占用CPU的程序

### 检测不准确
**解决**：
- 调整 `min_area` 参数（第115行）
- 检查光照条件（需要红色发光飞镖头）
- 确认HSV阈值适合你的环境

## 开发说明

### 核心算法

1. **颜色检测**：HSV颜色空间 + 双范围红色检测
2. **形态学操作**：开运算去噪 + 闭运算填充
3. **轮廓过滤**：面积 + 长宽比
4. **轨迹追踪**：FIFO队列（最多100点）+ 起始点触发

### 代码结构

```python
main()
├── 相机初始化
├── 配置加载
├── 主循环
│   ├── 获取帧 + 镜像翻转
│   ├── 起始点创建（首次）
│   ├── HSV颜色检测
│   ├── 轮廓分析
│   ├── 起始点触发检测
│   ├── 轨迹记录与绘制
│   └── 显示 + 录制
└── 清理资源
```

## 版本历史

### v2.0 (2026-01-21)
- ✅ 完全重写检测系统
- ✅ 添加轨迹追踪功能
- ✅ 实现起始点触发机制
- ✅ 优化启动速度（<5秒）
- ✅ 添加视频镜像功能
- ✅ 修复视频加速问题
- ✅ 移除鼠标交互（简化操作）

### v1.0 (Earlier)
- 基础相机采集
- 简单物体检测

## 贡献者

- **开发者**：ZongyuanYeeeeeeeeeah /  JoeyLiu
- **组织**：Illini RoboMaster
- **项目**：Dart 2025 Trajectory Detection

## 许可证

MIT License

## 相关链接

- GitHub仓库：https://github.com/illini-robomaster/dart_2025_trajectory
- 迈德威视相机SDK：http://www.mindvision.com.cn/

---

**最后更新**：2026-01-21
