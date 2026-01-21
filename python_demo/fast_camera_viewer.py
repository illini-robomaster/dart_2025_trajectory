#coding=utf-8
"""
工业相机高性能实时显示程序 - 优化版
针对树莓派本地显示优化，追求最高帧率
操作说明：
  q - 退出
  s - 保存当前帧
  + - 增加曝光 
  - - 减少曝光
  a - 切换自动/手动曝光
"""
import cv2
import numpy as np
import mvsdk
import platform
import time
from datetime import datetime

def main():
    print("=" * 50)
    print("工业相机高性能实时显示")
    print("=" * 50)
    
    # 枚举相机
    print("正在搜索相机...")
    DevList = mvsdk.CameraEnumerateDevice()
    nDev = len(DevList)
    if nDev < 1:
        print("错误：未找到相机！")
        return

    print(f"\n找到 {nDev} 个相机：")
    for i, DevInfo in enumerate(DevList):
        print(f"  [{i}]: {DevInfo.GetFriendlyName()} ({DevInfo.GetPortType()})")
    
    i = 0 if nDev == 1 else int(input("\n选择相机编号: "))
    DevInfo = DevList[i]
    print(f"\n使用: {DevInfo.GetFriendlyName()}")

    # 打开相机
    print("正在初始化相机...")
    try:
        hCamera = mvsdk.CameraInit(DevInfo, -1, -1)
    except mvsdk.CameraException as e:
        print(f"初始化失败: {e.message}")
        return

    try:
        print("正在配置相机参数...")
        cap = mvsdk.CameraGetCapability(hCamera)
        monoCamera = (cap.sIspCapacity.bMonoSensor != 0)
        
        print(f"类型: {'黑白' if monoCamera else '彩色'}")
        print(f"最大分辨率: {cap.sResolutionRange.iWidthMax}x{cap.sResolutionRange.iHeightMax}")

        # 降低相机采集分辨率以提高帧率
        try:
            # 列出所有可用的预设分辨率
            print(f"\n相机支持 {cap.sResolutionRange.iImageSizeDesc} 种预设分辨率:")
            for i in range(cap.sResolutionRange.iImageSizeDesc):
                desc = cap.pImageSizeDesc[i]
                print(f"  [{i}] {desc.iWidth}x{desc.iHeight}")
            
            # 选择最小的分辨率以获得最高帧率
            target_index = cap.sResolutionRange.iImageSizeDesc - 1  # 通常最后一个是最小的
            min_pixels = float('inf')
            for i in range(cap.sResolutionRange.iImageSizeDesc):
                desc = cap.pImageSizeDesc[i]
                pixels = desc.iWidth * desc.iHeight
                if pixels < min_pixels:
                    min_pixels = pixels
                    target_index = i
            
            if target_index >= 0:
                mvsdk.CameraSetImageResolution(hCamera, cap.pImageSizeDesc[target_index])
                new_res = mvsdk.CameraGetImageResolution(hCamera)
                print(f"\n已设置相机分辨率为: {new_res.iWidth}x{new_res.iHeight}")
            else:
                print("\n未找到合适的低分辨率预设，使用默认分辨率")
        except Exception as e:
            print(f"设置分辨率失败: {e}")

        # 设置输出格式
        if monoCamera:
            mvsdk.CameraSetIspOutFormat(hCamera, mvsdk.CAMERA_MEDIA_TYPE_MONO8)
        else:
            mvsdk.CameraSetIspOutFormat(hCamera, mvsdk.CAMERA_MEDIA_TYPE_BGR8)

        # 连续采集模式
        mvsdk.CameraSetTriggerMode(hCamera, 0)

        # 自动曝光
        auto_exposure = True
        exposure_time = 50 * 1000
        mvsdk.CameraSetAeState(hCamera, 1)
        print("已启用自动曝光")

        # 开始采集
        mvsdk.CameraPlay(hCamera)

        # 分配缓存
        FrameBufferSize = cap.sResolutionRange.iWidthMax * cap.sResolutionRange.iHeightMax * (1 if monoCamera else 3)
        pFrameBuffer = mvsdk.CameraAlignMalloc(FrameBufferSize, 16)

        print("\n[q]退出 [s]保存 [+/-]曝光 [a]自动曝光")
        print("=" * 50 + "\n")

        # 性能计数
        fps_time = time.time()
        fps_counter = 0
        fps = 0
        frame_count = 0

        # 创建窗口（固定大小，不随手动调整而缩放）
        window_name = "工业相机 - 按q退出"
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
        
        print("\n启动完成！开始采集...")

        while True:
            try:
                # 获取图像
                pRawData, FrameHead = mvsdk.CameraGetImageBuffer(hCamera, 200)
                mvsdk.CameraImageProcess(hCamera, pRawData, pFrameBuffer, FrameHead)
                mvsdk.CameraReleaseImageBuffer(hCamera, pRawData)

                if platform.system() == "Windows":
                    mvsdk.CameraFlipFrameBuffer(pFrameBuffer, FrameHead, 1)
                
                # 转换为numpy
                frame_data = (mvsdk.c_ubyte * FrameHead.uBytes).from_address(pFrameBuffer)
                frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = frame.reshape((FrameHead.iHeight, FrameHead.iWidth, 
                                      1 if FrameHead.uiMediaType == mvsdk.CAMERA_MEDIA_TYPE_MONO8 else 3))

                # 计算FPS
                fps_counter += 1
                frame_count += 1
                if time.time() - fps_time > 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_time = time.time()

                # 缩小显示窗口到320x240以提高性能和减小窗口大小
                display_frame = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_NEAREST)

                # 显示完整信息（相机实际采集分辨率）
                color = (0, 255, 0) if not monoCamera else 255
                cv2.putText(display_frame, f"FPS: {fps}", (5, 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                cv2.putText(display_frame, f"Cam: {FrameHead.iWidth}x{FrameHead.iHeight}", (5, 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                cv2.putText(display_frame, f"Exp: {'Auto' if auto_exposure else f'{exposure_time/1000:.0f}ms'}", (5, 58), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

                # 显示
                cv2.imshow(window_name, display_frame)
                
                # 键盘控制 - waitKey(1) 可以提供更高帧率
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    print("\n退出...")
                    break
                elif key == ord('s'):
                    # 保存原始分辨率的图像
                    filename = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"已保存: {filename}")
                elif key == ord('+') or key == ord('='):
                    if not auto_exposure:
                        exposure_time = min(exposure_time + 5000, 1000000)
                        mvsdk.CameraSetExposureTime(hCamera, exposure_time)
                        print(f"曝光: {exposure_time/1000:.1f}ms")
                elif key == ord('-') or key == ord('_'):
                    if not auto_exposure:
                        exposure_time = max(exposure_time - 5000, 100)
                        mvsdk.CameraSetExposureTime(hCamera, exposure_time)
                        print(f"曝光: {exposure_time/1000:.1f}ms")
                elif key == ord('a') or key == ord('A'):
                    auto_exposure = not auto_exposure
                    mvsdk.CameraSetAeState(hCamera, 1 if auto_exposure else 0)
                    print(f"{'自动' if auto_exposure else '手动'}曝光")
                    if not auto_exposure:
                        exposure_time = mvsdk.CameraGetExposureTime(hCamera)
                
            except mvsdk.CameraException as e:
                if e.error_code != mvsdk.CAMERA_STATUS_TIME_OUT:
                    print(f"错误: {e.message}")

    finally:
        mvsdk.CameraUnInit(hCamera)
        mvsdk.CameraAlignFree(pFrameBuffer)
        cv2.destroyAllWindows()
        print("相机已关闭")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cv2.destroyAllWindows()
