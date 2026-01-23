# 绿色引导灯检测调试指南

## 功能说明
新版本添加了绿色引导灯检测功能，只有在检测到绿灯时才会进行飞镖头检测。

## 绿灯规格
- 波长：520-530nm
- 功率：30W
- HSV范围：H=55-65°, S=100-255, V=150-255

## 检测逻辑
1. **优先检测绿灯**：系统首先在画面中寻找绿色LED
2. **条件触发**：只有检测到绿灯后，才会进行红色飞镖头检测
3. **状态显示**：
   - 左上角显示 "GREEN: ON" (绿色) - 检测到绿灯
   - 左上角显示 "GREEN: OFF" (红色) - 未检测到绿灯
4. **视觉标记**：
   - 绿灯用**青色框**标记
   - 飞镖头用**绿色框**标记

## 调试步骤

### 1. 初次测试
```bash
sudo python dart_detector.py
```

观察画面左上角的绿灯状态指示器。

### 2. 如果绿灯检测不到

可能原因和解决方案：

#### A. HSV范围不匹配
30W高亮绿LED可能偏黄或偏蓝，需要调整HSV范围：

在代码中找到这一行（约第147行）：
```python
lower_green = np.array([55, 100, 150])
upper_green = np.array([65, 255, 255])
```

调整建议：
- **如果LED偏黄绿**：`lower_green = np.array([45, 100, 150])`
- **如果LED偏蓝绿**：`upper_green = np.array([75, 255, 255])`
- **如果亮度不够**：降低V值 `lower_green = np.array([55, 100, 100])`
- **如果太敏感**：提高S值 `lower_green = np.array([55, 150, 150])`

#### B. 面积阈值不合适
在代码中找到这一行（约第151行）：
```python
green_min_area = 100  # 绿灯最小面积
green_max_area = 5000  # 绿灯最大面积
```

调整建议：
- 如果绿灯太小无法检测：降低 `green_min_area = 50`
- 如果绿灯太大被过滤：增大 `green_max_area = 10000`

### 3. 调试工具
可以使用 `dart_detector_headless.py` 进行快速测试：
```bash
sudo python dart_detector_headless.py
```

该版本输出英文信息，方便观察帧率和检测状态。

### 4. HSV颜色查看
如果不确定绿LED的HSV值，可以用以下代码测试：
```python
import cv2
import numpy as np

# 假设绿LED的BGR颜色大约是 (0, 255, 0)
green_bgr = np.uint8([[[0, 255, 100]]])  # 调整这个值
green_hsv = cv2.cvtColor(green_bgr, cv2.COLOR_BGR2HSV)
print(f"HSV: {green_hsv[0][0]}")
```

### 5. 实时调整（高级）
如果需要频繁调试，可以在代码中添加trackbar：
```python
def nothing(x):
    pass

cv2.createTrackbar('H_min', window_name, 55, 180, nothing)
cv2.createTrackbar('H_max', window_name, 65, 180, nothing)
cv2.createTrackbar('S_min', window_name, 100, 255, nothing)
cv2.createTrackbar('V_min', window_name, 150, 255, nothing)

# 在循环中读取
h_min = cv2.getTrackbarPos('H_min', window_name)
h_max = cv2.getTrackbarPos('H_max', window_name)
# ...
lower_green = np.array([h_min, s_min, v_min])
```

## 常见问题

**Q: 为什么绿灯检测到了但不显示飞镖？**  
A: 可能是曝光时间设置导致红色过饱和。当前手动曝光20ms可能对30W绿灯太亮，可以尝试降低曝光时间到10ms。

**Q: 绿灯闪烁检测不稳定？**  
A: 30W LED可能有AC纹波。解决方法：
1. 增加形态学操作的kernel大小
2. 添加时间滤波（连续N帧检测到才判定为有效）

**Q: 会不会误检测背景绿光？**  
A: 使用面积阈值过滤，只检测第一个符合条件的绿色区域。

## 性能影响
绿灯检测采用与飞镖检测相同的优化策略（640x480 + 缩放检测），对帧率影响很小（<5 FPS）。

预期性能：
- 纯采集：80+ FPS
- 仅绿灯检测：75+ FPS
- 绿灯+飞镖检测：40+ FPS

## 下一步优化
如果需要更高精度的绿灯检测，可以考虑：
1. 使用Lab颜色空间（对光照变化更鲁棒）
2. 添加亮度梯度检测（LED中心最亮）
3. 使用Blob检测器检测圆形LED
