[English](/home/kunp/TrosWork/MyFridge_Agent/README.md) | [简体中文](/home/kunp/TrosWork/MyFridge_Agent/README_cn.md)

# MyFridge_Agent

`MyFridge_Agent` is a ROS2-based intelligent dietary management robot project.  
Its goal is to integrate refrigerator inventory management, food recognition, tongue diagnosis, nutrition guidance, and device coordination into a single runnable system.

The project now follows a more standard ROS2 launch layout:

- `my_fridge_agent_bringup` is the system-level entry point
- each functional package keeps its own local `launch` file

## What The System Does

MyFridge_Agent is designed around a practical smart-fridge scenario:

- it tracks ingredients stored in the refrigerator
- it recognizes food items from the camera feed
- it records shelf position and remaining shelf life
- it performs tongue-image analysis and generates lightweight health-oriented guidance
- it combines fridge data and recent health context to generate diet suggestions
- it coordinates UI, database, camera, MCU, and motor-related nodes through ROS2

## Package Overview

### `src/my_fridge_agent_bringup`

This is the top-level bringup package for the whole robot.

Responsibilities:

- starts the complete application stack
- includes the launch files of the main functional packages
- centralizes system-level launch arguments such as test mode, tongue diagnosis enablement, tongue model directory, tongue diagnosis confidence threshold, and USB camera device path

If you want one command for the whole robot, this is the package you use.

### `src/qt_display`

This is the main interaction layer of the project and one of the most important packages.

Responsibilities:

- provides the Qt-based graphical interface
- subscribes to camera images and updates the live UI
- triggers food recognition workflows
- triggers nutrition recommendation workflows
- sends tongue diagnosis requests
- receives tongue diagnosis results and formats them for the UI
- communicates with the database service through `/sql_operation`
- publishes UART bridge commands for MCU-side coordination

In practice, this package is the business center of the application: it is where user actions, image-driven workflows, recommendation logic, and health-result display come together.

### `src/sql_server`

This package provides the SQLite-backed database service layer.

Responsibilities:

- opens and manages the project database
- exposes the `/sql_operation` ROS2 service
- stores and retrieves fridge inventory records
- stores recent health-status history
- reacts to some environment and position events that update stored data

It is the persistence layer of the project.

### `src/sql_interface`

This package defines the service contract used to talk to the database layer.

Responsibilities:

- provides `SQLOperation.srv`
- defines the request/response fields shared between UI and database service
- acts as the protocol boundary between application logic and persistence logic

This package does not contain business logic by itself, but it is essential for keeping the rest of the system decoupled.

### `src/connector`

This is the device bridge package between ROS2 and lower-level hardware.

Responsibilities:

- handles MCU serial communication
- publishes environment-related topics such as position and clock events
- subscribes to `/uart/data` for outgoing UART packets
- manages QDriver-related motor control logic

This package is where software and external hardware meet.

### `src/hobot_usb_cam`

This package is responsible for image acquisition from the USB camera.

Responsibilities:

- opens the configured USB video device
- publishes ROS2 image topics used by upper-layer components
- serves as the unified visual input source for the Qt display layer, food recognition, and tongue diagnosis

In this project, the camera feed is a core upstream dependency for multiple workflows.

### `src/tongue_diagnosis`

This package implements the tongue diagnosis inference pipeline.

Responsibilities:

- subscribes to `/tongue_diagnosis/input_image`
- decodes incoming compressed images
- runs tongue-region segmentation
- runs four classification heads: tongue color, coating color, thickness, and greasy / putrefaction state
- publishes structured JSON results to `/tongue_diagnosis/result`

The package is designed so it can still be launched independently, but in normal usage it is started by `my_fridge_agent_bringup`.

### `database/`

This directory stores the database-related assets of the project.

Contents include:

- the SQLite database file
- the SQL schema
- database-side build / install / log artifacts already present in the repository layout

For this project, `database/` should be treated as a real data boundary, not just a sample folder.

## System Architecture

At a high level, the runtime flow is:

1. `hobot_usb_cam` publishes camera data
2. `qt_display` subscribes to the image stream and updates the UI
3. `qt_display` triggers recognition, recommendation, and tongue diagnosis workflows
4. `sql_server` persists inventory and health-related records
5. `connector` bridges ROS2 messages to MCU / UART communication
6. `tongue_diagnosis` processes tongue images and returns structured results

## Main Topics And Service

### Topics

- `/image`
  Used as the main camera image topic consumed by the display layer.

- `/tongue_diagnosis/input_image`
  Published by `qt_display` when a tongue diagnosis task is started.

- `/tongue_diagnosis/result`
  Published by `tongue_diagnosis` after inference.

- `/uart/data`
  Used by the UI layer to publish UART packets toward the MCU bridge.

- `/env/pos`
  Used for refrigerator position / slot-related state updates.

- `/env/clock`
  Used for time-delta style updates that may affect expiry logic.

### Service

- `/sql_operation`
  Backed by `sql_server`, defined by `sql_interface/srv/SQLOperation.srv`

Typical usage includes:

- appending inventory records
- deleting or modifying slot records
- querying inventory by location
- appending health-status records
- retrieving recent health-status history

## Quick Start

### 1. Build

```bash
cd ~/TrosWork/MyFridge_Agent
colcon build
source install/setup.bash
```

### 2. Launch The Full System

```bash
ros2 launch my_fridge_agent_bringup bringup.launch.py
```

This command starts the main runtime stack:

- `qt_display`
- `sql_server`
- `connector`
- `hobot_usb_cam`
- `tongue_diagnosis`

## Common Launch Arguments

Enable test mode:

```bash
ros2 launch my_fridge_agent_bringup bringup.launch.py test_mode:=true
```

Disable tongue diagnosis temporarily:

```bash
ros2 launch my_fridge_agent_bringup bringup.launch.py enable_tongue_diagnosis:=false
```

Use a custom tongue-model directory:

```bash
ros2 launch my_fridge_agent_bringup bringup.launch.py tongue_model_dir:=/your/model/bin
```

Use a different USB camera device:

```bash
ros2 launch my_fridge_agent_bringup bringup.launch.py usb_video_device:=/dev/video0
```

Show all available bringup arguments:

```bash
ros2 launch my_fridge_agent_bringup bringup.launch.py --show-args
```

## Runtime Relationships

- `hobot_usb_cam` provides the image stream
- `qt_display` consumes images and drives user-facing workflows
- `qt_display` talks to `sql_server` through `/sql_operation`
- `connector` bridges ROS2 traffic to UART / MCU interactions
- `tongue_diagnosis` handles the inference path for tongue analysis
- health results are written back into the database and reused by recommendation logic

## Data And Persistence

Database-related files:

- database file: `database/my_fridge`
- schema file: `database/schema.sql`

Main persisted tables currently relevant to the running application:

- `ingredients`
- `health_status_history`

If you plan to modify schema, migrations, or persistent data, backing up the database first is strongly recommended.

## Key Configuration Files

- system bringup: `src/my_fridge_agent_bringup/launch/bringup.launch.py`
- UI launch: `src/qt_display/launch/qtapp.launch.py`
- SQL service launch: `src/sql_server/launch/sql_server.launch.py`
- connector launch: `src/connector/launch/connector.launch.py`
- tongue diagnosis launch: `src/tongue_diagnosis/launch/tongue_diagnosis.launch.py`
- cloud / model-related UI config: `src/qt_display/qt_display/config.py`

## Environment Notes

- recommended ROS2 distribution: Humble
- mixed Python / C++ workspace
- tongue diagnosis depends on RDK X5-related runtime support and `.bin` model files
- the default USB camera device is `/dev/video8`

## Practical Recommendation

For normal usage, launch the project through `my_fridge_agent_bringup`.

When deploying to a new machine or board, verify these first:

- USB camera device path
- tongue-model directory
- cloud API configuration in `qt_display`
- database path and file permissions
