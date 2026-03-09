"""User resting-face baseline for scoring. Load/save from JSON; compute from landmarks."""
import json
from pathlib import Path
from typing import Any

try:
    import config
except ImportError:
    import sys
    _root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_root))
    import config


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    import math
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def load_baseline() -> dict[str, float] | None:
    """Load baseline from config.BASELINE_PATH. Returns None if missing or invalid."""
    path = config.BASELINE_PATH
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        # Require core keys; mouth_center_y optional (for mouth-lift boost)
        if all(k in data for k in ("ear", "brow_left", "brow_right", "mouth_ratio", "contraction")):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def save_baseline(data: dict[str, float]) -> None:
    """Save baseline dict to config.BASELINE_PATH."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.BASELINE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_baseline_values_from_landmarks(landmarks: list) -> dict[str, float]:
    """
    Compute current resting values from one face's landmarks.
    Used when user clicks "Set as baseline" – call with the frame's landmarks.
    """
    # EAR (average of both eyes)
    def ear(inds):
        p1 = (landmarks[inds[0]].x, landmarks[inds[0]].y)
        p2 = (landmarks[inds[1]].x, landmarks[inds[1]].y)
        p3 = (landmarks[inds[2]].x, landmarks[inds[2]].y)
        p4 = (landmarks[inds[3]].x, landmarks[inds[3]].y)
        p5 = (landmarks[inds[4]].x, landmarks[inds[4]].y)
        p6 = (landmarks[inds[5]].x, landmarks[inds[5]].y)
        v1, v2 = _dist(p2, p6), _dist(p3, p5)
        h = _dist(p1, p4)
        return (v1 + v2) / (2.0 * h) if h > 0 else 0.0
    left_ear = ear((33, 160, 158, 133, 153, 144))
    right_ear = ear((263, 387, 385, 362, 380, 373))
    ear_avg = (left_ear + right_ear) / 2.0

    # Brow-to-lid distance (left and right)
    def brow_lid(brow_i, lid_i):
        return _dist(
            (landmarks[brow_i].x, landmarks[brow_i].y),
            (landmarks[lid_i].x, landmarks[lid_i].y),
        )
    brow_left = brow_lid(70, 160)
    brow_right = brow_lid(336, 362)

    # Mouth height/width ratio
    w = _dist((landmarks[78].x, landmarks[78].y), (landmarks[308].x, landmarks[308].y))
    mouth_ratio = _dist((landmarks[13].x, landmarks[13].y), (landmarks[14].x, landmarks[14].y)) / w if w > 0 else 0.2

    # Mouth center Y (for "weird lift" – lower y = higher on face; lift = mouth moves up)
    mouth_center_y = (landmarks[13].y + landmarks[14].y) / 2.0

    # Contraction (mean nose-to-points distance)
    nose = (landmarks[1].x, landmarks[1].y)
    contraction = sum(
        _dist(nose, (landmarks[i].x, landmarks[i].y)) for i in (234, 454, 10, 152)
    ) / 4.0

    return {
        "ear": ear_avg,
        "brow_left": brow_left,
        "brow_right": brow_right,
        "mouth_ratio": mouth_ratio,
        "mouth_center_y": mouth_center_y,
        "contraction": contraction,
    }
