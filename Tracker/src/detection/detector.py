import cv2
import numpy as np
import time
import queue
from functools import partial
from src.core.config import cfg
from src.utils.logger import get_logger
from .hailo_inference import HailoInfer
from .postprocess import extract_detections

logger = get_logger(__name__)

class HailoDetector:
    def __init__(self):
        self.model_path = cfg.get("detection.model_path")
        self.conf_threshold = cfg.get("detection.confidence_threshold", 0.5)
        self.enabled = cfg.get("detection.enabled", True)
        self.labels_path = cfg.get("detection.labels_path")
        self.labels = self.load_labels(self.labels_path)
        
        self.hailo_infer = None
        self.input_shape = None
        self.queue = queue.Queue(maxsize=1)
        
        self.config_data = {
             "labels": self.labels,
             "print_boxes": False,
             "visualization_params": {
                 "score_thres": self.conf_threshold,
                 "max_boxes_to_draw": 50
             },
             "target_classes": cfg.get("detection.target_classes")
        }

        try:
            logger.info(f"Initializing Hailo Detector with model: {self.model_path}")
            self.hailo_infer = HailoInfer(self.model_path)
            self.input_shape = self.hailo_infer.get_input_shape()
            logger.info(f"Hailo Initialized. Input shape: {self.input_shape}")
        except Exception as e:
            logger.error(f"Failed to initialize Hailo: {e}")
            self.hailo_infer = None
            
    def load_labels(self, path):
        if not path: return []
        try:
            with open(path, 'r') as f:
                return [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            logger.warning(f"Labels file not found: {path}")
            return ["object"] * 100

    def preprocess(self, image):
        """
        Resize image with unchanged aspect ratio using padding.
        """
        model_h, model_w, _ = self.input_shape
        img_h, img_w, _ = image.shape[:3]
        scale = min(model_w / img_w, model_h / img_h)
        new_img_w, new_img_h = int(img_w * scale), int(img_h * scale)
        image_resized = cv2.resize(image, (new_img_w, new_img_h), interpolation=cv2.INTER_CUBIC)

        padded_image = np.full((model_h, model_w, 3), (114, 114, 114), dtype=np.uint8)
        x_offset = (model_w - new_img_w) // 2
        y_offset = (model_h - new_img_h) // 2
        padded_image[y_offset : y_offset + new_img_h, x_offset : x_offset + new_img_w] = image_resized

        return padded_image

    def _callback(self, completion_info, bindings_list, output_queue):
        """
        Callback from HailoInfer.
        """
        if completion_info.exception:
            print(f"[ERROR] Inference error: {completion_info.exception}")
            output_queue.put(None)
        else:
            # We assume batch size 1
            for i, bindings in enumerate(bindings_list):
                 if len(bindings._output_names) == 1:
                     result = bindings.output().get_buffer()
                 else:
                     result = {
                         name: np.expand_dims(bindings.output(name).get_buffer(), axis=0)
                         for name in bindings._output_names
                     }
                 output_queue.put(result)

    def detect(self, frame):
        """
        Synchonous detection wrapper.
        """
        if not self.enabled or self.hailo_infer is None:
            return []

        try:
            # 1. Preprocess
            processed = self.preprocess(frame)
            
            # 2. Run Inference
            # Define callback specifically for this run
            cb = partial(self._callback, output_queue=self.queue)
            
            try:
                self.hailo_infer.run([processed], cb)
            except Exception as e:
                 logger.error(f"Hailo Run Failed: {e}")
                 return []
            
            # 3. Wait for result
            try:
                raw_results = self.queue.get(timeout=1.0) # 1 sec timeout
            except queue.Empty:
                logger.warning("Inference timed out.")
                return []
            
            if raw_results is None:
                return []

            # 4. Postprocess
            detections_input = []
            
            if isinstance(raw_results, list):
                detections_input = raw_results
            elif isinstance(raw_results, dict):
                detections_input = list(raw_results.values())
            elif isinstance(raw_results, np.ndarray):
                if len(raw_results.shape) == 3 and raw_results.shape[0] == 1:
                     detections_input = [raw_results[0]]
                else:
                     detections_input = [raw_results]
            else:
                logger.warning(f"Unknown raw_results type: {type(raw_results)}")
                return []

            # Try to catch the specific postprocess error
            try:
                results = extract_detections(frame, detections_input, self.config_data)
            except Exception as e:
                logger.error(f"extract_detections failed: {e}")
                return []

            # Convert to our format: [(label, conf, (x,y,w,h))]
            detections = []
            boxes = results.get("detection_boxes", [])
            scores = results.get("detection_scores", [])
            classes = results.get("detection_classes", [])
            
            for i in range(len(boxes)):
                box = boxes[i] # [xmin, ymin, xmax, ymax]
                score = scores[i]
                class_id = int(classes[i])
                
                label = self.labels[class_id] if class_id < len(self.labels) else f"Class {class_id}"
                
                x = int(box[0])
                y = int(box[1])
                w = int(box[2] - box[0])
                h = int(box[3] - box[1])
                
                detections.append((label, score, (x, y, w, h)))
                
            return detections
            
        except Exception as e:
            print(f"[ERROR] Detection Loop Error: {e}")
            return []

    def close(self):
        if self.hailo_infer:
            self.hailo_infer.close()
