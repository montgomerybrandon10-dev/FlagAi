# FlagAI — Solid Consumer Version

Text + image AI signal checker with neural detector, license codes, and SQLite persistence.

## Run locally
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Deploy

### Railway (recommended)
1. Push this folder to GitHub
2. New project → Deploy from GitHub repo
3. Railway will detect `railway.toml` and `Procfile`
4. Deploy. You’ll get a public URL.

### Render
1. New Web Service → connect repo
2. Use the settings in `render.yaml` or set:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Demo license codes
- FLAG-DEMO-2026
- FLAG-TEST-1234
- FLAG-YEAR-9K2M

## Storage
SQLite database is created automatically at `data/flagai.db`.
On Railway/Render, add a volume mounted at `/app/data` if you want the DB to survive redeploys (optional for early testing).

## Features
- Text multi-signal analysis
- Image analysis with neural ViT detector + metadata + statistics
- Free tier + license code unlock
- Check history
- Privacy & Terms pages
- PWA installable
