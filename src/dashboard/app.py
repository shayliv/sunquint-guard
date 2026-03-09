"""Flask dashboard: read-only API and single-page UI.

Author: Shay Livni (https://shaylivni.com)
Disclaimer: This app is for awareness only; not medical or ergonomic advice.
"""
import sys
import time
import cv2
import numpy as np
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context
import config
from src.storage import get_scores, get_stats_for_date
from src.analyzer import analyze_frame_bgr
from src.capture import capture_frame
from src.baseline import get_baseline_values_from_landmarks, save_baseline, load_baseline
from datetime import datetime

app = Flask(__name__, static_folder="static", static_url_path="")

# MJPEG boundary for live stream
MJPEG_BOUNDARY = "frame"


def _generate_live_frames():
    """Capture from webcam, analyze, draw overlay, yield JPEG frames. Releases camera on exit."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        # Minimal frame so browser gets valid MJPEG
        img = np.zeros((120, 320, 3), dtype=np.uint8)
        cv2.putText(img, "Camera not available", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        _, placeholder = cv2.imencode(".jpg", img)
        yield (b"--" + MJPEG_BOUNDARY.encode() + b"\r\nContent-Type: image/jpeg\r\n\r\n" + placeholder.tobytes() + b"\r\n")
        return
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            # Resize for faster analysis and smaller stream
            h, w = frame.shape[:2]
            if w > 640:
                frame = cv2.resize(frame, (640, int(h * 640 / w)), interpolation=cv2.INTER_AREA)
            result = analyze_frame_bgr(frame)
            # Store latest landmarks for "Set baseline" (use current frame when user clicks)
            if result.landmarks_list and len(result.landmarks_list) == 1:
                app.last_live_landmarks = result.landmarks_list[0]
                app.last_live_landmarks_ts = time.time()
            # Overlay: face count, score, mood
            face_text = f"Faces: {result.num_faces}"
            if result.success and result.squint_result:
                score_text = f"Score: {result.squint_result.score}"
                mood_text = result.squint_result.mood
                cv2.putText(frame, score_text, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, mood_text[:40], (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 200), 1)
            else:
                cv2.putText(frame, "No single face – move into frame (score = non-resting)", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)
            cv2.putText(frame, face_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            _, jpeg = cv2.imencode(".jpg", frame)
            yield (b"--" + MJPEG_BOUNDARY.encode() + b"\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
    finally:
        cap.release()


@app.route("/api/scores")
def api_scores():
    from_ts = request.args.get("from")
    to_ts = request.args.get("to")
    rows = get_scores(from_ts=from_ts, to_ts=to_ts)
    return jsonify(rows)


@app.route("/api/stats")
def api_stats():
    date_str = request.args.get("date")
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    stats = get_stats_for_date(date_str)
    return jsonify(stats)


@app.route("/api/report")
def api_report():
    """Daily grumpiness report: summary + optional export format (json or md)."""
    date_str = request.args.get("date")
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    fmt = request.args.get("format", "json")
    stats = get_stats_for_date(date_str)
    peaks = stats.get("peaks", [])
    hourly = stats.get("hourly_avg", {})
    worst_hour = max(hourly.items(), key=lambda x: x[1])[0] if hourly else None
    report = {
        "date": date_str,
        "samples": stats.get("count", 0),
        "average_score": round(stats.get("average_score", 0), 1),
        "peak_score": peaks[0]["score"] if peaks else None,
        "peak_time": peaks[0]["ts"] if peaks else None,
        "worst_hour": worst_hour,
        "peaks": peaks,
        "hourly_avg": hourly,
    }
    if fmt == "md":
        lines = [
            f"# Grumpiness Report – {date_str}",
            "",
            f"- **Samples:** {report['samples']}",
            f"- **Average score:** {report['average_score']}",
            f"- **Peak score:** {report['peak_score']} at {report['peak_time'] or 'N/A'}",
            f"- **Worst hour:** {report['worst_hour']}:00" if report['worst_hour'] is not None else "- **Worst hour:** N/A",
        ]
        lines.extend(["", "## Peak moments", ""])
        for p in report["peaks"]:
            lines.append(f"- {p['ts']} – Score: {p['score']} – {p.get('mood', '')}")
        from flask import Response
        return Response("\n".join(lines), mimetype="text/markdown")
    return jsonify(report)


@app.route("/api/baseline")
def api_baseline():
    """Return current resting baseline if set."""
    b = load_baseline()
    return jsonify(b if b else {})


@app.route("/api/baseline/set", methods=["POST", "GET"])
def api_baseline_set():
    """Use current face as resting baseline. Prefer last frame from live stream if recent; else capture one."""
    landmarks = None
    if getattr(app, "last_live_landmarks", None) and (time.time() - getattr(app, "last_live_landmarks_ts", 0)) < 10:
        landmarks = app.last_live_landmarks
    if landmarks is None:
        frame, _ = capture_frame(save_path=None)
        if frame is None:
            return jsonify({"ok": False, "error": "Could not capture from camera. Is the live view open? Try opening Live test first."}), 400
        result = analyze_frame_bgr(frame)
        if not result.success or not result.landmarks_list or len(result.landmarks_list) != 1:
            return jsonify({
                "ok": False,
                "error": f"Need exactly one face in frame (got {result.num_faces}). Look at the camera and try again.",
            }), 400
        landmarks = result.landmarks_list[0]
    baseline = get_baseline_values_from_landmarks(landmarks)
    save_baseline(baseline)
    return jsonify({"ok": True, "message": "Resting baseline set. Score will now use this as 0."})


@app.route("/api/live")
def api_live():
    """MJPEG stream: live camera with face count and squint score overlaid. For testing."""
    return Response(
        stream_with_context(_generate_live_frames()),
        mimetype=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
    )


@app.route("/live")
def live_page():
    return send_from_directory(app.static_folder, "live.html")


@app.route("/api/snapshots/<path:filename>")
def api_snapshot(filename):
    """Serve a saved snapshot image by filename (e.g. 2025-03-09_14-30-00.jpg)."""
    return send_from_directory(config.SNAPSHOTS_DIR, filename)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def main():
    app.run(host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
