# Detection Module

This directory contains all object detection components: inference, post-processing, visualization, and the main pipeline orchestrator.

## Module Structure

```
detection/
├── __init__.py              # Module exports
├── README.md                # This file
├── hailo_inference.py       # Hailo AI accelerator inference
├── postprocess.py           # Detection post-processing
├── visualize.py             # Visualization and display
└── pipeline.py              # Detection pipeline orchestrator
```

---

## Modules

### 1. **Hailo Inference** (`hailo_inference.py`)

Wrapper for Hailo AI accelerator devices (Hailo-8, Hailo-8L, Hailo-10).

```python
from src.detection import HailoInfer

# Initialize inference engine
hailo = HailoInfer(
    hef_path="yolov8n.hef",
    batch_size=1,
    input_type="UINT8",    # Optional
    output_type="FLOAT32",  # Optional
    priority=0
)

# Get input shape
input_shape = hailo.get_input_shape()  # (height, width, channels)

# Run inference (async)
hailo.run(preprocessed_batch, callback_function)

# Cleanup
hailo.close()
```

**Features:**
- Asynchronous inference execution
- Automatic VDevice configuration with round-robin scheduling
- Support for multiple input/output data types
- Automatic NMS post-processing detection
- Batch processing support

**Key Class:**
- `HailoInfer`: Main inference wrapper

**Methods:**
- `__init__(hef_path, batch_size, input_type, output_type, priority)`
- `get_input_shape()` → Returns model input dimensions
- `run(input_batch, callback_fn)` → Execute async inference
- `create_bindings(configured_model, input_batch)` → Create I/O bindings
- `close()` → Release resources

---

### 2. **Post-Processing** (`postprocess.py`)

Detection extraction and coordinate transformation.

```python
from src.detection import extract_detections, denormalize_and_rm_pad

# Extract detections from model output
detections = extract_detections(
    image=original_image,
    detections=raw_model_output,
    config_data=config
)

# Returns:
# {
#     'detection_boxes': [...],      # List of [ymin, xmin, ymax, xmax]
#     'detection_classes': [...],    # List of class IDs
#     'detection_scores': [...],     # List of confidence scores
#     'num_detections': N            # Number of detections
# }
```

**Features:**
- Denormalizes bounding box coordinates
- Removes letterbox padding effects
- Filters detections by confidence threshold
- Prints detection results to console
- Returns top-N detections sorted by score

**Key Functions:**
- `extract_detections(image, detections, config_data)` → Extract and filter detections
- `denormalize_and_rm_pad(box, size, padding_length, img_h, img_w)` → Transform coordinates

**Configuration:**
```python
config_data = {
    "visualization_params": {
        "score_thres": 0.25,        # Confidence threshold
        "max_boxes_to_draw": 500    # Maximum detections
    },
    "labels": ["person", "car", ...],  # Class names
    "print_boxes": True                 # Print to console
}
```

**Console Output:**
```
================================================================================
Image Resolution: 1280x720
Detections: 2
================================================================================
Detection 1:
  Class: person (ID: 0)
  Confidence: 95.23%
  BBox [xmin, ymin, xmax, ymax]: [342, 156, 789, 923]
  BBox [x, y, width, height]: [342, 156, 447, 767]

Detection 2:
  Class: car (ID: 2)
  Confidence: 87.45%
  BBox [xmin, ymin, xmax, ymax]: [1024, 543, 1456, 876]
  BBox [x, y, width, height]: [1024, 543, 432, 333]
```

---

### 3. **Visualization** (`visualize.py`)

Drawing detections and displaying results.

```python
from src.detection import visualize, draw_detections, draw_detection, id_to_color

# Draw all detections on image
annotated_image = draw_detections(
    detections=detection_dict,
    img_out=image,
    labels=["person", "car", ...]
)

# Or draw single detection
color = id_to_color(class_id)
draw_detection(image, bbox, "person", 95.2, color)

# Visualize with display/save
visualize(
    output_queue=queue,
    cap=video_capture,      # For video/camera
    save_output=True,
    output_dir="results",
    callback=draw_callback
)
```

**Features:**
- Draws bounding boxes with class labels
- Color-coded by class (consistent colors per class)
- Real-time display window
- Save to video file or images
- Handles both streaming and batch modes

**Key Functions:**
- `visualize(output_queue, cap, save_output, output_dir, callback)` → Main visualization loop
- `draw_detections(detections, img_out, labels)` → Draw all detections
- `draw_detection(image, box, label, score, color)` → Draw single detection
- `id_to_color(idx)` → Generate consistent color for class ID

**Display Controls:**
- **`q`** key - Quit visualization
- Window close - Stop display

**Output Formats:**
- **Video**: `output_dir/output.avi` (XVID codec)
- **Images**: `output_dir/output_0.jpg`, `output_dir/output_1.jpg`, ...

---

### 4. **Pipeline** (`pipeline.py`)

Main detection pipeline orchestrator with multi-threading.

```python
from src.detection import run_detection_pipeline
from src.camera import CameraFactory
from src.config import COCO_CLASSES

# Initialize input
camera = CameraFactory.create("camera")
camera.open()

# Run detection pipeline
run_detection_pipeline(
    input_source=camera,
    hef_path="yolov8n.hef",
    batch_size=1,
    labels=COCO_CLASSES,
    output_dir="output",
    save_output=False,
    print_boxes=True
)

camera.release()
```

**Pipeline Architecture:**
```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Preprocessing  │────▶│  Inference   │────▶│ Visualization   │
│     Thread      │     │    Thread    │     │     Thread      │
└─────────────────┘     └──────────────┘     └─────────────────┘
        │                      │                      │
        ▼                      ▼                      ▼
  input_queue            Hailo Device          output_queue
```

**Features:**
- 3-thread pipeline for optimal performance
- Queue-based communication between threads
- Automatic preprocessing (letterbox with padding)
- Unified interface for all input types
- Performance timing and metrics

**Key Functions:**
- `run_detection_pipeline(...)` → Main pipeline entry point
- `default_preprocess(image, width, height)` → Letterbox preprocessing
- `preprocess_stream(...)` → Video/camera preprocessing thread
- `preprocess_images(...)` → Image batch preprocessing thread
- `infer(...)` → Inference thread
- `inference_callback(...)` → Async result handler

**Preprocessing:**
```python
# Letterbox resize with padding
preprocessed = default_preprocess(
    image,      # Original image (RGB)
    model_w=640,
    model_h=640
)
# Returns: Padded image maintaining aspect ratio
```

---

## Complete Pipeline Flow

### 1. **Input Stage**
```python
# Camera/Video/Images → RGB frames
input_source.read_frame()  # Returns (success, rgb_frame)
```

### 2. **Preprocessing Stage**
```python
# Resize + Letterbox padding
preprocessed = default_preprocess(frame, 640, 640)
# → Queue → Inference
```

### 3. **Inference Stage**
```python
# Hailo async inference
hailo.run(preprocessed_batch, callback)
# → Queue → Post-processing
```

### 4. **Post-Processing Stage**
```python
# Extract detections
detections = extract_detections(frame, raw_output, config)
# → Queue → Visualization
```

### 5. **Visualization Stage**
```python
# Draw and display
annotated = draw_detections(detections, frame, labels)
cv2.imshow("Detection", annotated)
# Optional: Save to file
```

---

## Usage Examples

### Basic Detection
```python
from src.camera import VideoInput
from src.detection import run_detection_pipeline
from src.config import COCO_CLASSES

# Load video
video = VideoInput("video.mp4")
video.open()

# Run detection
run_detection_pipeline(
    input_source=video,
    hef_path="yolov8n.hef",
    batch_size=1,
    labels=COCO_CLASSES,
    output_dir="results",
    save_output=True,
    print_boxes=True
)

video.release()
```

### Batch Image Processing
```python
from src.camera import ImageInput
from src.detection import run_detection_pipeline
from src.config import COCO_CLASSES

# Load images
images = ImageInput("dataset/", batch_size=4)
images.load()

# Run detection
run_detection_pipeline(
    input_source=images,
    hef_path="yolov8n.hef",
    batch_size=4,
    labels=COCO_CLASSES,
    output_dir="detections",
    save_output=True,
    print_boxes=False
)
```

### Custom Post-Processing
```python
from src.detection import HailoInfer, extract_detections
from src.config import DEFAULT_CONFIG

# Custom config
config = DEFAULT_CONFIG.copy()
config["visualization_params"]["score_thres"] = 0.5  # Higher threshold
config["visualization_params"]["max_boxes_to_draw"] = 100
config["labels"] = custom_labels
config["print_boxes"] = False

# Use in pipeline
detections = extract_detections(frame, raw_output, config)
```

---

## Configuration

### Detection Parameters
```python
config = {
    "visualization_params": {
        "score_thres": 0.25,      # Confidence threshold (0.0-1.0)
        "max_boxes_to_draw": 500  # Max detections per image
    },
    "labels": [                   # Class names
        "person", "car", "dog", ...
    ],
    "print_boxes": True           # Print detections to console
}
```

### Model Input Requirements
- **Format**: RGB images
- **Size**: Letterbox resized to model input size
- **Padding**: Gray (114, 114, 114) padding
- **Normalization**: Handled by Hailo device

---

## Performance Optimization

### Threading
- **Preprocessing**: CPU-bound, runs in parallel
- **Inference**: Async on Hailo device
- **Visualization**: I/O-bound (display/save)

### Batch Processing
```python
# Optimal batch sizes
- USB Camera: batch_size=1 (real-time)
- Video File: batch_size=1-2
- Images: batch_size=4-8 (depending on memory)
```

### Latency Reduction
1. Use GStreamer for USB cameras
2. Set `buffer_size=1` in camera config
3. Use `batch_size=1` for real-time
4. Disable `print_boxes` for production

---

## Troubleshooting

### No Detections
- Check confidence threshold (`score_thres`)
- Verify model is correct for input
- Check preprocessing (image should be RGB)

### Low FPS
- Reduce batch size
- Use GStreamer pipeline for cameras
- Check CPU usage (preprocessing bottleneck)
- Verify Hailo device is being used

### Memory Issues
- Reduce batch size
- Limit `max_boxes_to_draw`
- Close windows after processing

### Wrong Bounding Boxes
- Verify input image is RGB (not BGR)
- Check aspect ratio preservation
- Ensure letterbox padding is correct

---

## API Reference

### HailoInfer
```python
class HailoInfer:
    def __init__(hef_path, batch_size, input_type, output_type, priority)
    def get_input_shape() -> tuple
    def run(input_batch, callback_fn)
    def close()
```

### Post-Processing
```python
def extract_detections(image, detections, config_data) -> dict
def denormalize_and_rm_pad(box, size, padding_length, h, w) -> list
```

### Visualization
```python
def visualize(output_queue, cap, save_output, output_dir, callback)
def draw_detections(detections, img_out, labels) -> np.ndarray
def draw_detection(image, box, label, score, color)
def id_to_color(idx) -> np.ndarray
```

### Pipeline
```python
def run_detection_pipeline(input_source, hef_path, batch_size,
                          labels, output_dir, save_output, print_boxes)
def default_preprocess(image, model_w, model_h) -> np.ndarray
```

---

## Dependencies

- **HailoRT**: 4.23.0+ (Hailo-8) or 5.1.1+ (Hailo-10)
- **OpenCV**: `cv2` for visualization
- **NumPy**: Array operations
- **hailo_platform**: Hailo Python SDK

---

This module provides a complete, production-ready object detection pipeline optimized for Hailo AI accelerators! 🚀
