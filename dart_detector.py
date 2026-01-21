#coding=utf-8
"""
工业相机实时飞镖头检测
识别红色发光的飞镖头，区分背景中的灯光
操作：
  q - 退出
  s - 保存当前检测结果
  + - 增加面积阈值
  - - 减少面积阈值
"""
import cv2
import numpy as np
import sys
sys.path.append('python_demo')
import mvsdk
import platform
import time
from datetime import datetime
import json
import os

def save_config(start_point, config_file='dart_detector_config.json'):
    """保存起始点配置到JSON文件"""
    config = {'start_point': start_point}
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"保存配置失败: {e}")

def load_config(config_file='dart_detector_config.json'):
    """从JSON文件加载起始点配置"""
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get('start_point')
        except Exception as e:
            print(f"加载配置失败: {e}")
    return None

def main():
    print("飞镖头检测启动中...")
    
    # 枚举相机
    DevList = mvsdk.CameraEnumerateDevice()
    nDev = len(DevList)
    if nDev < 1:
        print("错误：未找到相机！")
        return

    # 直接使用第一个相机
    DevInfo = DevList[0]
    print(f"使用相机: {DevInfo.GetFriendlyName()}")

    # 打开相机
    try:
        hCamera = mvsdk.CameraInit(DevInfo, -1, -1)
    except mvsdk.CameraException as e:
        print(f"初始化失败: {e.message}")
        return

    try:
        cap = mvsdk.CameraGetCapability(hCamera)
        monoCamera = (cap.sIspCapacity.bMonoSensor != 0)
        
        if monoCamera:
            print("错误：需要彩色相机！")
            return

        # 设置最小分辨率
        try:
            target_index = cap.sResolutionRange.iImageSizeDesc - 1
            min_pixels = float('inf')
            for i in range(cap.sResolutionRange.iImageSizeDesc):
                desc = cap.pImageSizeDesc[i]
                pixels = desc.iWidth * desc.iHeight
                if pixels < min_pixels:
                    min_pixels = pixels
                    target_index = i
            
            if target_index >= 0:
                mvsdk.CameraSetImageResolution(hCamera, cap.pImageSizeDesc[target_index])
        except:
            pass  # 忽略错误，使用默认分辨率

        # 设置输出格式为BGR8
        mvsdk.CameraSetIspOutFormat(hCamera, mvsdk.CAMERA_MEDIA_TYPE_BGR8)

        # 连续采集模式
        mvsdk.CameraSetTriggerMode(hCamera, 0)

        # 自动曝光
        auto_exposure = True
        exposure_time = 50 * 1000
        mvsdk.CameraSetAeState(hCamera, 1)

        # 开始采集
        mvsdk.CameraPlay(hCamera)

        # 分配缓存
        FrameBufferSize = cap.sResolutionRange.iWidthMax * cap.sResolutionRange.iHeightMax * 3
        pFrameBuffer = mvsdk.CameraAlignMalloc(FrameBufferSize, 16)
        
        # 视频录制变量
        video_writer = None
        recording = False
        record_filename = None

        # 轨迹追踪变量
        trajectory_points = []  # 存储飞镖头中心点轨迹
        max_trajectory_length = 100  # 最多保存100个点
        
        # 起始点相关变量
        loaded_start_point = load_config()
        start_point = tuple(loaded_start_point) if loaded_start_point and isinstance(loaded_start_point, list) and len(loaded_start_point) == 2 else None
        start_point_radius = 70  # 起始点触发半径
        start_point_triggered = False if start_point else True  # 如果没有起始点，直接启用追踪
        
        if start_point:
            print(f"已加载起始点: {start_point}")

        # 红色的HSV阈值范围（红色在HSV中分为两段）
        # 红色1: 0-10度
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        # 红色2: 170-180度
        lower_red2 = np.array([170, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        
        # 飞镖头的特征阈值（可调）
        min_area = 300  # 最小面积（降低以提高灵敏度）
        max_area = 10000  # 最大面积（排除太大的区域）
        # 取消长宽比限制，让所有形状都能通过
        min_aspect_ratio = 0.1  # 极小值，基本不限制
        max_aspect_ratio = 10.0  # 极大值，基本不限制

        # 性能计数
        fps_time = time.time()
        fps_counter = 0
        fps = 0

        # 创建窗口
        window_name = "飞镖头检测"
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
        
        print("检测开始 [q]退出 [s]保存 [r]录制 [c]清空轨迹和起始点")

        while True:
            try:
                # 获取图像
                pRawData, FrameHead = mvsdk.CameraGetImageBuffer(hCamera, 200)
                mvsdk.CameraImageProcess(hCamera, pRawData, pFrameBuffer, FrameHead)
                mvsdk.CameraReleaseImageBuffer(hCamera, pRawData)

                if platform.system() == "Windows":
                    mvsdk.CameraFlipFrameBuffer(pFrameBuffer, FrameHead, 1)
                
                # 转换为numpy数组
                frame_data = (mvsdk.c_ubyte * FrameHead.uBytes).from_address(pFrameBuffer)
                frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = frame.reshape((FrameHead.iHeight, FrameHead.iWidth, 3))
                
                # 镜像翻转（左右翻转）
                frame = cv2.flip(frame, 1)

                # 如果起始点还没有设置，在右下角创建
                if start_point is None:
                    start_point = (int(FrameHead.iWidth * 0.85), int(FrameHead.iHeight * 0.85))
                    save_config(start_point)
                    print(f"起始点已创建在右下角: {start_point}")

                # 计算FPS
                fps_counter += 1
                if time.time() - fps_time > 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_time = time.time()

                # === 性能优化：缩小图像用于检测 ===
                # 将图像缩小到1/2进行检测，大幅提升速度
                detect_frame = cv2.resize(frame, (FrameHead.iWidth // 2, FrameHead.iHeight // 2), 
                                         interpolation=cv2.INTER_LINEAR)
                scale_factor = 2  # 缩放倍数

                # === 红色发光飞镖头检测 ===
                
                # 1. 转换到HSV颜色空间
                hsv = cv2.cvtColor(detect_frame, cv2.COLOR_BGR2HSV)
                
                # 2. 检测红色（两个范围的掩模合并）
                mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
                mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
                mask = cv2.bitwise_or(mask1, mask2)
                
                # 3. 形态学操作，去除噪声
                kernel = np.ones((3, 3), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                
                # 4. 查找轮廓
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 5. 分析轮廓，识别飞镖头
                detected_objects = 0
                dart_candidates = []
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    
                    # 面积过滤（注意：面积也要除以scale_factor^2）
                    scaled_min_area = min_area / (scale_factor * scale_factor)
                    scaled_max_area = max_area / (scale_factor * scale_factor)
                    if area < scaled_min_area or area > scaled_max_area:
                        continue
                    
                    # 获取边界框（在缩小的图像上）
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # 计算长宽比
                    aspect_ratio = max(w, h) / (min(w, h) + 1e-5)
                    
                    # 长宽比过滤（几乎不过滤，只排除极端异常的）
                    # 只有极端细长的才会被灰色框标记
                    if aspect_ratio > 15.0:  # 只过滤极端异常的长宽比
                        # 映射回原图坐标并绘制灰色框
                        x_orig, y_orig = x * scale_factor, y * scale_factor
                        w_orig, h_orig = w * scale_factor, h * scale_factor
                        cv2.rectangle(frame, (x_orig, y_orig), (x_orig + w_orig, y_orig + h_orig), (128, 128, 128), 1)
                        continue
                    
                    # 计算圆形度（4*pi*area / perimeter^2，圆形接近1）
                    perimeter = cv2.arcLength(contour, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                    else:
                        circularity = 0
                    
                    detected_objects += 1
                    
                    # 映射回原图坐标
                    x_orig, y_orig = x * scale_factor, y * scale_factor
                    w_orig, h_orig = w * scale_factor, h * scale_factor
                    
                    # 绘制绿色矩形框表示检测到的飞镖头
                    cv2.rectangle(frame, (x_orig, y_orig), (x_orig + w_orig, y_orig + h_orig), (0, 255, 0), 2)
                    
                    # 计算中心点（原图坐标）
                    cx = x_orig + w_orig // 2
                    cy = y_orig + h_orig // 2
                    cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                    
                    # 显示详细信息
                    text1 = f"DART ({cx},{cy})"
                    text2 = f"A:{int(area * scale_factor * scale_factor)} R:{aspect_ratio:.2f}"
                    cv2.putText(frame, text1, (x_orig, y_orig - 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                    cv2.putText(frame, text2, (x_orig, y_orig - 5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
                    
                    dart_candidates.append({
                        'center': (cx, cy),
                        'area': area * scale_factor * scale_factor,
                        'aspect_ratio': aspect_ratio,
                        'circularity': circularity
                    })
                
                # 检查是否经过起始点（如果设置了起始点）
                if start_point is not None and not start_point_triggered and detected_objects > 0 and dart_candidates:
                    cx, cy = dart_candidates[0]['center']
                    distance_to_start = np.sqrt((cx - start_point[0])**2 + (cy - start_point[1])**2)
                    
                    if distance_to_start < start_point_radius:
                        # 飞镖经过起始点，开始追踪
                        start_point_triggered = True
                        trajectory_points.clear()
                        trajectory_points.append((cx, cy))
                        print(f"飞镖经过起始点！开始追踪")
                
                # 更新轨迹点（只在触发后记录）
                if start_point_triggered and detected_objects > 0 and dart_candidates:
                    # 添加当前帧的第一个飞镖头中心点
                    trajectory_points.append(dart_candidates[0]['center'])
                    # 限制轨迹长度
                    if len(trajectory_points) > max_trajectory_length:
                        trajectory_points.pop(0)
                
                # 绘制轨迹线（只在触发后显示）
                if start_point_triggered and len(trajectory_points) > 1:
                    for i in range(1, len(trajectory_points)):
                        # 绘制红色轨迹线，线条粗细为2
                        cv2.line(frame, trajectory_points[i-1], trajectory_points[i], (0, 0, 255), 2)
                
                # 绘制起始点圆圈
                if start_point is not None:
                    color = (0, 255, 0) if start_point_triggered else (0, 255, 255)
                    cv2.circle(frame, start_point, start_point_radius, color, 2)
                    cv2.circle(frame, start_point, 5, color, -1)
                    label = "START (OK)" if start_point_triggered else "START POINT"
                    cv2.putText(frame, label, (start_point[0] - 40, start_point[1] - start_point_radius - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                # 在原图上绘制信息，避免缩放后文字模糊
                cv2.putText(frame, f"FPS: {fps}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(frame, f"Darts: {detected_objects}", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Area: {min_area}-{max_area}", (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # 显示录制状态
                if recording:
                    cv2.circle(frame, (FrameHead.iWidth - 30, 30), 10, (0, 0, 255), -1)
                    cv2.putText(frame, "REC", (FrameHead.iWidth - 60, 35), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                # 录制视频
                if recording and video_writer is not None:
                    video_writer.write(frame)
                
                # 缩小显示窗口到320x240以提升显示性能
                display_frame = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)
                
                cv2.imshow(window_name, display_frame)
                
                # 键盘控制
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    filename = f"dart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(filename, frame)
                elif key == ord('c') or key == ord('C'):
                    # 清空轨迹和起始点
                    trajectory_points.clear()
                    start_point = None
                    start_point_triggered = False  # 重置为未触发状态，等待飞镖经过
                    save_config(None)
                    print("已清空轨迹和起始点")
                elif key == ord('r') or key == ord('R'):
                    if not recording:
                        record_filename = f"dart_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                        # 使用固定帧率10，避免视频加速
                        video_writer = cv2.VideoWriter(record_filename, fourcc, 10, 
                                                      (FrameHead.iWidth, FrameHead.iHeight))
                        recording = True
                    else:
                        recording = False
                        if video_writer is not None:
                            video_writer.release()
                            video_writer = None
                
            except mvsdk.CameraException as e:
                if e.error_code != mvsdk.CAMERA_STATUS_TIME_OUT:
                    print(f"相机错误: {e.message}")

    finally:
        if video_writer is not None:
            video_writer.release()
        mvsdk.CameraUnInit(hCamera)
        mvsdk.CameraAlignFree(pFrameBuffer)
        cv2.destroyAllWindows()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cv2.destroyAllWindows()
