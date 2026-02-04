"""
Detection Module
Handles object detection pipeline, inference, and visualization
"""

from .hailo_inference import HailoInfer
from .postprocess import extract_detections, denormalize_and_rm_pad
from .visualize import visualize, draw_detections, draw_detection, id_to_color
# from .pipeline import run_detection_pipeline, default_preprocess

__all__ = [
    "HailoInfer",
    "extract_detections",
    "denormalize_and_rm_pad",
    "visualize",
    "draw_detections",
    "draw_detection",
    "id_to_color",
    #"run_detection_pipeline",
    #"default_preprocess",
]
