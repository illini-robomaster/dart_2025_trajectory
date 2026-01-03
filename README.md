# Dart 2025 Trajectory Tracking System

A computer vision-based dart trajectory tracking system for RoboMaster competitions. This project uses OpenCV to detect and track yellow darts in video footage, visualizing their flight paths in real-time or post-processing.

## 🎯 Features

- **Real-time Dart Detection**: Track yellow-colored darts using RGB color space filtering
- **Trajectory Visualization**: Display the complete flight path with motion trails
- **Web Interface**: Interactive web-based parameter tuning and visualization
- **Color Range Adjustment**: Built-in tools for calibrating color detection parameters
- **Multi-mode Processing**: Support for single dart, multi-dart, and RGB-based tracking
- **Configurable Parameters**: JSON-based configuration for easy parameter management

## 📁 Project Structure

```
dart_2025_trajectory/
├── src/                          # Source code
│   ├── track_dart.py            # Main tracking script
│   ├── track_dart_rgb.py        # RGB-based tracking
│   ├── track_single_dart.py     # Single dart tracking
│   ├── track_dart_web.py        # Web interface with Flask
│   └── adjust_color_range.py    # Color calibration tool
├── templates/                    # HTML templates
│   └── track_dart.html          # Web interface template
├── data/                         # Input video files
├── output/                       # Generated output videos
├── examples/                     # Example videos and results
├── dart_track_config.json       # Configuration parameters
├── requirements.txt             # Python dependencies
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

## 🚀 Getting Started

### Prerequisites

- Python 3.7+
- OpenCV
- NumPy
- Flask (for web interface)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/illini-robomaster/dart_2025_trajectory.git
cd dart_2025_trajectory
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## 📖 Usage

### Basic Tracking

Track a dart in a video file:

```bash
python src/track_dart.py
```

The script will process the video and save the output with trajectory overlay.

### Web Interface

Launch the interactive web interface for real-time parameter tuning:

```bash
python src/track_dart_web.py
```

Then open your browser and navigate to `http://localhost:5000`

Features:
- Real-time parameter adjustment
- Frame-by-frame analysis
- Live trajectory preview
- Configuration save/load

### Color Calibration

Adjust color detection parameters for different lighting conditions:

```bash
python src/adjust_color_range.py
```

Use the trackbars to fine-tune HSV/RGB ranges until the dart is properly detected.

### Configuration

Edit `dart_track_config.json` to customize tracking parameters:

```json
{
  "R_min": 77,
  "R_max": 246,
  "G_min": 105,
  "G_max": 255,
  "B_min": 0,
  "B_max": 150,
  "Min_Area": 26,
  "Max_Area": 1906,
  "RG_ratio": 23,
  "RB_diff": 70,
  "Max_Jump": 158,
  "Exclude_Right": 480,
  "Exclude_Bottom": 701,
  "Min_Motion": 27,
  "Motion_Frames": 2
}
```

**Key Parameters:**
- `R/G/B_min/max`: RGB color range for dart detection
- `Min/Max_Area`: Size constraints for dart detection (in pixels)
- `RG_ratio`: Red-Green ratio threshold
- `RB_diff`: Red-Blue difference threshold
- `Max_Jump`: Maximum pixel distance between consecutive frames
- `Exclude_Right/Bottom`: Exclude zones to filter out false positives
- `Min_Motion`: Minimum motion threshold
- `Motion_Frames`: Number of frames to confirm motion

## 🎮 Scripts Overview

### `track_dart.py`
Main tracking script with HSV-based color detection. Best for controlled lighting.

### `track_dart_rgb.py`
RGB-based tracking with advanced filtering. Better for varied lighting conditions.

### `track_single_dart.py`
Optimized for tracking a single dart with higher accuracy.

### `track_dart_web.py`
Flask web application providing an interactive interface for parameter tuning and real-time visualization.

### `adjust_color_range.py`
Interactive tool for calibrating color detection parameters using trackbars.

## 🛠️ Technical Details

The tracking system uses several computer vision techniques:

1. **Color Space Filtering**: Detects dart using RGB/HSV color thresholds
2. **Contour Detection**: Identifies dart shape using OpenCV contours
3. **Motion Analysis**: Filters false positives using motion detection
4. **Trajectory Smoothing**: Maintains trajectory history with deque
5. **Spatial Filtering**: Excludes specific regions to reduce false positives

## 📊 Performance Tips

- Adjust color ranges based on your lighting conditions
- Use the web interface for quick parameter iteration
- Enable exclusion zones to filter out background objects
- Tune `Max_Jump` to prevent tracking jumps
- Adjust `Min_Area` and `Max_Area` based on dart size in frame

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is developed for the Illini RoboMaster team.

## 👥 Authors

Illini RoboMaster Team - Dart Trajectory Analysis Group

## 🙏 Acknowledgments

- RoboMaster Competition
- OpenCV Community
- Illini RoboMaster Team

## 📧 Contact

For questions or suggestions, please open an issue on GitHub.

---

**Note**: Place your input videos in the `data/` folder and output videos will be saved to `output/`.
