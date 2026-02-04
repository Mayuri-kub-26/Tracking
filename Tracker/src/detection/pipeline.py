"""
Detection Pipeline
Main orchestrator for object detection pipeline
"""

import time
import queue
import threading
import cv2
import numpy as np
from typing import List, Optional
from functools import partial

from ..camera import CameraFactory, VideoInput, ImageInput
from .hailo_inference import HailoInfer
from .postprocess import extract_detections
from .visualize import visualize, draw_detections
from ..config import DEFAULT_CONFIG
from ..tracker import ManualObjectTracker
from ..utils.logger import get_logger

logger = get_logger(__name__)


def default_preprocess(image: np.ndarray, model_w: int, model_h: int) -> np.ndarray:
    """
    Resize image with unchanged aspect ratio using padding.

    Args:
        image: Input image (RGB format).
        model_w: Model input width.
        model_h: Model input height.

    Returns:
        Preprocessed and padded image.
    """
    img_h, img_w, _ = image.shape[:3]
    scale = min(model_w / img_w, model_h / img_h)
    new_img_w, new_img_h = int(img_w * scale), int(img_h * scale)
    image = cv2.resize(image, (new_img_w, new_img_h), interpolation=cv2.INTER_CUBIC)

    padded_image = np.full((model_h, model_w, 3), (114, 114, 114), dtype=np.uint8)
    x_offset = (model_w - new_img_w) // 2
    y_offset = (model_h - new_img_h) // 2
    padded_image[y_offset : y_offset + new_img_h, x_offset : x_offset + new_img_w] = (
        image
    )

    return padded_image


def divide_list_to_batches(images_list: List[np.ndarray], batch_size: int):
    """Divide the list of images into batches."""
    for i in range(0, len(images_list), batch_size):
        yield images_list[i : i + batch_size]


def preprocess_stream(
    input_source,
    batch_size: int,
    input_queue: queue.Queue,
    width: int,
    height: int,
    drop_frames: bool = False,
) -> None:
    """
    Preprocess frames from video/camera stream.

    Args:
        input_source: Camera or Video input source.
        batch_size: Number of frames per batch.
        input_queue: Queue for input frames.
        width: Model input width.
        height: Model input height.
        drop_frames: If True, drop frames when queue is full (reduces latency).
    """
    frames = []
    processed_frames = []

    while True:
        ret, frame = input_source.read_frame()
        if not ret:
            break

        frames.append(frame)
        processed_frame = default_preprocess(frame, width, height)
        processed_frames.append(processed_frame)

        if len(frames) == batch_size:
            if drop_frames:
                # Non-blocking put - skip frame if queue is full
                try:
                    input_queue.put((frames, processed_frames), block=False)
                except queue.Full:
                    # Queue full, drop this batch to maintain real-time performance
                    pass
            else:
                # Blocking put - wait until queue has space
                input_queue.put((frames, processed_frames))
            processed_frames, frames = [], []

    # Handle remaining frames
    if frames:
        if drop_frames:
            try:
                input_queue.put((frames, processed_frames), block=False)
            except queue.Full:
                pass
        else:
            input_queue.put((frames, processed_frames))

    input_queue.put(None)  # Sentinel value


def preprocess_images(
    image_source: ImageInput,
    batch_size: int,
    input_queue: queue.Queue,
    width: int,
    height: int,
) -> None:
    """
    Preprocess batch of images.

    Args:
        image_source: Image input source.
        batch_size: Number of images per batch.
        input_queue: Queue for input images.
        width: Model input width.
        height: Model input height.
    """
    images = image_source.get_all_images()

    for batch in divide_list_to_batches(images, batch_size):
        input_tuple = (
            [image for image in batch],
            [default_preprocess(image, width, height) for image in batch],
        )
        input_queue.put(input_tuple)

    input_queue.put(None)  # Sentinel value


def infer(
    hailo_inference: HailoInfer,
    input_queue: queue.Queue,
    output_queue: queue.Queue,
    detection_skip_frames: int = 0,
    enable_tracking: bool = False
):
    """
    Main inference loop with optional frame skipping for tracking optimization.

    Args:
        hailo_inference: The inference engine.
        input_queue: Queue providing (input_batch, preprocessed_batch) tuples.
        output_queue: Queue collecting (input_frame, result) tuples.
        detection_skip_frames: Number of frames to skip between detections when tracking (default: 0).
        enable_tracking: Whether tracking is enabled.
    """
    frame_counter = 0

    while True:
        next_batch = input_queue.get()
        if not next_batch:
            break

        input_batch, preprocessed_batch = next_batch

        # Frame skipping optimization: only run detection every Nth frame when tracking
        if enable_tracking and detection_skip_frames > 0:
            # Run detection on first frame and every (skip_frames + 1)th frame
            should_detect = (frame_counter % (detection_skip_frames + 1)) == 0

            if should_detect:
                # Run full inference
                inference_callback_fn = partial(
                    inference_callback, input_batch=input_batch, output_queue=output_queue
                )
                hailo_inference.run(preprocessed_batch, inference_callback_fn)
            else:
                # Skip inference, pass frames with None marker for tracker prediction
                for frame in input_batch:
                    output_queue.put((frame, None))

            frame_counter += len(input_batch)
        else:
            # Normal mode: run inference on every frame
            inference_callback_fn = partial(
                inference_callback, input_batch=input_batch, output_queue=output_queue
            )
            hailo_inference.run(preprocessed_batch, inference_callback_fn)

    hailo_inference.close()


def inference_callback(
    completion_info, bindings_list: list, input_batch: list, output_queue: queue.Queue
) -> None:
    """
    Callback to handle inference results.

    Args:
        completion_info: Hailo inference completion info.
        bindings_list: Output bindings for each inference.
        input_batch: Original input frames.
        output_queue: Queue to push output results to.
    """
    if completion_info.exception:
        logger.error(f"Inference error: {completion_info.exception}")
    else:
        for i, bindings in enumerate(bindings_list):
            if len(bindings._output_names) == 1:
                result = bindings.output().get_buffer()
            else:
                result = {
                    name: np.expand_dims(bindings.output(name).get_buffer(), axis=0)
                    for name in bindings._output_names
                }
            output_queue.put((input_batch[i], result))


def run_detection_pipeline(
    input_source,
    hef_path: str,
    batch_size: int,
    labels: List[str],
    output_dir: str,
    save_output: bool = False,
    print_boxes: bool = True,
    detection_config: Optional[dict] = None,
    enable_tracking: bool = False,
    tracking_config: Optional[dict] = None,
    debug: bool = True,
    manual_tracking: bool = False,
    detection_skip_frames: int = 0,
    gimbal_controller = None,
) -> None:
    """
    Run the complete object detection pipeline.

    Args:
        input_source: Input source (Camera, Video, or Image).
        hef_path: Path to HEF model file.
        batch_size: Number of images per batch.
        labels: List of class labels.
        output_dir: Directory to save outputs.
        save_output: Whether to save output.
        print_boxes: Whether to print bounding box coordinates.
        detection_config: Optional detection configuration dict.
        enable_tracking: Whether to enable object tracking.
        tracking_config: Optional tracking configuration dict.
        debug: Whether to display video feed (default: True).
        manual_tracking: Whether to enable manual object selection (default: False).
        detection_skip_frames: Number of frames to skip between detections when tracking (default: 0).
                               Set to 4 to run detection every 5th frame (1 detect + 4 track).
    """
    config_data = DEFAULT_CONFIG.copy()
    config_data["labels"] = labels
    config_data["print_boxes"] = print_boxes

    # Apply detection config settings
    if detection_config:
        if "confidence_threshold" in detection_config:
            config_data["visualization_params"]["score_thres"] = detection_config[
                "confidence_threshold"
            ]
        if "max_detections" in detection_config:
            config_data["visualization_params"]["max_boxes_to_draw"] = detection_config[
                "max_detections"
            ]
        if "target_classes" in detection_config:
            config_data["target_classes"] = detection_config["target_classes"]

    # Create queues
    # Use smaller queues when tracking is enabled to reduce latency
    if enable_tracking or manual_tracking:
        # Small queues prevent frame buffering and reduce delay
        input_queue = queue.Queue(maxsize=2)
        output_queue = queue.Queue(maxsize=2)
        input_queue = queue.Queue(maxsize=2)
        output_queue = queue.Queue(maxsize=2)
        logger.info("Using optimized queue sizes for tracking (maxsize=2)")
    else:
        input_queue = queue.Queue()
        output_queue = queue.Queue()

    # Initialize Hailo inference
    hailo_inference = HailoInfer(hef_path, batch_size)
    height, width, _ = hailo_inference.get_input_shape()

    logger.info(f"Model input shape: {height}x{width}")
    logger.debug(f"Batch size: {batch_size}")

    # Initialize tracker if enabled
    tracker = None
    manual_tracker_wrapper = None
    if (enable_tracking or manual_tracking) and tracking_config:
        try:
            from src.tracker import BYTETracker

            tracker_params = tracking_config.get("tracker", {})

            # Convert config to tracker arguments
            tracker_args = type(
                "Args",
                (),
                {
                    "track_thresh": tracker_params.get("track_thresh", 0.3),
                    "track_buffer": tracker_params.get("track_buffer", 30),
                    "match_thresh": tracker_params.get("match_thresh", 0.8),
                    "aspect_ratio_thresh": tracker_params.get(
                        "aspect_ratio_thresh", 2.0
                    ),
                    "min_box_area": tracker_params.get("min_box_area", 1000),
                    "mot20": tracker_params.get("mot20", False),
                },
            )()

            byte_tracker = BYTETracker(tracker_args)

            if manual_tracking:
                # Wrap in ManualObjectTracker for manual selection
                manual_tracker_wrapper = ManualObjectTracker(byte_tracker)
                tracker = manual_tracker_wrapper
            if manual_tracking:
                # Wrap in ManualObjectTracker for manual selection
                manual_tracker_wrapper = ManualObjectTracker(byte_tracker)
                tracker = manual_tracker_wrapper
                logger.info("Manual object tracking enabled - Click on objects to track them")
            else:
                tracker = byte_tracker
                logger.info(f"Object tracking enabled: {tracker_params.get('type', 'BYTETracker')}")
        except Exception as e:
            logger.warning(f"Failed to initialize tracker: {e}")
            logger.warning("Tracking will be disabled")
            tracker = None
            manual_tracker_wrapper = None

    # Create callback for post-processing (after tracker initialization)
    post_process_callback_fn = partial(
        inference_result_handler,
        labels=labels,
        config_data=config_data,
        tracker=tracker,
        manual_tracking=manual_tracking,
        gimbal_controller=gimbal_controller,
    )

    # Log frame skipping optimization if enabled
    if (enable_tracking or manual_tracking) and detection_skip_frames > 0:
        logger.info(f"Frame skipping optimization enabled: Running detection every {detection_skip_frames + 1} frames")
        logger.debug(f"  → Detect on frame: 1, {detection_skip_frames + 2}, {detection_skip_frames * 2 + 3}, ...")
        logger.debug(f"  → Track-only frames: {detection_skip_frames} frames between each detection")
        logger.debug(f"  → Expected performance gain: ~{int((detection_skip_frames / (detection_skip_frames + 1)) * 100)}% reduction in inference load")

    # Determine input type and setup preprocessing
    input_props = input_source.get_properties()
    input_type = input_props["type"]

    # Get VideoCapture object if stream type
    cap = None
    if input_type in ["camera", "video"]:
        cap = input_source.cap

    # Create threads
    if input_type in ["camera", "video"]:
        preprocess_thread = threading.Thread(
            target=preprocess_stream,
            args=(
                input_source,
                batch_size,
                input_queue,
                width,
                height,
                enable_tracking or manual_tracking,
            ),
        )
    else:  # image
        preprocess_thread = threading.Thread(
            target=preprocess_images,
            args=(input_source, batch_size, input_queue, width, height),
        )

    postprocess_thread = threading.Thread(
        target=visualize,
        args=(output_queue, cap, save_output, output_dir, post_process_callback_fn, debug, manual_tracker_wrapper),
    )

    infer_thread = threading.Thread(
        target=infer,
        args=(hailo_inference, input_queue, output_queue, detection_skip_frames, enable_tracking or manual_tracking)
    )

    # Start threads
    start_time = time.time()
    preprocess_thread.start()
    postprocess_thread.start()
    infer_thread.start()

    # Wait for threads to complete
    preprocess_thread.join()
    infer_thread.join()
    output_queue.put(None)  # Signal visualization thread to exit
    postprocess_thread.join()

    elapsed_time = time.time() - start_time

    elapsed_time = time.time() - start_time

    logger.info(f"{'='*60}")
    logger.info(f"Inference completed successfully!")
    logger.info(f"Total time: {elapsed_time:.2f} seconds")
    if save_output or input_type != "camera":
        logger.info(f"Results saved in: {output_dir}")
    logger.info(f"{'='*60}")


def inference_result_handler(
    original_frame: np.ndarray,
    infer_results: list,
    labels: List[str],
    config_data: dict,
    tracker=None,
    manual_tracking: bool = False,
    gimbal_controller=None,
) -> np.ndarray:
    """
    Process inference results and draw detections.

    Args:
        original_frame: Original image frame.
        infer_results: Raw output from the model (None if frame was skipped).
        labels: List of class labels.
        config_data: Configuration data.
        tracker: Optional tracker for multi-object tracking.
        manual_tracking: Whether manual tracking mode is enabled.

    Returns:
        Frame with detections drawn.
    """
    # Handle skipped frames (when detection was not run)
    predicted_tracks = None
    
    if infer_results is None:
        # No inference run - use tracker prediction if available
        if tracker is not None:
            predicted_tracks = tracker.predict()
            
        # Use empty detections for visualization
        detections = {
            "detection_boxes": np.array([]),
            "detection_scores": np.array([]),
            "detection_classes": np.array([]),
            "num_detections": 0
        }
    else:
        # Normal inference - extract detections
        detections = extract_detections(original_frame, infer_results, config_data)

    # Get image dimensions for tracking
    img_height, img_width = original_frame.shape[:2]

    # Draw detections (with or without tracking)
    frame_with_detections, tracked_center_point = draw_detections(
        detections,
        original_frame,
        labels,
        tracker=tracker,
        img_height=img_height,
        img_width=img_width,
        manual_tracking=manual_tracking,
        tracks=predicted_tracks,
    )
    
    # Gimbal Update based on tracking
    if gimbal_controller is not None:
        if tracked_center_point is not None:
            # Update gimbal to center the tracked object
            # tracked_center_point is (x, y) pixel coordinates of the tracked object
            # logger.debug(f"Calling Gimbal Update -> Center: {tracked_center_point}")
            gimbal_controller.update(tracked_center_point, img_width, img_height)
        else:
            # No target tracked - stop gimbal movement
            gimbal_controller.stop()
        
    return frame_with_detections
