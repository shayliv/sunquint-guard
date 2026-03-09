"""Capture a single frame from the built-in webcam."""
import tempfile
import time
from pathlib import Path
import cv2
import numpy as np

# Optional resize for faster processing (width)
CAPTURE_WIDTH = 640


# Discard this many frames after opening so the camera has time to expose (avoids black first frame)
WARMUP_FRAMES = 3


def capture_frame(save_path: Path | None = None) -> tuple[np.ndarray | None, Path | None]:
    """
    Open default camera, read one frame, release.
    Skips a few warmup frames so the first returned frame is not black.
    Returns (frame as BGR numpy array, path to saved image if save_path given).
    If capture fails, returns (None, None).
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None, None
    for _ in range(WARMUP_FRAMES):
        cap.read()  # throw away warmup frames
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None or frame.size == 0:
        return None, None
    # Resize for faster downstream processing
    h, w = frame.shape[:2]
    if w > CAPTURE_WIDTH:
        scale = CAPTURE_WIDTH / w
        frame = cv2.resize(frame, (CAPTURE_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
    out_path = None
    if save_path is not None:
        cv2.imwrite(str(save_path), frame)
        out_path = save_path
    return frame, out_path


def capture_frame_to_temp() -> tuple[np.ndarray | None, Path | None]:
    """
    Capture one frame and save to a temporary file. Returns (frame, path).
    Caller should delete the file when done if discard_images is enabled.
    """
    frame, _ = capture_frame(save_path=None)
    if frame is None:
        return None, None
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    path = Path(tmp.name)
    cv2.imwrite(str(path), frame)
    return frame, path


def capture_frames_for_duration(
    duration_sec: float,
    interval_sec: float,
) -> "tuple[list[np.ndarray], float]":
    """
    Open the camera and yield frames every interval_sec for up to duration_sec.
    Returns (list of BGR frames, actual elapsed time in seconds).
    Resizes frames to CAPTURE_WIDTH for consistency with single capture.
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return [], 0.0
    for _ in range(WARMUP_FRAMES):
        cap.read()
    frames = []
    start = time.monotonic()
    deadline = start + duration_sec
    while time.monotonic() < deadline:
        ret, frame = cap.read()
        if not ret or frame is None or frame.size == 0:
            break
        h, w = frame.shape[:2]
        if w > CAPTURE_WIDTH:
            scale = CAPTURE_WIDTH / w
            frame = cv2.resize(frame, (CAPTURE_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
        frames.append(frame)
        if time.monotonic() + interval_sec > deadline:
            break
        time.sleep(interval_sec)
    cap.release()
    elapsed = time.monotonic() - start
    return frames, elapsed
