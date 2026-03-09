"""Download Face Landmarker model if not present."""
import urllib.request
from pathlib import Path

try:
    import config
except ImportError:
    import sys
    _root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_root))
    import config


def ensure_face_landmarker_model() -> Path:
    """Download face_landmarker.task to config.DATA_DIR if missing. Returns path."""
    path = config.FACE_LANDMARKER_MODEL
    if path.exists():
        return path
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(config.FACE_LANDMARKER_URL, path)
    return path
