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
    print("Dart detector starting (headless mode)...")
    
    # 枚举相机
    DevList = mvsdk.CameraEnumerateDevice()
    nDev = len(DevList)
    if nDev < 1:
        print("Error: No camera found!")
        return

    # 直接使用第一个相机
    DevInfo = DevList[0]
    print(f"Using camera: {DevInfo.GetFriendlyName()}")

    # 打开相机
    try:
        hCamera = mvsdk.CameraInit(DevInfo, -1, -1)
    except mvsdk.CameraException as e:
        print(f"Init failed: {e.message}")
        return

    try:
        cap = mvsdk.CameraGetCapability(hCamera)
        monoCamera = (cap.sIspCapacity.bMonoSensor != 0)
        
        if monoCamera:
            print("Error: Color camera required!")
            return

        # 打印相机支持的分辨率范围
        print(f"Camera resolution range: {cap.sResolutionRange.iWidthMin}x{cap.sResolutionRange.iHeightMin} to {cap.sResolutionRange.iWidthMax}x{cap.sResolutionRange.iHeightMax}")
        
        # 设置自定义分辨率640x480
        target_width = 640
        target_height = 480
        
        try:
            # 使用SDK的tSdkImageResolution结构体
            custom_res = mvsdk.tSdkImageResolution()
            custom_res.iIndex = 0xff  # 0xff表示自定义分辨率
            custom_res.iWidth = target_width
            custom_res.iHeight = target_height
            custom_res.iWidthFOV = target_width
            custom_res.iHeightFOV = target_height
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
            print(f"✓ Set custom resolution: {target_width} x {target_height}")
            selected_width = target_width
            selected_height = target_height
        except Exception as e:
            print(f"⚠ Failed to set custom resolution: {e}")
            print(f"  Using default resolution: {cap.sResolutionRange.iWidthMax} x {cap.sResolutionRange.iHeightMax}")
            selected_width = cap.sResolutionRange.iWidthMax
            selected_height = cap.sResolutionRange.iHeightMax

        # 设置输出格式为BGR8
        mvsdk.CameraSetIspOutFormat(hCamera, mvsdk.CAMERA_MEDIA_TYPE_BGR8)

        # 连续采集模式
        mvsdk.CameraSetTriggerMode(hCamera, 0)

        # 手动曝光（关键优化：避免AE限制帧率）
        mvsdk.CameraSetAeState(hCamera, 0)  # 关闭自动曝光
        mvsdk.CameraSetExposureTime(hCamera, 20000)  # 20000us = 20ms
        print(f"Exposure mode: Manual 20ms")

        # 开始采集
        mvsdk.CameraPlay(hCamera)

        # 按实际分辨率分配缓存
        FrameBufferSize = selected_width * selected_height * 3
        pFrameBuffer = mvsdk.CameraAlignMalloc(FrameBufferSize, 16)
        print(f"Buffer size: {selected_width} x {selected_height} x 3 = {FrameBufferSize} bytes")

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
        
        print("\nDetection started - Press Ctrl+C to exit")
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
                # 将图像缩小到1/2进行检测
                detect_frame = cv2.resize(frame, (FrameHead.iWidth // 2, FrameHead.iHeight // 2), 
                                         interpolation=cv2.INTER_LINEAR)
                scale_factor = 2

                # === 红色发光飞镖头检测 ===
                
                # 1. 转换到HSV颜色空间
                hsv = cv2.cvtColor(detect_frame, cv2.COLOR_BGR2HSV)
                
                # 2. 检测红色（两个范围的掩模合并）
                mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
                mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
                mask = cv2.bitwise_or(mask1, mask2)
                
                # 3. 形态学操作（简化：只做一次）
                kernel = np.ones((3, 3), np.uint8)
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
                
                # 打印结果（每秒一次）
                if fps_counter == 1:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] FPS: {fps:2d} | Darts: {detected_objects}", end="")
                    if detected_objects > 0:
                        print(" | Pos: ", end="")
                        for dart in dart_positions[:3]:  # 只显示前3个
                            cx, cy = dart['center']
                            print(f"({cx},{cy})", end=" ")
                    print()
                
            except mvsdk.CameraException as e:
                if e.error_code != mvsdk.CAMERA_STATUS_TIME_OUT:
                    print(f"Camera error: {e.message}")
            except KeyboardInterrupt:
                print("\n\nUser interrupted")
                break

    finally:
        mvsdk.CameraUnInit(hCamera)
        mvsdk.CameraAlignFree(pFrameBuffer)
        print("Camera closed")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
