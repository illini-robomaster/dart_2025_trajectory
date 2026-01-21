#coding=utf-8
"""
工业相机实时显示程序
按 'q' 键退出
按 's' 键保存当前帧
按 '+' 键增加曝光时间
按 '-' 键减少曝光时间
按 'a' 键切换自动/手动曝光
"""
import cv2
import numpy as np
import mvsdk
import platform
import time
from datetime import datetime

def main():
    print("=" * 50)
    print("工业相机实时显示程序")
    print("=" * 50)
    
    # 枚举相机
    print("\n正在搜索相机...")
    DevList = mvsdk.CameraEnumerateDevice()
    nDev = len(DevList)
    
    if nDev < 1:
        print("错误：未找到相机！")
        print("请检查：")
        print("  1. 相机是否正确连接")
        print("  2. 相机驱动是否已安装")
        print("  3. USB/网线连接是否正常")
        return

    print(f"\n找到 {nDev} 个相机：")
    for i, DevInfo in enumerate(DevList):
        print(f"  [{i}]: {DevInfo.GetFriendlyName()} ({DevInfo.GetPortType()})")
    
    # 选择相机
    if nDev == 1:
        i = 0
        print(f"\n自动选择相机 [0]")
    else:
        i = int(input("\n请输入要使用的相机编号: "))
    
    DevInfo = DevList[i]
    print(f"\n使用相机: {DevInfo.GetFriendlyName()}")

    # 打开相机
    hCamera = 0
    try:
        hCamera = mvsdk.CameraInit(DevInfo, -1, -1)
    except mvsdk.CameraException as e:
        print(f"相机初始化失败 ({e.error_code}): {e.message}")
        return

    try:
        # 获取相机特性描述
        cap = mvsdk.CameraGetCapability(hCamera)

        # 判断是黑白相机还是彩色相机
        monoCamera = (cap.sIspCapacity.bMonoSensor != 0)
        camera_type = "黑白相机" if monoCamera else "彩色相机"
        print(f"相机类型: {camera_type}")
        print(f"分辨率: {cap.sResolutionRange.iWidthMax} x {cap.sResolutionRange.iHeightMax}")

        # 黑白相机让ISP直接输出MONO数据，而不是扩展成R=G=B的24位灰度
        if monoCamera:
            mvsdk.CameraSetIspOutFormat(hCamera, mvsdk.CAMERA_MEDIA_TYPE_MONO8)
        else:
            mvsdk.CameraSetIspOutFormat(hCamera, mvsdk.CAMERA_MEDIA_TYPE_BGR8)

        # 相机模式切换成连续采集
        mvsdk.CameraSetTriggerMode(hCamera, 0)

        # 启用自动曝光，获得更好的画面
        auto_exposure = True
        exposure_time = 50 * 1000  # 微秒
        mvsdk.CameraSetAeState(hCamera, 1)
        print("已启用自动曝光模式")

        # 让SDK内部取图线程开始工作
        mvsdk.CameraPlay(hCamera)

        # 计算RGB buffer所需的大小，这里直接按照相机的最大分辨率来分配
        FrameBufferSize = cap.sResolutionRange.iWidthMax * cap.sResolutionRange.iHeightMax * (1 if monoCamera else 3)

        # 分配RGB buffer，用来存放ISP输出的图像
        pFrameBuffer = mvsdk.CameraAlignMalloc(FrameBufferSize, 16)

        print("\n" + "=" * 50)
        print("实时显示中...")
        print("操作说明：")
        print("  [q] - 退出程序")
        print("  [s] - 保存当前帧")
        print("  [+] - 增加曝光时间 (+5ms)")
        print("  [-] - 减少曝光时间 (-5ms)")
        print("  [a] - 切换自动/手动曝光")
        print("=" * 50 + "\n")

        # 帧率计算
        fps_time = time.time()
        fps_counter = 0
        fps = 0

        window_name = "工业相机实时显示 - 按 'q' 退出"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        while True:
            try:
                # 从相机取一帧图片
                pRawData, FrameHead = mvsdk.CameraGetImageBuffer(hCamera, 200)
                mvsdk.CameraImageProcess(hCamera, pRawData, pFrameBuffer, FrameHead)
                mvsdk.CameraReleaseImageBuffer(hCamera, pRawData)

                # windows下取到的图像数据是上下颠倒的，以BMP格式存放。转换成opencv则需要上下翻转成正的
                # linux下直接输出正的，不需要上下翻转
                if platform.system() == "Windows":
                    mvsdk.CameraFlipFrameBuffer(pFrameBuffer, FrameHead, 1)
                
                # 此时图片已经存储在pFrameBuffer中，对于彩色相机pFrameBuffer=RGB数据，黑白相机pFrameBuffer=8位灰度数据
                # 把pFrameBuffer转换成opencv的图像格式以进行后续算法处理
                frame_data = (mvsdk.c_ubyte * FrameHead.uBytes).from_address(pFrameBuffer)
                frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = frame.reshape((FrameHead.iHeight, FrameHead.iWidth, 
                                      1 if FrameHead.uiMediaType == mvsdk.CAMERA_MEDIA_TYPE_MONO8 else 3))

                # 计算帧率
                fps_counter += 1
                if time.time() - fps_time > 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_time = time.time()

                # 只在每5帧显示一次信息，减少文字渲染开销
                if fps_counter % 5 == 0:
                    info_y = 30
                    info_color = (0, 255, 0) if not monoCamera else 255
                    cv2.putText(frame, f"FPS: {fps}", (10, info_y), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, info_color, 1)
                    cv2.putText(frame, f"{FrameHead.iWidth}x{FrameHead.iHeight}", (10, info_y + 25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, info_color, 1)
                    cv2.putText(frame, f"Exp: {exposure_time/1000:.0f}ms {'(A)' if auto_exposure else '(M)'}", 
                               (10, info_y + 45),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, info_color, 1)

                # 显示图像（不缩放）
                cv2.imshow(window_name, frame)
                
                # 处理键盘事件
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    print("\n退出程序...")
                    break
                elif key == ord('s'):
                    # 保存图片
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"camera_capture_{timestamp}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"已保存图片: {filename}")
                elif key == ord('+') or key == ord('='):
                    # 增加曝光时间
                    if not auto_exposure:
                        exposure_time = min(exposure_time + 5000, 1000000)  # 最大1秒
                        mvsdk.CameraSetExposureTime(hCamera, exposure_time)
                        print(f"曝光时间: {exposure_time/1000:.1f}ms")
                elif key == ord('-') or key == ord('_'):
                    # 减少曝光时间
                    if not auto_exposure:
                        exposure_time = max(exposure_time - 5000, 100)  # 最小0.1ms
                        mvsdk.CameraSetExposureTime(hCamera, exposure_time)
                        print(f"曝光时间: {exposure_time/1000:.1f}ms")
                elif key == ord('a') or key == ord('A'):
                    # 切换自动/手动曝光
                    auto_exposure = not auto_exposure
                    mvsdk.CameraSetAeState(hCamera, 1 if auto_exposure else 0)
                    if auto_exposure:
                        print("已切换到自动曝光")
                    else:
                        print("已切换到手动曝光")
                        exposure_time = mvsdk.CameraGetExposureTime(hCamera)
                
            except mvsdk.CameraException as e:
                if e.error_code != mvsdk.CAMERA_STATUS_TIME_OUT:
                    print(f"获取图像失败 ({e.error_code}): {e.message}")

    finally:
        # 关闭相机
        mvsdk.CameraUnInit(hCamera)

        # 释放帧缓存
        mvsdk.CameraAlignFree(pFrameBuffer)

        # 关闭所有窗口
        cv2.destroyAllWindows()
        
        print("相机已关闭")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cv2.destroyAllWindows()
