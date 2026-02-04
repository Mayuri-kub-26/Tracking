# API Usage Examples

Here are examples of how to interact with the enhanced Tracking API.
Ensure the server is running: `python3 src/main.py --mode production`

## 1. Click to Select (Track Point)

This endpoint attempts to select a detected object at the clicked location. If found, it tracks the object; otherwise, it tracks a fixed area around the point.

**Endpoint:** `POST /track_point`

### cURL Example
```bash
curl -X POST "http://localhost:8000/track_point" \
     -H "Content-Type: application/json" \
     -d '{
           "x_norm": 0.5,
           "y_norm": 0.5,
           "video_width": 1280,
           "video_height": 720
         }'
```

### Python Example
```python
import requests

url = "http://localhost:8000/track_point"
data = {
    "x_norm": 0.45,       # Normalized X (0.0 - 1.0)
    "y_norm": 0.33,       # Normalized Y (0.0 - 1.0)
    "video_width": 1280,  # Client video width
    "video_height": 720   # Client video height
}

response = requests.post(url, json=data)
print(response.json())
```

---

## 2. Drag to Select (Custom ROI)

This endpoint sets a custom Region of Interest (ROI) defined by a dragged box.

**Endpoint:** `POST /drag_point`

### cURL Example
```bash
curl -X POST "http://localhost:8000/drag_point" \
     -H "Content-Type: application/json" \
     -d '{
           "x1_norm": 0.2,
           "y1_norm": 0.2,
           "x2_norm": 0.4,
           "y2_norm": 0.4,
           "video_width": 1280,
           "video_height": 720
         }'
```

### Python Example
```python
import requests

url = "http://localhost:8000/drag_point"
data = {
    "x1_norm": 0.25,      # Start X
    "y1_norm": 0.25,      # Start Y
    "x2_norm": 0.55,      # End X
    "y2_norm": 0.55,      # End Y
    "video_width": 1280,
    "video_height": 720
}

response = requests.post(url, json=data)
print(response.json())
```

---

## 3. Control Tracking Status

**Endpoint:** `POST /track_status`

### Stop Tracking
```bash
curl -X POST "http://localhost:8000/track_status" \
     -H "Content-Type: application/json" \
     -d '{"trackingStatus": false}'
```

---

## 4. Camera & Gimbal Control

The following endpoints allow control over the camera and gimbal. They do not require a request body.

**Common Response:**
```json
{
  "status": "ok"
}
```

### Center Gimbal
**Endpoint:** `POST /center`
Centers the gimbal to the default position.

### Zoom Control
**Endpoint:** `POST /zoom_in`
**Endpoint:** `POST /zoom_out`
**Endpoint:** `POST /stop_zoom`
Starts zooming in/out or stops the zoom.
*Note: The camera will continue zooming until `stop_zoom` is called or limits are reached.*

### Camera Actions
**Endpoint:** `POST /take_photo`
Captures a still image.

**Endpoint:** `POST /start_recording`
**Endpoint:** `POST /stop_recording`
Starts or stops video recording. 
*Note: The underlying hardware toggles recording state. Ensure you track state if needed.*

### Manual Gimbal Movement
**Endpoints:** 
- `POST /pitch_up`
- `POST /pitch_down`
- `POST /yaw_left`
- `POST /yaw_right`
- `POST /stop_gimbal`

Moves the gimbal at a fixed speed. Use `stop_gimbal` to stop movement.

### cURL Examples

```bash
# Center Gimbal
curl -X POST "http://localhost:8000/center"

# Zoom In
curl -X POST "http://localhost:8000/zoom_in"

# Take Photo
curl -X POST "http://localhost:8000/take_photo"
```
