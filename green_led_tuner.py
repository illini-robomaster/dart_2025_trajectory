#coding=utf-8
"""
绿色LED HSV参数调试工具
使用交互式trackbar实时调整HSV范围和面积阈值
找到最佳参数后按 's' 保存到配置文件
"""
import cv2
import numpy as np
import sys
sys.path.append('python_demo')
import mvsdk
import platform
import json

def save_green_config(h_min, h_max, s_min, s_max, v_min, v_max, area_min, area_max):
    """保存绿色LED检测参数到配置文件"""
    config = {
        'green_led': {
            'hsv_lower': [h_min, s_min, v_min],
            'hsv_upper': [h_max, s_max, v_max],
            'area_min': area_min,
            'area_max': area_max
        }
    }
    with open('green_led_config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] Configuration saved to green_led_config.json")
    print(f"  HSV: [{h_min},{s_min},{v_min}] - [{h_max},{s_max},{v_max}]")
    print(f"  Area: {area_min} - {area_max}")

def nothing(x):
    """Trackbar回调函数（空函数）"""
    pass

def main():
    print("Green LED HSV Tuner - Interactive Parameter Adjustment")
    print("=" * 60)
    
    # 枚举相机
    DevList = mvsdk.CameraEnumerateDevice()
    nDev = len(DevList)
    if nDev < 1:
        print("ERROR: No camera found!")
        return

    DevInfo = DevList[0]
    print(f"Using camera: {DevInfo.GetFriendlyName()}")

    # 打开相机
    try:
        hCamera = mvsdk.CameraInit(DevInfo, -1, -1)
    except mvsdk.CameraException as e:
        print(f"Camera init failed: {e.message}")
        return

    try:
        cap = mvsdk.CameraGetCapability(hCamera)
        
        # 设置640x480分辨率（与主程序一致）
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
        custom_res.uSkipMode = 0
        custom_res.uResampleMask = 0
        custom_res.iVSubSample = 0
        custom_res.iHSubSample = 0
        
        mvsdk.CameraSetImageResolution(hCamera, custom_res)
        print("Resolution set to 640x480")
        
        # 禁用自动曝光，设置手动曝光20ms（与主程序一致）
        mvsdk.CameraSetAeState(hCamera, 0)
        mvsdk.CameraSetExposureTime(hCamera, 20000)
        print("Auto-exposure disabled, manual exposure: 20ms")
        
        # 设置为连续采集模式
        mvsdk.CameraSetTriggerMode(hCamera, 0)
        
        # 分配图像缓冲区
        pFrameBuffer = mvsdk.CameraAlignMalloc(custom_res.iWidth * custom_res.iHeight * 3, 16)
        
        # 开始采集
        mvsdk.CameraPlay(hCamera)
        print("\n[Camera started] Adjust trackbars to tune parameters")
        print("Controls:")
        print("  [s] - Save current parameters to green_led_config.json")
        print("  [q] - Quit")
        print("=" * 60)
        
        # 创建窗口和trackbars
        window_name = "Original Frame"
        mask_window = "Green Mask (White=Detected)"
        result_window = "Detection Result"
        
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.namedWindow(mask_window, cv2.WINDOW_NORMAL)
        cv2.namedWindow(result_window, cv2.WINDOW_NORMAL)
        
        # 创建HSV trackbars（初始值设为宽范围）
        cv2.createTrackbar('H_min', mask_window, 35, 180, nothing)
        cv2.createTrackbar('H_max', mask_window, 90, 180, nothing)
        cv2.createTrackbar('S_min', mask_window, 50, 255, nothing)
        cv2.createTrackbar('S_max', mask_window, 255, 255, nothing)
        cv2.createTrackbar('V_min', mask_window, 50, 255, nothing)
        cv2.createTrackbar('V_max', mask_window, 255, 255, nothing)
        
        # 创建面积阈值trackbars
        cv2.createTrackbar('Area_min', result_window, 100, 10000, nothing)
        cv2.createTrackbar('Area_max', result_window, 5000, 20000, nothing)
        
        scale_factor = 2  # 与主程序一致的缩放比例
        
        while True:
            # 获取图像
            try:
                pRawData, FrameHead = mvsdk.CameraGetImageBuffer(hCamera, 200)
                mvsdk.CameraImageProcess(hCamera, pRawData, pFrameBuffer, FrameHead)
                mvsdk.CameraReleaseImageBuffer(hCamera, pRawData)

                if platform.system() == "Windows":
                    mvsdk.CameraFlipFrameBuffer(pFrameBuffer, FrameHead, 1)
                
                # 转换为numpy数组
                frame_data = (mvsdk.c_ubyte * FrameHead.uBytes).from_address(pFrameBuffer)
                frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = frame.reshape((FrameHead.iHeight, FrameHead.iWidth, 3))
                frame = cv2.flip(frame, 1)
                
                # 缩小图像用于检测（与主程序一致）
                detect_frame = cv2.resize(frame, (FrameHead.iWidth // 2, FrameHead.iHeight // 2), 
                                         interpolation=cv2.INTER_LINEAR)
                
                # 读取trackbar值
                h_min = cv2.getTrackbarPos('H_min', mask_window)
                h_max = cv2.getTrackbarPos('H_max', mask_window)
                s_min = cv2.getTrackbarPos('S_min', mask_window)
                s_max = cv2.getTrackbarPos('S_max', mask_window)
                v_min = cv2.getTrackbarPos('V_min', mask_window)
                v_max = cv2.getTrackbarPos('V_max', mask_window)
                area_min = cv2.getTrackbarPos('Area_min', result_window)
                area_max = cv2.getTrackbarPos('Area_max', result_window)
                
                # 转换到HSV
                hsv = cv2.cvtColor(detect_frame, cv2.COLOR_BGR2HSV)
                
                # 应用HSV阈值
                lower_green = np.array([h_min, s_min, v_min])
                upper_green = np.array([h_max, s_max, v_max])
                green_mask = cv2.inRange(hsv, lower_green, upper_green)
                
                # 形态学操作
                kernel = np.ones((3, 3), np.uint8)
                green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)
                green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
                
                # 查找轮廓
                contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 在结果帧上绘制检测结果
                result_frame = frame.copy()
                detected_count = 0
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    # 转换为原图尺寸的面积
                    area_orig = area * scale_factor * scale_factor
                    
                    if area_orig >= area_min and area_orig <= area_max:
                        detected_count += 1
                        
                        # 获取边界框（缩放回原图）
                        x, y, w, h = cv2.boundingRect(contour)
                        x_orig, y_orig = x * scale_factor, y * scale_factor
                        w_orig, h_orig = w * scale_factor, h * scale_factor
                        
                        # 绘制青色框
                        cv2.rectangle(result_frame, (x_orig, y_orig), 
                                    (x_orig + w_orig, y_orig + h_orig), (255, 255, 0), 2)
                        
                        # 显示面积
                        cx = x_orig + w_orig // 2
                        cy = y_orig + h_orig // 2
                        cv2.circle(result_frame, (cx, cy), 5, (255, 255, 0), -1)
                        cv2.putText(result_frame, f"Area:{int(area_orig)}", (x_orig, y_orig - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
                
                # 在各窗口显示参数信息
                cv2.putText(frame, f"Original Frame", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # 放大mask显示
                mask_display = cv2.resize(green_mask, (FrameHead.iWidth, FrameHead.iHeight))
                mask_color = cv2.cvtColor(mask_display, cv2.COLOR_GRAY2BGR)
                cv2.putText(mask_color, f"H:[{h_min},{h_max}] S:[{s_min},{s_max}] V:[{v_min},{v_max}]", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.putText(mask_color, f"White pixels = Detected green", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                cv2.putText(result_frame, f"Detected: {detected_count} objects", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(result_frame, f"Area filter: [{area_min}, {area_max}]", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                cv2.putText(result_frame, f"Press 's' to save config", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # 显示所有窗口
                cv2.imshow(window_name, frame)
                cv2.imshow(mask_window, mask_color)
                cv2.imshow(result_window, result_frame)
                
                # 处理按键
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == ord('Q'):
                    print("\n[Quit] Exiting tuner...")
                    break
                elif key == ord('s') or key == ord('S'):
                    save_green_config(h_min, h_max, s_min, s_max, v_min, v_max, area_min, area_max)
                    
            except Exception as e:
                print(f"Error: {e}")
                break
        
    finally:
        # 清理资源
        mvsdk.CameraUnInit(hCamera)
        mvsdk.CameraAlignFree(pFrameBuffer)
        cv2.destroyAllWindows()
        print("\n[Cleanup] Camera released, windows closed")

if __name__ == '__main__':
    main()
