# 🏭 AI Predictive Maintenance System (Cloud Architecture)

An enterprise-grade, cloud-ready Predictive Maintenance IoT & AI Telemetry System. Monitors industrial machines (`M01`–`M03`), performs real-time Machine Learning failure risk classification using a trained Random Forest model, visualizes live telemetry graphs, and dispatches automated **SMTP email alerts** with per-machine cooldowns when critical risk thresholds are crossed.

---

## 🏗️ Architecture Overview

The system is decoupled into two independent modules designed for scalable cloud hosting:

```
┌────────────────────────────────────────────────────────┐
│               Frontend (Vercel Deployable)             │
│  - Modern Real-Time Dashboard (Tailwind + Chart.js)    │
│  - Live Telemetry Metrics (Temp, Vibration, Curr, RPM) │
│  - Radial Risk Gauges & Automated Incident Log         │
│  - Configurable Backend URL (VITE_API_URL / In-App)    │
└───────────────────────────┬────────────────────────────┘
                            │ HTTPS / REST API (CORS)
                            ▼
┌────────────────────────────────────────────────────────┐
│               Backend (Render Deployable)              │
│  - FastAPI Asynchronous REST API (Uvicorn)             │
│  - Scikit-Learn ML Inference Engine (Random Forest)    │
│  - SMTP Email Alert Service with Anti-Spam Cooldown    │
│  - Interactive Simulation Engine (/api/simulator)      │
└───────────────────────────┬────────────────────────────┘
                            │ PostgreSQL Connection (SSL)
                            ▼
┌────────────────────────────────────────────────────────┐
│           Database (Render PostgreSQL / Cloud)         │
│  - sensor_readings (Historical telemetry streams)      │
│  - alert_log (Audit trail of dispatched alerts)        │
└────────────────────────────────────────────────────────┘
```

---

## ⚡ Quickstart (Local Development)

You can run both the FastAPI backend and the frontend dashboard locally with **one single command**:

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Configure environment (PostgreSQL & SMTP)
cp backend/.env.example backend/.env
# Edit backend/.env with your DB password and SMTP credentials

# 3. Start both services together!
python run_local.py
```

- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Backend:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🚀 Deployment Guide

### Part 1: Deploy Backend to [Render](https://render.com)

1. **Push your code to GitHub / GitLab**.
2. Log into [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **PostgreSQL**:
   - **Name:** `predictive-maintenance-db`
   - **Database:** `maintenance`
   - Click **Create Database** and copy the **Internal Database URL** (or External Database URL).
3. Click **New +** -> **Web Service**:
   - Connect your Git repository.
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. In the **Environment Variables** section, add:
   - `DATABASE_URL`: *(Paste your Render PostgreSQL connection string)*
   - `CORS_ORIGINS`: `*` (or your Vercel URL once created)
   - `SMTP_HOST`: `smtp.gmail.com`
   - `SMTP_PORT`: `587`
   - `SMTP_USER`: `your-email@gmail.com`
   - `SMTP_PASSWORD`: `your-16-char-app-password` *(Generated from Google Account App Passwords)*
   - `ALERT_RECIPIENTS`: `lead-engineer@example.com,team@example.com`
   - `ALERT_RISK_THRESHOLD`: `60`
   - `ALERT_COOLDOWN_MINUTES`: `15`
   - `EMAIL_ALERTS_ENABLED`: `true`
5. Click **Create Web Service**.
6. Once deployed, copy your backend service URL (e.g., `https://ai-predictive-maintenance-api.onrender.com`).

---

### Part 2: Deploy Frontend to [Vercel](https://vercel.com)

1. Log into [Vercel Dashboard](https://vercel.com/) and click **Add New...** -> **Project**.
2. Import your Git repository.
3. In the project setup configuration:
   - **Framework Preset:** `Other` (or `Vite`)
   - **Root Directory:** Click **Edit** and select `frontend`
   - **Build Command:** *(Leave default or empty)*
   - **Output Directory:** *(Leave default or `.`)*
4. Under **Environment Variables**, add:
   - `VITE_API_URL`: *(Your Render backend URL, e.g. `https://ai-predictive-maintenance-api.onrender.com`)*
5. Click **Deploy**.

> 💡 **Tip:** You can also dynamically change or test the backend URL directly inside the live frontend UI at any time by clicking the **API Status / Settings** button in the header!

---

## 📡 REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Service health check and machine listing |
| `/api/overview` | `GET` | System stats, fleet overview & latest readings |
| `/api/machines` | `GET` | List of all monitored machines (`["M01", "M02", "M03"]`) |
| `/api/readings/latest` | `GET` | Latest telemetry + AI predicted risk per machine |
| `/api/readings/history` | `GET` | Time-series sensor history for charts (`?machine_id=M01&limit=50`) |
| `/api/readings` | `POST` | Ingest sensor data, run ML prediction & trigger email alert if risk ≥ threshold |
| `/api/predict` | `POST` | Direct inference endpoint for raw sensor inputs |
| `/api/alerts/recent` | `GET` | Recent alert history log from `alert_log` |
| `/api/alerts/test` | `POST` | Dispatch a live test email via SMTP |
| `/api/simulator/tick` | `POST` | Generate 1 simulated telemetry cycle across all machines |
| `/api/simulator/hazard` | `POST` | Inject an abnormal sensor spike into a specific machine |

---

## 📁 Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI REST API & routes
│   │   ├── config.py          # Config loader (DATABASE_URL, .env)
│   │   ├── database.py        # PostgreSQL access layer & schema migration
│   │   ├── ml_model.py        # ML inference engine
│   │   ├── alerts.py          # SMTP email alerting & cooldowns
│   │   └── schemas.py         # Pydantic data models
│   ├── model/
│   │   └── failure_model.pkl  # Trained Random Forest classifier
│   ├── sensor_simulator.py    # Background CLI sensor generator
│   ├── train_model.py         # Model training script
│   ├── test_email.py          # SMTP testing script
│   ├── requirements.txt       # Python backend dependencies
│   ├── render.yaml            # Render Blueprint deployment config
│   ├── Procfile               # Render startup procfile
│   └── .env.example           # Backend env template
├── frontend/
│   ├── index.html             # High-performance dashboard SPA
│   ├── app.js                 # Dashboard controller, polling & chart updates
│   ├── config.js              # Dynamic API connection manager
│   ├── style.css              # Custom styling, glow animations & themes
│   ├── vercel.json            # Vercel routing & headers configuration
│   ├── package.json           # Vercel build compatibility
│   └── vite.config.js         # Vite configuration
├── run_local.py               # 1-command runner for local development
└── README.md                  # Comprehensive documentation
```
