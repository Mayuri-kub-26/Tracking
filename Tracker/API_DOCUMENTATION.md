# Tracker System API Documentation

Base URL: `http://<host>:8000`

## 1. Tracking & Selection

### Select Object by Point
**Endpoint:** `POST /track_point`
**Description:** Attempts to select and track an object at the specified normalized coordinates.

**Request Body:** `application/json`
```json
{
  "x_norm": float,       // Normalized X coordinate (0.0 - 1.0)
  "y_norm": float,       // Normalized Y coordinate (0.0 - 1.0)
  "video_width": float,  // Width of the video stream on client side
  "video_height": float  // Height of the video stream on client side
}
```

**Response:**
```json
{ "status": "ok" }
```

### Select Region of Interest (ROI)
**Endpoint:** `POST /drag_point`
**Description:** Initializes tracking based on a user-defined box (drag selection).

**Request Body:** `application/json`
```json
{
  "x1_norm": float,      // Start X (0.0 - 1.0)
  "y1_norm": float,      // Start Y (0.0 - 1.0)
  "x2_norm": float,      // End X (0.0 - 1.0)
  "y2_norm": float,      // End Y (0.0 - 1.0)
  "video_width": float,
  "video_height": float
}
```

**Response:**
```json
{ "status": "ok" }
```

### Hold Position
**Endpoint:** `POST /hold_point`
**Description:** Directs the gimbal to center on a specific coordinate and hold that position visually.

**Request Body:** `application/json`
```json
{
  "hold_x": float,       // Normalized X (0.0 - 1.0)
  "hold_y": float,       // Normalized Y (0.0 - 1.0)
  "video_width": float,
  "video_height": float
}
```

**Response:**
```json
{ "status": "ok" }
```

### Tracking Status
**Endpoint:** `POST /track_status`
**Description:** Enable or disable tracking (Master Switch).

**Request Body:** `application/json`
```json
{
  "trackingStatus": bool // true to enable (noop), false to cancel tracking
}
```

**Response:**
```json
{ "enabled": bool }
```

**Endpoint:** `GET /track_status`
**Description:** Get current tracking status.

**Response:**
```json
{ "enabled": bool }
```

---

## 2. Gimbal Control

### Center Gimbal
**Endpoint:** `POST /center`
**Description:** Resets the gimbal to its center position (0 yaw, 0 pitch).

**Request Body:** None
**Response:**
```json
{ "status": "ok" }
```

---

## 3. Camera Operations

### Zoom In
**Endpoint:** `POST /zoom_in`
**Description:** Starts zooming in (Continuous).
**Behavior:** Sends `Manual Zoom (1)` command. Camera continues zooming until stopped.

**Request Body:** None
**Response:**
```json
{ "status": "ok" }
```

### Zoom Out
**Endpoint:** `POST /zoom_out`
**Description:** Starts zooming out (Continuous).
**Behavior:** Sends `Manual Zoom (-1)` command. Camera continues zooming until stopped.

**Request Body:** None
**Response:**
```json
{ "status": "ok" }
```

### Stop Zoom
**Endpoint:** `POST /stop_zoom`
**Description:** Stops any active zoom operation.
**Behavior:** Sends `Manual Zoom (0)` command.

**Request Body:** None
**Response:**
```json
{ "status": "ok" }
```

### Take Photo
**Endpoint:** `POST /take_photo`
**Description:** Triggers the camera to capture a still image.

**Request Body:** None
**Response:**
```json
{ "status": "ok" }
```

### Recording Control
**Endpoint:** `POST /start_recording`
**Endpoint:** `POST /stop_recording`
**Description:** Toggles video recording on the camera.
**Note:** The SIYI SDK treat this as a toggle. Ensure you handle state management if strictly separate start/stop logic is needed.

**Request Body:** None
**Response:**
```json
{ "status": "ok" }
```

---

## 4. Manual Gimbal Movement

### Rotate Gimbal
**Endpoints:**
- `POST /pitch_up` (Moves camera UP)
- `POST /pitch_down` (Moves camera DOWN)
- `POST /yaw_left` (Moves camera LEFT)
- `POST /yaw_right` (Moves camera RIGHT)

**Description:** Starts rotating the gimbal at a preset speed (default 15).
**Behavior:** The gimbal will continue rotating until `stop_gimbal` is called or a hardware limit is reached.

**Request Body:** None
**Response:**
```json
{ "status": "ok" }
```

### Stop Gimbal
**Endpoint:** `POST /stop_gimbal`
**Description:** Stops all gimbal rotation.
**Behavior:** Sends rotation speed (0, 0).

**Request Body:** None
**Response:**
```json
{ "status": "ok" }
```
