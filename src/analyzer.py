"""Face detection and squint analysis using MediaPipe Face Landmarker (tasks API)."""
import cv2
import numpy as np
from typing import NamedTuple

from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, FaceLandmarkerResult
from mediapipe.tasks.python.vision.core import vision_task_running_mode as running_mode_lib
from mediapipe.tasks.python.core import base_options as base_options_lib
from mediapipe.tasks.python.vision.core import image as image_lib

from .squint_score import SquintResult, compute_squint_score
from .model_loader import ensure_face_landmarker_model


class AnalysisResult(NamedTuple):
    success: bool
    num_faces: int
    squint_result: SquintResult | None
    landmarks_list: list | None


_landmarker_cache: FaceLandmarker | None = None


def _get_landmarker() -> FaceLandmarker:
    global _landmarker_cache
    if _landmarker_cache is None:
        model_path = ensure_face_landmarker_model()
        base_options = base_options_lib.BaseOptions(model_asset_path=str(model_path))
        options = FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=running_mode_lib.VisionTaskRunningMode.IMAGE,
            num_faces=4,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        _landmarker_cache = FaceLandmarker.create_from_options(options)
    return _landmarker_cache


def analyze_frame(rgb_frame: np.ndarray) -> AnalysisResult:
    """
    Run MediaPipe Face Landmarker on an RGB frame (H, W, 3) uint8.
    Returns AnalysisResult. If exactly one face: squint_result set.
    """
    if not rgb_frame.flags.c_contiguous:
        rgb_frame = np.ascontiguousarray(rgb_frame)
    mp_image = image_lib.Image(image_format=image_lib.ImageFormat.SRGB, data=rgb_frame)
    landmarker = _get_landmarker()
    result = landmarker.detect(mp_image)
    face_landmarks = result.face_landmarks
    if not face_landmarks:
        return AnalysisResult(success=False, num_faces=0, squint_result=None, landmarks_list=None)
    if len(face_landmarks) != 1:
        return AnalysisResult(
            success=False,
            num_faces=len(face_landmarks),
            squint_result=None,
            landmarks_list=[[p for p in face] for face in face_landmarks],
        )
    landmarks = list(face_landmarks[0])
    squint = compute_squint_score(landmarks)
    return AnalysisResult(
        success=True,
        num_faces=1,
        squint_result=squint,
        landmarks_list=[landmarks],
    )


def analyze_frame_bgr(bgr_frame: np.ndarray) -> AnalysisResult:
    """Convert BGR (OpenCV) to RGB and run analyze_frame."""
    rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    return analyze_frame(rgb)
