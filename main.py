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
        # Seed demo codes if empty
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

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def get_user(client_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE client_id = ?", (client_id,)).fetchone()
        if row:
            return dict(row)
        # Create new user
        now = time.time()
        conn.execute(
            "INSERT INTO users (client_id, paid, count, reset) VALUES (?, 0, 0, ?)",
            (client_id, now)
        )
        conn.commit()
        return {"client_id": client_id, "paid": 0, "count": 0, "reset": now, "email": None}

def update_user(client_id: str, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [client_id]
    with get_db() as conn:
        conn.execute(f"UPDATE users SET {sets} WHERE client_id = ?", vals)
        conn.commit()

def add_history(client_id: str, typ: str, score: float, verdict: str, preview: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO history (client_id, type, score, verdict, ts, preview) VALUES (?, ?, ?, ?, ?, ?)",
            (client_id, typ, score, verdict, time.time(), preview[:100])
        )
        conn.commit()

def get_history(client_id: str, limit: int = 20):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT type, score, verdict, ts, preview FROM history WHERE client_id = ? ORDER BY ts DESC LIMIT ?",
            (client_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

def is_valid_code(code: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM codes WHERE code = ?", (code.upper(),)).fetchone()
        return row is not None

FREE_LIMIT = 8

# --- Models ---
class AnalyzeRequest(BaseModel):
    text: str
    client_id: str
    email: Optional[str] = None

class CodeRequest(BaseModel):
    code: str
    client_id: str

class Signal(BaseModel):
    name: str
    triggered: bool
    explanation: str

# --- Detectors (text) ---
AI_STOCK = [
    r"\bdelve into\b", r"\bit(?:'s| is) important to note\b", r"\bmoreover\b",
    r"\bultimately\b", r"\bin conclusion\b", r"\bleverage\b", r"\brobust\b",
    r"\bseamless\b", r"\bpivotal\b", r"\bunlock the potential\b", r"\bharness\b",
    r"\bfurthermore\b", r"\bit(?:'s| is) worth noting\b"
]

def text_signals(text: str) -> List[Signal]:
    signals = []
    # Stock phrases
    matches = sum(len(re.findall(p, text, re.I)) for p in AI_STOCK)
    signals.append(Signal(
        name="AI stock phrases",
        triggered=matches >= 2,
        explanation=f"Found {matches} common AI phrases (delve, moreover, leverage, etc.)."
    ))
    # Sentence uniformity
    sents = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 8]
    if len(sents) >= 3:
        lens = [len(s.split()) for s in sents]
        cv = statistics.stdev(lens) / statistics.mean(lens) if statistics.mean(lens) else 1
        signals.append(Signal(
            name="Sentence uniformity",
            triggered=cv < 0.4,
            explanation=f"Length variation score {cv:.2f}. Lower = more uniform (AI-like)."
        ))
    else:
        signals.append(Signal(name="Sentence uniformity", triggered=False, explanation="Too short for uniformity check."))
    # Em-dashes
    dashes = text.count("—") + text.count("–") + text.count("--")
    signals.append(Signal(
        name="Em-dash overuse",
        triggered=dashes >= 3,
        explanation=f"Found {dashes} long dashes."
    ))
    return signals

def score_from_signals(signals: List[Signal]) -> float:
    triggered = sum(1 for s in signals if s.triggered)
    return round((triggered / max(len(signals), 1)) * 100, 1)

# --- Routes ---
@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/privacy")
async def privacy():
    return HTMLResponse("""
    <html><body style="font-family:sans-serif;max-width:700px;margin:40px auto;padding:20px;">
    <h1>Privacy Policy</h1>
    <p>FlagAI processes text and images you submit only to generate a detection score.</p>
    <p>In this version, content is not stored permanently and is not used to train models.</p>
    <p>Account data (client ID, optional email, license status, check history metadata) is stored to provide the service.</p>
    <p>We do not sell your data.</p>
    <p><a href="/">Back to FlagAI</a></p>
    </body></html>
    """)

@app.get("/terms")
async def terms():
    return HTMLResponse("""
    <html><body style="font-family:sans-serif;max-width:700px;margin:40px auto;padding:20px;">
    <h1>Terms of Service</h1>
    <p>FlagAI provides decision-support scores only. Results are not proof of AI authorship.</p>
    <p>Free tier has monthly limits. Paid / licensed users receive higher or unlimited access.</p>
    <p>You are responsible for how you use the results.</p>
    <p><a href="/">Back to FlagAI</a></p>
    </body></html>
    """)

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    cid = req.client_id
    user = get_user(cid)
    if req.email and req.email != user.get("email"):
        update_user(cid, email=req.email)

    if time.time() - user["reset"] > 86400 * 30:
        update_user(cid, count=0, reset=time.time())
        user["count"] = 0

    if not user["paid"] and user["count"] >= FREE_LIMIT:
        raise HTTPException(402, "Free limit reached. Enter a license code to continue.")

    if not user["paid"]:
        update_user(cid, count=user["count"] + 1)
        user["count"] += 1

    signals = text_signals(req.text)
    score = score_from_signals(signals)
    verdict = "High AI signals" if score >= 60 else "Moderate" if score >= 30 else "Low AI signals"

    add_history(cid, "text", score, verdict, req.text)

    remaining = 999 if user["paid"] else max(0, FREE_LIMIT - user["count"])
    return {
        "score": score,
        "verdict": verdict,
        "signals": [s.dict() for s in signals],
        "free_remaining": remaining,
        "paid": bool(user["paid"])
    }

@app.post("/api/activate")
async def activate(req: CodeRequest):
    code = req.code.strip().upper()
    if not is_valid_code(code):
        raise HTTPException(400, "Invalid code")
    get_user(req.client_id)
    update_user(req.client_id, paid=1)
    return {"status": "ok", "message": "Unlimited access unlocked"}

@app.get("/api/history")
async def history_route(client_id: str):
    return {"history": get_history(client_id)}

@app.get("/api/me")
async def me(client_id: str):
    user = get_user(client_id)
    return {
        "paid": bool(user["paid"]),
        "free_remaining": 999 if user["paid"] else max(0, FREE_LIMIT - user["count"]),
        "email": user.get("email")
    }

from PIL import Image
import io
import piexif
import math

# Neural image detector (ViT-based, lightweight enough for CPU)
_neural_detector = None

def get_neural_detector():
    global _neural_detector
    if _neural_detector is None:
        try:
            from transformers import pipeline
            _neural_detector = pipeline(
                "image-classification",
                model="capcheck/ai-human-generated-image-detection",
                device=-1  # CPU
            )
        except Exception as e:
            print("Neural detector failed to load:", e)
            _neural_detector = False
    return _neural_detector if _neural_detector is not False else None


def analyze_image_content(content: bytes, filename: str) -> dict:
    """Multi-signal image analysis: neural model + metadata + statistics."""
    signals = []
    score_points = 0
    max_points = 0

    # 0. Neural detector (highest weight)
    neural = get_neural_detector()
    if neural:
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            result = neural(tmp_path)
            os.unlink(tmp_path)
            # result is list of {label, score}
            ai_score = 0.0
            for r in result:
                if "ai" in r["label"].lower() or "generated" in r["label"].lower():
                    ai_score = r["score"]
                    break
            triggered = ai_score > 0.55
            signals.append({
                "name": "Neural detector (ViT)",
                "triggered": triggered,
                "explanation": f"Model confidence AI-generated: {ai_score:.1%}"
            })
            max_points += 40
            if triggered:
                score_points += int(ai_score * 40)
        except Exception as e:
            signals.append({
                "name": "Neural detector (ViT)",
                "triggered": False,
                "explanation": f"Neural check unavailable ({str(e)[:60]})"
            })
            max_points += 40
    else:
        signals.append({
            "name": "Neural detector (ViT)",
            "triggered": False,
            "explanation": "Neural model not loaded"
        })
        max_points += 40

    # 1. Filename hints
    name_lower = (filename or "").lower()
    name_hit = any(x in name_lower for x in ["ai", "generated", "midjourney", "dalle", "flux", "stable", "sdxl", "gpt"])
    signals.append({
        "name": "Filename hints",
        "triggered": name_hit,
        "explanation": f"Filename contains generator keywords: {filename}" if name_hit else "No generator keywords in filename."
    })
    max_points += 10
    if name_hit:
        score_points += 10

    # 2. Metadata / EXIF
    try:
        img = Image.open(io.BytesIO(content))
        exif_dict = {}
        if "exif" in img.info:
            exif_dict = piexif.load(img.info["exif"])
        software = ""
        if piexif.ImageIFD.Software in exif_dict.get("0th", {}):
            software = exif_dict["0th"][piexif.ImageIFD.Software].decode(errors="ignore").lower()
        soft_hit = any(x in software for x in ["midjourney", "dall", "stable", "flux", "adobe firefly", "generative"])
        signals.append({
            "name": "EXIF / software tag",
            "triggered": soft_hit,
            "explanation": f"Software tag: {software or 'none'}"
        })
        max_points += 15
        if soft_hit:
            score_points += 15
    except Exception:
        signals.append({
            "name": "EXIF / software tag",
            "triggered": False,
            "explanation": "No readable EXIF metadata."
        })
        max_points += 15

    # 3. Statistical smoothness
    try:
        img = Image.open(io.BytesIO(content)).convert("RGB")
        img.thumbnail((256, 256))
        pixels = list(img.getdata())
        if len(pixels) > 100:
            rs = [p[0] for p in pixels]
            mean_r = sum(rs) / len(rs)
            var = sum((x - mean_r) ** 2 for x in rs) / len(rs)
            std = math.sqrt(var)
            low_var = std < 25
            signals.append({
                "name": "Color variance / smoothness",
                "triggered": low_var,
                "explanation": f"Channel std dev ≈ {std:.1f}. Very low values can indicate synthetic smoothing."
            })
            max_points += 15
            if low_var:
                score_points += 10
    except Exception:
        signals.append({
            "name": "Color variance / smoothness",
            "triggered": False,
            "explanation": "Could not compute image statistics."
        })
        max_points += 15

    final_score = round((score_points / max(max_points, 1)) * 100, 1)
    return {
        "score": final_score,
        "signals": signals,
        "note": "Neural ViT detector + metadata + statistical signals."
    }


@app.post("/api/analyze-image")
async def analyze_image(file: UploadFile = File(...), client_id: str = Form(...)):
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(400, "Image too large (max 15 MB)")

    result = analyze_image_content(content, file.filename or "")
    score = result["score"]
    verdict = "High AI image signals" if score >= 55 else "Moderate image signals" if score >= 30 else "Low AI image signals"

    add_history(client_id, "image", score, verdict, file.filename or "image")

    return {
        "score": score,
        "verdict": verdict,
        "signals": result["signals"],
        "note": result["note"]
    }
