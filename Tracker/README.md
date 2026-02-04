# Modular Video Tracking System (Hailo + SIYI)

A high-performance object tracking system integrating **Hailo-8L AI acceleration** for object detection and **SIYI Gimbal SDK** for automated camera control. Designed for drone/UAV surveillance applications with QGroundControl integration.

## Features

*   **Real-time AI Detection**: Uses Hailo-8L (YOLOv10/v8) for high-speed object detection.
*   **Object Tracking**: Robust object tracking (CSRT/BYTETracker) to maintain lock on targets.
*   **Gimbal Control**: PID-based automated control for SIYI ZT30/A8 Mini gimbals to center targets.
*   **Dual Modes**:
    *   **Debug Mode**: Local GUI with keyboard controls for development.
    *   **Production Mode**: Headless API server with QGroundControl (QGC) integration.
*   **Video Streaming**:
    *   **Web Stream**: Low-latency MJPEG for browser viewing.
    *   **RTSP Push**: Push video to MediaMTX for QGC/VLC integration.
*   **Modular Architecture**: Clean separation of Hardware, Detection, Core Logic, and API.

## Directory Structure

```
src/
├── api/            # FastAPI server for QGC integration
├── core/           # Main application loop and status management
├── detection/      # Hailo inference, post-processing, and trackers
├── hardware/       # Camera and Gimbal drivers
└── utils/          # Logging, visualization, and PID controllers
```

## Installation

### Prerequisites
*   Raspberry Pi 5 (or compatible Linux SBC)
*   Hailo AI HAT + Hailo TAPPAS/RT software installed
*   Python 3.8+
*   OpenCV with GStreamer support

### Setup
1.  Clone the repository:
    ```bash
    git clone https://github.com/Flying-Wedge-Defence-AI/Tracker.git
    cd Tracker
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Ensure model files are in `models/`:
    *   `models/yolov10s.hef` (or your specific HEF model)

## Configuration (`src/config.yaml`)

Edit `src/config.yaml` to customize the system:

```yaml
detection:
  model_path: "models/yolov10s.hef"
  target_classes: ["person", "car"] # Objects to detect

stream:
  type: "web"  # "web" for MJPEG, "rtsp" for pushing to MediaMTX
  rtsp_url: "rtsp://127.0.0.1:8554/video1"
```

## Usage

### 1. Production Mode (API + Streaming)
Best for deployment and QGroundControl usage.
```bash
python src/main.py --mode production
```
*   **Stream URL**: `http://<IP>:8000/video1` (Web) or `rtsp://<IP>:8554/video1` (RTSP)
*   **API**: `http://<IP>:8000/docs`

### 2. Debug Mode (Local GUI)
Best for development. Requires a display or X forwarding.
```bash
python src/main.py --mode debug
```
*   **Controls**:
    *   `s`: Stop gimbal and select manual ROI.
    *   `c` (or Right Click): Cancel tracking and center gimbal.
    *   `q`: Quit.
    *   **Mouse**: Left-click on any detected object (orange box) to start tracking it.

### 3. API Usage (Production Mode)
The system supports REST API endpoints for integration with QGroundControl or custom clients. See [api_examples.md](api_examples.md) for detailed examples.

*   **Track Point (Smart Select)**: `POST /track_point`
    *   Clicks inside a detected object's box will start tracking that object.
    *   **Note**: Strict mode is enabled. Tracking **only** starts if the click matches a detected object.
*   **Drag Select (Custom ROI)**: `POST /drag_point`
    *   Starts tracking a custom region defined by normalized coordinates (0.0-1.0).
*   **Status Control**: `POST /track_status`
    *   Enable/Disable tracking.

## QGroundControl Integration

1.  **Video**: Set Source to RTSP/HTTP and use the stream URL above.
2.  **Control**: The API endpoints (`/track_point`, `/drag_point`) are compatible with custom QML widgets for "click-to-track".

## License
Proprietary / Internal Use Only.
