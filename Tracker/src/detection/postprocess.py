"""
Post-processing Functions
Detection extraction and coordinate transformation
"""

import numpy as np
from typing import List, Dict


def denormalize_and_rm_pad(
    box: list, size: int, padding_length: int, input_height: int, input_width: int
) -> list:
    """
    Denormalize bounding box coordinates and remove padding.

    The model outputs normalized coordinates in [y1, x1, y2, x2] format (row, col).
    We need to convert to [xmin, ymin, xmax, ymax] format (col, row) in original image space.

    Args:
        box: Normalized bounding box coordinates [y1_norm, x1_norm, y2_norm, x2_norm].
        size: Size to scale the coordinates (max of width/height).
        padding_length: Length of padding to remove.
        input_height: Height of the original image.
        input_width: Width of the original image.

    Returns:
        Denormalized bounding box coordinates [xmin, ymin, xmax, ymax].
    """
    # Scale normalized coords to size
    box = [int(x * size) for x in box]
    # box is now [y1, x1, y2, x2] in padded space

    # Remove padding based on which dimension was padded
    if input_height < input_width:
        # Image is wider than tall -> padding added to top/bottom (y-direction)
        # Subtract padding from y coordinates (indices 0 and 2)
        box[0] -= padding_length  # y1
        box[2] -= padding_length  # y2
    elif input_width < input_height:
        # Image is taller than wide -> padding added to left/right (x-direction)
        # Subtract padding from x coordinates (indices 1 and 3)
        box[1] -= padding_length  # x1
        box[3] -= padding_length  # x2
    # If width == height, no padding was added

    # Convert from [y1, x1, y2, x2] to [xmin, ymin, xmax, ymax]
    return [box[1], box[0], box[3], box[2]]


def extract_detections(image: np.ndarray, detections: list, config_data: dict) -> dict:
    """
    Extract detections from the raw model output.

    Args:
        image: Image to draw on.
        detections: Raw detections from the model.
        config_data: Configuration containing post-processing metadata and labels.

    Returns:
        Dictionary containing filtered detection results.
    """
    visualization_params = config_data["visualization_params"]
    score_threshold = visualization_params.get("score_thres", 0.25)
    max_boxes = visualization_params.get("max_boxes_to_draw", 500)
    print_boxes = config_data.get("print_boxes", True)
    labels = config_data.get("labels", [])
    target_classes = config_data.get("target_classes", None)

    # Build target class IDs if target_classes is specified
    target_class_ids = None
    if target_classes and len(target_classes) > 0:
        target_class_ids = set()
        for class_name in target_classes:
            # Find class_id for this class_name
            for idx, label in enumerate(labels):
                if label.lower() == class_name.lower():
                    target_class_ids.add(idx)
                    break

    img_height, img_width = image.shape[:2]
    size = max(img_height, img_width)
    padding_length = int(abs(img_height - img_width) / 2)

    all_detections = []

    for class_id, detection in enumerate(detections):
        # Skip this class if target_classes is specified and this class is not in it
        if target_class_ids is not None and class_id not in target_class_ids:
            continue

        # Skip empty detection arrays
        if isinstance(detection, np.ndarray) and detection.size == 0:
            continue

        for det in detection:
            # Ensure det has at least 5 elements (4 bbox coords + 1 score)
            if len(det) < 5:
                continue
            bbox, score = det[:4], det[4]
            if score >= score_threshold:
                denorm_bbox = denormalize_and_rm_pad(
                    bbox, size, padding_length, img_height, img_width
                )
                all_detections.append((score, class_id, denorm_bbox))

    # Sort by score descending
    all_detections.sort(reverse=True, key=lambda x: x[0])

    # Take top max_boxes
    top_detections = all_detections[:max_boxes]

    scores, class_ids, boxes = zip(*top_detections) if top_detections else ([], [], [])

    # Print bounding boxes in original image coordinates
    if print_boxes and top_detections:
        labels = config_data.get("labels", [])
        print(f"\n{'='*80}")
        print(f"Image Resolution: {img_width}x{img_height}")
        print(f"Detections: {len(top_detections)}")
        print(f"{'='*80}")
        for idx, (score, class_id, box) in enumerate(top_detections):
            # box is [xmin, ymin, xmax, ymax]
            xmin, ymin, xmax, ymax = box[0], box[1], box[2], box[3]

            width = xmax - xmin
            height = ymax - ymin
            class_name = (
                labels[class_id] if class_id < len(labels) else f"Class_{class_id}"
            )
            print(f"Detection {idx+1}:")
            print(f"  Class: {class_name} (ID: {class_id})")
            print(f"  Confidence: {score*100:.2f}%")
            print(f"  BBox [xmin, ymin, xmax, ymax]: [{xmin}, {ymin}, {xmax}, {ymax}]")
            print(f"  BBox [x, y, width, height]: [{xmin}, {ymin}, {width}, {height}]")
            print()

    return {
        "detection_boxes": list(boxes),
        "detection_classes": list(class_ids),
        "detection_scores": list(scores),
        "num_detections": len(top_detections),
    }
