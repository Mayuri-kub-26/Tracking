"""
SIYI Gimbal Object Tracking and Centering with PID Control
Includes Low-Latency Threaded Video Capture
"""

import cv2
import sys
import os
import time
import threading
import queue
import numpy as np

# Add parent directory to path to import siyi_sdk
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from siyi_sdk import SIYISDK

class PIDController:
    def __init__(self, kp, ki, kd, output_limits=(-100, 100)):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.min_out, self.max_out = output_limits
        
        self.prev_error = 0
        self.integral = 0
        self.last_time = None

    def update(self, error):
        current_time = time.time()
        
        if self.last_time is None:
            self.last_time = current_time
            dt = 0.0
        else:
            dt = current_time - self.last_time
            
        self.last_time = current_time

        p_term = self.kp * error
        self.integral += error * dt
        i_term = self.ki * self.integral

        d_term = 0
        if dt > 0:
            d_term = self.kd * (error - self.prev_error) / dt
        
        self.prev_error = error
        output = p_term + i_term + d_term
        return max(min(output, self.max_out), self.min_out)

    def reset(self):
        self.prev_error = 0
        self.integral = 0
        self.last_time = None

class LatestFrameReader:
    """
    Reads frames in a separate thread to ensure we always get the latest frame
    and prevent buffering/latency buildup.
    """
    def __init__(self, cap):
        self.cap = cap
        self.frame = None
        self.ret = False
        self.running = False
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        while self.running:
            ret, frame = self.cap.read()
            with self.lock:
                self.ret = ret
                self.frame = frame
            time.sleep(0.001) # Slight yield

    def read(self):
        with self.lock:
            return self.ret, self.frame

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

def track_and_center(
    rtsp_url="rtsp://192.168.144.25:8554/main.264",
    camera_ip="192.168.144.25", 
    camera_port=37260,
    kp=0.15,
    ki=0.01,
    kd=0.005,
    deadzone=20
):
    print("="*60)
    print("SIYI Object Tracking & Gymbal Centering (PID + Low Latency)")
    print("="*60)

    # 1. Connect to Gimbal
    print(f"[INFO] Connecting to gimbal at {camera_ip}:{camera_port}...")
    sdk = SIYISDK(camera_ip, camera_port)
    if not sdk.connect():
        print("[ERROR] Failed to connect to gimbal")
        return

    print("[SUCCESS] Gimbal connected")
    sdk.center_gimbal()
    time.sleep(1)

    # 2. Open Video Stream (H.265 optimized)
    print(f"[INFO] Opening Stream: {rtsp_url}")
    # optimized pipeline: appsink drop=true max-buffers=1
    gst_pipeline = f"rtspsrc location={rtsp_url} latency=0 ! rtph265depay ! h265parse ! avdec_h265 ! videoconvert ! appsink drop=true max-buffers=1"
    
    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
    
    if not cap.isOpened():
        print("[WARNING] GStreamer failed, falling back to default backend...")
        cap = cv2.VideoCapture(rtsp_url)
    
    if not cap.isOpened():
        print("[ERROR] Failed to open video stream")
        sdk.disconnect()
        return

    # Start threaded reader
    print("[INFO] Starting separate video thread...")
    reader = LatestFrameReader(cap)
    reader.start()
    
    # Wait for first frame
    print("[INFO] Waiting for first frame...")
    for _ in range(100):
        ret, frame = reader.read()
        if ret:
            break
        time.sleep(0.1)
    
    if not ret:
        print("[ERROR] Cannot read video frame")
        reader.stop()
        return

    print("\n" + "=" * 60)
    print("CONTROLS:")
    print("  s : Select Object to Track")
    print("  c : Cancel Tracking / Center Gimbal")
    print("  q : Quit")
    print("=" * 60)

    tracker = None
    pid_yaw = PIDController(kp, ki, kd, output_limits=(-100, 100))
    pid_pitch = PIDController(kp, ki, kd, output_limits=(-100, 100))
    
    frame_h, frame_w = frame.shape[:2]
    center_x, center_y = frame_w // 2, frame_h // 2

    last_ctrl_time = 0
    ctrl_interval = 0.05 

    try:
        while True:
            # Always get latest frame
            ret, frame = reader.read()
            if not ret:
                time.sleep(0.01)
                continue

            # Draw center
            cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)

            if tracker:
                success, box = tracker.update(frame)

                if success:
                    x, y, w, h = [int(v) for v in box]
                    target_x = x + w // 2
                    target_y = y + h // 2

                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.circle(frame, (target_x, target_y), 5, (0, 255, 0), -1)
                    cv2.line(frame, (center_x, center_y), (target_x, target_y), (255, 255, 0), 2)

                    error_x = target_x - center_x
                    error_y = target_y - center_y
                    
                    # Yaw Control
                    yaw_speed = 0
                    if abs(error_x) > deadzone:
                        yaw_speed = int(pid_yaw.update(error_x))
                    else:
                        pid_yaw.reset() 
                    
                    # Pitch Control
                    pitch_speed = 0
                    if abs(error_y) > deadzone:
                        pitch_speed = int(pid_pitch.update(-error_y))
                    else:
                        pid_pitch.reset()

                    # Send command periodically
                    now = time.time()
                    if now - last_ctrl_time > ctrl_interval:
                        if yaw_speed != 0 or pitch_speed != 0:
                            sdk.rotate_gimbal(yaw_speed, pitch_speed)
                        else:
                            sdk.rotate_gimbal(0, 0)
                        last_ctrl_time = now

                    cv2.putText(frame, f"Err: {error_x},{error_y}", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    cv2.putText(frame, f"PID: {yaw_speed},{pitch_speed}", (10, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                else:
                    cv2.putText(frame, "Tracking Lost", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    pid_yaw.reset()
                    pid_pitch.reset()
                    
                    if time.time() - last_ctrl_time > ctrl_interval:
                         sdk.rotate_gimbal(0, 0)
                         last_ctrl_time = time.time()
            else:
                cv2.putText(frame, "Press 's' to select object", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            cv2.imshow("Tracking & Centering (PID + LowLatency)", frame)

            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            
            elif key == ord('c'):
                print("[INFO] Tracking canceled / Centering...")
                tracker = None
                sdk.center_gimbal()
                pid_yaw.reset()
                pid_pitch.reset()
            
            elif key == ord('s'):
                print("[INFO] Pausing for object selection...")
                # Stop gimbal before selection
                sdk.rotate_gimbal(0, 0)
                
                # Select ROI on current frame
                bbox = cv2.selectROI("Tracking & Centering (PID + LowLatency)", frame, fromCenter=False, showCrosshair=True)
                
                if bbox != (0, 0, 0, 0):
                    print("[INFO] Object selected, initializing tracker...")
                    try:
                        tracker = cv2.TrackerCSRT_create()
                    except AttributeError:
                        tracker = cv2.TrackerKCF_create()
                    
                    tracker.init(frame, bbox)
                    pid_yaw.reset()
                    pid_pitch.reset()
                else:
                    print("[INFO] Selection skipped")

    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        if 'reader' in locals():
            reader.stop()
        sdk.rotate_gimbal(0, 0)
        time.sleep(0.5)
        # sdk.disconnect() # Sometimes causes hang on exit, but good practice
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    track_and_center()
