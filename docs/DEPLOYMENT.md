# Deployment Guide

CarbonVerify is a full-stack application with three deployable components:

1. **Frontend** (React + Vite) → Static hosting (Vercel, Netlify, Cloudflare Pages)
2. **Backend** (FastAPI) → Container hosting (Railway, Render, Fly.io, AWS ECS, DigitalOcean App Platform)
3. **Infrastructure** (PostgreSQL + Redis) → Managed services or self-hosted

---

## Quick Decision Matrix

| If you want... | Use this setup |
|----------------|---------------|
| Easiest full-stack deploy | Railway (frontend + backend + DB in one platform) |
| Best frontend performance | Vercel frontend + Railway backend |
| Most control / lowest cost | AWS ECS + RDS + ElastiCache |
| Free tier everything | Render frontend + Render backend + Render PostgreSQL + Upstash Redis |

---

## Option A: Vercel (Frontend Only) + Railway (Backend + DB)

### 1. Deploy Frontend to Vercel

**Prerequisites:**
- Vercel account (free tier works)
- Git repository pushed to GitHub/GitLab/Bitbucket

**Steps:**

```bash
cd frontend

# Install Vercel CLI
npm i -g vercel

# Login and deploy
vercel --prod
```

**Or use the Vercel Dashboard:**
1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your Git repository
3. Set **Root Directory** to `frontend`
4. Set **Framework Preset** to `Vite`
5. Add environment variables:
   - `VITE_API_URL` = `https://your-backend-domain.com`
6. Deploy

**Required Environment Variables:**

| Variable | Example | Required |
|----------|---------|----------|
| `VITE_API_URL` | `https://api.carbonverify.io` | Yes |
| `VITE_WS_URL` | `wss://api.carbonverify.io` | No (defaults to API URL) |

**Important:** Vercel only hosts the frontend. The backend must be deployed separately.

### 2. Deploy Backend to Railway

**Prerequisites:**
- Railway account
- Backend pushed to Git

**Steps:**

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
cd backend
railway init

# Add PostgreSQL and Redis
railway add --database postgres
railway add --database redis

# Set environment variables
railway variables set ENVIRONMENT=production
railway variables set SECRET_KEY=$(openssl rand -hex 32)
railway variables set DATABASE_URL=${{Postgres.DATABASE_URL}}
railway variables set REDIS_URL=${{Redis.REDIS_URL}}
railway variables set CELERY_BROKER_URL=${{Redis.REDIS_URL}}
railway variables set CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}

# Deploy
railway up
```

**Required Environment Variables:**

| Variable | Source | Required |
|----------|--------|----------|
| `DATABASE_URL` | Railway PostgreSQL | Yes |
| `REDIS_URL` | Railway Redis | Yes |
| `SECRET_KEY` | Generate with `openssl rand -hex 32` | Yes |
| `S3_BUCKET_NAME` | AWS S3 bucket name | Yes (for file uploads) |
| `AWS_ACCESS_KEY_ID` | AWS IAM | Yes (for S3) |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM | Yes (for S3) |
| `AWS_REGION` | `us-east-1` | Yes |
| `FRONTEND_URL` | Your Vercel domain | Yes (for CORS) |
| `ENVIRONMENT` | `production` | Yes |
| `LOG_LEVEL` | `INFO` | No (defaults to INFO) |
| `ENCRYPTION_KEY_HEX` | Generate with Python `secrets.token_hex(32)` | Yes (for PII encryption) |
| `IOT_WEBHOOK_API_KEY` | Generate secure token | Yes (if using IoT) |
| `KIMI_API_KEY` | Moonshot AI API key | No (only for AI features) |

### 3. Connect Frontend to Backend

After both are deployed:
1. Copy the Railway backend URL (e.g., `https://carbonverify-production.up.railway.app`)
2. In Vercel dashboard, set `VITE_API_URL` to this URL
3. Redeploy frontend

---

## Option B: Render (Free Tier Friendly)

### Frontend (Static Site)

1. Create new **Static Site** on Render
2. Connect your GitHub repo
3. Set **Build Command**: `cd frontend && npm install && npm run build`
4. Set **Publish Directory**: `frontend/dist`
5. Add env var: `VITE_API_URL=https://your-backend.onrender.com`

### Backend (Web Service)

1. Create new **Web Service** on Render
2. Connect your GitHub repo
3. Set **Root Directory**: `backend`
4. Set **Build Command**: `pip install -r requirements.txt`
5. Set **Start Command**: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
6. Add all required environment variables
7. Create **PostgreSQL** and **Redis** instances on Render

### Worker (Background Jobs)

1. Create new **Background Worker** on Render
2. Same repo, root directory `backend`
3. Start Command: `celery -A app.tasks.celery_app worker --loglevel=info`
4. Same environment variables as backend

> **Graceful shutdown:** The app registers `worker_shutdown` signal handlers to close the persistent Playwright browser. Ensure your platform allows at least 10–15 seconds for cleanup before force-terminating the worker process.

### Cron Job (Scheduled Tasks)

1. Create **Cron Job** on Render
2. Start Command: `celery -A app.tasks.celery_app beat --loglevel=info`

---

## Option C: AWS (Production Scale)

### Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│  CloudFront │────▶│  S3 (frontend)  │     │   Route 53   │
│   (CDN)     │     │  (static files) │     │   (DNS)      │
└─────────────┘     └─────────────────┘     └──────────────┘
                            │
                            ▼
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│  API Gateway │────▶│  ECS Fargate    │────▶│  RDS         │
│              │     │  (FastAPI)      │     │  (PostgreSQL)│
└─────────────┘     └─────────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ ElastiCache  │
                     │   (Redis)    │
                     └──────────────┘
```

### Terraform/CDK (Infrastructure as Code)

See `infrastructure/terraform/` for Terraform templates.

---

## Option D: Self-Hosted (Docker Compose on VPS)

For full control, deploy to a VPS (DigitalOcean, Hetzner, Linode):

```bash
# On your server
git clone <repo>
cd carbonverify

# Create .env file
cp .env.example .env
# Edit .env with production values

# Start everything
docker-compose -f docker-compose.production.yml up -d
```

The production compose includes an nginx reverse proxy with CSP/HSTS headers and serves the built SPA directly; no separate Traefik/Caddy layer is required unless you want automatic HTTPS, in which case place it in front of nginx.

---

## Pre-Deployment Checklist

### Security
- [ ] `SECRET_KEY` is at least 32 random characters
- [ ] `ENCRYPTION_KEY_HEX` is a 64-character hex string (32 bytes)
- [ ] `IOT_WEBHOOK_API_KEY` is a secure random token
- [ ] `WHATSAPP_VERIFY_TOKEN` is set (if using WhatsApp bot)
- [ ] HTTPS enforced (handled by platform or reverse proxy)
- [ ] CORS `FRONTEND_URL` matches your actual domain
- [ ] `ENVIRONMENT=production` set
- [ ] `CLAMAV_HOST` / `CLAMAV_PORT` or `CLAMAV_SOCKET_PATH` configured (if using containerized scanning)

### Database
- [ ] PostgreSQL 15+ running and accessible
- [ ] Run `alembic upgrade head` to apply all migrations
- [ ] Enable automated backups (daily minimum)
- [ ] Set `statement_timeout=30000` in PostgreSQL

### Storage
- [ ] S3 bucket created with private ACL
- [ ] IAM user has minimal permissions (PutObject, GetObject only)
- [ ] Bucket CORS configured for your frontend domain

### Monitoring
- [ ] Prometheus `/metrics` endpoint accessible
- [ ] Logs aggregated (CloudWatch, Datadog, or Grafana)
- [ ] Alertmanager configured for critical alerts
- [ ] Health check endpoint (`/health/`) monitored

### Domain & SSL
- [ ] Domain DNS points to your platform
- [ ] SSL certificate auto-renews (Let's Encrypt or managed)
- [ ] `FRONTEND_URL` and API domain configured in CORS

---

## Environment Variable Reference

### Frontend (Vercel/Render/Netlify)

| Variable | Example | Purpose |
|----------|---------|---------|
| `VITE_API_URL` | `https://api.carbonverify.io` | Backend API base URL |
| `VITE_WS_URL` | `wss://api.carbonverify.io` | WebSocket URL |

### Backend (Railway/Render/AWS)

| Variable | Example | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `REDIS_URL` | `redis://...` | Redis connection |
| `SECRET_KEY` | `a1b2c3...` (64 hex chars) | JWT signing |
| `SECRET_KEY_PREVIOUS` | `x9y8z7...` | Previous JWT key (rotation) |
| `S3_BUCKET_NAME` | `carbonverify-uploads` | File storage bucket |
| `AWS_ACCESS_KEY_ID` | `AKIA...` | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | `...` | S3 credentials |
| `AWS_REGION` | `us-east-1` | S3 region |
| `FRONTEND_URL` | `https://carbonverify.io` | CORS allowed origin |
| `ENVIRONMENT` | `production` | App environment |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENCRYPTION_KEY_HEX` | `0000...` (64 hex chars) | PII encryption |
| `IOT_WEBHOOK_API_KEY` | `secure_token...` | IoT device auth |
| `WHATSAPP_VERIFY_TOKEN` | `verify_...` | Meta WhatsApp webhook verify token |
| `KIMI_API_KEY` | `sk-...` | Moonshot AI (optional) |
| `PROXY_URL` | `http://proxy:8080` | HTTP proxy for scrapers (optional) |
| `SCRAPER_FORCE_HEADLESS` | `true` | Force Playwright headless mode |
| `SCRAPER_USER_AGENTS` | `Mozilla/5.0...,Mozilla/5.0...` | Comma-separated UA rotation list |
| `CLAMAV_HOST` | `clamav` | ClamAV daemon hostname |
| `CLAMAV_PORT` | `3310` | ClamAV daemon port |
| `CLAMAV_SOCKET_PATH` | `/tmp/clamd.socket` | ClamAV Unix socket (alt to TCP) |
| `CELERY_BROKER_URL` | `redis://...` | Celery queue |
| `CELERY_RESULT_BACKEND` | `redis://...` | Celery results |
| `VERRA_API_KEY` | `...` | Verra registry API key |
| `GOLD_STANDARD_API_KEY` | `...` | Gold Standard registry API key |
| `KENYA_NATIONAL_REGISTRY_API_KEY` | `...` | Kenya National Carbon Registry API key |

---

## Troubleshooting

### CORS errors in browser
- Ensure `FRONTEND_URL` matches exactly (including `https://`)
- Check that `withCredentials: true` is set in frontend Axios config
- Verify backend sends `Access-Control-Allow-Credentials: true`

### 413 Request Entity Too Large
- Increase `client_max_body_size` in nginx (default is 50MB for uploads)
- Vercel has a 4.5MB function payload limit — use S3 pre-signed URLs for large uploads

### WebSocket connection fails
- Ensure `VITE_WS_URL` uses `wss://` (not `ws://`) in production
- Some platforms (Render free tier) don't support WebSockets
- Use `VITE_API_URL` with polling fallback if WebSockets unavailable

### Alembic migration fails
- Ensure `DATABASE_URL` uses `postgresql+asyncpg://` driver
- Run migrations manually: `alembic upgrade head`
- Check that PostgreSQL version is 15+

### Celery tasks not running
- Verify `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` point to Redis
- Check worker logs for connection errors
- Ensure worker service is running (not just the web service)
- On Kubernetes, set `terminationGracePeriodSeconds: 60` so the `worker_shutdown` signal handler has time to clean up Playwright/browser resources
