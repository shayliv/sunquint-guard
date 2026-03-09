"""
Compute a 0-100 score from MediaPipe face landmarks.
Score = eye squeezing + concentration (furrowed brows) + mouth weird lift. Smiles ignored.
- 0 = relaxed (eyes, brows, mouth at rest)
- 100 = strong squeeze + concentration + any mouth lift (e.g. lip tension / weird lift)

Signals: (1) eyes more closed than baseline, (2) brows furrowed, (3) mouth lifted above baseline.
"""
import math
from dataclasses import dataclass
from typing import Sequence

# MediaPipe Face Mesh (468 landmarks) indices
LEFT_EYE_INDICES = (33, 160, 158, 133, 153, 144)
RIGHT_EYE_INDICES = (263, 387, 385, 362, 380, 373)
# Eyebrow-to-lid vertical distance (brow 70/336, lid 160/362)
# Mouth: upper 13, lower 14, corners 78, 308


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _eye_aspect_ratio(landmarks: list, indices: tuple[int, ...]) -> float:
    """EAR = (|p2-p6| + |p3-p5|) / (2*|p1-p4|). Lower = more closed; used for deviation from neutral."""
    p1 = (landmarks[indices[0]].x, landmarks[indices[0]].y)
    p2 = (landmarks[indices[1]].x, landmarks[indices[1]].y)
    p3 = (landmarks[indices[2]].x, landmarks[indices[2]].y)
    p4 = (landmarks[indices[3]].x, landmarks[indices[3]].y)
    p5 = (landmarks[indices[4]].x, landmarks[indices[4]].y)
    p6 = (landmarks[indices[5]].x, landmarks[indices[5]].y)
    v1 = _dist(p2, p6)
    v2 = _dist(p3, p5)
    h = _dist(p1, p4)
    if h <= 0:
        return 0.0
    return (v1 + v2) / (2.0 * h)


# Default neutral baselines when no user baseline is set (generic fallbacks)
DEFAULT_EAR = 0.26
DEFAULT_BROW_LID = 0.05
DEFAULT_MOUTH_RATIO = 0.20
DEFAULT_MOUTH_CENTER_Y = 0.5
DEFAULT_CONTRACTION_LO = 0.25


def _brow_furrow(landmarks: list, brow_idx: int, lid_idx: int, neutral: float) -> float:
    """Only furrowed brows (closer to lid than baseline) count. Raised brows = 0."""
    brow = (landmarks[brow_idx].x, landmarks[brow_idx].y)
    lid = (landmarks[lid_idx].x, landmarks[lid_idx].y)
    d = _dist(brow, lid)
    if d >= neutral:
        return 0.0
    # Scale so strong furrow ~100, light furrow ~30–50 (smooth gradient)
    return min(100.0, (neutral - d) / 0.025 * 100)


def _mouth_lift(landmarks: list, baseline_mouth_y: float) -> float:
    """Mouth lifted above baseline (e.g. lip tension / weird lift) can boost score. Lower y = higher on face."""
    mouth_y = (landmarks[13].y + landmarks[14].y) / 2.0
    if mouth_y >= baseline_mouth_y:
        return 0.0
    lift = baseline_mouth_y - mouth_y
    return min(100.0, lift / 0.028 * 100)


def _mouth_activity(landmarks: list, mouth_neutral: float) -> float:
    """Not used for score (smiles ignored). Kept for API."""
    upper = (landmarks[13].x, landmarks[13].y)
    lower = (landmarks[14].x, landmarks[14].y)
    left = (landmarks[78].x, landmarks[78].y)
    right = (landmarks[308].x, landmarks[308].y)
    width = _dist(left, right)
    if width <= 0:
        return 0.0
    ratio = _dist(upper, lower) / width
    dev = abs(ratio - mouth_neutral)
    return min(100.0, dev / 0.15 * 100)


def _contraction_score(landmarks: list, contraction_lo: float) -> float:
    """Not used for score. Kept for API."""
    nose = (landmarks[1].x, landmarks[1].y)
    total = 0.0
    for i in (234, 454, 10, 152):
        total += _dist(nose, (landmarks[i].x, landmarks[i].y))
    mean_d = total / 4.0
    if mean_d >= contraction_lo:
        return 0.0
    return min(100.0, (contraction_lo - mean_d) / 0.12 * 100)


@dataclass
class SquintResult:
    score: int  # 0-100
    mood: str
    eye_component: float
    brow_component: float
    mouth_component: float
    contraction_component: float


def _ear_squeeze_component(ear: float, ear_neutral: float) -> float:
    """Only eyes more closed than baseline count (squeeze). Wide eyes = 0."""
    if ear >= ear_neutral:
        return 0.0
    # Scale so strong squeeze ~100, light squeeze ~30–50 (smooth gradient)
    return min(100.0, (ear_neutral - ear) / 0.10 * 100)


def compute_squint_score(landmarks: list, baseline: dict[str, float] | None = None) -> SquintResult:
    """
    Score (0-100) = eye squeeze + brow furrow + mouth lift. Smiles etc. ignored.
    If baseline is None, loads from data/baseline.json; if missing, uses default neutrals.
    Weights: eyes 60%, brows 25%, mouth lift 15%.
    """
    if baseline is None:
        try:
            from .baseline import load_baseline
            baseline = load_baseline()
        except ImportError:
            from src.baseline import load_baseline
            baseline = load_baseline()
    if baseline is None:
        ear_neutral = DEFAULT_EAR
        brow_left_neutral = brow_right_neutral = DEFAULT_BROW_LID
        mouth_neutral = DEFAULT_MOUTH_RATIO
        mouth_center_y = None  # no mouth-lift boost until user re-sets baseline
        contraction_lo = DEFAULT_CONTRACTION_LO
    else:
        ear_neutral = baseline["ear"]
        brow_left_neutral = baseline["brow_left"]
        brow_right_neutral = baseline["brow_right"]
        mouth_neutral = baseline["mouth_ratio"]
        mouth_center_y = baseline.get("mouth_center_y")
        contraction_lo = baseline["contraction"]

    ear_left = _eye_aspect_ratio(landmarks, LEFT_EYE_INDICES)
    ear_right = _eye_aspect_ratio(landmarks, RIGHT_EYE_INDICES)
    ear_avg = (ear_left + ear_right) / 2.0
    eye_c = _ear_squeeze_component(ear_avg, ear_neutral)

    brow_left = _brow_furrow(landmarks, 70, 160, brow_left_neutral)
    brow_right = _brow_furrow(landmarks, 336, 362, brow_right_neutral)
    brow_c = (brow_left + brow_right) / 2.0

    if mouth_center_y is not None:
        mouth_lift_c = _mouth_lift(landmarks, mouth_center_y)
        raw = eye_c * 0.55 + brow_c * 0.25 + mouth_lift_c * 0.20
    else:
        mouth_lift_c = 0.0
        raw = eye_c * 0.70 + brow_c * 0.30
    mouth_c = _mouth_activity(landmarks, mouth_neutral)
    contract_c = _contraction_score(landmarks, contraction_lo)
    # Rescale: raw ~48 → ~77; 100 only for strong focus (divisor 62)
    score = max(0, min(100, int(round(raw * 100 / 62))))

    if score <= 15:
        mood = "Resting"
    elif score <= 40:
        mood = "Slight focus"
    elif score <= 65:
        mood = "Concentrated"
    elif score <= 85:
        mood = "Squeezed / focused"
    else:
        mood = "Strong squeeze + concentration"

    return SquintResult(
        score=score,
        mood=mood,
        eye_component=eye_c,
        brow_component=brow_c,
        mouth_component=mouth_lift_c,
        contraction_component=contract_c,
    )

