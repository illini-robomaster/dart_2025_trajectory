import cv2
import numpy as np
from collections import deque
import os

def track_yellow_dart(video_path, output_path=None):
    """
    追踪视频中黄色飞镖的轨迹
    
    参数:
        video_path: 视频文件路径
        output_path: 输出视频路径（可选）
    """
    # 打开视频
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return
    
    # 获取视频属性
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"视频信息: {width}x{height}, {fps}FPS, {total_frames}帧")
    
    # 如果需要保存输出视频
    out = None
    if output_path:
        # 根据文件扩展名选择编码器
        if output_path.endswith('.avi'):
            fourcc = cv2.VideoWriter_fourcc(*'XVID')  # Xvid编码，非常兼容
        else:
            fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264编码
        
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # 如果失败，尝试其他编码器
        if not out.isOpened():
            print("警告: 首选编码器失败，尝试备用编码器...")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # 存储飞镖轨迹的点
    trajectory = deque(maxlen=500)  # 最多保存500个点
    
    # 黄色的HSV范围（可能需要根据实际情况调整）
    # 黄色在HSV中的范围
    lower_yellow = np.array([20, 100, 100])
    upper_yellow = np.array([30, 255, 255])
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # 转换到HSV色彩空间
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 创建黄色掩码
        mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # 形态学操作去除噪声
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # 找到最大的轮廓（假设是飞镖）
            largest_contour = max(contours, key=cv2.contourArea)
            
            # 计算轮廓面积，过滤太小的区域
            area = cv2.contourArea(largest_contour)
            if area > 10:  # 最小面积阈值
                # 计算轮廓的矩
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    # 计算质心（飞镖头的位置）
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # 添加到轨迹
                    trajectory.append((cx, cy))
                    
                    # 在当前位置画一个圆
                    cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
                    
                    # 绘制轮廓
                    cv2.drawContours(frame, [largest_contour], -1, (0, 255, 255), 2)
        
        # 绘制轨迹
        if len(trajectory) > 1:
            for i in range(1, len(trajectory)):
                # 轨迹线条颜色从红色渐变到蓝色
                thickness = int(np.sqrt(len(trajectory) / float(i + 1)) * 2.5)
                cv2.line(frame, trajectory[i - 1], trajectory[i], (0, 0, 255), thickness)
        
        # 显示帧数和轨迹点数
        cv2.putText(frame, f"Frame: {frame_count}/{total_frames}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Trajectory Points: {len(trajectory)}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 显示画面
        cv2.imshow('Dart Tracking', frame)
        cv2.imshow('Mask', mask)  # 显示掩码用于调试
        
        # 保存输出视频
        if out:
            out.write(frame)
        
        # 按'q'退出，按'p'暂停
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('p'):
            cv2.waitKey(0)  # 暂停直到按任意键
    
    # 释放资源
    cap.release()
    if out:
        out.release()
    cv2.destroyAllWindows()
    
    print(f"处理完成！共追踪到 {len(trajectory)} 个轨迹点")
    return trajectory


def process_both_videos():
    """处理两个视频文件"""
    video_files = [
        "26626a1e70f7ca7deb61f05a9a5caefa.mp4",
        "e56a41ee506b45a52e200d071209eafa.mp4"
    ]
    
    for i, video_file in enumerate(video_files, 1):
        if os.path.exists(video_file):
            print(f"\n{'='*50}")
            print(f"正在处理视频 {i}: {video_file}")
            print(f"{'='*50}")
            
            # 尝试使用.avi格式，通常更兼容
            output_file = f"tracked_{video_file.rsplit('.', 1)[0]}.avi"
            trajectory = track_yellow_dart(video_file, output_file)
            
            if trajectory:
                print(f"输出已保存到: {output_file}")
                print(f"如果无法播放，请尝试使用VLC播放器或转换格式")
        else:
            print(f"找不到视频文件: {video_file}")


if __name__ == "__main__":
    print("飞镖轨迹追踪程序")
    print("=" * 50)
    print("操作说明:")
    print("- 按 'q' 退出")
    print("- 按 'p' 暂停/继续")
    print("=" * 50)
    
    # 处理两个视频
    process_both_videos()
