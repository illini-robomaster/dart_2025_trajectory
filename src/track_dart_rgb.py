import cv2
import numpy as np
from collections import deque
import json
import os

def nothing(x):
    pass

def save_config(params, config_file='dart_track_config.json'):
    """保存参数配置到JSON文件"""
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(params, f, indent=2, ensure_ascii=False)
    print(f"\n参数已保存到配置文件: {config_file}")

def load_config(config_file='dart_track_config.json'):
    """从JSON文件加载参数配置"""
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                params = json.load(f)
            print(f"已从配置文件加载参数: {config_file}")
            return params
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return None
    return None

def track_dart_rgb_interactive():
    """
    使用RGB颜色空间追踪飞镖
    """
    video_path = "f2c1d23f0f9186952eb6d78e283ffc0b_raw.mp4"
    
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return
    
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"视频信息: {width}x{height}, {fps}FPS, {total_frames}帧")
    
    # 创建窗口 - 合并窗口显示tracking和mask
    cv2.namedWindow('Dart Tracking', cv2.WINDOW_NORMAL)
    cv2.namedWindow('Controls', cv2.WINDOW_NORMAL)
    
    # 设置合并窗口的初始大小（左右并排，宽度翻倍）
    cv2.resizeWindow('Dart Tracking', width * 2, height)
    
    # 创建一个大的控制面板背景，显示参数说明
    control_panel = np.zeros((900, 700, 3), dtype=np.uint8)
    cv2.putText(control_panel, "=== Dart Tracking Parameters ===", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    # 添加参数说明文字
    params_help = [
        "",
        "COLOR DETECTION (RGB):",
        "  R_min/max: Red channel range (100-255 for yellow)",
        "  G_min/max: Green channel range (100-255 for yellow)",
        "  B_min/max: Blue channel range (0-150 for yellow)",
        "  RG_ratio: R/G similarity (80-100, closer to 100 = more similar)",
        "  RB_diff: R-B difference (50-100, yellow has high R-B)",
        "",
        "SIZE FILTERING:",
        "  Min_Area: Minimum contour area (pixels)",
        "  Max_Area: Maximum contour area (pixels)",
        "",
        "MOTION DETECTION:",
        "  Min_Motion: Total movement to trigger tracking (pixels)",
        "  Motion_Frames: Frames to observe before tracking (2-10)",
        "  Max_Jump: Max allowed jump distance during tracking",
        "",
        "REGION EXCLUSION:",
        "  Exclude_Right: Exclude right side (X > value)",
        "  Exclude_Bottom: Exclude bottom area (Y > value)",
        "",
        "PLAYBACK:",
        "  PlaySpeed: Video playback speed (1=slowest, 10=fastest)",
    ]
    
    y_pos = 60
    for text in params_help:
        if text.startswith("  "):
            cv2.putText(control_panel, text, (40, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        elif text == "":
            pass
        else:
            cv2.putText(control_panel, text, (20, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_pos += 25
    
    cv2.imshow('Controls', control_panel)
    cv2.resizeWindow('Controls', 700, 900)
    
    # 加载保存的配置（如果存在）
    saved_config = load_config()
    
    # 设置默认参数值（如果有保存的配置则使用保存的值）
    default_params = {
        'R_min': 77, 'R_max': 246, 'G_min': 105, 'G_max': 255,
        'B_min': 0, 'B_max': 150, 'Min_Area': 26, 'Max_Area': 1906,
        'RG_ratio': 23, 'RB_diff': 70, 'Max_Jump': 158,
        'Exclude_Right': 582, 'Exclude_Bottom': 514, 'PlaySpeed': 2,
        'Min_Motion': 27, 'Motion_Frames': 2
    }
    
    # 如果有保存的配置，使用保存的值覆盖默认值
    if saved_config:
        default_params.update(saved_config)
    
    # 创建控制滑动条 - RGB范围（使用用户调整的默认值）
    # 黄色在RGB中: R高, G高, B低
    cv2.createTrackbar('R_min', 'Controls', default_params['R_min'], 255, nothing)
    cv2.createTrackbar('R_max', 'Controls', default_params['R_max'], 255, nothing)
    cv2.createTrackbar('G_min', 'Controls', default_params['G_min'], 255, nothing)
    cv2.createTrackbar('G_max', 'Controls', default_params['G_max'], 255, nothing)
    cv2.createTrackbar('B_min', 'Controls', default_params['B_min'], 255, nothing)
    cv2.createTrackbar('B_max', 'Controls', default_params['B_max'], 255, nothing)
    cv2.createTrackbar('Min_Area', 'Controls', default_params['Min_Area'], 1000, nothing)
    cv2.createTrackbar('Max_Area', 'Controls', default_params['Max_Area'], 5000, nothing)
    cv2.createTrackbar('RG_ratio', 'Controls', default_params['RG_ratio'], 200, nothing)  # R/G比例 (%)
    cv2.createTrackbar('RB_diff', 'Controls', default_params['RB_diff'], 255, nothing)  # R-B差值
    
    # 运动连续性检测
    cv2.createTrackbar('Max_Jump', 'Controls', default_params['Max_Jump'], 500, nothing)  # 最大跳跃距离
    cv2.createTrackbar('Exclude_Right', 'Controls', default_params['Exclude_Right'], width, nothing)  # 排除右侧区域(X坐标)
    cv2.createTrackbar('Exclude_Bottom', 'Controls', default_params['Exclude_Bottom'], height, nothing)  # 排除底部区域(Y坐标)
    cv2.createTrackbar('PlaySpeed', 'Controls', default_params['PlaySpeed'], 10, nothing)  # 播放速度
    cv2.createTrackbar('Min_Motion', 'Controls', default_params['Min_Motion'], 200, nothing)  # 最小移动距离才开始追踪
    cv2.createTrackbar('Motion_Frames', 'Controls', default_params['Motion_Frames'], 10, nothing)  # 连续移动帧数
    
    trajectory = deque(maxlen=500)
    pre_track_positions = deque(maxlen=10)  # 预追踪位置队列
    is_tracking = False  # 是否开始正式追踪
    start_point = None  # 手动标记的起始点
    start_point_triggered = False  # 是否已经触发起始点
    paused = False
    frame_buffer = []
    current_frame_idx = 0
    
    # 预加载所有帧
    print("正在加载视频帧...")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_buffer.append(frame.copy())
    print(f"加载完成，共 {len(frame_buffer)} 帧")
    
    cap.release()
    
    print("\n操作说明:")
    print("空格键: 暂停/播放")
    print("左/右方向键: 上一帧/下一帧（暂停时）")
    print("'r': 重置轨迹")
    print("'s': 保存当前参数和输出视频")
    print("'q': 退出")
    print("'m': 切换模式 (RGB/LAB)")
    print("鼠标左键: 在左侧追踪窗口点击设置起始点（暂停时）")
    print("\nMin_Motion: 检测到连续移动多少像素才开始追踪")
    print("Motion_Frames: 需要连续移动多少帧才判定为飞镖")
    print("Max_Jump: 追踪中最大允许跳跃距离")
    print("Exclude_Right: 排除右侧区域（皮筋位置），设置X坐标阈值\n")
    
    # 鼠标回调函数
    def mouse_callback(event, x, y, flags, param):
        nonlocal start_point, start_point_triggered, is_tracking, trajectory, pre_track_positions
        if event == cv2.EVENT_LBUTTONDOWN and paused:
            # 只在左半部分（tracking区域）响应点击
            if x < width:
                start_point = (x, y)
            start_point_triggered = False
            is_tracking = False
            trajectory.clear()
            pre_track_positions.clear()
            print(f"起始点已设置: ({x}, {y})")
    
    cv2.setMouseCallback('Dart Tracking', mouse_callback)
    
    use_lab = False  # RGB或LAB模式切换
    start_point_radius = 50  # 起始点触发半径
    
    while True:
        if current_frame_idx >= len(frame_buffer):
            current_frame_idx = 0
            trajectory.clear()
            pre_track_positions.clear()
            is_tracking = False
            start_point_triggered = False
            
        frame = frame_buffer[current_frame_idx].copy()
        
        # 获取参数 - 即使暂停也要获取最新参数以实时显示效果
        r_min = cv2.getTrackbarPos('R_min', 'Controls')
        r_max = cv2.getTrackbarPos('R_max', 'Controls')
        g_min = cv2.getTrackbarPos('G_min', 'Controls')
        g_max = cv2.getTrackbarPos('G_max', 'Controls')
        b_min = cv2.getTrackbarPos('B_min', 'Controls')
        b_max = cv2.getTrackbarPos('B_max', 'Controls')
        min_area = cv2.getTrackbarPos('Min_Area', 'Controls')
        max_area = cv2.getTrackbarPos('Max_Area', 'Controls')
        rg_ratio = cv2.getTrackbarPos('RG_ratio', 'Controls')
        rb_diff = cv2.getTrackbarPos('RB_diff', 'Controls')
        max_jump = cv2.getTrackbarPos('Max_Jump', 'Controls')
        exclude_right = cv2.getTrackbarPos('Exclude_Right', 'Controls')
        exclude_bottom = cv2.getTrackbarPos('Exclude_Bottom', 'Controls')
        speed = max(1, cv2.getTrackbarPos('PlaySpeed', 'Controls'))
        min_motion = cv2.getTrackbarPos('Min_Motion', 'Controls')
        motion_frames = max(2, cv2.getTrackbarPos('Motion_Frames', 'Controls'))
        
        if use_lab:
            # LAB颜色空间（更符合人眼感知）
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            # LAB中，黄色的a值接近0-127，b值较高（127-255）
            lower = np.array([r_min, 0, g_min])  # L, a, b
            upper = np.array([r_max, 127, g_max])
            mask = cv2.inRange(lab, lower, upper)
        else:
            # RGB颜色空间检测
            # 基本RGB范围
            lower = np.array([b_min, g_min, r_min])  # BGR顺序
            upper = np.array([b_max, g_max, r_max])
            mask1 = cv2.inRange(frame, lower, upper)
            
            # 增强检测：颜色比例过滤
            # 黄色特征: R≈G, 且R和G都远大于B
            b, g, r = cv2.split(frame.astype(np.float32) + 1)  # +1避免除零
            
            # R-B差值（黄色R比B大很多）
            rb_mask = ((r - b) > rb_diff).astype(np.uint8) * 255
            
            # R/G比例（黄色R和G接近）
            rg_mask = (np.abs(r / g - 1.0) < (200 - rg_ratio) / 100.0).astype(np.uint8) * 255
            
            # 组合所有掩码
            mask = cv2.bitwise_and(mask1, rb_mask)
            mask = cv2.bitwise_and(mask, rg_mask)
        
        # 形态学操作
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 过滤和显示轮廓
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area < area < max_area:
                # 获取中心点
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # 区域过滤：排除右侧和底部区域
                    if exclude_right > 0 and cx > exclude_right:
                        cv2.drawContours(frame, [contour], -1, (128, 128, 128), 1)  # 灰色表示被排除
                        cv2.putText(frame, "EXCLUDED-R", (cx-35, cy),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.3, (128, 128, 128), 1)
                        continue
                    
                    if exclude_bottom > 0 and cy > exclude_bottom:
                        cv2.drawContours(frame, [contour], -1, (128, 128, 128), 1)
                        cv2.putText(frame, "EXCLUDED-B", (cx-35, cy),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.3, (128, 128, 128), 1)
                        continue
                    
                    # 如果已经在追踪，检查运动连续性
                    if is_tracking and len(trajectory) > 0 and max_jump > 0:
                        last_pos = trajectory[-1]
                        distance = np.sqrt((cx - last_pos[0])**2 + (cy - last_pos[1])**2)
                        
                        # 如果距离太远，标记为可疑
                        if distance > max_jump:
                            cv2.drawContours(frame, [contour], -1, (0, 165, 255), 1)  # 橙色表示太远
                            cv2.putText(frame, f"FAR:{int(distance)}", (cx-30, cy),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 165, 255), 1)
                            continue
                    
                    valid_contours.append(contour)
                    # 绘制候选轮廓
                    cv2.drawContours(frame, [contour], -1, (255, 0, 255), 1)
                    
                    # 显示面积和长宽比
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = float(w) / h if h > 0 else 0
                    cv2.putText(frame, f"{int(area)}", (cx, cy-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
                    cv2.putText(frame, f"{aspect_ratio:.1f}", (cx, cy+10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 0), 1)
        
        # 追踪最大的符合条件的轮廓
        if valid_contours:
            # 选择最佳候选
            if is_tracking and len(trajectory) > 0:
                # 已经在追踪，选择距离最近的
                last_pos = trajectory[-1]
                min_distance = float('inf')
                best_contour = None
                
                for contour in valid_contours:
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        distance = np.sqrt((cx - last_pos[0])**2 + (cy - last_pos[1])**2)
                        
                        if distance < min_distance:
                            min_distance = distance
                            best_contour = contour
            else:
                # 还未开始追踪，选择最大的
                best_contour = max(valid_contours, key=lambda c: cv2.contourArea(c))
            
            if best_contour is not None:
                M = cv2.moments(best_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # 如果设置了起始点，检查是否经过起始点
                    if start_point is not None and not start_point_triggered:
                        distance_to_start = np.sqrt((cx - start_point[0])**2 + (cy - start_point[1])**2)
                        
                        if distance_to_start < start_point_radius:
                            # 飞镖经过起始点，开始追踪
                            start_point_triggered = True
                            is_tracking = True
                            trajectory.clear()
                            trajectory.append((cx, cy))
                            pre_track_positions.clear()
                            print(f"飞镖经过起始点！开始追踪")
                        else:
                            # 还未经过起始点，只显示检测
                            cv2.drawContours(frame, [best_contour], -1, (128, 128, 255), 2)
                            cv2.circle(frame, (cx, cy), 5, (128, 128, 255), -1)
                            cv2.putText(frame, "WAITING START", (cx-50, cy-15),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 255), 1)
                    # 预追踪阶段：检测运动
                    elif not is_tracking:
                        pre_track_positions.append((cx, cy))
                        
                        # 检查是否有连续运动
                        if len(pre_track_positions) >= motion_frames:
                            # 计算总移动距离
                            total_distance = 0
                            for i in range(1, len(pre_track_positions)):
                                dist = np.sqrt((pre_track_positions[i][0] - pre_track_positions[i-1][0])**2 + 
                                             (pre_track_positions[i][1] - pre_track_positions[i-1][1])**2)
                                total_distance += dist
                            
                            # 如果总移动距离超过阈值，开始追踪
                            if total_distance > min_motion:
                                is_tracking = True
                                # 将预追踪的点加入轨迹
                                trajectory.extend(pre_track_positions)
                                print(f"检测到飞镖移动！总移动距离: {int(total_distance)}px")
                                # 清空预追踪队列
                                pre_track_positions.clear()
                        
                        # 标记为预追踪状态
                        cv2.drawContours(frame, [best_contour], -1, (0, 255, 255), 2)
                        cv2.circle(frame, (cx, cy), 5, (255, 255, 0), -1)  # 黄色表示预追踪
                        cv2.putText(frame, "DETECTING", (cx-40, cy-15),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
                    else:
                        # 正式追踪阶段 - 只有在非暂停时才添加到轨迹
                        if not paused:
                            trajectory.append((cx, cy))
                        
                        # 高亮显示追踪的轮廓
                        cv2.drawContours(frame, [best_contour], -1, (0, 255, 255), 2)
                        cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
                        
                        # 显示中心十字
                        cv2.line(frame, (cx-10, cy), (cx+10, cy), (0, 255, 0), 2)
                        cv2.line(frame, (cx, cy-10), (cx, cy+10), (0, 255, 0), 2)
        elif not paused:
            # 没有检测到有效轮廓
            if is_tracking:
                # 如果正在追踪但丢失目标，可以考虑重置
                pass
            else:
                # 预追踪阶段没检测到，清空预追踪队列
                if len(pre_track_positions) > 0:
                    pre_track_positions.clear()
        
        # 绘制轨迹 - 细线条
        if len(trajectory) > 1:
            # 绘制轨迹线条
            points = np.array(trajectory, dtype=np.int32)
            
            # 先画一条细的黑色边框
            for i in range(1, len(trajectory)):
                cv2.line(frame, trajectory[i - 1], trajectory[i], (0, 0, 0), 3)
            
            # 再画红色轨迹线
            for i in range(1, len(trajectory)):
                cv2.line(frame, trajectory[i - 1], trajectory[i], (0, 0, 255), 2)
            
            # 在轨迹起点和终点标记
            cv2.circle(frame, trajectory[0], 8, (255, 0, 0), -1)  # 起点：蓝色
            cv2.circle(frame, trajectory[-1], 8, (0, 255, 0), -1)  # 终点：绿色
        
        # 绘制手动设置的起始点
        if start_point is not None:
            color = (0, 255, 0) if start_point_triggered else (0, 255, 255)
            cv2.circle(frame, start_point, start_point_radius, color, 2)
            cv2.circle(frame, start_point, 5, color, -1)
            label = "START (OK)" if start_point_triggered else "START POINT"
            cv2.putText(frame, label, (start_point[0] - 40, start_point[1] - start_point_radius - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 显示信息
        info_y = 30
        mode_text = "LAB Mode" if use_lab else "RGB Mode"
        cv2.putText(frame, mode_text, (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        info_y += 30
        
        # 显示起始点状态
        if start_point is not None:
            start_status = "START OK" if start_point_triggered else "WAITING START"
            start_color = (0, 255, 0) if start_point_triggered else (0, 255, 255)
            cv2.putText(frame, start_status, (10, info_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, start_color, 2)
            info_y += 30
        
        # 显示追踪状态
        if start_point is None or start_point_triggered:
            status_text = "TRACKING" if is_tracking else f"DETECTING ({len(pre_track_positions)}/{motion_frames})"
            status_color = (0, 255, 0) if is_tracking else (255, 255, 0)
            cv2.putText(frame, status_text, (10, info_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            info_y += 30
        
        cv2.putText(frame, f"Frame: {current_frame_idx + 1}/{len(frame_buffer)}", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        info_y += 25
        cv2.putText(frame, f"Contours: {len(valid_contours)}", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        info_y += 25
        cv2.putText(frame, f"Trajectory: {len(trajectory)} pts", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        info_y += 25
        cv2.putText(frame, f"Max Jump: {max_jump}px", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        info_y += 20
        cv2.putText(frame, f"Exclude: R>{exclude_right} B>{exclude_bottom}", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        if not use_lab:
            info_y += 25
            cv2.putText(frame, f"RGB: [{r_min},{g_min},{b_min}]-[{r_max},{g_max},{b_max}]", (10, info_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        
        # 如果设置了排除区域，在画面上绘制标记线
        if exclude_right > 0:
            cv2.line(frame, (exclude_right, 0), (exclude_right, height), (128, 128, 128), 2)
            cv2.putText(frame, "EXCLUDE-RIGHT", (exclude_right + 10, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
        
        if exclude_bottom > 0:
            cv2.line(frame, (0, exclude_bottom), (width, exclude_bottom), (128, 128, 128), 2)
            cv2.putText(frame, "EXCLUDE-BOTTOM", (10, exclude_bottom - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
        
        if paused:
            cv2.putText(frame, "PAUSED", (width//2 - 50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
        
        # 将mask转换为BGR格式以便合并
        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        
        # 左右并排显示：左边tracking，右边mask
        combined = np.hstack([frame, mask_bgr])
        
        # 显示合并后的窗口
        cv2.imshow('Dart Tracking', combined)
        
        # 按键处理
        wait_time = 1 if paused else max(30, int(1000 / fps / max(1, speed)))
        key = cv2.waitKeyEx(wait_time)  # 使用waitKeyEx获取扩展键码
        
        # 调试：显示按键码（除了-1和空格，避免输出过多）
        if key != -1 and key != ord(' ') and paused:
            print(f"按键码: {key} (十六进制: 0x{key:X})")
        
        # 标准ASCII键（不需要修改）
        if key == ord('q'):
            break
        elif key == ord(' '):
            paused = not paused
        elif key == ord('r'):
            trajectory.clear()
            pre_track_positions.clear()
            is_tracking = False
            start_point_triggered = False
            print("轨迹已重置")
        elif key == ord('m'):
            use_lab = not use_lab
            print(f"切换到 {'LAB' if use_lab else 'RGB'} 模式")
        elif key == ord('s'):
            # 保存当前参数配置到文件
            current_params = {
                'R_min': r_min, 'R_max': r_max, 'G_min': g_min, 'G_max': g_max,
                'B_min': b_min, 'B_max': b_max, 'Min_Area': min_area, 'Max_Area': max_area,
                'RG_ratio': rg_ratio, 'RB_diff': rb_diff, 'Max_Jump': max_jump,
                'Exclude_Right': exclude_right, 'Exclude_Bottom': exclude_bottom,
                'PlaySpeed': speed, 'Min_Motion': min_motion, 'Motion_Frames': motion_frames
            }
            save_config(current_params)
            
            # 保存参数和视频
            print("\n正在保存当前追踪结果...")
            print("当前参数:")
            if use_lab:
                print(f"LAB模式 - lower = np.array([{r_min}, 0, {g_min}])")
                print(f"LAB模式 - upper = np.array([{r_max}, 127, {g_max}])")
            else:
                print(f"RGB模式 - lower_bgr = np.array([{b_min}, {g_min}, {r_min}])")
                print(f"RGB模式 - upper_bgr = np.array([{b_max}, {g_max}, {r_max}])")
                print(f"RG_ratio threshold = {rg_ratio}")
                print(f"RB_diff threshold = {rb_diff}")
            print(f"min_area = {min_area}, max_area = {max_area}")
            print(f"max_jump = {max_jump}, exclude_right = {exclude_right}, exclude_bottom = {exclude_bottom}")
            print(f"min_motion = {min_motion}, motion_frames = {motion_frames}")
            if start_point:
                print(f"start_point = {start_point}, radius = {start_point_radius}")
            
            # 生成规范的文件名
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"dart_trajectory_{timestamp}.mp4"
            
            # 暂停视频准备保存
            was_paused = paused
            paused = True
            
            # 使用当前参数重新处理并保存视频
            save_video_with_current_params(frame_buffer, output_path,
                                           r_min, r_max, g_min, g_max, b_min, b_max,
                                           min_area, max_area, rg_ratio, rb_diff, 
                                           max_jump, exclude_right, exclude_bottom, 
                                           min_motion, motion_frames, start_point, 
                                           start_point_radius, use_lab, width, height)
            
            paused = was_paused
            print(f"\n视频已保存到: {output_path}")
        elif key == 2424832 and paused:  # 左箭头 (0x250000)
            current_frame_idx = max(0, current_frame_idx - 1)
            trajectory.clear()
            pre_track_positions.clear()
            is_tracking = False
            start_point_triggered = False
            print(f"跳转到帧 {current_frame_idx + 1}")
            continue
        elif key == 2555904 and paused:  # 右箭头 (0x270000)
            current_frame_idx = min(len(frame_buffer) - 1, current_frame_idx + 1)
            trajectory.clear()
            pre_track_positions.clear()
            is_tracking = False
            start_point_triggered = False
            print(f"跳转到帧 {current_frame_idx + 1}")
            continue
            print(f"跳转到帧 {current_frame_idx + 1}")
            continue
        
        # 只有在非暂停状态下才自动前进到下一帧
        if not paused:
            current_frame_idx += 1
            if current_frame_idx >= len(frame_buffer):
                current_frame_idx = 0  # 循环播放
                trajectory.clear()
                pre_track_positions.clear()
                is_tracking = False
                start_point_triggered = False
    
    cv2.destroyAllWindows()


def save_video_with_current_params(frame_buffer, output_path,
                                   r_min, r_max, g_min, g_max, b_min, b_max,
                                   min_area, max_area, rg_ratio, rb_diff, 
                                   max_jump, exclude_right, exclude_bottom, 
                                   min_motion, motion_frames, start_point, 
                                   start_point_radius, use_lab, orig_width, orig_height):
    """使用当前参数保存带完整调试信息的视频（包含tracking和mask）"""
    if not frame_buffer:
        return
    
    height, width = frame_buffer[0].shape[:2]
    
    # 输出视频尺寸：左右并排显示tracking和mask
    output_width = width * 2
    output_height = height
    
    # 使用H.264编码器保存为MP4格式
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, 30, (output_width, output_height))
    
    if not out.isOpened():
        print("警告: mp4v编码器失败，尝试使用avc1...")
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, 30, (output_width, output_height))
    
    if not out.isOpened():
        print("错误: 无法创建视频文件")
        return
    
    trajectory = deque(maxlen=500)
    pre_track_positions = deque(maxlen=10)
    is_tracking = False
    start_point_triggered = False if start_point else True  # 如果没有设置起始点，直接开始
    
    print(f"正在生成输出视频... 共{len(frame_buffer)}帧")
    
    for idx, frame in enumerate(frame_buffer):
        frame_out = frame.copy()
        
        # 应用颜色检测
        if use_lab:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            lower = np.array([r_min, 0, g_min])
            upper = np.array([r_max, 127, g_max])
            mask = cv2.inRange(lab, lower, upper)
        else:
            lower = np.array([b_min, g_min, r_min])
            upper = np.array([b_max, g_max, r_max])
            mask1 = cv2.inRange(frame, lower, upper)
            
            b_ch, g_ch, r_ch = cv2.split(frame.astype(np.float32) + 1)
            rb_mask = ((r_ch - b_ch) > rb_diff).astype(np.uint8) * 255
            rg_mask = (np.abs(r_ch / g_ch - 1.0) < (200 - rg_ratio) / 100.0).astype(np.uint8) * 255
            
            mask = cv2.bitwise_and(mask1, rb_mask)
            mask = cv2.bitwise_and(mask, rg_mask)
        
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours = []
        for c in contours:
            if min_area < cv2.contourArea(c) < max_area:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # 应用区域过滤
                    if exclude_right > 0 and cx > exclude_right:
                        cv2.drawContours(frame_out, [c], -1, (128, 128, 128), 1)
                        continue
                    
                    if exclude_bottom > 0 and cy > exclude_bottom:
                        cv2.drawContours(frame_out, [c], -1, (128, 128, 128), 1)
                        continue
                    
                    # 应用运动连续性过滤（仅在追踪时）
                    if is_tracking and len(trajectory) > 0 and max_jump > 0:
                        last_pos = trajectory[-1]
                        distance = np.sqrt((cx - last_pos[0])**2 + (cy - last_pos[1])**2)
                        if distance > max_jump:
                            cv2.drawContours(frame_out, [c], -1, (0, 165, 255), 1)
                            continue
                    
                    valid_contours.append(c)
        
        if valid_contours:
            # 选择最佳轮廓
            if is_tracking and len(trajectory) > 0:
                last_pos = trajectory[-1]
                best_contour = min(valid_contours, 
                                  key=lambda c: np.sqrt((int(cv2.moments(c)["m10"]/max(cv2.moments(c)["m00"], 0.001)) - last_pos[0])**2 + 
                                                       (int(cv2.moments(c)["m01"]/max(cv2.moments(c)["m00"], 0.001)) - last_pos[1])**2))
            else:
                best_contour = max(valid_contours, key=lambda c: cv2.contourArea(c))
            
            M = cv2.moments(best_contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # 如果设置了起始点，检查是否经过起始点
                if start_point is not None and not start_point_triggered:
                    distance_to_start = np.sqrt((cx - start_point[0])**2 + (cy - start_point[1])**2)
                    
                    if distance_to_start < start_point_radius:
                        start_point_triggered = True
                        is_tracking = True
                        trajectory.clear()
                        trajectory.append((cx, cy))
                        pre_track_positions.clear()
                    else:
                        cv2.drawContours(frame_out, [best_contour], -1, (128, 128, 255), 2)
                        cv2.circle(frame_out, (cx, cy), 5, (128, 128, 255), -1)
                # 运动检测逻辑
                elif not is_tracking:
                    pre_track_positions.append((cx, cy))
                    
                    if len(pre_track_positions) >= motion_frames:
                        total_distance = 0
                        for i in range(1, len(pre_track_positions)):
                            dist = np.sqrt((pre_track_positions[i][0] - pre_track_positions[i-1][0])**2 + 
                                         (pre_track_positions[i][1] - pre_track_positions[i-1][1])**2)
                            total_distance += dist
                        
                        if total_distance > min_motion:
                            is_tracking = True
                            trajectory.extend(pre_track_positions)
                            pre_track_positions.clear()
                    
                    cv2.drawContours(frame_out, [best_contour], -1, (0, 255, 255), 2)
                    cv2.circle(frame_out, (cx, cy), 5, (255, 255, 0), -1)
                else:
                    trajectory.append((cx, cy))
                    cv2.drawContours(frame_out, [best_contour], -1, (0, 255, 255), 2)
                    cv2.circle(frame_out, (cx, cy), 5, (0, 255, 0), -1)
                    cv2.line(frame_out, (cx-10, cy), (cx+10, cy), (0, 255, 0), 2)
                    cv2.line(frame_out, (cx, cy-10), (cx, cy+10), (0, 255, 0), 2)
        else:
            if not is_tracking and len(pre_track_positions) > 0:
                pre_track_positions.clear()
        
        # 绘制轨迹
        if is_tracking and len(trajectory) > 1:
            for i in range(1, len(trajectory)):
                thickness = max(3, int(np.sqrt(len(trajectory) / float(i + 1)) * 3))
                cv2.line(frame_out, trajectory[i - 1], trajectory[i], (0, 0, 0), thickness + 2)
            
            for i in range(1, len(trajectory)):
                thickness = max(2, int(np.sqrt(len(trajectory) / float(i + 1)) * 3))
                cv2.line(frame_out, trajectory[i - 1], trajectory[i], (0, 0, 255), thickness)
            
            cv2.circle(frame_out, trajectory[0], 8, (255, 0, 0), -1)
            cv2.circle(frame_out, trajectory[-1], 8, (0, 255, 0), -1)
        
        # 绘制起始点标记
        if start_point is not None:
            color = (0, 255, 0) if start_point_triggered else (0, 255, 255)
            cv2.circle(frame_out, start_point, start_point_radius, color, 2)
            cv2.circle(frame_out, start_point, 5, color, -1)
            label = "START (OK)" if start_point_triggered else "START POINT"
            cv2.putText(frame_out, label, (start_point[0] - 40, start_point[1] - start_point_radius - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 绘制排除区域线
        if exclude_right > 0:
            cv2.line(frame_out, (exclude_right, 0), (exclude_right, height), (128, 128, 128), 2)
            cv2.putText(frame_out, "EXCLUDE-RIGHT", (exclude_right + 10, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
        
        if exclude_bottom > 0:
            cv2.line(frame_out, (0, exclude_bottom), (width, exclude_bottom), (128, 128, 128), 2)
            cv2.putText(frame_out, "EXCLUDE-BOTTOM", (10, exclude_bottom - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
        
        # 添加调试信息文字
        info_y = 30
        cv2.putText(frame_out, "RGB Mode" if not use_lab else "LAB Mode", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        info_y += 30
        
        if start_point is not None:
            start_status = "START OK" if start_point_triggered else "WAITING START"
            start_color = (0, 255, 0) if start_point_triggered else (0, 255, 255)
            cv2.putText(frame_out, start_status, (10, info_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, start_color, 2)
            info_y += 30
        
        if start_point is None or start_point_triggered:
            status_text = "TRACKING" if is_tracking else "DETECTING"
            status_color = (0, 255, 0) if is_tracking else (255, 255, 0)
            cv2.putText(frame_out, status_text, (10, info_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            info_y += 30
        
        cv2.putText(frame_out, f"Frame: {idx + 1}/{len(frame_buffer)}", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        info_y += 25
        cv2.putText(frame_out, f"Contours: {len(valid_contours)}", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        info_y += 25
        cv2.putText(frame_out, f"Trajectory: {len(trajectory)} pts", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 将mask转换为BGR格式以便合并
        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        
        # 左右并排显示tracking和mask
        combined = np.hstack([frame_out, mask_bgr])
        
        out.write(combined)
        
        if (idx + 1) % 30 == 0:
            print(f"处理进度: {idx + 1}/{len(frame_buffer)} 帧 ({int((idx+1)/len(frame_buffer)*100)}%)")
    
    out.release()
    print(f"完成！追踪到 {len(trajectory)} 个点")


if __name__ == "__main__":
    print("飞镖轨迹追踪 - RGB模式")
    print("=" * 50)
    print("黄色在RGB中的特征:")
    print("- R值高 (100-255)")
    print("- G值高 (100-255)")
    print("- B值低 (0-150)")
    print("- R≈G (RG_ratio接近100)")
    print("- R-B差值大 (RB_diff > 50)")
    print("=" * 50)
    track_dart_rgb_interactive()
