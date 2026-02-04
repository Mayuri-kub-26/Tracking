# Client-Side "Press-and-Hold" Zoom Implementation

With the updated API (Continuous Zoom), the logic is event-driven:

1.  **On Button Press (MouseDown/TouchStart):**
    *   Send `POST /zoom_in` (Starts the zoom motor).
2.  **On Button Release (MouseUp/TouchEnd or MouseLeave):**
    *   Send `POST /stop_zoom` (Stops the zoom motor).

## JavaScript Example (Web Client)

```javascript
// 1. Setup Event Listeners
const btn = document.getElementById('zoom-in-btn');

// Start Zooming (Press)
btn.addEventListener('mousedown', async () => {
    try {
        await fetch('http://localhost:8000/zoom_in', { method: 'POST' });
    } catch (e) {
        console.error("Failed to start zoom", e);
    }
});

// Stop Zooming (Release)
const stopZoom = async () => {
    try {
        await fetch('http://localhost:8000/stop_zoom', { method: 'POST' });
    } catch (e) {
        console.error("Failed to stop zoom", e);
    }
};

btn.addEventListener('mouseup', stopZoom);
btn.addEventListener('mouseleave', stopZoom);
```

## Python Example (PySide/Tkinter/Hardware Button)

```python
import requests

class ZoomController:
    def start_zoom(self):
        try:
             requests.post("http://localhost:8000/zoom_in")
        except:
             pass

    def stop_zoom(self):
        try:
             requests.post("http://localhost:8000/stop_zoom")
        except:
             pass

## Legacy/QGC JavaScript Example (XMLHttpRequest)

If you are using QGroundControl or an environment without `fetch`:

```javascript
    function sendHoldPoint(x, y) {
        // ... (hold logic)
    }

    function sendZoomIn() {
        // Starts zooming in
        sendJson("/zoom_in", {})
    }

    function sendZoomOut() {
        // Starts zooming out
        sendJson("/zoom_out", {}) // Fixed typo (removed space)
    }
    
    function sendStopZoom() {
        // Stops zooming (Call this on button release)
        sendJson("/stop_zoom", {})
    }

    function sendTakePhoto() {
        sendJson("/take_photo", {})
    }

    function sendStartTakeVideo() {
        sendJson("/start_recording", {})
    }

    function sendStopTakeVideo() {
        sendJson("/stop_recording", {})
    }

    function sendSetCenter() {
        sendJson("/center", {})
    }

    function sendJson(endpoint, payload) {
        var xhr = new XMLHttpRequest()
        // Ensure IP matches your setup
        xhr.open("POST", "http://192.168.144.60:8000" + endpoint)
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.send(JSON.stringify(payload))
    }
```
