import cv2
import time
import threading
from src.core.config import cfg
from src.hardware.camera import Camera
from src.hardware.gimbal import GimbalController
from src.detection.detector import HailoDetector
from src.detection.tracker import ObjectTracker
from src.utils.visualization import draw_detections, draw_tracking_info, draw_hud
from src.utils.logger import get_logger

logger = get_logger(__name__)

class TrackingApp:
    def __init__(self, mode="debug"):
        self.mode = mode
        self.headless = cfg.get("system.headless", False)
        
        # Initialize components
        self.camera = Camera()
        self.gimbal = GimbalController()
        self.detector = HailoDetector()
        self.tracker = ObjectTracker(detector=self.detector)
        
        self.latest_detections = []
        
        self.running = False
        self.fps = 0
        self.frame_count = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.latest_frame = None
        
        # Output Streamer
        self.stream_type = cfg.get("stream.type", "web")
        self.rtsp_url = cfg.get("stream.rtsp_url", "rtsp://127.0.0.1:8554/stream")
        print(self.rtsp_url)
        self.stream_writer = None
        
        # Mouse Interaction State
        self.drag_start_point = None
        self.current_mouse_point = None
        self.is_dragging = False
        
    def start(self):
        self._setup()
        self._setup_streamer()
        self.running = True
        self.loop()

    def start_threaded(self):
        self._setup()
        self._setup_streamer()
        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def _setup(self):
        logger.info("Starting TrackingApp...")
        if not self.camera.start():
            logger.error("Could not start camera.")
            return

        if not self.gimbal.connect():
           logger.warning("Gimbal not connected. Continuing in simulation mode.")
        else:
           self.gimbal.center()

        if not self.headless and self.mode == "debug":
            cv2.namedWindow("Tracker", cv2.WINDOW_NORMAL)
            cv2.setMouseCallback("Tracker", self._mouse_callback)
            logger.info("Mouse callback registered for Tracker window")
           
    def _setup_streamer(self):
        if self.stream_type == "rtsp":
            logger.info(f"Setting up RTSP Streamer to {self.rtsp_url}")
            # GStreamer pipeline for RTSP push
            # Requires an RTSP server listening (e.g., mediamtx)

            w = cfg.get("camera.width", 1280)
            h = cfg.get("camera.height", 720)
            fps = cfg.get("camera.fps", 30)

            gst_out = (
                f"appsrc ! videoconvert ! x264enc tune=zerolatency bitrate=2000 speed-preset=ultrafast ! "
                f"rtspclientsink location={self.rtsp_url}"
            )

            self.stream_writer = cv2.VideoWriter(gst_out, cv2.CAP_GSTREAMER, 0, fps, (w, h), True)
            if not self.stream_writer.isOpened():
                logger.error("Failed to open RTSP stream writer. Exiting to trigger service restart.")
                raise RuntimeError("Failed to open RTSP stream writer")
            else:
                logger.info("RTSP Stream writer opened successfully")

    def loop(self):
        try:
            while self.running:
                loop_start = time.time()
                
                # 1. Get Frame
                ret, frame = self.camera.read()
                if not ret or frame is None:
                    time.sleep(0.01)
                    continue

                frame_h, frame_w = frame.shape[:2]
                center_x, center_y = frame_w // 2, frame_h // 2

                # Check for external tracking command
                if hasattr(self, 'pending_tracker_init') and self.pending_tracker_init:
                    logger.info(f"Initializing tracker from API: {self.pending_tracker_init}")
                    self.tracker.init(frame, self.pending_tracker_init)
                    self.pending_tracker_init = None

                # 2. Tracking Logic
                if self.tracker.tracking_active:
                    success, bbox = self.tracker.update(frame)
                    if success:
                        x, y, w, h = [int(v) for v in bbox]
                        target_x = x + w // 2
                        target_y = y + h // 2
                        
                        error_x = target_x - center_x
                        error_y = target_y - center_y
                        
                        # Update Gimbal
                        self.gimbal.update_tracking(error_x, error_y)
                        
                        # Visualize (Always draw for streaming)
                        draw_tracking_info(frame, bbox, center_x, center_y, error_x, error_y)
                    else:
                        logger.info("Tracking lost.")
                        self.tracker.tracking_active = False
                        self.gimbal.stop()
                
                # 3. Detection Logic (if not tracking)
                elif self.detector.enabled:
                    detections = self.detector.detect(frame)
                    self.latest_detections = detections # Store for mouse selection
                    # Always draw detections for streaming
                    draw_detections(frame, detections)
                        
                # 4. Display & Input
                self._calculate_fps()
                # Always draw HUD for streaming
                draw_hud(frame, self.mode, self.fps)
                
                # Store processed frame for streaming
                self.latest_frame = frame.copy()
                
                # Write to RTSP if enabled
                if self.stream_writer is not None:
                     # Resize to configured stream dimensions to avoid GStreamer errors
                     w = cfg.get("camera.width", 1280)
                     h = cfg.get("camera.height", 720)

                     if frame.shape[1] != w or frame.shape[0] != h:
                         out_frame = cv2.resize(frame, (w, h))
                     else:
                         out_frame = frame

                     self.stream_writer.write(out_frame)
                
                if not self.headless:
                    # Draw ROI selection if dragging
                    if self.is_dragging and self.drag_start_point and self.current_mouse_point:
                        cv2.rectangle(frame, self.drag_start_point, self.current_mouse_point, (255, 255, 0), 2)
                        
                    cv2.imshow("Tracker", frame)
                    
                    key = cv2.waitKey(1) & 0xFF
                    self._handle_input(key, frame)
                    
                    if key == ord('q'):
                        self.running = False
                else:
                    # In headless, minimal sleep to prevent CPU hogging if capture is non-blocking (though read() is usually blocking/rate-limited)
                    # But we also need to allow API/Signals to process.
                    # Since Camera.read() is threaded and Rate-limited by FPS, we are fine.
                    time.sleep(0.001)
            
        except KeyboardInterrupt:
            print("Interrupted")
        finally:
            self.cleanup()

    def _handle_input(self, key, frame):
        if key == ord('s'): # Select ROI
            self.gimbal.stop()
            bbox = cv2.selectROI("Tracker", frame, fromCenter=False, showCrosshair=True)
            if bbox != (0, 0, 0, 0):
                self.tracker.init(frame, bbox)
        
        elif key == ord('c'): # Cancel tracking
            self.tracker.stop()
            self.gimbal.center()
            logger.info("Tracking canceled.")

    def _calculate_fps(self):
        self.frame_count += 1
        elapsed = time.time() - self.start_time
        if elapsed > 1.0:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.start_time = time.time()

    def cleanup(self):
        logger.info("Cleaning up...")
        if self.stream_writer:
            self.stream_writer.release()
            
        self.camera.stop()
        self.gimbal.stop() # Stop movement
        self.gimbal.disconnect()
        # self.detector.close()
        # self.detector.close()
        cv2.destroyAllWindows()

    def _mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drag_start_point = (x, y)
            self.is_dragging = True
            self.current_mouse_point = (x, y)

        elif event == cv2.EVENT_MOUSEMOVE:
            if self.is_dragging:
                self.current_mouse_point = (x, y)
                
        elif event == cv2.EVENT_LBUTTONUP:
            self.is_dragging = False
            self.current_mouse_point = (x, y)
            
            if self.drag_start_point:
                start_x, start_y = self.drag_start_point
                # Calculate distance to distinguish click vs drag
                dist = ((start_x - x)**2 + (start_y - y)**2)**0.5
                
                if dist > 10: # Drag behavior (ROI Selection)
                    x1 = min(start_x, x)
                    y1 = min(start_y, y)
                    x2 = max(start_x, x)
                    y2 = max(start_y, y)
                    w, h = x2 - x1, y2 - y1
                    
                    if w > 0 and h > 0:
                        bbox = (x1, y1, w, h)
                        logger.info(f"Selected Custom ROI: {bbox}")
                        self.pending_tracker_init = bbox
                        
                else: # Click behavior (Object Selection)
                    logger.info(f"Mouse click at ({x}, {y})")
                    # Check if click is inside any detection box
                    for label, conf, bbox in self.latest_detections:
                         dx, dy, dw, dh = [int(v) for v in bbox]
                         if dx <= x <= dx + dw and dy <= y <= dy + dh:
                             logger.info(f"Selected object: {label} ({conf:.2f})")
                             self.pending_tracker_init = (dx, dy, dw, dh)
                             break
                             
            self.drag_start_point = None

        elif event == cv2.EVENT_RBUTTONDOWN:
             # Right click to cancel
             self.tracker.stop()
             self.gimbal.center()
             logger.info("Tracking canceled via mouse.")

    # API Methods for Production Mode
    def set_tracking_target(self, bbox):
        """
        Sets the tracking target from external coordination.
        bbox: (x, y, w, h)
        """
        # We need the current frame to init. 
        # So we set a flag 'pending_init_tracker' = bbox
        # And handle it in the loop
        self.pending_tracker_init = bbox

    def cancel_tracking(self):
        """
        Stops current tracking.
        """
        self.tracker.stop()
        self.gimbal.stop()
        self.gimbal.center()
        logger.info("Tracking canceled via API.")

    def stop_tracking_without_center(self):
        """
        Stops current tracking without centering the gimbal.
        """
        self.tracker.stop()
        self.gimbal.stop()
        logger.info("Tracking canceled (no center) via API.")

    def hold_at_point(self, x_norm, y_norm):
        """
        Moves the gimbal to center the given normalized point.
        Initializes a visual tracker at the point to ensure it stays centered.
        """
        current_frame = self.latest_frame
        if current_frame is None:
            # Fallback to config dims
            h = cfg.get("camera.height", 720)
            w = cfg.get("camera.width", 1280)
        else:
            h, w = current_frame.shape[:2]
            
        # Target pixel coordinates
        target_x = int(x_norm * w)
        target_y = int(y_norm * h)
        
        # Define ROI size for the tracker (e.g., 64x64 or smaller)
        roi_size = 64
        x1 = max(0, target_x - roi_size // 2)
        y1 = max(0, target_y - roi_size // 2)
        bbox = (x1, y1, roi_size, roi_size)
        
        # Switch to visual tracker if currently using BYTE (detection-based)
        # This ensures we can track "irrespective of detections"
        if self.tracker.tracker_type == 'BYTE':
             logger.info("Switching to CSRT tracker for manual Hold Point")
             self.tracker.tracker_type = 'CSRT'
             
        # Trigger tracker initialization in the main loop
        self.pending_tracker_init = bbox
        logger.info(f"Hold Point requested at ({target_x}, {target_y}). Initializing tracker.")


    def center_gimbal(self):
        """Centers the gimbal."""
        if self.tracker.tracking_active:
             logger.warning("Center command ignored because tracking is active.")
             return
             
        self.gimbal.center()
        # Reset any tracking if needed?
        # self.tracker.stop() # Maybe?
        
    def zoom_in(self):
        self.gimbal.zoom_in()
        
    def zoom_out(self):
        self.gimbal.zoom_out()
        
    def stop_zoom(self):
        self.gimbal.stop_zoom()
        
    def take_photo(self):
        self.gimbal.take_photo()
        
    # Note: SIYI SDK uses a toggle for recording. 
    # We will just expose the toggle.
    def start_recording(self):
        self.gimbal.toggle_recording()
        
    def stop_recording(self):
        self.gimbal.toggle_recording()

    # Manual Gimbal Movement
    def move_gimbal(self, yaw_speed, pitch_speed):
        # Stop tracking if active to prevent conflict
        if self.tracker.tracking_active:
             self.tracker.stop()
        self.gimbal.move_gimbal(yaw_speed, pitch_speed)
        
    def stop_gimbal(self):
        self.gimbal.stop_gimbal()
