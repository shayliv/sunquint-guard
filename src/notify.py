"""macOS notifications: text and image popup via terminal-notifier."""
import subprocess
from pathlib import Path
from typing import Optional


def _run_notifier(
    title: str,
    message: str,
    content_image: Optional[Path] = None,
) -> bool:
    """Send macOS notification. Uses terminal-notifier (brew install terminal-notifier)."""
    cmd = [
        "terminal-notifier",
        "-title", title,
        "-message", message,
    ]
    if content_image is not None and content_image.exists():
        cmd.extend(["-contentImage", str(content_image.resolve())])
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def notify_squint_warning() -> None:
    """Show notice when non-resting score exceeds threshold."""
    _run_notifier(
        "Developer Squint Monitor",
        "Notice: Strong non-resting expression detected (e.g. squeezed eyes, active face).",
    )


def notify_face_detected(score: int, image_path: Optional[Path] = None) -> None:
    """Show notification every time a face is caught, with optional image."""
    _run_notifier(
        "Developer Squint Monitor",
        f"Face detected – Score: {score} (0=resting, 100=active/weird)",
        content_image=image_path,
    )
