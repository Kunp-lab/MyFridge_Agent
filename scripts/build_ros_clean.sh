#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

env \
  -u CONDA_PREFIX \
  -u CONDA_DEFAULT_ENV \
  -u CONDA_PROMPT_MODIFIER \
  -u CONDA_EXE \
  -u CONDA_PYTHON_EXE \
  -u CONDA_SHLVL \
  PATH="/home/kunp/.local/bin:/home/kunp/.npm-global/bin:/opt/ros/foxy/bin:/opt/tros/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  PYTHONPATH="/opt/ros/foxy/lib/python3.8/site-packages:/opt/tros/lib/python3.8/site-packages" \
  AMENT_PREFIX_PATH="/opt/ros/foxy:/opt/tros" \
  CMAKE_PREFIX_PATH="/opt/tros" \
  COLCON_PREFIX_PATH="/opt/tros" \
  bash -lc "
    cd \"$ROOT_DIR\"
    colcon build --symlink-install \
      --allow-overriding hobot_usb_cam \
      --cmake-args -DPYTHON_EXECUTABLE=/usr/bin/python3 \"\$@\"
  " bash "$@"
