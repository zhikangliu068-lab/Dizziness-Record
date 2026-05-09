import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("dizziness_records.db").resolve()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER,
            location TEXT,
            actions TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def add_record(start_time: datetime, end_time: datetime = None, location: str = "",
               actions: list = None, notes: str = "") -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    duration = None
    if end_time:
        duration = int((end_time - start_time).total_seconds())

    cursor.execute("""
        INSERT INTO records (start_time, end_time, duration_seconds, location, actions, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        end_time.strftime("%Y-%m-%d %H:%M:%S") if end_time else None,
        duration,
        location,
        json.dumps(actions or [], ensure_ascii=False),
        notes
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def update_record(record_id: int, start_time: datetime, end_time: datetime,
                  location: str, actions: list, notes: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    duration = int((end_time - start_time).total_seconds())

    cursor.execute("""
        UPDATE records
        SET start_time = ?, end_time = ?, duration_seconds = ?, location = ?, actions = ?, notes = ?
        WHERE id = ?
    """, (
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        end_time.strftime("%Y-%m-%d %H:%M:%S"),
        duration,
        location,
        json.dumps(actions or [], ensure_ascii=False),
        notes,
        record_id
    ))
    conn.commit()
    conn.close()


def get_record(record_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM records WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_dict(row)


def get_all_records() -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM records ORDER BY start_time DESC")
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]


def get_records_by_date_range(start: datetime, end: datetime) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM records
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time DESC
    """, (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]


def delete_record(record_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def _row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "start_time": row[1],
        "end_time": row[2],
        "duration_seconds": row[3],
        "location": row[4] or "",
        "actions": json.loads(row[5]) if row[5] else [],
        "notes": row[6] or "",
        "created_at": row[7]
    }


def format_duration(seconds: int) -> str:
    if seconds is None:
        return "未结束"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}小时{minutes}分{sec}秒"
    elif minutes > 0:
        return f"{minutes}分{sec}秒"
    else:
        return f"{sec}秒"
