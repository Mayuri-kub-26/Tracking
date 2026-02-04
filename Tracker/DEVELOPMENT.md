# Development Documentation

## Feature Implementation Details

### Mouse Selection for Tracking
The mouse selection feature allows users to click on a detected object in `debug` mode to initiate tracking.

**Implementation:**
- **App (`src/core/app.py`):**
    - Stores `latest_detections` from the `HailoDetector` in the main loop.
    - Registers a mouse callback `_mouse_callback` using `cv2.setMouseCallback`.
    - On `EVENT_LBUTTONDOWN`, checks if the click coordinates fall within any bounding box in `latest_detections`.
    - If a match is found, sets `pending_tracker_init` which triggers the tracker initialization in the next loop iteration.
    - On `EVENT_RBUTTONDOWN`, stops the tracker and centers the gimbal.

**Files Modified:**
- `src/core/app.py`: Added `latest_detections` storage and `_mouse_callback`.
### API Drag and Click Selection (Production Mode)
Enables object selection and custom ROI tracking via REST API, primarily for QGroundControl.

**Implementation:**
- **Server (`src/api/server.py`):**
    - `POST /track_point`: Accepts normalized coordinates.
        - Checks `tracker_app.latest_detections`.
        - If point is inside a detection bbox, initializes tracking for that object.
        - **Strict Mode**: If point matches no object, tracking is **not** initialized (prevents false positives).
    - `POST /drag_point`: Accepts a normalized rectangle `(x1, y1, x2, y2)`.
        - Converts to pixel coordinates and initializes tracking for the specified ROI.

**Files Modified:**
- `src/api/server.py`: Added logic for `latest_detections` check and strict mode.
- `src/core/app.py`: Ensured `latest_detections` is exposed.
- `api_examples.md`: Added usage examples.
- `README.md`: Updated with usage instructions.

## Running Tests
To verify the implementation:
1. Run in debug mode: `python src/main.py --mode debug`
2. Ensure you have a working camera and display (or X11 forwarding).
3. Verify that clicking a box starts tracking (box turns green).
