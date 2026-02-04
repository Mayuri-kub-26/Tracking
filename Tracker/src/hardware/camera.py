import cv2
import threading
import time
from src.core.config import cfg
from src.utils.logger import get_logger

logger = get_logger(__name__)

class Camera:
    """
    Reads frames in a separate thread to ensure we always get the latest frame
    and prevent buffering/latency buildup.
    """
    def __init__(self):
        self.running = False
        self.lock = threading.Lock()
        self.thread = None
        self.cap = None
        
        self.frame = None
        self.ret = False
        
        self._connected = False

    def connect(self):
        url = cfg.get("camera.url")
        # Optimized pipeline for low latency
        # Note: This is specific to the setup provided in track_and_center.py
        # We might need to adjust this based on actual hardware
        if "rtsp" in str(url):
             gst_pipeline = (
                f"rtspsrc location={url} latency={cfg.get('camera.latency', 0)} ! "
                "rtph265depay ! h265parse ! avdec_h265 ! videoconvert ! appsink drop=true max-buffers=1"
            )
             logger.info(f"Attempting GStreamer pipeline: {gst_pipeline}")
             self.cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
             
             if not self.cap.isOpened():
                logger.warning("GStreamer failed, falling back to default backend...")
                self.cap = cv2.VideoCapture(url)
        else:
             self.cap = cv2.VideoCapture(url) # Webcams or files

        if not self.cap.isOpened():
            logger.error("Failed to open video stream")
            return False

        self._connected = True
        return True

    def start(self):
        if not self._connected:
            if not self.connect():
                return False
        
        if self.running:
            return True

        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        
        # Determine frame size for config if needed? 
        # Actually better to just read it
        return True

    def _update(self):
        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            with self.lock:
                self.ret = ret
                self.frame = frame
            time.sleep(0.001) # Low CPU usage yield

    def read(self):
        with self.lock:
            return self.ret, self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.cap:
            self.cap.release()
        self._connected = False

    def is_opened(self):
        return self._connected and self.cap.isOpened()
