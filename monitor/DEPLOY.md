# Deployment Guide

## Overview

The Dilution Monitor is a FastAPI + React application that can be deployed as a single web service. In production, FastAPI serves both the API and the built React frontend.

## Architecture

```
Client Request → FastAPI
                   ├─ /api/* → API endpoints
                   └─ /* → React SPA (from /frontend/dist)
```

## Deploy to Render

### Prerequisites

- GitHub account with your code pushed
- Render account (free tier available)
- FMP API key from https://financialmodelingprep.com/developer
- Anthropic API key from https://console.anthropic.com

### Steps

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Connect to Render**
   - Go to https://render.com
   - Click "New" → "Web Service"
   - Connect your GitHub repo
   - Render auto-detects `render.yaml`

3. **Configure Environment Variables**

   In the Render dashboard, add these environment variables:

   | Variable | Value |
   |----------|-------|
   | `FMP_API_KEY` | Your Financial Modeling Prep API key |
   | `ANTHROPIC_API_KEY` | Your Anthropic API key |
   | `EDGAR_USER_AGENT` | `DilutionMonitor your-email@example.com` |

4. **Deploy**

   Click "Create Web Service". Render will:
   - Install Python dependencies
   - Install Node dependencies
   - Build the React frontend (`npm run build`)
   - Start the FastAPI server

   First deploy takes ~5-10 minutes.

5. **Access Your App**

   Once deployed, access at: `https://your-app-name.onrender.com`

### Limitations of Free Tier

- **Ephemeral storage**: Database resets on every deploy
- **512MB RAM**: Limit backfill to 500-1000 companies
- **Spin down**: Server sleeps after 15 min inactivity (takes ~30s to wake)

For production use:
- Upgrade to paid Render plan ($7/mo for persistent disk)
- Use external PostgreSQL database
- Enable always-on instance

## Deploy to Railway

Railway is an alternative to Render with similar ease of deployment:

1. Push to GitHub
2. Go to https://railway.app
3. Create new project from GitHub repo
4. Railway auto-detects Python + Node
5. Add environment variables
6. Deploy

Railway automatically provisions a PostgreSQL database on paid plans.

## Deploy to Your Own Server

### Requirements

- Ubuntu 20.04+ or similar Linux distribution
- Python 3.12+
- Node.js 18+
- Nginx (for reverse proxy)
- Supervisor or systemd (for process management)

### Setup

```bash
# 1. Clone repo
git clone https://github.com/your-username/dilution-monitor.git
cd dilution-monitor/monitor

# 2. Build frontend
cd frontend
npm install
npm run build
cd ..

# 3. Set up Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
nano .env  # Add your API keys

# 5. Initialize database (optional: run backfill)
python -m backend.pipelines.backfill --quick --max-companies 500

# 6. Test the server
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Run with Gunicorn

```bash
gunicorn backend.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Nginx Configuration

Create `/etc/nginx/sites-available/dilution-monitor`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/dilution-monitor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Systemd Service

Create `/etc/systemd/system/dilution-monitor.service`:

```ini
[Unit]
Description=Dilution Monitor API
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/var/www/dilution-monitor/monitor
Environment="PATH=/var/www/dilution-monitor/monitor/venv/bin"
ExecStart=/var/www/dilution-monitor/monitor/venv/bin/gunicorn \
    backend.main:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable dilution-monitor
sudo systemctl start dilution-monitor
```

## Database Persistence

### SQLite (Default)

SQLite is fine for single-user or demo deployments. The database file is stored at `data/dilution_monitor.db`.

**On Render/Railway**: Mount a persistent disk and point `DB_PATH` to it.

### PostgreSQL (Production)

For multi-user production:

1. **Install PostgreSQL** or use a managed service (Render, Railway, AWS RDS)

2. **Update `backend/database.py`**:
   ```python
   engine = create_engine(
       os.getenv("DATABASE_URL", "sqlite:///data/dilution_monitor.db"),
       echo=False
   )
   ```

3. **Set `DATABASE_URL`** environment variable:
   ```
   postgresql://user:password@host:5432/dbname
   ```

4. **Migrate schema**: SQLAlchemy will auto-create tables on first run

## Monitoring & Logs

### Render
View logs in the Render dashboard under "Logs" tab.

### Your Server
```bash
# View logs
sudo journalctl -u dilution-monitor -f

# Check status
sudo systemctl status dilution-monitor
```

## Troubleshooting

### Build fails on Render

**Problem**: `npm run build` fails with out of memory error

**Solution**: Free tier has limited RAM. Try:
```bash
NODE_OPTIONS="--max-old-space-size=512" npm run build
```

Add to `render.yaml`:
```yaml
envVars:
  - key: NODE_OPTIONS
    value: "--max-old-space-size=512"
```

### React routes return 404

**Problem**: Direct navigation to `/company/TSLA` returns 404

**Solution**: Make sure the catch-all route in `backend/main.py` is defined AFTER all API routes. The order matters.

### Database resets on deploy

**Problem**: All data lost after Render redeploy

**Solution**: Mount a persistent disk in Render or use external PostgreSQL.

### API calls fail in production

**Problem**: Frontend shows "API error" or CORS issues

**Solution**: Check that `VITE_API_URL` is NOT set (should use relative URLs). In production, the API client defaults to `""` (same origin).

## Performance Tuning

### Backfill on Deploy

To auto-populate data on first deploy, add to `render.yaml`:

```yaml
buildCommand: |
  pip install -r requirements.txt
  cd frontend && npm install && npm run build && cd ..
  python -m backend.pipelines.backfill --quick --max-companies 500
```

**Warning**: This increases deploy time by 10-15 minutes.

### Caching

Add Redis for caching API responses:

```python
# backend/cache.py
import redis
r = redis.from_url(os.getenv("REDIS_URL"))
```

### Background Jobs

Use Celery + Redis for:
- Scheduled backfills (daily)
- Re-scoring (hourly)
- Email alerts

See full architecture in `ARCHITECTURE.md`.
