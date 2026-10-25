"""
FlagAI Solid Consumer Version
- Text + image checking
- Simple accounts (client ID + optional email)
- Check history
- License codes + free tier
- Privacy & terms
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import re
import statistics
from collections import defaultdict
import time
import hashlib
import json
from pathlib import Path
from typing import List, Optional

app = FastAPI(title="FlagAI", version="1.0-consumer")

app.mount("/static", StaticFiles(directory="static"), name="static")

import sqlite3
from contextlib import contextmanager

# SQLite storage
DB_PATH = Path("data/flagai.db")
DB_PATH.parent.mkdir(exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                client_id TEXT PRIMARY KEY,
                paid INTEGER DEFAULT 0,
                count INTEGER DEFAULT 0,
                reset REAL,
                email TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                type TEXT,
                score REAL,
                verdict TEXT,
                ts REAL,
                preview TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS codes (
                code TEXT PRIMARY KEY,
                type TEXT
            )
        """)
        cur = conn.execute("SELECT COUNT(*) FROM codes")
        if cur.fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO codes (code, type) VALUES (?, ?)",
                [
                    ("FLAG-DEMO-2026", "lifetime"),
                    ("FLAG-TEST-1234", "lifetime"),
                    ("FLAG-YEAR-9K2M", "yearly"),
                ]
            )
        conn.commit()

init_db()

print("Core DB and app skeleton pushed — full detectors follow in next commit if needed")
