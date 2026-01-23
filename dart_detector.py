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

def load_green_led_config(config_file='green_led_config.json'):
    """从JSON文件加载绿色LED检测配置"""
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            green_config = config.get('green_led', {})
            return {
                'hsv_lower': green_config.get('hsv_lower', [35, 50, 50]),
                'hsv_upper': green_config.get('hsv_upper', [90, 255, 255]),
                'area_min': green_config.get('area_min', 100),
                'area_max': green_config.get('area_max', 5000)
            }
        except Exception as e:
            print(f"加载绿灯配置失败: {e}，使用默认值")
    return None

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

        # 设置640x480分辨率（优化性能）
        try:
            custom_res = mvsdk.tSdkImageResolution()
            custom_res.iIndex = 0xff
            custom_res.iWidth = 640
            custom_res.iHeight = 480
            custom_res.iWidthFOV = 640
            custom_res.iHeightFOV = 480
            custom_res.iHOffsetFOV = 0
            custom_res.iVOffsetFOV = 0
            custom_res.iWidthZoomSw = 0
            custom_res.iHeightZoomSw = 0
            custom_res.iWidthZoomHd = 0
            custom_res.iHeightZoomHd = 0
            custom_res.uBinSumMode = 0
            custom_res.uBinAverageMode = 0
            custom_res.uSkipMode = 0
            custom_res.uResampleMask = 0
            
            mvsdk.CameraSetImageResolution(hCamera, custom_res)
            print(f"✓ 已设置分辨率: 640x480")
        except Exception as e:
            print(f"⚠ 设置分辨率失败: {e}")
            pass

        # 设置输出格式为BGR8
        mvsdk.CameraSetIspOutFormat(hCamera, mvsdk.CAMERA_MEDIA_TYPE_BGR8)

        # 连续采集模式
        mvsdk.CameraSetTriggerMode(hCamera, 0)

        # 手动曝光（关键优化：避免AE限制帧率）
        mvsdk.CameraSetAeState(hCamera, 0)  # 关闭自动曝光
        mvsdk.CameraSetExposureTime(hCamera, 20000)  # 20000us = 20ms
        print(f"曝光模式: 手动 5ms")

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
        trajectory_points = []  # 当前飞镖头中心点轨迹
        max_trajectory_length = 100  # 最多保存100个点
        
        # 多飞镖追踪
        completed_trajectories = []  # 已完成的轨迹列表，每个元素是一个轨迹点列表
        dart_landing_points = []  # 飞镖落点（与绿灯中心的最近点）
        max_darts = 4  # 最多追踪4个飞镖
        landing_threshold = 20  # 飞镖y坐标接近绿灯中心y坐标的阈值（像素）
        
        # 绿灯中心位置缓存（用于绿灯被遮挡时）
        last_known_green_center = None
        
        # 起始点相关变量
        loaded_start_point = load_config()
        # 如果有旧的起始点坐标，需要检查是否超出当前分辨率范围
        # 假设旧坐标是基于1280x1024，新分辨率是640x480，需要缩放
        if loaded_start_point and isinstance(loaded_start_point, list) and len(loaded_start_point) == 2:
            # 获取当前实际分辨率（第一帧才知道，这里先假设640x480）
            # 如果坐标超出640x480范围，说明是旧坐标，需要缩放
            old_x, old_y = loaded_start_point
            if old_x > 640 or old_y > 480:
                # 按比例缩放 (假设原来是1280x1024)
                new_x = int(old_x * 640 / 1280)
                new_y = int(old_y * 480 / 1024)
                start_point = (new_x, new_y)
                print(f"已缩放起始点: {loaded_start_point} -> {start_point}")
            else:
                start_point = tuple(loaded_start_point)
                print(f"已加载起始点: {start_point}")
        else:
            start_point = None
        
        # 起始区域：画面上半部分的矩形 (x1, y1, x2, y2)
        start_zone = None  # 将在第一帧初始化
        start_zone_triggered = False  # 起始区域触发状态
        
        # 加载绿色LED配置（如果存在）
        green_config = load_green_led_config()
        if green_config:
            lower_green = np.array(green_config['hsv_lower'])
            upper_green = np.array(green_config['hsv_upper'])
            green_min_area = green_config['area_min']
            green_max_area = green_config['area_max']
            print(f"已加载绿灯配置: HSV [{green_config['hsv_lower']}] - [{green_config['hsv_upper']}], Area [{green_min_area}, {green_max_area}]")
        else:
            # 默认绿色引导灯HSV范围（扩大到全部绿色范围）
            lower_green = np.array([35, 50, 50])
            upper_green = np.array([90, 255, 255])
            green_min_area = 100
            green_max_area = 5000
            print("使用默认绿灯参数")
        
        # 红色的HSV阈值范围（红色在HSV中分为两段）
        # 红色1: 0-10度
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        # 红色2: 170-180度
        lower_red2 = np.array([170, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        
        green_light_detected = False  # 绿灯检测状态
        
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

                # 如果起始区域还没有设置，创建为画面上半部分
                if start_zone is None:
                    # 矩形区域: 从画面顶部到中间，全宽
                    start_zone = (0, 0, FrameHead.iWidth, FrameHead.iHeight // 2)
                    print(f"起始区域已创建：画面上半部分 {start_zone}")

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

                # 转换到HSV颜色空间（共用）
                hsv = cv2.cvtColor(detect_frame, cv2.COLOR_BGR2HSV)
                
                # === 1. 绿色引导灯检测（优先） ===
                green_mask = cv2.inRange(hsv, lower_green, upper_green)
                
                # 形态学操作去噪
                kernel = np.ones((3, 3), np.uint8)
                green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)
                green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
                
                # 查找绿灯轮廓
                green_contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                green_light_detected = False
                green_light_center = None
                
                for contour in green_contours:
                    area = cv2.contourArea(contour)
                    scaled_green_min = green_min_area / (scale_factor * scale_factor)
                    scaled_green_max = green_max_area / (scale_factor * scale_factor)
                    
                    # 调试：打印所有绿色轮廓信息
                    if area > 10:  # 只显示面积>10的
                        print(f"[DEBUG] Green contour area: {int(area * scale_factor * scale_factor)} (min:{green_min_area}, max:{green_max_area})")
                    
                    if area >= scaled_green_min and area <= scaled_green_max:
                        green_light_detected = True
                        
                        # 获取绿灯位置
                        x, y, w, h = cv2.boundingRect(contour)
                        x_orig, y_orig = x * scale_factor, y * scale_factor
                        w_orig, h_orig = w * scale_factor, h * scale_factor
                        
                        # 绘制蓝色框标记绿灯
                        cv2.rectangle(frame, (x_orig, y_orig), (x_orig + w_orig, y_orig + h_orig), (255, 255, 0), 2)
                        
                        cx = x_orig + w_orig // 2
                        cy = y_orig + h_orig // 2
                        green_light_center = (cx, cy)
                        cv2.circle(frame, (cx, cy), 5, (255, 255, 0), -1)
                        
                        text = f"GREEN LED ({cx},{cy})"
                        cv2.putText(frame, text, (x_orig, y_orig - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
                        
                        # 更新绿灯位置缓存
                        last_known_green_center = (cx, cy)
                        break  # 只检测第一个绿灯

                # === 2. 红色发光飞镖头检测（仅在检测到绿灯时） ===
                detected_objects = 0
                dart_candidates = []
                
                if green_light_detected:
                
                    # 检测红色（两个范围的掩模合并）
                    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
                    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
                    mask = cv2.bitwise_or(mask1, mask2)
                    
                    # 形态学操作，去除噪声
                    kernel = np.ones((3, 3), np.uint8)
                    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                    
                    # 查找轮廓
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    # 分析轮廓，识别飞镖头
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
                        
                        # 计算圆形度（4*pi*area / perimeter^2，圆形接近1）
                        perimeter = cv2.arcLength(contour, True)
                        if perimeter > 0:
                            circularity = 4 * np.pi * area / (perimeter * perimeter)
                        else:
                            circularity = 0
                        
                        detected_objects += 1
                        
                        # 长宽比过滤（几乎不过滤，只排除极端异常的）
                        # 只有极端细长的才会被灰色框标记
                        if aspect_ratio > 15.0:  # 只过滤极端异常的长宽比
                            # 如果还未完成所有飞镖，才显示灰色框
                            if len(completed_trajectories) < max_darts:
                                # 映射回原图坐标并绘制灰色框
                                x_orig, y_orig = x * scale_factor, y * scale_factor
                                w_orig, h_orig = w * scale_factor, h * scale_factor
                                cv2.rectangle(frame, (x_orig, y_orig), (x_orig + w_orig, y_orig + h_orig), (128, 128, 128), 1)
                            continue
                        
                        # 计算中心点（原图坐标）
                        x_orig, y_orig = x * scale_factor, y * scale_factor
                        w_orig, h_orig = w * scale_factor, h * scale_factor
                        cx = x_orig + w_orig // 2
                        cy = y_orig + h_orig // 2
                        
                        # 只有还未完成所有飞镖追踪时才显示检测框和信息
                        if len(completed_trajectories) < max_darts:
                            # 绘制绿色矩形框表示检测到的飞镖头
                            cv2.rectangle(frame, (x_orig, y_orig), (x_orig + w_orig, y_orig + h_orig), (0, 255, 0), 2)
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
                
                # 检查飞镖是否进入起始区域（画面上半部分）
                if start_zone is not None and not start_zone_triggered and detected_objects > 0 and dart_candidates:
                    cx, cy = dart_candidates[0]['center']
                    x1, y1, x2, y2 = start_zone
                    
                    # 检查飞镖中心是否在矩形区域内
                    if x1 <= cx <= x2 and y1 <= cy <= y2:
                        # 飞镖进入起始区域，开始追踪
                        start_zone_triggered = True
                        trajectory_points.clear()
                        trajectory_points.append((cx, cy))
                        print(f"飞镖进入起始区域！开始追踪")
                
                # 更新轨迹点（只在触发后记录）
                if start_zone_triggered and detected_objects > 0 and dart_candidates:
                    # 添加当前帧的第一个飞镖头中心点
                    cx, cy = dart_candidates[0]['center']
                    trajectory_points.append((cx, cy))
                    
                    # 检查是否到达绿灯中心的水平线（轨迹结束条件）
                    # 使用当前检测到的绿灯位置，如果未检测到则使用缓存位置
                    target_green_center = green_light_center if green_light_detected else last_known_green_center
                    
                    if target_green_center is not None and len(completed_trajectories) < max_darts:
                        gx, gy = target_green_center
                        # 判断飞镖y坐标是否到达绿灯中心的水平线附近
                        if abs(cy - gy) < landing_threshold and cy >= gy - landing_threshold:
                            # 飞镖到达绿灯水平线，轨迹结束
                            status = "(检测到)" if green_light_detected else "(使用缓存)"
                            print(f"飞镖 #{len(completed_trajectories) + 1} 轨迹结束！落点: ({cx}, {cy})，绿灯y坐标: {gy} {status}")
                            
                            # 保存当前轨迹和落点
                            completed_trajectories.append(trajectory_points.copy())
                            dart_landing_points.append((cx, cy))
                            
                            # 重置当前轨迹，等待下一个飞镖
                            trajectory_points.clear()
                            start_zone_triggered = False
                            
                            if len(completed_trajectories) >= max_darts:
                                print(f"已完成所有 {max_darts} 个飞镖追踪！")
                    
                    # 限制当前轨迹长度
                    if len(trajectory_points) > max_trajectory_length:
                        trajectory_points.pop(0)
                
                # 绘制已完成的轨迹和落点
                for idx, completed_traj in enumerate(completed_trajectories):
                    # 绘制已完成的轨迹（蓝色，半透明）
                    if len(completed_traj) > 1:
                        for i in range(1, len(completed_traj)):
                            cv2.line(frame, completed_traj[i-1], completed_traj[i], (255, 0, 0), 1)
                    
                    # 绘制落点（紫色圆圈+编号）
                    if idx < len(dart_landing_points):
                        lx, ly = dart_landing_points[idx]
                        cv2.circle(frame, (lx, ly), 10, (255, 0, 255), 2)
                        cv2.circle(frame, (lx, ly), 3, (255, 0, 255), -1)
                        cv2.putText(frame, f"#{idx+1}", (lx + 15, ly - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                
                # 绘制绿灯水平参考线（如果有绿灯位置）
                ref_green_center = green_light_center if green_light_detected else last_known_green_center
                if ref_green_center is not None:
                    gx, gy = ref_green_center
                    line_color = (0, 255, 255) if green_light_detected else (128, 128, 128)
                    cv2.line(frame, (0, gy), (FrameHead.iWidth, gy), line_color, 1, cv2.LINE_AA)
                    cv2.putText(frame, f"Landing Line (y={gy})", (10, gy - 5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, line_color, 1)
                
                # 绘制当前轨迹线（只在触发后显示，红色）
                if start_zone_triggered and len(trajectory_points) > 1:
                    for i in range(1, len(trajectory_points)):
                        # 绘制红色轨迹线，线条粗细为2
                        cv2.line(frame, trajectory_points[i-1], trajectory_points[i], (0, 0, 255), 2)
                
                # 绘制起始区域矩形（画面上半部分）
                if start_zone is not None:
                    x1, y1, x2, y2 = start_zone
                    color = (0, 255, 0) if start_zone_triggered else (0, 255, 255)
                    # 绘制半透明矩形区域
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
                    cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
                    # 绘制边框
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    label = "ENTRY ZONE (OK)" if start_zone_triggered else "ENTRY ZONE (Waiting)"
                    cv2.putText(frame, label, (x1 + 10, y1 + 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                
                # 在原图上绘制信息，避免缩放后文字模糊
                cv2.putText(frame, f"FPS: {fps}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                # 绿灯状态显示
                green_status = "GREEN: ON" if green_light_detected else "GREEN: OFF"
                green_color = (0, 255, 0) if green_light_detected else (0, 0, 255)
                cv2.putText(frame, green_status, (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, green_color, 2)
                
                cv2.putText(frame, f"Darts: {detected_objects}", (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Completed: {len(completed_trajectories)}/{max_darts}", (10, 120),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
                cv2.putText(frame, f"Area: {min_area}-{max_area}", (10, 150), 
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
                    # 清空所有轨迹、落点和重置触发状态
                    trajectory_points.clear()
                    completed_trajectories.clear()
                    dart_landing_points.clear()
                    start_zone_triggered = False  # 重置为未触发状态，等待下一次飞镖进入
                    print("已清空所有轨迹和落点，重置触发状态")
                elif key == ord('r') or key == ord('R'):
                    if not recording:
                        record_filename = f"dart_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                        # 使用固定帧率10
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
