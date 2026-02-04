import time
from src.hardware.siyi_sdk import SIYISDK
from src.utils.pid import PIDController
from src.core.config import cfg
from src.utils.logger import get_logger

logger = get_logger(__name__)

class GimbalController:
    def __init__(self):
        self.ip = cfg.get("gimbal.ip")
        self.port = cfg.get("gimbal.port")
        self.sdk = SIYISDK(self.ip, self.port)
        
        pid_cfg = cfg.get("gimbal.pid")
        self.pid_yaw = PIDController(
            pid_cfg['yaw']['kp'], 
            pid_cfg['yaw']['ki'], 
            pid_cfg['yaw']['kd']
        )
        self.pid_pitch = PIDController(
            pid_cfg['pitch']['kp'], 
            pid_cfg['pitch']['ki'], 
            pid_cfg['pitch']['kd']
        )
        
        self.deadzone = cfg.get("gimbal.deadzone", 20)
        self.move_interval = cfg.get("gimbal.move_interval", 0.05)
        self.last_move_time = 0
        
        self.connected = False

    def connect(self):
        logger.info(f"Connecting to gimbal at {self.ip}:{self.port}...")
        self.connected = self.sdk.connect()
        return self.connected

    def disconnect(self):
        self.sdk.disconnect()
        self.connected = False

    def center(self):
        if not self.connected: return
        self.sdk.center_gimbal()
        self.pid_yaw.reset()
        self.pid_pitch.reset()

    def update_tracking(self, error_x, error_y):
        """
        Update gimbal based on error from center (in pixels)
        error_x: target_x - center_x
        error_y: target_y - center_y
        """
        if not self.connected: return
        
        # Yaw Control
        yaw_speed = 0
        if abs(error_x) > self.deadzone:
            yaw_speed = int(self.pid_yaw.update(error_x))
        else:
            self.pid_yaw.reset() 
        
        # Pitch Control (Note: Pitch might need inversion depending on mount)
        pitch_speed = 0
        if abs(error_y) > self.deadzone:
            # Often pitch error needs to be inverted because +y is down in images but might mean down/up for gimbal
            # In track_and_center.py it was -error_y
            pitch_speed = int(self.pid_pitch.update(-error_y))
        else:
            self.pid_pitch.reset()

        # Send command periodically
        now = time.time()
        if now - self.last_move_time > self.move_interval:
            if yaw_speed != 0 or pitch_speed != 0:
                self.sdk.rotate_gimbal(yaw_speed, pitch_speed)
                logger.debug(f"Gimbal Move: Yaw={yaw_speed}, Pitch={pitch_speed}")
            else:
                self.stop()
            self.last_move_time = now
            
        return yaw_speed, pitch_speed

    def stop(self):
        if not self.connected: return
        self.sdk.rotate_gimbal(0, 0)

    # New API Methods
    def zoom_in(self):
        if not self.connected: return False
        return self.sdk.zoom_in()

    def zoom_out(self):
        if not self.connected: return False
        return self.sdk.zoom_out()

    def stop_zoom(self):
        if not self.connected: return False
        return self.sdk.zoom.stop_zoom()

    def take_photo(self):
        if not self.connected: return False
        return self.sdk.take_picture()

    def toggle_recording(self):
        if not self.connected: return False
        return self.sdk.record_video()
        
    def move_gimbal(self, yaw_speed: int, pitch_speed: int):
        """
        Manually rotate gimbal with specific speeds (-100 to 100)
        """
        if not self.connected: return False
        return self.sdk.rotate_gimbal(yaw_speed, pitch_speed)
        
    def stop_gimbal(self):
        """
        Stop gimbal rotation
        """
        if not self.connected: return False
        return self.sdk.rotate_gimbal(0, 0)
