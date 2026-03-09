"""Background monitor: listen 20s, pick best frame, then log/notify every 3-5 min."""
import random
import sys
import tempfile
import time
from pathlib import Path

# Allow running from project root: python -m src.monitor or python src/monitor.py
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import config
from .capture import capture_frames_for_duration
from .analyzer import analyze_frame_bgr
from .storage import init_db, append_score
from .notify import notify_squint_warning, notify_face_detected


def run_once() -> None:
    frames, elapsed = capture_frames_for_duration(
        config.LISTEN_DURATION_SEC,
        config.LISTEN_SAMPLE_INTERVAL_SEC,
    )
    if not frames:
        print("Capture failed (no frames)", flush=True)
        return
    # Find the frame with the highest squint score (single face only)
    best_frame = None
    best_score = -1
    best_result = None
    for frame in frames:
        result = analyze_frame_bgr(frame)
        if not result.success or result.squint_result is None:
            continue
        score = result.squint_result.score
        if score > best_score:
            best_score = score
            best_frame = frame
            best_result = result
    if best_frame is None or best_result is None:
        print(f"No single face in any of {len(frames)} frames (listened {elapsed:.1f}s)", flush=True)
        return
    frame = best_frame
    score = best_score
    result = best_result
    mood = result.squint_result.mood
    hour = time.localtime().tm_hour
    image_path: Path | None = None
    try:
        # Save snapshot only when score is above threshold
        snapshot_path_for_db = None
        if score > config.SNAPSHOT_SCORE_THRESHOLD:
            snapshot_filename = time.strftime("%Y-%m-%d_%H-%M-%S") + ".jpg"
            snapshot_path = config.SNAPSHOTS_DIR / snapshot_filename
            cv2.imwrite(str(snapshot_path), frame)
            snapshot_path_for_db = snapshot_filename
        append_score(
            score=score,
            mood=mood,
            hour_of_day=hour,
            snapshot_path=snapshot_path_for_db,
        )
        # Notification with best frame as image
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        image_path = Path(tmp.name)
        cv2.imwrite(str(image_path), frame)
        notify_face_detected(score=score, image_path=image_path)
        if score > config.SQUINT_WARNING_THRESHOLD:
            notify_squint_warning()
    finally:
        if image_path and config.DISCARD_IMAGES_AFTER_USE and image_path.exists():
            image_path.unlink(missing_ok=True)


def main() -> None:
    init_db()
    print(
        f"Developer Squint Monitor running (listen {config.LISTEN_DURATION_SEC}s, then 3-5 min interval). Ctrl+C to stop.",
        flush=True,
    )
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"Error: {e}", flush=True)
        interval = random.randint(config.CAPTURE_INTERVAL_MIN, config.CAPTURE_INTERVAL_MAX)
        time.sleep(interval)


if __name__ == "__main__":
    main()
