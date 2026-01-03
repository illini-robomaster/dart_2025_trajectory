import cv2
import numpy as np

def nothing(x):
    """滑动条回调函数"""
    pass

def adjust_hsv_range(video_path):
    """
    调整HSV颜色范围的工具
    用于找到最佳的黄色追踪参数
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return
    
    # 创建窗口
    cv2.namedWindow('HSV Adjuster')
    cv2.namedWindow('Original')
    cv2.namedWindow('Mask')
    
    # 创建滑动条
    cv2.createTrackbar('H_min', 'HSV Adjuster', 20, 179, nothing)
    cv2.createTrackbar('H_max', 'HSV Adjuster', 30, 179, nothing)
    cv2.createTrackbar('S_min', 'HSV Adjuster', 100, 255, nothing)
    cv2.createTrackbar('S_max', 'HSV Adjuster', 255, 255, nothing)
    cv2.createTrackbar('V_min', 'HSV Adjuster', 100, 255, nothing)
    cv2.createTrackbar('V_max', 'HSV Adjuster', 255, 255, nothing)
    
    # 暂停/播放状态
    paused = True
    
    print("\n操作说明:")
    print("- 空格键: 暂停/播放")
    print("- 'q': 退出并打印最佳参数")
    print("- 左/右方向键: 逐帧前进/后退（暂停时）")
    print("\n调整滑动条直到只有飞镖被高亮显示\n")
    
    while True:
        if not paused:
            ret, frame = cap.read()
            if not ret:
                # 视频结束，重新播放
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
        else:
            # 暂停时读取当前帧
            current_pos = cap.get(cv2.CAP_PROP_POS_FRAMES)
            ret, frame = cap.read()
            if ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
        
        if not ret:
            break
        
        # 获取滑动条的值
        h_min = cv2.getTrackbarPos('H_min', 'HSV Adjuster')
        h_max = cv2.getTrackbarPos('H_max', 'HSV Adjuster')
        s_min = cv2.getTrackbarPos('S_min', 'HSV Adjuster')
        s_max = cv2.getTrackbarPos('S_max', 'HSV Adjuster')
        v_min = cv2.getTrackbarPos('V_min', 'HSV Adjuster')
        v_max = cv2.getTrackbarPos('V_max', 'HSV Adjuster')
        
        # 转换到HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 创建掩码
        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(hsv, lower, upper)
        
        # 形态学操作
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 在原图上绘制轮廓
        result = frame.copy()
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            
            if area > 10:
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    cv2.circle(result, (cx, cy), 5, (0, 255, 0), -1)
                    cv2.drawContours(result, [largest_contour], -1, (0, 255, 255), 2)
                    
                    # 显示面积
                    cv2.putText(result, f"Area: {int(area)}", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 显示当前参数
        param_text = f"HSV: [{h_min},{s_min},{v_min}] - [{h_max},{s_max},{v_max}]"
        cv2.putText(result, param_text, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 显示图像
        cv2.imshow('Original', result)
        cv2.imshow('Mask', mask)
        
        # 按键处理
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            print("\n最佳HSV参数:")
            print(f"lower_yellow = np.array([{h_min}, {s_min}, {v_min}])")
            print(f"upper_yellow = np.array([{h_max}, {s_max}, {v_max}])")
            break
        elif key == ord(' '):
            paused = not paused
        elif key == 83 and paused:  # 右箭头
            # 前进一帧
            pass
        elif key == 81 and paused:  # 左箭头
            # 后退一帧
            current_pos = cap.get(cv2.CAP_PROP_POS_FRAMES)
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, current_pos - 2))
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import sys
    
    video_files = [
        "26626a1e70f7ca7deb61f05a9a5caefa.mp4",
        "e56a41ee506b45a52e200d071209eafa.mp4"
    ]
    
    print("选择要调整的视频:")
    for i, video in enumerate(video_files, 1):
        print(f"{i}. {video}")
    
    choice = input("请输入数字 (1 或 2): ")
    
    try:
        video_path = video_files[int(choice) - 1]
        adjust_hsv_range(video_path)
    except (ValueError, IndexError):
        print("无效的选择！")
