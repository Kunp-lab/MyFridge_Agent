# tongue_diagnosis

ROS2 package for tongue diagnosis inference on RDK X5.

## Overview

This package implements an end-to-end tongue diagnosis pipeline:

1. **YOLO26 Segmentation** - Locates and extracts tongue region from input image
2. **4D ResNet Classification** - Classifies:
   - Tongue color (舌质色) - 5 classes
   - Coating color (舌苔色) - 3 classes  
   - Thickness (厚度) - 2 classes
   - Greasiness/Putrefaction (腻腐) - 2 classes

## Architecture

```
/tongue_diagnosis/input_image (CompressedImage)
                    ↓
              [Image Decode]
                    ↓
         [YOLO26 Segmentation]
                    ↓
      [4x ResNet Classification]
        ├─ tongue_color
        ├─ coating_color
        ├─ thickness
        └─ rot_greasy
                    ↓
/tongue_diagnosis/result (String / JSON)
```

## Dependencies

- ROS2 (tested on ROS2 Humble)
- Python 3.8+
- opencv-python
- numpy
- hbm-runtime (RDK specific)

## Quick Start

### Build

```bash
cd ~/TrosWork/MyFridge_Agent
colcon build --packages-select tongue_diagnosis
source install/setup.bash
```

### Run

```bash
ros2 launch tongue_diagnosis tongue_diagnosis.launch.py
```

This launch file now defaults `model_dir` to the installed package path:

`share/tongue_diagnosis/bin`

## Configuration

Launch parameters:
- `model_dir` (str): Directory containing `.bin` model files
- `yolo_score_threshold` (float, default=0.7): YOLO26 confidence threshold
- `input_image_topic` (str, default=`/tongue_diagnosis/input_image`)
- `output_result_topic` (str, default=`/tongue_diagnosis/result`)

## ROS2 Interface

### Subscribe
- Topic: `/tongue_diagnosis/input_image`
- Type: `sensor_msgs/msg/CompressedImage`

### Publish
- Topic: `/tongue_diagnosis/result`
- Type: `std_msgs/msg/String`
- Payload: JSON
  ```json
  {
    "record_id": "user1",
    "code": 1,
    "result": {
      "tongue_color": 1,
      "coating_color": 2,
      "thickness": 0,
      "rot_greasy": 1
    }
  }
  ```

## Model Files

Required `.bin` files in `bin/` directory:
- `yolo_seg2_bayese_640x640_nv12.bin` - YOLO26 segmentation model
- `tongue_color_bayese_224x224_nv12.bin` - Tongue color classifier
- `tongue_coat_color_bayese_224x224_nv12.bin` - Coating color classifier
- `thickness_bayese_224x224_nv12.bin` - Thickness classifier
- `rot_and_greasy_bayese_224x224_nv12.bin` - Greasiness/Putrefaction classifier

## Module Structure

```
tongue_diagnosis/
├── tongue_diagnosis_node.py      # Main ROS2 node
├── yolov26seg.py                 # YOLO26 segmentation wrapper
├── resnet.py                     # ResNet classification wrapper
└── utils.py                      # Shared utilities
```

## Future Work

- [ ] Add RDK-specific optimization (e.g., multi-core BPU scheduling)
- [ ] Replace fixed `record_id` with a real request-side identifier
- [ ] Add inference performance monitoring/profiling
- [ ] Support batch processing for multiple images
- [ ] Add model versioning and fallback mechanisms

## License

Apache 2.0
