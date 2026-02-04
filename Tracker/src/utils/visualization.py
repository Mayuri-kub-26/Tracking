import cv2

def draw_detections(frame, detections):
    """
    Draw detection boxes.
    detections: [(label, conf, (x,y,w,h)), ...]
    """
    for label, conf, (x, y, w, h) in detections:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 165, 255), 2)
        cv2.putText(frame, f"{label}: {conf:.2f}", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

def draw_tracking_info(frame, bbox, center_x, center_y, error_x, error_y):
    """
    Draw tracking box and error info.
    """
    x, y, w, h = [int(v) for v in bbox]
    target_x = x + w // 2
    target_y = y + h // 2

    # Box
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    
    # Center points
    cv2.circle(frame, (target_x, target_y), 5, (0, 255, 0), -1)
    cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)
    
    # Line
    cv2.line(frame, (center_x, center_y), (target_x, target_y), (255, 255, 0), 2)
    
    # Text
    cv2.putText(frame, f"Err: {error_x},{error_y}", (10, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

def draw_hud(frame, mode, fps):
    cv2.putText(frame, f"Mode: {mode.upper()}", (10, frame.shape[0] - 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
    cv2.putText(frame, f"FPS: {fps:.1f}", (frame.shape[1] - 120, frame.shape[0] - 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
