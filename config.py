"""Configuration for Developer Squint Monitor. Override via environment or edit defaults.

Author: Shay Livni (https://shaylivni.com)
"""
import os
from pathlib import Path

# Interval between captures: min and max seconds (plan: 3-5 minutes)
CAPTURE_INTERVAL_MIN = int(os.environ.get("SQUINT_INTERVAL_MIN", 180))   # 3 min
CAPTURE_INTERVAL_MAX = int(os.environ.get("SQUINT_INTERVAL_MAX", 300))   # 5 min

# Listen window: capture and analyze for this many seconds, then keep the highest-scoring frame
LISTEN_DURATION_SEC = int(os.environ.get("SQUINT_LISTEN_DURATION", 20))
# Sample one frame every this many seconds during the listen window
LISTEN_SAMPLE_INTERVAL_SEC = float(os.environ.get("SQUINT_LISTEN_SAMPLE_INTERVAL", "1.0"))

# Notify when squint score exceeds this
SQUINT_WARNING_THRESHOLD = int(os.environ.get("SQUINT_WARNING_THRESHOLD", 70))

# Only save snapshot when score is above this (0-100)
SNAPSHOT_SCORE_THRESHOLD = int(os.environ.get("SQUINT_SNAPSHOT_SCORE_THRESHOLD", 60))

# Paths
DATA_DIR = Path(os.environ.get("SQUINT_DATA_DIR", Path(__file__).resolve().parent / "data"))
DB_PATH = DATA_DIR / "squint.db"
LOG_FILE = DATA_DIR / "squint.log"
BASELINE_PATH = DATA_DIR / "baseline.json"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
FACE_LANDMARKER_MODEL = DATA_DIR / "face_landmarker.task"
FACE_LANDMARKER_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

# Discard captured images after analysis and notifications (privacy)
DISCARD_IMAGES_AFTER_USE = os.environ.get("SQUINT_DISCARD_IMAGES", "false").lower() in ("1", "true", "yes")

# Dashboard
DASHBOARD_HOST = os.environ.get("SQUINT_DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.environ.get("SQUINT_DASHBOARD_PORT", "5050"))

# Ensure data dir and snapshots dir exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
