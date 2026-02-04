"""
Visualization Functions
Drawing detections on images and displaying results
"""

import os
import cv2
import queue
import numpy as np
from typing import List, Optional, Callable

# from ..streaming import get_streaming_queue


def id_to_color(idx: int) -> np.ndarray:
    """Generate a unique color for a given ID."""
    np.random.seed(idx)
    return np.random.randint(0, 255, size=3, dtype=np.uint8)


class BBoxSmoother:
    """
    Smooth bounding box coordinates using exponential moving average to reduce flickering.
    """
    def __init__(self, alpha: float = 0.6):
        """
        Args:
            alpha: Smoothing factor (0-1). Higher = more responsive, Lower = smoother.
                   0.6 provides good balance for moving objects.
        """
        self.alpha = alpha
        self.smoothed_boxes = {}  # track_id -> [xmin, ymin, xmax, ymax]

    def smooth(self, track_id: int, bbox: List[float]) -> List[int]:
        """
        Apply exponential moving average to bounding box coordinates.

        Args:
            track_id: Unique track identifier
            bbox: Current bounding box [xmin, ymin, xmax, ymax]

        Returns:
            Smoothed bounding box [xmin, ymin, xmax, ymax]
        """
        if track_id not in self.smoothed_boxes:
            # First occurrence - initialize with current box
            self.smoothed_boxes[track_id] = bbox
            return [int(x) for x in bbox]

        # Apply exponential moving average: smoothed = alpha * current + (1-alpha) * previous
        prev = self.smoothed_boxes[track_id]
        smoothed = [
            self.alpha * bbox[i] + (1 - self.alpha) * prev[i]
            for i in range(4)
        ]
        self.smoothed_boxes[track_id] = smoothed
        return [int(x) for x in smoothed]

    def reset(self, track_id: int):
        """Remove smoothing history for a track (when track is lost)."""
        if track_id in self.smoothed_boxes:
            del self.smoothed_boxes[track_id]


# Global bbox smoother instance
_bbox_smoother = BBoxSmoother(alpha=0.6)


def draw_detection(
    image: np.ndarray, box: list, label: str, score: float, color: tuple
):
    """
    Draw box and label for one detection.

    Args:
        image: Image to draw on.
        box: Bounding box coordinates [xmin, ymin, xmax, ymax].
        label: Class label.
        score: Detection score.
        color: Color for the bounding box.
    """
    xmin, ymin, xmax, ymax = map(int, box)
    cv2.rectangle(image, (xmin, ymin), (xmax, ymax), color, 2)
    font = cv2.FONT_HERSHEY_SIMPLEX

    text = f"{label}: {score:.1f}%"
    text_color = (255, 255, 255)  # White
    border_color = (0, 0, 0)  # Black

    # Draw text with black border
    cv2.putText(
        image, text, (xmin + 4, ymin + 20), font, 0.5, border_color, 2, cv2.LINE_AA
    )
    cv2.putText(
        image, text, (xmin + 4, ymin + 20), font, 0.5, text_color, 1, cv2.LINE_AA
    )


def draw_detections(
    detections: dict,
    img_out: np.ndarray,
    labels: List[str],
    tracker=None,
    img_height: int = None,
    img_width: int = None,
    manual_tracking: bool = False,
    tracks: Optional[List] = None,
) -> np.ndarray:
    """
    Draw detections on the image, with optional tracking.

    Args:
        detections: Dictionary containing detection data.
        img_out: Image to draw on.
        labels: List of class labels.
        tracker: Optional tracker object for multi-object tracking.
        img_height: Image height (required for tracking).
        img_width: Image width (required for tracking).
        manual_tracking: If True, only show tracking for manual selected object.
        tracks: Optional list of precomputed tracks (if provided, tracker.update is skipped).

    Returns:
        Tuple[np.ndarray, Optional[Tuple[int, int]]]: (Annotated image, Tracked object center point (x, y))
    """
    tracked_center_point = None
    boxes = detections["detection_boxes"]
    scores = detections["detection_scores"]
    num_detections = detections["num_detections"]
    classes = detections["detection_classes"]

    # If tracking is enabled
    if (tracker is not None or tracks is not None) and img_height is not None and img_width is not None:
        if tracks is not None:
            # Use precomputed tracks (e.g. from prediction on skipped frame)
            online_targets = tracks
        else:
            # Convert detections to ByteTracker format
            # ByteTracker expects: [[x1, y1, x2, y2, score], ...]
            dets_for_tracker = []
            for idx in range(num_detections):
                box = boxes[idx]
                score = scores[idx]
                # box is [xmin, ymin, xmax, ymax]
                dets_for_tracker.append([box[0], box[1], box[2], box[3], score])

            # Update tracker
            if len(dets_for_tracker) > 0:
                dets_array = np.array(dets_for_tracker)
                online_targets = tracker.update(dets_array)
            else:
                online_targets = []

        if manual_tracking:
            # Manual tracking mode with smart detection box visibility:
            # - Show detection boxes when NO object is being tracked (so user can see what to click)
            # - Hide detection boxes when tracking is ACTIVE (prevents flickering)
            # - Show detection boxes again when track is LOST

            # Check if we have an active track
            has_active_track = len(online_targets) > 0

            if not has_active_track:
                # No tracking yet - show all detection boxes so user can select one
                for idx in range(num_detections):
                    color = tuple(id_to_color(classes[idx]).tolist())
                    draw_detection(
                        img_out, boxes[idx], labels[classes[idx]], scores[idx] * 100.0, color
                    )

            # Draw the selected tracked object with tracking ID
            for track in online_targets:
                tlwh = track.tlwh
                track_id = track.track_id

                # Convert from tlwh to xyxy
                raw_bbox = [tlwh[0], tlwh[1], tlwh[0] + tlwh[2], tlwh[1] + tlwh[3]]

                # Apply smoothing to reduce flickering
                xmin, ymin, xmax, ymax = _bbox_smoother.smooth(track_id, raw_bbox)

                # Calculate center point
                center_x = int((xmin + xmax) / 2)
                center_y = int((ymin + ymax) / 2)
                tracked_center_point = (center_x, center_y)

                # Use green color for selected object
                color = (0, 255, 0)  # Green

                # Find the class label for this track
                label = "tracked"
                score = 0.0
                for idx in range(num_detections):
                    det_box = boxes[idx]
                    if abs(det_box[0] - xmin) < 10 and abs(det_box[1] - ymin) < 10:
                        label = labels[classes[idx]]
                        score = scores[idx] * 100.0
                        break

                # Print center point coordinates to console
                print(f"[VISUALIZE_DEBUG] [TRACKING] ID{track_id} ({label}): Center point = ({center_x}, {center_y})")

                # Draw the selected track with thicker border
                cv2.rectangle(img_out, (xmin, ymin), (xmax, ymax), color, 4)

                # Draw center point marker (crosshair)
                cv2.drawMarker(img_out, (center_x, center_y), color,
                              markerType=cv2.MARKER_CROSS, markerSize=20, thickness=3)

                # Draw center point circle
                cv2.circle(img_out, (center_x, center_y), 5, color, -1)

                font = cv2.FONT_HERSHEY_SIMPLEX

                text = f"TRACKING ID{track_id}: {label} {score:.1f}%"
                text_color = (255, 255, 255)  # White
                border_color = (0, 0, 0)  # Black

                # Larger text for selected object
                cv2.putText(
                    img_out,
                    text,
                    (xmin + 4, ymin + 25),
                    font,
                    0.6,
                    border_color,
                    3,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    img_out,
                    text,
                    (xmin + 4, ymin + 25),
                    font,
                    0.6,
                    text_color,
                    2,
                    cv2.LINE_AA,
                )

                # Display center coordinates on frame
                coord_text = f"({center_x}, {center_y})"
                cv2.putText(
                    img_out,
                    coord_text,
                    (center_x + 10, center_y - 10),
                    font,
                    0.5,
                    border_color,
                    3,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    img_out,
                    coord_text,
                    (center_x + 10, center_y - 10),
                    font,
                    0.5,
                    text_color,
                    2,
                    cv2.LINE_AA,
                )
        else:
            # Auto tracking mode: draw all tracked objects
            for track in online_targets:
                tlwh = track.tlwh
                track_id = track.track_id

                # Convert from tlwh (top-left, width, height) to xyxy (xmin, ymin, xmax, ymax)
                raw_bbox = [tlwh[0], tlwh[1], tlwh[0] + tlwh[2], tlwh[1] + tlwh[3]]

                # Apply smoothing to reduce flickering
                xmin, ymin, xmax, ymax = _bbox_smoother.smooth(track_id, raw_bbox)
                box = [xmin, ymin, xmax, ymax]

                # Calculate center point
                center_x = int((xmin + xmax) / 2)
                center_y = int((ymin + ymax) / 2)
                # In auto mode, we just take the last one or none? 
                # For now let's not auto-gimbal in multi-object auto mode unless specified.
                # But to be safe if someone wants to use it:
                tracked_center_point = (center_x, center_y)

                # Use track_id for color to maintain consistent colors
                color = tuple(id_to_color(track_id).tolist())

                # Find the class label for this track (match with detection)
                label = "tracked"
                score = 0.0
                for idx in range(num_detections):
                    det_box = boxes[idx]
                    # Simple IoU check to match track with detection
                    if abs(det_box[0] - xmin) < 10 and abs(det_box[1] - ymin) < 10:
                        label = labels[classes[idx]]
                        score = scores[idx] * 100.0
                        break

                # Print center point coordinates to console
                print(f"[VISUALIZE_DEBUG] [TRACKING] ID{track_id} ({label}): Center point = ({center_x}, {center_y})")

                # Draw the track
                cv2.rectangle(img_out, (xmin, ymin), (xmax, ymax), color, 2)

                # Draw center point marker (crosshair)
                cv2.drawMarker(img_out, (center_x, center_y), color,
                              markerType=cv2.MARKER_CROSS, markerSize=15, thickness=2)

                # Draw center point circle
                cv2.circle(img_out, (center_x, center_y), 4, color, -1)

                font = cv2.FONT_HERSHEY_SIMPLEX

                text = f"ID{track_id}: {label} {score:.1f}%"
                text_color = (255, 255, 255)  # White
                border_color = (0, 0, 0)  # Black

                cv2.putText(
                    img_out,
                    text,
                    (xmin + 4, ymin + 20),
                    font,
                    0.5,
                    border_color,
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    img_out,
                    text,
                    (xmin + 4, ymin + 20),
                    font,
                    0.5,
                    text_color,
                    1,
                    cv2.LINE_AA,
                )

                # Display center coordinates on frame
                coord_text = f"({center_x}, {center_y})"
                cv2.putText(
                    img_out,
                    coord_text,
                    (center_x + 8, center_y - 8),
                    font,
                    0.4,
                    border_color,
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    img_out,
                    coord_text,
                    (center_x + 8, center_y - 8),
                    font,
                    0.4,
                    text_color,
                    1,
                    cv2.LINE_AA,
                )
    else:
        # No tracking - draw raw detections
        for idx in range(num_detections):
            color = tuple(id_to_color(classes[idx]).tolist())
            draw_detection(
                img_out, boxes[idx], labels[classes[idx]], scores[idx] * 100.0, color
            )

            

    return img_out, tracked_center_point


def visualize(
    output_queue: queue.Queue,
    cap: Optional[cv2.VideoCapture],
    save_output: bool,
    output_dir: str,
    callback: Callable,
    debug: bool = True,
    manual_tracker=None,
) -> None:
    """
    Visualize inference results and optionally save output.

    Args:
        output_queue: Queue with (frame, inference_result) tuples.
        cap: VideoCapture for camera/video input, or None for image mode.
        save_output: If True, save the visualization.
        output_dir: Directory to save output.
        callback: Function that draws detections on the frame.
        debug: If True, display feed with cv2.imshow. If False, send to streaming_queue.
        manual_tracker: Optional ManualObjectTracker for manual object selection.
    """
    image_id = 0
    out = None

    # Mouse callback for manual tracking
    mouse_move_count = [0]  # Use list to modify in nested function

    def mouse_callback(event, x, y, flags, param):
        """Handle mouse events for manual object selection."""
        # Show all mouse events for debugging
        if event == cv2.EVENT_MOUSEMOVE:
            # Update coordinates
            param['mouse_pos'] = (x, y)
            # Print every 30th move to confirm callback is working
            mouse_move_count[0] += 1
            if mouse_move_count[0] % 30 == 0:
                print(f"[VISUALIZE_DEBUG] Callback working - position: ({x}, {y})")
        elif event == cv2.EVENT_LBUTTONDOWN:
            print(f"\n{'='*60}")
            print(f"[VISUALIZE_DEBUG] [Mouse] LEFT CLICK detected at window coordinates: ({x}, {y})")
            print(f"{'='*60}")
            if manual_tracker is not None:
                manual_tracker.on_mouse_click(x, y)
            else:
                print("[Mouse] ERROR: manual_tracker is None!")
        elif event == cv2.EVENT_RBUTTONDOWN:
            print(f"\n[VISUALIZE_DEBUG] [Mouse] RIGHT CLICK at ({x}, {y}) - Deselecting")
            if manual_tracker is not None:
                manual_tracker.deselect()
            else:
                print("[Mouse] ERROR: manual_tracker is None!")


    # Initialize streaming queue if not in debug mode
    streaming_queue = None
    # if not debug:
    #     streaming_queue = get_streaming_queue()

    # Mouse state for callback
    mouse_state = {'mouse_pos': None}

    # Window setup for camera/video (only in debug mode)
    if cap is not None and debug:
        try:
            cv2.namedWindow("Object Detection", cv2.WINDOW_NORMAL)
        except cv2.error as e:
            print(f"[ERROR] Could not open display: {e}")
            print("[INFO] Switching to headless mode (no display)")
            debug = False
            # If we switch to non-debug, we might need streaming queue, but we removed it.
            # So just continue without display.
        # Set mouse callback for manual tracking
        print(f"[VISUALIZE_DEBUG] MANUAL TRACKER INSTANCE: {manual_tracker}")
        if manual_tracker is not None:
            cv2.setMouseCallback("Object Detection", mouse_callback, mouse_state)
            print("\n" + "="*60)
            print("MANUAL TRACKING ENABLED")
            print("="*60)
            print("Instructions:")
            print("  - LEFT CLICK on any detected object to start tracking it")
            print("  - RIGHT CLICK to deselect and stop tracking")
            print("  - Press 'q' to quit")
            print("="*60 + "\n")

    # Video writer setup for camera/video (independent of debug mode)
    if cap is not None and save_output:
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, "output.avi")
        out = cv2.VideoWriter(
            out_path,
            cv2.VideoWriter_fourcc(*"XVID"),
            fps,
            (frame_width, frame_height),
        )

    # Main visualization loop
    while True:
        result = output_queue.get()
        if result is None:
            output_queue.task_done()
            break

        original_frame, inference_result = result

        if isinstance(inference_result, list) and len(inference_result) == 1:
            inference_result = inference_result[0]

        frame_with_detections = callback(original_frame, inference_result)

        bgr_frame = cv2.cvtColor(frame_with_detections, cv2.COLOR_RGB2BGR)

        # Add manual tracking UI indicators
        if cap is not None and debug and manual_tracker is not None:
            # Add header text showing manual tracking is active
            cv2.putText(bgr_frame, "MANUAL TRACKING MODE", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(bgr_frame, "Click on object to track", (10, 55),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            # Show mouse position if available
            if mouse_state.get('mouse_pos'):
                mx, my = mouse_state['mouse_pos']
                cv2.circle(bgr_frame, (mx, my), 5, (0, 255, 255), -1)
                cv2.putText(bgr_frame, f"({mx},{my})", (mx+10, my-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            # Show if an object is selected
            if manual_tracker.is_selected():
                track_id = manual_tracker.get_selected_track_id()
                cv2.putText(bgr_frame, f"Tracking ID: {track_id}", (10, 80),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        if cap is not None:
            if debug:
                # Debug mode: display the frame
                cv2.imshow("Object Detection", bgr_frame)
            else:
                # Non-debug mode: send to streaming queue
                pass
                # if streaming_queue is not None:
                #    try:
                #        # Non-blocking put to avoid deadlock
                #        streaming_queue.put_nowait((frame_with_detections, inference_result))
                #    except queue.Full:
                #        # Queue full, drop frame (prevents memory buildup)
                #        pass

            if save_output and out is not None:
                out.write(bgr_frame)
        else:
            output_path = os.path.join(output_dir, f"output_{image_id}.jpg")
            cv2.imwrite(output_path, bgr_frame)

        image_id += 1
        output_queue.task_done()

        # Press 'q' to quit (only in debug mode)
        if debug and cv2.waitKey(1) & 0xFF == ord("q"):
            break

    if cap is not None and save_output and out is not None:
        out.release()

    if debug:
        cv2.destroyAllWindows()
