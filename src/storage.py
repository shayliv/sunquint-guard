"""Persist squint scores to SQLite and optional human-readable log."""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import config from parent so storage can be used from project root or as package
try:
    import config
except ImportError:
    from pathlib import Path as _P
    _root = _P(__file__).resolve().parent.parent
    import sys
    sys.path.insert(0, str(_root))
    import config


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            score INTEGER NOT NULL,
            mood TEXT NOT NULL,
            hour_of_day INTEGER,
            snapshot_path TEXT
        )
    """)
    conn.commit()
    # Add snapshot_path column if table existed from before
    try:
        conn.execute("ALTER TABLE scores ADD COLUMN snapshot_path TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    finally:
        conn.close()


def append_score(
    score: int,
    mood: str,
    hour_of_day: Optional[int] = None,
    snapshot_path: Optional[str] = None,
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_connection()
    conn.execute(
        "INSERT INTO scores (ts, score, mood, hour_of_day, snapshot_path) VALUES (?, ?, ?, ?, ?)",
        (ts, score, mood, hour_of_day, snapshot_path),
    )
    conn.commit()
    conn.close()
    # Human-readable log line
    log_line = f"{ts}\nScore: {score}\nMood: {mood}\n"
    with open(config.LOG_FILE, "a") as f:
        f.write(log_line)


def get_scores(from_ts: Optional[str] = None, to_ts: Optional[str] = None) -> list[dict]:
    conn = get_connection()
    q = "SELECT id, ts, score, mood, hour_of_day, snapshot_path FROM scores WHERE 1=1"
    params = []
    if from_ts:
        q += " AND ts >= ?"
        params.append(from_ts)
    if to_ts:
        q += " AND ts <= ?"
        params.append(to_ts)
    q += " ORDER BY ts ASC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_scores_below(threshold: int) -> int:
    """Delete all score rows with score < threshold. Removes snapshot image files from disk.
    Returns the number of rows deleted."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, snapshot_path FROM scores WHERE score < ?",
        (threshold,),
    ).fetchall()
    deleted = 0
    for row in rows:
        snapshot_path = row["snapshot_path"] if row["snapshot_path"] else None
        if snapshot_path:
            path = config.SNAPSHOTS_DIR / snapshot_path
            if path.is_file():
                path.unlink()
        conn.execute("DELETE FROM scores WHERE id = ?", (row["id"],))
        deleted += 1
    conn.commit()
    conn.close()
    return deleted


def get_stats_for_date(date_str: str) -> dict:
    """date_str: YYYY-MM-DD. Returns hourly averages, peak moments, etc."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, ts, score, mood, hour_of_day, snapshot_path FROM scores WHERE date(ts) = ? ORDER BY ts ASC",
        (date_str,),
    ).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]
    if not rows:
        return {"hourly_avg": {}, "peaks": [], "average_score": 0, "count": 0}
    hourly: dict[int, list[int]] = {}
    for r in rows:
        h = r.get("hour_of_day")
        if h is None and r.get("ts"):
            try:
                h = int(r["ts"].split()[1][:2])
            except (IndexError, ValueError):
                h = 0
        hourly.setdefault(h or 0, []).append(r["score"])
    hourly_avg = {h: sum(s) / len(s) for h, s in hourly.items()}
    sorted_by_score = sorted(rows, key=lambda x: x["score"], reverse=True)
    peaks = sorted_by_score[:5]
    return {
        "hourly_avg": hourly_avg,
        "peaks": peaks,
        "average_score": sum(r["score"] for r in rows) / len(rows),
        "count": len(rows),
    }
