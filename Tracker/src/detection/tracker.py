import threading
import numpy as np
import cv2
from src.core.config import cfg
from src.detection.bytetracker.byte_tracker import BYTETracker

class ObjectTracker:
    def __init__(self, detector=None):
        self.tracker_type = cfg.get("tracking.tracker_type", "CSRT")
        self.tracker = None
        self.tracking_active = False
        self.detector = detector # Reference to detector for ByteTracker
        self.tracked_id = None   # ID to follow in ByteTracker mode
        self.lock = threading.Lock() # Thread safety lock
        
        # ByteTracker args from config
        class Args:
            track_thresh = cfg.get("tracking.bytetracker.track_thresh", 0.1)
            track_buffer = cfg.get("tracking.bytetracker.track_buffer", 30)
            match_thresh = cfg.get("tracking.bytetracker.match_thresh", 0.9)
            mot20 = cfg.get("tracking.bytetracker.mot20", False)
        self.byte_args = Args()

        if self.tracker_type == "BYTE":
             print("[INFO] specific tracker args not fully implemented via config yet, using defaults")

    def _create_tracker(self):
        if self.tracker_type == 'CSRT':
            return cv2.TrackerCSRT_create()
        elif self.tracker_type == 'KCF':
            return cv2.TrackerKCF_create()
        elif self.tracker_type == 'MOSSE':
            return cv2.legacy.TrackerMOSSE_create()
        elif self.tracker_type == 'BYTE':
            return BYTETracker(self.byte_args)
        else:
            return cv2.TrackerCSRT_create()

    def init(self, frame, bbox):
        """
        Initialize tracker with frame and bbox (x, y, w, h)
        For ByteTracker, we find the object matching this bbox to get its ID.
        """
        with self.lock:
            self.tracker = self._create_tracker()
            self.tracking_active = True
            
            if self.tracker_type == 'BYTE':
                 # In ByteTracker, 'init' implies finding the ID of the object at bbox
                 # We need to run detection once to find the ID
                 if self.detector:
                     detections = self.detector.detect(frame)
                     # Find match
                     x, y, w, h = bbox
                     mx, my = x + w/2, y + h/2
                     
                     best_iou = 0
                     best_id = None
                     
                     min_dist = float('inf')
                     
                     # Prepare detections for ByteTracker to initialize internal state
                     # Format: [[x1, y1, x2, y2, score], ...]
                     formatted_dets = []
                     for label, score, (dx, dy, dw, dh) in detections:
                         formatted_dets.append([dx, dy, dx+dw, dy+dh, score])
                     
                     if formatted_dets:
                         dets_np = np.array(formatted_dets, dtype=float)
                         online_targets = self.tracker.update(dets_np)
                         
                         for t in online_targets:
                             tx, ty, tw, th = t.tlwh
                             tcx, tcy = tx + tw/2, ty + th/2
                             dist = ((tcx - mx)**2 + (tcy - my)**2)**0.5
                             
                             if dist < min_dist:
                                 min_dist = dist
                                 best_id = t.track_id
                         
                         if best_id is not None and min_dist < 100: # Threshold
                             self.tracked_id = best_id
                             print(f"[INFO] ByteTracker locked on ID: {self.tracked_id}")
                         else:
                             print("[WARN] ByteTracker could not match init bbox to an object ID")
                             self.tracking_active = False
                 else:
                     print("[ERROR] ByteTracker requires a detector!")
                     self.tracking_active = False

            else:
                self.tracker.init(frame, bbox)
                
            print(f"[INFO] Tracker initialized ({self.tracker_type})")

    def update(self, frame):
        """
        Update tracker.
        Returns (success, bbox)
        """
        # Run detection outside lock if possible to minimize blocking? 
        # But for ByteTracker we need detection first.
        # Actually ByteTracker update IS fast, detection is the slow part.
        # For thread safety, we must hold lock when accessing self.tracker.
        
        # However, detector.detect is slow. We should perhaps run it without lock?
        # BUT, if we stop tracking mid-detection, we shouldn't update the tracker.
        
        detections = None
        if self.tracker_type == 'BYTE' and self.detector and self.tracking_active:
             detections = self.detector.detect(frame)

        with self.lock:
            if not self.tracking_active or self.tracker is None:
                return False, None
                
            if self.tracker_type == 'BYTE':
                if not detections:
                    return False, None
                
                # 2. Format for ByteTracker
                formatted_dets = []
                for label, score, (x, y, w, h) in detections:
                    formatted_dets.append([x, y, x+w, y+h, score])
                
                if not formatted_dets:
                     formatted_dets = np.empty((0, 5))
                else:
                     formatted_dets = np.array(formatted_dets, dtype=float)

                # 3. Update Tracker
                online_targets = self.tracker.update(formatted_dets)
                
                # 4. Find our locked ID
                for t in online_targets:
                    if t.track_id == self.tracked_id:
                        x, y, w, h = t.tlwh
                        return True, (x, y, w, h)
                
                return False, None

            else:
                success, bbox = self.tracker.update(frame)
                if not success:
                    self.tracking_active = False # Lost tracking
                    
                return success, bbox

    def stop(self):
        with self.lock:
            self.tracker = None
            self.tracking_active = False
            self.tracked_id = None
