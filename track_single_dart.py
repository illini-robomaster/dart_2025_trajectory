import cv2
import numpy as np
from collections import deque

def nothing(x):
    pass

def track_dart_interactive():
    """
    交互式追踪飞镖，可以实时调整参数
    """
    video_path = "8a095a81b00f885cefc49e879ed90171.mp4"
    
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return
    
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"视频信息: {width}x{height}, {fps}FPS, {total_frames}帧")
    
    # 创建窗口
    cv2.namedWindow('Tracking')
    cv2.namedWindow('Mask')
    cv2.namedWindow('Controls')
    
    # 创建控制滑动条（使用你调整好的参数作为默认值）
    cv2.createTrackbar('H_min', 'Controls', 30, 179, nothing)
    cv2.createTrackbar('H_max', 'Controls', 39, 179, nothing)
    cv2.createTrackbar('S_min', 'Controls', 68, 255, nothing)
    cv2.createTrackbar('S_max', 'Controls', 219, 255, nothing)
    cv2.createTrackbar('V_min', 'Controls', 29, 255, nothing)
    cv2.createTrackbar('V_max', 'Controls', 163, 255, nothing)
    cv2.createTrackbar('Min_Area', 'Controls', 0, 1000, nothing)
    cv2.createTrackbar('Max_Area', 'Controls', 500, 5000, nothing)
    cv2.createTrackbar('Speed', 'Controls', 1, 10, nothing)  # 播放速度，1最慢
    
    trajectory = deque(maxlen=500)
    paused = False
    frame_buffer = []
    current_frame_idx = 0
    
    # 预加载所有帧以便快速跳转
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
    print("Speed滑动条: 1=最慢, 10=最快")
    print("\n视频将循环播放，调整滑动条查看追踪效果\n")
    
    while True:  # 无限循环播放
        if current_frame_idx >= len(frame_buffer):
            current_frame_idx = 0  # 重新开始
            trajectory.clear()  # 清空轨迹重新追踪
            
        frame = frame_buffer[current_frame_idx].copy()
        
        # 获取参数
        h_min = cv2.getTrackbarPos('H_min', 'Controls')
        h_max = cv2.getTrackbarPos('H_max', 'Controls')
        s_min = cv2.getTrackbarPos('S_min', 'Controls')
        s_max = cv2.getTrackbarPos('S_max', 'Controls')
        v_min = cv2.getTrackbarPos('V_min', 'Controls')
        v_max = cv2.getTrackbarPos('V_max', 'Controls')
        min_area = cv2.getTrackbarPos('Min_Area', 'Controls')
        max_area = cv2.getTrackbarPos('Max_Area', 'Controls')
        speed = max(1, cv2.getTrackbarPos('Speed', 'Controls'))
        
        # 转换到HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 创建掩码
        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(hsv, lower, upper)
        
        # 形态学操作
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 绘制所有轮廓（用于调试）
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area < area < max_area:
                valid_contours.append(contour)
                # 绘制所有符合条件的轮廓
                cv2.drawContours(frame, [contour], -1, (255, 0, 255), 1)
                
                # 显示面积
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    cv2.putText(frame, f"{int(area)}", (cx, cy-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
        
        # 追踪最大的符合条件的轮廓
        if valid_contours and not paused:
            largest_contour = max(valid_contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            
            M = cv2.moments(largest_contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # 添加到轨迹
                trajectory.append((cx, cy))
                
                # 高亮显示追踪的轮廓
                cv2.drawContours(frame, [largest_contour], -1, (0, 255, 255), 2)
                cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
                
                # 显示中心十字
                cv2.line(frame, (cx-10, cy), (cx+10, cy), (0, 255, 0), 2)
                cv2.line(frame, (cx, cy-10), (cx, cy+10), (0, 255, 0), 2)
        
        # 绘制轨迹
        if len(trajectory) > 1:
            for i in range(1, len(trajectory)):
                thickness = max(1, int(np.sqrt(len(trajectory) / float(i + 1)) * 2))
                cv2.line(frame, trajectory[i - 1], trajectory[i], (0, 0, 255), thickness)
        
        # 显示信息
        info_y = 30
        cv2.putText(frame, f"Frame: {current_frame_idx + 1}/{len(frame_buffer)}", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        info_y += 25
        cv2.putText(frame, f"Contours: {len(valid_contours)}", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        info_y += 25
        cv2.putText(frame, f"Trajectory: {len(trajectory)} pts", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        info_y += 25
        cv2.putText(frame, f"HSV: [{h_min},{s_min},{v_min}]-[{h_max},{s_max},{v_max}]", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        info_y += 20
        cv2.putText(frame, f"Area: {min_area}-{max_area}", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        
        if paused:
            cv2.putText(frame, "PAUSED", (width//2 - 50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
        
        # 显示
        cv2.imshow('Tracking', frame)
        cv2.imshow('Mask', mask)
        
        # 按键处理
        wait_time = 1 if paused else max(30, int(1000 / fps / max(1, speed)))  # 减慢播放速度
        key = cv2.waitKey(wait_time) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord(' '):
            paused = not paused
        elif key == ord('r'):
            trajectory.clear()
            print("轨迹已重置")
        elif key == ord('s'):
            # 保存参数和视频
            print("\n当前最佳参数:")
            print(f"lower_yellow = np.array([{h_min}, {s_min}, {v_min}])")
            print(f"upper_yellow = np.array([{h_max}, {s_max}, {v_max}])")
            print(f"min_area = {min_area}")
            print(f"max_area = {max_area}")
            
            # 保存视频
            output_path = "tracked_26626a1e70f7ca7deb61f05a9a5caefa_final.avi"
            save_video_with_trajectory(frame_buffer, output_path, trajectory, 
                                       h_min, h_max, s_min, s_max, v_min, v_max, min_area, max_area)
            print(f"\n视频已保存到: {output_path}")
        elif key == 81 and paused:  # 左箭头
            current_frame_idx = max(0, current_frame_idx - 1)
            trajectory.clear()
            continue
        elif key == 83 and paused:  # 右箭头
            current_frame_idx = min(len(frame_buffer) - 1, current_frame_idx + 1)
            trajectory.clear()
            continue
        
        if not paused:
            current_frame_idx += 1
    
    cv2.destroyAllWindows()


def save_video_with_trajectory(frame_buffer, output_path, trajectory_data, 
                               h_min, h_max, s_min, s_max, v_min, v_max, min_area, max_area):
    """保存带轨迹的视频"""
    if not frame_buffer:
        return
    
    height, width = frame_buffer[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_path, fourcc, 30, (width, height))
    
    trajectory = deque(maxlen=500)
    
    print("正在生成输出视频...")
    for idx, frame in enumerate(frame_buffer):
        frame_out = frame.copy()
        
        # 应用颜色检测
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(hsv, lower, upper)
        
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours = [c for c in contours if min_area < cv2.contourArea(c) < max_area]
        
        if valid_contours:
            largest_contour = max(valid_contours, key=cv2.contourArea)
            M = cv2.moments(largest_contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                trajectory.append((cx, cy))
                
                cv2.drawContours(frame_out, [largest_contour], -1, (0, 255, 255), 2)
                cv2.circle(frame_out, (cx, cy), 5, (0, 255, 0), -1)
        
        # 绘制轨迹
        if len(trajectory) > 1:
            for i in range(1, len(trajectory)):
                thickness = max(1, int(np.sqrt(len(trajectory) / float(i + 1)) * 2))
                cv2.line(frame_out, trajectory[i - 1], trajectory[i], (0, 0, 255), thickness)
        
        out.write(frame_out)
        
        if (idx + 1) % 30 == 0:
            print(f"处理进度: {idx + 1}/{len(frame_buffer)} 帧")
    
    out.release()
    print(f"完成！追踪到 {len(trajectory)} 个点")


if __name__ == "__main__":
    print("飞镖轨迹交互式追踪")
    print("=" * 50)
    track_dart_interactive()
