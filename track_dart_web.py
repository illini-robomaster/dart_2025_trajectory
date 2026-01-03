from flask import Flask, render_template, Response, jsonify, request
import cv2
import numpy as np
import json
import os
from collections import deque
import base64

app = Flask(__name__)

# 全局变量
current_video_path = "f2c1d23f0f9186952eb6d78e283ffc0b_raw.mp4"
frame_buffer = []
current_frame_idx = 0
trajectory = deque(maxlen=500)
is_tracking = False
last_frame_idx = -1  # 记录上次处理的帧号
start_point = None  # 起始点
start_point_radius = 50  # 起始点半径

# 默认参数
params = {
    'R_min': 77, 'R_max': 246, 'G_min': 105, 'G_max': 255,
    'B_min': 0, 'B_max': 150, 'Min_Area': 26, 'Max_Area': 1906,
    'RG_ratio': 23, 'RB_diff': 70, 'Max_Jump': 158,
    'Exclude_Right': 582, 'Exclude_Bottom': 514,
    'Min_Motion': 27, 'Motion_Frames': 2
}

# 保存的配置（用于恢复）
saved_params = params.copy()

def load_video(video_path):
    global frame_buffer, current_frame_idx, last_frame_idx
    cap = cv2.VideoCapture(video_path)
    frame_buffer = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_buffer.append(frame.copy())
    
    cap.release()
    current_frame_idx = 0
    last_frame_idx = -1
    return len(frame_buffer)

def process_frame(frame_idx):
    """只负责渲染当前帧，不修改轨迹"""
    global frame_buffer, trajectory, params
    
    if frame_idx >= len(frame_buffer):
        return None, None
    
    frame = frame_buffer[frame_idx].copy()
    
    # RGB颜色空间检测
    lower = np.array([params['B_min'], params['G_min'], params['R_min']])
    upper = np.array([params['B_max'], params['G_max'], params['R_max']])
    mask1 = cv2.inRange(frame, lower, upper)
    
    # 颜色比例过滤
    b, g, r = cv2.split(frame.astype(np.float32) + 1)
    rb_mask = ((r - b) > params['RB_diff']).astype(np.uint8) * 255
    rg_mask = (np.abs(r / g - 1.0) < (200 - params['RG_ratio']) / 100.0).astype(np.uint8) * 255
    
    mask = cv2.bitwise_and(mask1, rb_mask)
    mask = cv2.bitwise_and(mask, rg_mask)
    
    # 形态学操作
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # 查找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_contours = []
    contour_index = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if params['Min_Area'] < area < params['Max_Area']:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # 区域过滤
                if params['Exclude_Right'] > 0 and cx > params['Exclude_Right']:
                    cv2.drawContours(frame, [contour], -1, (128, 128, 128), 1)
                    cv2.putText(frame, "EXCLUDED", (cx-30, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (128, 128, 128), 1)
                    continue
                if params['Exclude_Bottom'] > 0 and cy > params['Exclude_Bottom']:
                    cv2.drawContours(frame, [contour], -1, (128, 128, 128), 1)
                    cv2.putText(frame, "EXCLUDED", (cx-30, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (128, 128, 128), 1)
                    continue
                
                valid_contours.append(contour)
                # 绘制候选轮廓，带编号
                cv2.drawContours(frame, [contour], -1, (255, 0, 255), 2)
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 255), 1)
                cv2.putText(frame, f"#{contour_index}", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
                cv2.putText(frame, f"{int(area)}", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
                contour_index += 1
    
    # 绘制当前帧检测到的最佳轮廓
    if valid_contours:
        best_contour = max(valid_contours, key=lambda c: cv2.contourArea(c))
        M = cv2.moments(best_contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            cv2.drawContours(frame, [best_contour], -1, (0, 255, 255), 2)
            cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
    
    # 绘制完整轨迹（使用已经计算好的trajectory）
    if len(trajectory) > 1:
        for i in range(1, len(trajectory)):
            cv2.line(frame, trajectory[i - 1], trajectory[i], (0, 0, 255), 2)
        cv2.circle(frame, trajectory[0], 8, (255, 0, 0), -1)
        cv2.circle(frame, trajectory[-1], 8, (0, 255, 0), -1)
    
    # 排除区域标记 - 更明显的显示
    height, width = frame.shape[:2]
    if params['Exclude_Right'] > 0 and params['Exclude_Right'] < width:
        # 绘制红色虚线和半透明区域
        for y in range(0, height, 20):
            cv2.line(frame, (params['Exclude_Right'], y), (params['Exclude_Right'], min(y+10, height)), (0, 0, 255), 3)
        cv2.putText(frame, "EXCLUDE RIGHT", (params['Exclude_Right'] + 10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        # 添加箭头
        cv2.arrowedLine(frame, (params['Exclude_Right']+50, 30), (params['Exclude_Right']+10, 30), (0, 0, 255), 2)
    
    if params['Exclude_Bottom'] > 0 and params['Exclude_Bottom'] < height:
        # 绘制红色虚线和半透明区域
        for x in range(0, width, 20):
            cv2.line(frame, (x, params['Exclude_Bottom']), (min(x+10, width), params['Exclude_Bottom']), (0, 0, 255), 3)
        cv2.putText(frame, "EXCLUDE BOTTOM", (10, params['Exclude_Bottom'] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    # 绘制起始点
    global start_point, start_point_radius
    if start_point is not None:
        cv2.circle(frame, start_point, start_point_radius, (0, 255, 255), 3)
        cv2.circle(frame, start_point, 5, (0, 255, 255), -1)
        cv2.putText(frame, "START", (start_point[0] - 25, start_point[1] - start_point_radius - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    # 信息文字
    cv2.putText(frame, f"Frame: {frame_idx + 1}/{len(frame_buffer)}", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, f"Contours: {len(valid_contours)}", (10, 60),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, f"Trajectory: {len(trajectory)} pts", (10, 90),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return frame, mask

@app.route('/')
def index():
    return render_template('track_dart.html')

@app.route('/load_video', methods=['POST'])
def load_video_route():
    data = request.json
    video_path = data.get('video_path', current_video_path)
    
    # 如果是相对路径，转换为绝对路径
    if not os.path.isabs(video_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        video_path = os.path.join(script_dir, video_path)
    
    if not os.path.exists(video_path):
        return jsonify({'error': f'Video file not found: {video_path}'}), 404
    
    frame_count = load_video(video_path)
    trajectory.clear()
    
    return jsonify({
        'success': True,
        'frame_count': frame_count,
        'video_path': video_path
    })

@app.route('/get_frame/<int:frame_idx>')
def get_frame(frame_idx):
    global trajectory, last_frame_idx
    
    if frame_idx >= len(frame_buffer) or frame_idx < 0:
        return jsonify({'error': 'Invalid frame index'}), 400
    
    # 如果不是连续帧或者往回跳了，需要重新计算轨迹
    if frame_idx != last_frame_idx + 1:
        trajectory.clear()
        start_frame = 0
    else:
        # 连续播放，从上一帧继续
        start_frame = frame_idx
    
    # 只计算需要的帧
    for i in range(start_frame, frame_idx + 1):
        if i >= len(frame_buffer):
            break
        
        frame_temp = frame_buffer[i].copy()
        
        # RGB颜色空间检测
        lower = np.array([params['B_min'], params['G_min'], params['R_min']])
        upper = np.array([params['B_max'], params['G_max'], params['R_max']])
        mask1 = cv2.inRange(frame_temp, lower, upper)
        
        # 颜色比例过滤
        b, g, r = cv2.split(frame_temp.astype(np.float32) + 1)
        rb_mask = ((r - b) > params['RB_diff']).astype(np.uint8) * 255
        rg_mask = (np.abs(r / g - 1.0) < (200 - params['RG_ratio']) / 100.0).astype(np.uint8) * 255
        
        mask_temp = cv2.bitwise_and(mask1, rb_mask)
        mask_temp = cv2.bitwise_and(mask_temp, rg_mask)
        
        # 形态学操作
        kernel = np.ones((3, 3), np.uint8)
        mask_temp = cv2.morphologyEx(mask_temp, cv2.MORPH_OPEN, kernel, iterations=1)
        mask_temp = cv2.morphologyEx(mask_temp, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask_temp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if params['Min_Area'] < area < params['Max_Area']:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # 区域过滤
                    if params['Exclude_Right'] > 0 and cx > params['Exclude_Right']:
                        continue
                    if params['Exclude_Bottom'] > 0 and cy > params['Exclude_Bottom']:
                        continue
                    
                    valid_contours.append(contour)
        
        # 追踪
        if valid_contours:
            best_contour = max(valid_contours, key=lambda c: cv2.contourArea(c))
            M = cv2.moments(best_contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                trajectory.append((cx, cy))
    
    # 更新最后处理的帧号
    last_frame_idx = frame_idx
    
    # 现在渲染当前帧
    frame, mask = process_frame(frame_idx)
    
    if frame is None:
        return jsonify({'error': 'Invalid frame index'}), 400
    
    # 转换为JPEG
    _, buffer_frame = cv2.imencode('.jpg', frame)
    _, buffer_mask = cv2.imencode('.jpg', mask)
    
    # Base64编码
    frame_base64 = base64.b64encode(buffer_frame).decode('utf-8')
    mask_base64 = base64.b64encode(buffer_mask).decode('utf-8')
    
    return jsonify({
        'frame': frame_base64,
        'mask': mask_base64,
        'frame_idx': frame_idx,
        'total_frames': len(frame_buffer)
    })

@app.route('/update_params', methods=['POST'])
def update_params():
    global params, last_frame_idx
    data = request.json
    params.update(data)
    last_frame_idx = -1  # 参数改变时重置
    return jsonify({'success': True, 'params': params})

@app.route('/get_params')
def get_params():
    return jsonify(params)

@app.route('/reset_trajectory', methods=['POST'])
def reset_trajectory():
    global trajectory, current_frame_idx, last_frame_idx
    trajectory.clear()
    last_frame_idx = -1
    current_frame_idx = 0
    return jsonify({'success': True})

@app.route('/save_config', methods=['POST'])
def save_config():
    global saved_params
    with open('dart_track_config.json', 'w', encoding='utf-8') as f:
        json.dump(params, f, indent=2, ensure_ascii=False)
    saved_params = params.copy()  # 更新保存的配置
    return jsonify({'success': True, 'message': 'Configuration saved'})

@app.route('/load_saved_config', methods=['POST'])
def load_saved_config():
    global params, last_frame_idx
    params = saved_params.copy()
    last_frame_idx = -1
    return jsonify({'success': True, 'params': params})

@app.route('/set_start_point', methods=['POST'])
def set_start_point():
    global start_point, last_frame_idx
    data = request.json
    x = data.get('x')
    y = data.get('y')
    
    if x is not None and y is not None:
        start_point = (int(x), int(y))
        last_frame_idx = -1  # 重置以重新计算轨迹
        return jsonify({'success': True, 'start_point': start_point})
    else:
        start_point = None
        return jsonify({'success': True, 'start_point': None})

if __name__ == '__main__':
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 加载初始视频（使用绝对路径）
    video_path_abs = os.path.join(script_dir, current_video_path)
    if os.path.exists(video_path_abs):
        print(f"正在加载视频: {video_path_abs}")
        load_video(video_path_abs)
        print(f"视频加载完成，共 {len(frame_buffer)} 帧")
    else:
        print(f"警告: 视频文件不存在: {video_path_abs}")
        print(f"当前工作目录: {os.getcwd()}")
        print(f"脚本目录: {script_dir}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
