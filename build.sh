#!/usr/bin/env bash
set -e
pip install --upgrade pip
pip install -r requirements.txt
pip uninstall -y opencv-python || true
pip install opencv-python-headless
