import threading
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import cv2
import time
import io
from pydantic import BaseModel
from src.core.app import TrackingApp
from src.core.config import cfg
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="QGC Tracking API")

# Allow QGroundControl / QML access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

tracker_app = None

# -----------------------
# Data Models
# -----------------------
class TrackPoint(BaseModel):
    x_norm: float
    y_norm: float
    video_width: float
    video_height: float

class DragPoint(BaseModel):
    x1_norm: float
    y1_norm: float
    x2_norm: float
    y2_norm: float
    video_width: float
    video_height: float

class HoldPoint(BaseModel):
    hold_x: float
    hold_y: float
    video_width: float
    video_height: float

class TrackStatus(BaseModel):
    trackingStatus: bool

# -----------------------
# Lifecycle
# -----------------------
@app.on_event("startup")
async def startup_event():
    global tracker_app
    logger.info("Starting Tracker App in background...")
    # Force headless in API mode
    cfg._config['system']['headless'] = True
    tracker_app = TrackingApp(mode="production")
    tracker_app.start_threaded()

@app.on_event("shutdown")
async def shutdown_event():
    global tracker_app
    if tracker_app:
        tracker_app.cleanup()

# -----------------------
# APIs
# -----------------------
@app.post("/track_point")
def track_point(data: TrackPoint):
    logger.info(f"📍 Track Point: {data}")
    
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")

    # Access current frame dimensions from config or tracker_app
    # Note: data.video_width/height are from client, might differ from actual stream
    # We use normalized coords so we multiply by OUR stream dimensions
    
    # We assume standard HD default if camera not ready, but better to get from config
    stream_w = cfg.get("camera.width", 1280)
    stream_h = cfg.get("camera.height", 720)
    
    # Check if we can get actual dimensions from camera
    if hasattr(tracker_app, 'camera') and tracker_app.camera.frame is not None:
        stream_h, stream_w = tracker_app.camera.frame.shape[:2]

    x = int(data.x_norm * stream_w)
    y = int(data.y_norm * stream_h)

    # Check for click on detected object
    selected_bbox = None
    if hasattr(tracker_app, 'latest_detections'):
        for label, conf, det_bbox in tracker_app.latest_detections:
            dx, dy, dw, dh = [int(v) for v in det_bbox]
            if dx <= x <= dx + dw and dy <= y <= dy + dh:
                logger.info(f"🎯 API Click selected object: {label} ({conf:.2f})")
                selected_bbox = (dx, dy, dw, dh)
                break
    
    if selected_bbox:
        tracker_app.set_tracking_target(selected_bbox)
    else:
        # Strict mode: Do not track if no object is clicked
        logger.warning(f"📍 API Click at ({x}, {y}) did not hit any of {len(tracker_app.latest_detections) if hasattr(tracker_app, 'latest_detections') else 0} objects. Tracking NOT started.")
        # Optional: return 404 or specific status? For now, 200 but no action.
    
    return {"status": "ok"}


@app.post("/drag_point")
def drag_point(data: DragPoint):
    logger.info(f"⬛ Drag Selection: {data}")

    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")

    stream_w = cfg.get("camera.width", 1280)
    stream_h = cfg.get("camera.height", 720)
    
    if hasattr(tracker_app, 'camera') and tracker_app.camera.frame is not None:
        stream_h, stream_w = tracker_app.camera.frame.shape[:2]

    # Calculate bbox
    # Ensure x1 < x2, y1 < y2
    x1 = min(data.x1_norm, data.x2_norm)
    y1 = min(data.y1_norm, data.y2_norm)
    w_norm = abs(data.x2_norm - data.x1_norm)
    h_norm = abs(data.y2_norm - data.y1_norm)

    x = int(x1 * stream_w)
    y = int(y1 * stream_h)
    w = int(w_norm * stream_w)
    h = int(h_norm * stream_h)

    bbox = (x, y, w, h)
    tracker_app.set_tracking_target(bbox)
    return {"status": "ok"}


@app.post("/hold_point")
def hold_point(data: HoldPoint):
    # logger.info(f"📍 Hold Point: {data}")
    
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")

    # Use tracker_app to handle the hold logic
    # We pass the normalized coordinates and let the app handle the conversion to frame pixels
    tracker_app.hold_at_point(data.hold_x, data.hold_y)
    
    return {"status": "ok"}


@app.post("/track_status")
def set_track_status(data: TrackStatus):
    logger.info(f"🎯 Set Tracking Enabled: {data.trackingStatus}")
    
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")

    if data.trackingStatus:
        # We can't really "enable" tracking without a target via this endpoint usually
        # But maybe this is a master switch. 
        # For now, if False, we cancel tracking
        pass 
    else:
        tracker_app.stop_tracking_without_center()

    return {"enabled": data.trackingStatus}


@app.post("/clear_track")
def clear_track():
    logger.info("🚫 API: Clear Track")
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")
    
    tracker_app.stop_tracking_without_center()
    return {"status": "ok"}


@app.post("/center")
def center_gimbal():
    logger.info("🎯 API: Center Gimbal")
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")
    
    tracker_app.center_gimbal()
    return {"status": "ok"}


@app.post("/zoom_in")
def zoom_in():
    logger.info("🔍 API: Zoom In")
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")
    
    tracker_app.zoom_in()
    return {"status": "ok"}


@app.post("/zoom_out")
def zoom_out():
    logger.info("🔍 API: Start Zoom Out")
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")
    
    tracker_app.zoom_out()
    return {"status": "ok"}


@app.post("/stop_zoom")
def stop_zoom():
    logger.info("🔍 API: Stop Zoom")
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")
    
    tracker_app.stop_zoom()
    return {"status": "ok"}


@app.post("/take_photo")
def take_photo():
    logger.info("📸 API: Take Photo")
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")
    
    tracker_app.take_photo()
    return {"status": "ok"}


@app.post("/start_recording")
def start_recording():
    logger.info("🎥 API: Start Recording")
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")
    
    tracker_app.start_recording()
    return {"status": "ok"}


@app.post("/stop_recording")
def stop_recording():
    logger.info("🎥 API: Stop Recording")
    if not tracker_app:
         raise HTTPException(status_code=503, detail="Tracker not initialized")
    
    tracker_app.stop_recording()
    return {"status": "ok"}


# --- Gimbal Movement APIs ---

GIMBAL_SPEED = 15

@app.post("/pitch_up")
def pitch_up():
    logger.info("⬆️ API: Pitch Up")
    if not tracker_app: raise HTTPException(status_code=503, detail="Tracker not initialized")
    tracker_app.move_gimbal(0, GIMBAL_SPEED) # Positive pitch is typically Up/Down depending on mount
    return {"status": "ok"}

@app.post("/pitch_down")
def pitch_down():
    logger.info("⬇️ API: Pitch Down")
    if not tracker_app: raise HTTPException(status_code=503, detail="Tracker not initialized")
    tracker_app.move_gimbal(0, -GIMBAL_SPEED)
    return {"status": "ok"}

@app.post("/yaw_left")
def yaw_left():
    logger.info("⬅️ API: Yaw Left")
    if not tracker_app: raise HTTPException(status_code=503, detail="Tracker not initialized")
    tracker_app.move_gimbal(-GIMBAL_SPEED, 0)
    return {"status": "ok"}

@app.post("/yaw_right")
def yaw_right():
    logger.info("➡️ API: Yaw Right")
    if not tracker_app: raise HTTPException(status_code=503, detail="Tracker not initialized")
    tracker_app.move_gimbal(GIMBAL_SPEED, 0)
    return {"status": "ok"}

@app.post("/stop_gimbal")
def stop_gimbal():
    logger.info("🛑 API: Stop Gimbal")
    if not tracker_app: raise HTTPException(status_code=503, detail="Tracker not initialized")
    tracker_app.stop_gimbal()
    return {"status": "ok"}


@app.get("/track_status")
def get_track_status():
    enabled = False
    if tracker_app and hasattr(tracker_app, 'tracker'):
        enabled = tracker_app.tracker.tracking_active
        
    return {"enabled": enabled}

def generate_frames():
    """Generator for MJPEG stream."""
    while True:
        if tracker_app and tracker_app.latest_frame is not None:
            # Encode frame
            try:
                ret, buffer = cv2.imencode('.jpg', tracker_app.latest_frame)
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                logger.error(f"Error encoding frame: {e}")
        
        # Limit streaming FPS to save bandwidth/cpu if needed
        time.sleep(0.03) # ~30fps

@app.get("/video_feed")
def video_feed():
    # Legacy default
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# Dynamic endpoint based on config
stream_endpoint = cfg.get("stream.web_endpoint", "/video1")
@app.get(stream_endpoint)
def custom_video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


def run_server(host="0.0.0.0", port=8000):
    import uvicorn
    
    stream_type = cfg.get("stream.type", "web")
    if stream_type == "web":
         endpoint = cfg.get("stream.web_endpoint", "/video1")
         logger.info(f"Web Streaming enabled at http://{host}:{port}{endpoint}")
    else:
         logger.info(f"RTSP Streaming enabled. Web endpoint might be inactive for video.")

    uvicorn.run(app, host=host, port=port)
