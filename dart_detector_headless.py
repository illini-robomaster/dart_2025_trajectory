#coding=utf-8
"""
工业相机飞镖头检测 - 无界面版本（性能测试）
只打印检测结果，不显示窗口，用于测试最大帧率
"""
import cv2
import numpy as np
import sys
sys.path.append('python_demo')
import mvsdk
import platform
import time
from datetime import datetime

def main():
    print("飞镖头检测启动中（无界面模式）...")
    
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
            pass

        # 设置输出格式为BGR8
        mvsdk.CameraSetIspOutFormat(hCamera, mvsdk.CAMERA_MEDIA_TYPE_BGR8)

        # 连续采集模式
        mvsdk.CameraSetTriggerMode(hCamera, 0)

        # 自动曝光
        mvsdk.CameraSetAeState(hCamera, 1)

        # 开始采集
        mvsdk.CameraPlay(hCamera)

        # 分配缓存
        FrameBufferSize = cap.sResolutionRange.iWidthMax * cap.sResolutionRange.iHeightMax * 3
        pFrameBuffer = mvsdk.CameraAlignMalloc(FrameBufferSize, 16)

        # 红色的HSV阈值范围
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        
        # 飞镖头的特征阈值
        min_area = 300
        max_area = 10000

        # 性能计数
        fps_time = time.time()
        fps_counter = 0
        fps = 0
        
        print("\n检测开始 - 按Ctrl+C退出")
        print("=" * 60)

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
                
                # 镜像翻转
                frame = cv2.flip(frame, 1)

                # 计算FPS
                fps_counter += 1
                if time.time() - fps_time > 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_time = time.time()

                # === 性能优化：缩小图像用于检测 ===
                detect_frame = cv2.resize(frame, (FrameHead.iWidth // 2, FrameHead.iHeight // 2), 
                                         interpolation=cv2.INTER_LINEAR)
                scale_factor = 2

                # === 红色发光飞镖头检测 ===
                
                # 1. 转换到HSV颜色空间
                hsv = cv2.cvtColor(detect_frame, cv2.COLOR_BGR2HSV)
                
                # 2. 检测红色
                mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
                mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
                mask = cv2.bitwise_or(mask1, mask2)
                
                # 3. 形态学操作
                kernel = np.ones((3, 3), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                
                # 4. 查找轮廓
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 5. 分析轮廓
                detected_objects = 0
                dart_positions = []
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    
                    scaled_min_area = min_area / (scale_factor * scale_factor)
                    scaled_max_area = max_area / (scale_factor * scale_factor)
                    if area < scaled_min_area or area > scaled_max_area:
                        continue
                    
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = max(w, h) / (min(w, h) + 1e-5)
                    
                    if aspect_ratio > 15.0:
                        continue
                    
                    detected_objects += 1
                    
                    # 映射回原图坐标
                    x_orig, y_orig = x * scale_factor, y * scale_factor
                    w_orig, h_orig = w * scale_factor, h * scale_factor
                    
                    # 计算中心点
                    cx = x_orig + w_orig // 2
                    cy = y_orig + h_orig // 2
                    
                    dart_positions.append({
                        'center': (cx, cy),
                        'area': int(area * scale_factor * scale_factor),
                        'aspect_ratio': aspect_ratio
                    })
                
                # 打印检测结果（每秒只打印一次，避免刷屏）
                if fps_counter == 1:  # 每秒开始时打印
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] FPS: {fps:2d} | 飞镖数: {detected_objects}", end="")
                    
                    if detected_objects > 0:
                        print(" | 位置: ", end="")
                        for i, dart in enumerate(dart_positions):
                            cx, cy = dart['center']
                            print(f"({cx},{cy})", end=" ")
                    print()  # 换行
                
            except mvsdk.CameraException as e:
                if e.error_code != mvsdk.CAMERA_STATUS_TIME_OUT:
                    print(f"相机错误: {e.message}")
            except KeyboardInterrupt:
                print("\n\n用户中断")
                break

    finally:
        mvsdk.CameraUnInit(hCamera)
        mvsdk.CameraAlignFree(pFrameBuffer)
        print("相机已关闭")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
