#coding=utf-8
"""
工业相机 Web 实时显示程序
在浏览器中访问 http://localhost:5000 查看实时画面
按 Ctrl+C 退出
"""
import cv2
import numpy as np
import mvsdk
import platform
import time
from datetime import datetime
from flask import Flask, render_template, Response, jsonify, request
import threading

app = Flask(__name__)

# 全局变量
camera_handler = None
current_frame = None
camera_info = {}
frame_lock = threading.Lock()

class CameraHandler:
    def __init__(self):
        self.hCamera = None
        self.pFrameBuffer = None
        self.running = False
        self.monoCamera = False
        self.exposure_time = 100 * 1000  # 增加到100ms
        self.auto_exposure = True  # 默认启用自动曝光
        self.fps = 0
        self.fps_counter = 0
        self.fps_time = time.time()
        
    def initialize(self):
        """初始化相机"""
        global camera_info
        
        # 枚举相机
        print("正在搜索相机...")
        DevList = mvsdk.CameraEnumerateDevice()
        nDev = len(DevList)
        
        if nDev < 1:
            raise Exception("未找到相机！")
        
        print(f"找到 {nDev} 个相机：")
        for i, DevInfo in enumerate(DevList):
            print(f"  [{i}]: {DevInfo.GetFriendlyName()} ({DevInfo.GetPortType()})")
        
        # 选择第一个相机
        DevInfo = DevList[0]
        print(f"使用相机: {DevInfo.GetFriendlyName()}")
        
        # 打开相机
        try:
            self.hCamera = mvsdk.CameraInit(DevInfo, -1, -1)
        except mvsdk.CameraException as e:
            raise Exception(f"相机初始化失败 ({e.error_code}): {e.message}")
        
        # 获取相机特性描述
        cap = mvsdk.CameraGetCapability(self.hCamera)
        
        # 判断是黑白相机还是彩色相机
        self.monoCamera = (cap.sIspCapacity.bMonoSensor != 0)
        camera_type = "黑白相机" if self.monoCamera else "彩色相机"
        
        camera_info = {
            'name': DevInfo.GetFriendlyName(),
            'type': camera_type,
            'width': cap.sResolutionRange.iWidthMax,
            'height': cap.sResolutionRange.iHeightMax,
            'port': DevInfo.GetPortType()
        }
        
        print(f"相机类型: {camera_type}")
        print(f"分辨率: {cap.sResolutionRange.iWidthMax} x {cap.sResolutionRange.iHeightMax}")
        
        # 设置输出格式
        if self.monoCamera:
            mvsdk.CameraSetIspOutFormat(self.hCamera, mvsdk.CAMERA_MEDIA_TYPE_MONO8)
        else:
            mvsdk.CameraSetIspOutFormat(self.hCamera, mvsdk.CAMERA_MEDIA_TYPE_BGR8)
        
        # 相机模式切换成连续采集
        mvsdk.CameraSetTriggerMode(self.hCamera, 0)
        
        # 启用自动曝光
        mvsdk.CameraSetAeState(self.hCamera, 1)
        print(f"已启用自动曝光模式")
        
        # 如果需要，也可以设置曝光时间范围
        # mvsdk.CameraSetExposureTime(self.hCamera, self.exposure_time)
        
        # 让SDK内部取图线程开始工作
        mvsdk.CameraPlay(self.hCamera)
        
        # 分配帧缓存
        FrameBufferSize = cap.sResolutionRange.iWidthMax * cap.sResolutionRange.iHeightMax * (1 if self.monoCamera else 3)
        self.pFrameBuffer = mvsdk.CameraAlignMalloc(FrameBufferSize, 16)
        
        print("相机初始化成功！")
        return True
    
    def capture_loop(self):
        """持续采集图像"""
        global current_frame
        
        self.running = True
        
        while self.running:
            try:
                # 从相机取一帧图片
                pRawData, FrameHead = mvsdk.CameraGetImageBuffer(self.hCamera, 200)
                mvsdk.CameraImageProcess(self.hCamera, pRawData, self.pFrameBuffer, FrameHead)
                mvsdk.CameraReleaseImageBuffer(self.hCamera, pRawData)
                
                # Windows下需要翻转
                if platform.system() == "Windows":
                    mvsdk.CameraFlipFrameBuffer(self.pFrameBuffer, FrameHead, 1)
                
                # 转换为numpy数组
                frame_data = (mvsdk.c_ubyte * FrameHead.uBytes).from_address(self.pFrameBuffer)
                frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = frame.reshape((FrameHead.iHeight, FrameHead.iWidth, 
                                      1 if FrameHead.uiMediaType == mvsdk.CAMERA_MEDIA_TYPE_MONO8 else 3))
                
                # 检查图像是否全黑
                if self.fps_counter == 1:  # 只在第一帧打印
                    mean_val = np.mean(frame)
                    print(f"图像平均亮度: {mean_val:.2f}, 最大值: {np.max(frame)}, 最小值: {np.min(frame)}")
                    if mean_val < 5:
                        print("警告：图像太暗，尝试获取当前曝光值...")
                        current_exp = mvsdk.CameraGetExposureTime(self.hCamera)
                        print(f"当前曝光时间: {current_exp/1000:.1f}ms")
                
                # 计算帧率
                self.fps_counter += 1
                if time.time() - self.fps_time > 1.0:
                    self.fps = self.fps_counter
                    self.fps_counter = 0
                    self.fps_time = time.time()
                
                # 在图像上显示信息
                info_color = (0, 255, 0) if not self.monoCamera else 255
                cv2.putText(frame, f"FPS: {self.fps}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, info_color, 2)
                cv2.putText(frame, f"Resolution: {FrameHead.iWidth}x{FrameHead.iHeight}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, info_color, 2)
                cv2.putText(frame, f"Exposure: {self.exposure_time/1000:.1f}ms {'(Auto)' if self.auto_exposure else '(Manual)'}", 
                           (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, info_color, 2)
                
                # 更新当前帧
                with frame_lock:
                    current_frame = frame.copy()
                
            except mvsdk.CameraException as e:
                if e.error_code != mvsdk.CAMERA_STATUS_TIME_OUT:
                    print(f"获取图像失败 ({e.error_code}): {e.message}")
                time.sleep(0.01)
    
    def set_exposure(self, value):
        """设置曝光时间（毫秒）"""
        try:
            self.exposure_time = int(value * 1000)  # 转换为微秒
            self.exposure_time = max(100, min(self.exposure_time, 1000000))
            mvsdk.CameraSetExposureTime(self.hCamera, self.exposure_time)
            return True
        except Exception as e:
            print(f"设置曝光失败: {e}")
            return False
    
    def toggle_auto_exposure(self):
        """切换自动/手动曝光"""
        try:
            self.auto_exposure = not self.auto_exposure
            mvsdk.CameraSetAeState(self.hCamera, 1 if self.auto_exposure else 0)
            if not self.auto_exposure:
                self.exposure_time = mvsdk.CameraGetExposureTime(self.hCamera)
            return self.auto_exposure
        except Exception as e:
            print(f"切换曝光模式失败: {e}")
            return self.auto_exposure
    
    def save_frame(self):
        """保存当前帧"""
        global current_frame
        with frame_lock:
            if current_frame is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"camera_capture_{timestamp}.jpg"
                cv2.imwrite(filename, current_frame)
                return filename
        return None
    
    def cleanup(self):
        """清理资源"""
        self.running = False
        if self.hCamera:
            mvsdk.CameraUnInit(self.hCamera)
        if self.pFrameBuffer:
            mvsdk.CameraAlignFree(self.pFrameBuffer)
        print("相机已关闭")

def generate_frames():
    """生成视频流"""
    global current_frame
    
    while True:
        with frame_lock:
            if current_frame is None:
                time.sleep(0.1)
                continue
            
            frame = current_frame.copy()
        
        # 编码为JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        
        # 生成multipart响应
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    """主页"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>工业相机实时显示</title>
        <meta charset="utf-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #2c3e50;
                color: #ecf0f1;
                margin: 0;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            h1 {
                text-align: center;
                color: #3498db;
            }
            .video-container {
                background: #34495e;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: center;
            }
            img {
                max-width: 100%;
                border: 3px solid #3498db;
                border-radius: 5px;
            }
            .controls {
                background: #34495e;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }
            .control-group {
                margin: 15px 0;
            }
            label {
                display: inline-block;
                width: 150px;
                font-weight: bold;
            }
            input[type="range"] {
                width: 300px;
                vertical-align: middle;
            }
            button {
                background: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                margin: 5px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
            }
            button:hover {
                background: #2980b9;
            }
            .info {
                background: #34495e;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
            }
            .info-item {
                margin: 8px 0;
            }
            #status {
                color: #2ecc71;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 工业相机实时显示系统</h1>
            
            <div class="info">
                <h3>相机信息</h3>
                <div class="info-item">名称: <span id="camera-name">加载中...</span></div>
                <div class="info-item">类型: <span id="camera-type">加载中...</span></div>
                <div class="info-item">分辨率: <span id="camera-resolution">加载中...</span></div>
                <div class="info-item">接口: <span id="camera-port">加载中...</span></div>
                <div class="info-item">状态: <span id="status">运行中</span></div>
            </div>
            
            <div class="video-container">
                <img src="/video_feed" alt="相机画面">
            </div>
            
            <div class="controls">
                <h3>控制面板</h3>
                
                <div class="control-group">
                    <label>曝光时间 (ms):</label>
                    <input type="range" id="exposure" min="0.1" max="200" step="0.5" value="100">
                    <span id="exposure-value">100.0</span> ms
                    <span style="margin-left: 20px; color: #95a5a6;">提示: 如果画面太暗，增加曝光时间或启用自动曝光</span>
                </div>
                
                <div class="control-group">
                    <button onclick="toggleAutoExposure()">切换自动/手动曝光</button>
                    <button onclick="saveFrame()">保存当前帧</button>
                </div>
            </div>
        </div>
        
        <script>
            // 加载相机信息
            fetch('/camera_info')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('camera-name').textContent = data.name;
                    document.getElementById('camera-type').textContent = data.type;
                    document.getElementById('camera-resolution').textContent = data.width + ' x ' + data.height;
                    document.getElementById('camera-port').textContent = data.port;
                });
            
            // 曝光控制
            const exposureSlider = document.getElementById('exposure');
            const exposureValue = document.getElementById('exposure-value');
            
            exposureSlider.addEventListener('input', function() {
                exposureValue.textContent = this.value;
            });
            
            exposureSlider.addEventListener('change', function() {
                fetch('/set_exposure?value=' + this.value)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            console.log('曝光设置成功');
                        }
                    });
            });
            
            // 切换自动曝光
            function toggleAutoExposure() {
                fetch('/toggle_auto_exposure')
                    .then(response => response.json())
                    .then(data => {
                        alert(data.auto ? '已切换到自动曝光' : '已切换到手动曝光');
                    });
            }
            
            // 保存图片
            function saveFrame() {
                fetch('/save_frame')
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            alert('图片已保存: ' + data.filename);
                        } else {
                            alert('保存失败');
                        }
                    });
            }
        </script>
    </body>
    </html>
    """
    return html

@app.route('/video_feed')
def video_feed():
    """视频流"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/camera_info')
def get_camera_info():
    """获取相机信息"""
    return jsonify(camera_info)

@app.route('/set_exposure')
def set_exposure():
    """设置曝光"""
    value = float(request.args.get('value', 30))
    success = camera_handler.set_exposure(value)
    return jsonify({'success': success})

@app.route('/toggle_auto_exposure')
def toggle_auto_exposure():
    """切换自动曝光"""
    auto = camera_handler.toggle_auto_exposure()
    return jsonify({'auto': auto})

@app.route('/save_frame')
def save_frame():
    """保存图片"""
    filename = camera_handler.save_frame()
    return jsonify({'success': filename is not None, 'filename': filename})

def main():
    global camera_handler
    
    print("=" * 60)
    print("工业相机 Web 实时显示系统")
    print("=" * 60)
    
    try:
        # 初始化相机
        camera_handler = CameraHandler()
        camera_handler.initialize()
        
        # 启动采集线程
        capture_thread = threading.Thread(target=camera_handler.capture_loop, daemon=True)
        capture_thread.start()
        
        # 等待第一帧
        print("\n等待相机准备...")
        while current_frame is None:
            time.sleep(0.1)
        
        print("\n" + "=" * 60)
        print("Web 服务器启动成功！")
        print("请在浏览器中访问: http://localhost:5000")
        print("或访问: http://0.0.0.0:5000")
        print("按 Ctrl+C 退出")
        print("=" * 60 + "\n")
        
        # 启动Web服务器
        app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
        
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if camera_handler:
            camera_handler.cleanup()

if __name__ == '__main__':
    main()
