#!/bin/bash
# Launch DEUS Eye
cd "$(dirname "$0")"
source deus_venv/bin/activate
python deus_eye.py
