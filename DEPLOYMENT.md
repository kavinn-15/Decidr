# Decidr — Production Deployment Guide

This guide walks you through deploying **Decidr** to production using the free tiers of **Supabase** (PostgreSQL & Storage), **Render** (FastAPI Backend), and **Vercel** (Next.js Frontend).

---

## Architecture Overview

```mermaid
flowchart LR
    Browser["User Browser"] -->|"HTTPS / UI"| Vercel["Vercel\n(Next.js 16 Frontend)"]
    Vercel -->|"HTTPS / REST API"| Render["Render\n(FastAPI Backend)"]
    Render -->|"PostgreSQL (SSL: 6543/5432)"| SupabaseDB[("Supabase PostgreSQL\n(Database)")]
    Render -.->|"HTTPS / REST"| SupabaseStorage[("Supabase Storage\n(decidr-transcripts)")]
```

| Component | Provider | Tier | Host/Port |
| :--- | :--- | :--- | :--- |
| **Frontend** | Vercel | Free Hobby | `https://<your-app>.vercel.app` |
| **Backend** | Render | Free Web Service | `https://<your-service>.onrender.com` |
| **Database** | Supabase | Free Tier (500 MB) | Transaction Pooler (`aws-0-*.pooler.supabase.com:6543`) |
| **File Storage** | Supabase Storage | Free Tier (1 GB) | Bucket: `decidr-transcripts` (optional) |

---

## Step 1: Set Up Supabase (Database & Storage)

### 1.1 Create a Free Project
1. Go to [https://supabase.com](https://supabase.com) and sign in.
2. Click **New Project**.
3. Choose an organization, enter a project name (e.g. `decidr-prod`), set a secure **Database Password** (keep this safe), and select your closest AWS region.
4. Click **Create new project** and wait ~2 minutes for provisioning.

### 1.2 Get the PostgreSQL Connection String
1. In your Supabase project dashboard, navigate to **Project Settings** &rarr; **Database**.
2. Scroll to **Connection string** and select **URI**.
3. For serverless/Render environments, choose the **Connection Pooling** tab (Port `6543`, Transaction mode):
   ```text
   postgresql://postgres.[YOUR-PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[YOUR-REGION].pooler.supabase.com:6543/postgres?sslmode=require
   ```
4. Replace `[YOUR-PASSWORD]` with your actual database password.
   > **Note:** Decidr automatically normalizes `postgres://` or `postgresql://` into `postgresql+psycopg2://` and enforces SSL (`sslmode=require`).

### 1.3 Apply Database Migrations
Run the initial Alembic migration from your local machine to create all tables on Supabase:

```bash
# In your local project terminal
cd backend
$env:DATABASE_URL="postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require"
..\.venv\Scripts\alembic.exe upgrade head
```
*(On Linux/macOS, use `export DATABASE_URL="..." && alembic upgrade head`)*

This creates all 18 tables: `users`, `project_members`, `people`, `meetings`, `utterances`, `items`, `decisions`, `decision_versions`, `premises`, `tasks`, `alerts`, `change_proposals`, `change_actions`, `reminders`, `tracker_tickets`, `audit_log`, `outbox`, and `alembic_version`.

### 1.4 (Optional) Create Supabase Storage Bucket for Transcripts
1. In the Supabase sidebar, click **Storage**.
2. Click **New Bucket**.
3. Name the bucket `decidr-transcripts`.
4. Keep it **Private** (recommended) or Public.
5. In **Project Settings** &rarr; **API**, copy:
   - **Project URL** (`https://<project-ref>.supabase.co`) &rarr; `SUPABASE_URL`
   - **service_role secret** &rarr; `SUPABASE_SERVICE_ROLE_KEY` (keep private on backend only)

---

## Step 2: Deploy Backend to Render

### 2.1 Connect Repository
1. Log in to [https://render.com](https://render.com).
2. Click **New +** &rarr; **Web Service**.
3. Select **Build and deploy from a Git repository** and connect `https://github.com/kavinn-15/Decidr`.

### 2.2 Configure Web Service
Configure the following settings:

| Field | Value |
| :--- | :--- |
| **Name** | `decidr-backend` |
| **Region** | Select region closest to your Supabase region |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install --upgrade pip && pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` |
| **Instance Type** | `Free` |

> [!IMPORTANT]
> Keep `--workers 1`. The single worker model guarantees APScheduler jobs (daily expiry, 15m reminders, weekly digests) run exactly once without race conditions.

### 2.3 Add Environment Variables
In the **Environment** tab on Render, add:

| Key | Example Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Enables production security mode |
| `DATABASE_URL` | `postgresql://postgres.[REF]:[PASSWORD]@...:6543/postgres?sslmode=require` | Supabase connection string |
| `JWT_SECRET_KEY` | *(Generate a 32+ character random string)* | Secret for signing auth tokens |
| `DEMO_MODE` | `false` | Disables demo database resets |
| `AUTH_ENFORCED` | `true` | Enforces authentication on all endpoints |
| `CORS_ORIGINS` | `https://<your-vercel-app>.vercel.app,http://localhost:3000` | Allowed frontend domains |
| `LLM_PROVIDER` | `gemini` *(or `fake` for offline mode)* | LLM provider backend |
| `LLM_MODE` | `live` *(or `cache`)* | LLM execution mode |
| `LLM_MODEL` | `gemini-1.5-pro` | LLM model name |
| `GEMINI_API_KEY` | `AIzaSy...` | Your Google Gemini API key |
| `TRACKER` | `mock` *(or `github`)* | Issue tracker backend |
| `TIMEZONE` | `UTC` | Timezone for scheduler |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` | Optional Supabase Storage URL |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJh...` | Optional Supabase Service Role Key |
| `SUPABASE_STORAGE_BUCKET` | `decidr-transcripts` | Storage bucket name |

### 2.4 Health Check & Deployment
1. Under **Advanced**, set **Health Check Path** to `/health`.
2. Click **Create Web Service**.
3. Once deployed, test the health check in your browser:
   ```text
   https://decidr-backend.onrender.com/health
   # Expected output: {"status": "ok"}
   ```

---

## Step 3: Deploy Frontend to Vercel

### 3.1 Import Project
1. Log in to [https://vercel.com](https://vercel.com).
2. Click **Add New...** &rarr; **Project**.
3. Select the `Decidr` repository.

### 3.2 Configure Build & Root Directory
In the project configuration:
1. **Framework Preset**: Next.js
2. **Root Directory**: Click **Edit** and choose `frontend`.
3. **Build Command**: `npm run build`
4. **Install Command**: `npm ci`

### 3.3 Set Environment Variables
Add the following environment variable:

| Key | Value |
| :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `https://decidr-backend.onrender.com` *(your actual Render backend URL without trailing slash)* |

### 3.4 Deploy
1. Click **Deploy**.
2. Once complete, copy your production Vercel URL (e.g. `https://decidr.vercel.app`).
3. Return to **Render** &rarr; `decidr-backend` &rarr; **Environment** and make sure `CORS_ORIGINS` contains your Vercel URL:
   ```text
   CORS_ORIGINS=https://decidr.vercel.app,http://localhost:3000
   ```

---

## Step 4: End-to-End Verification Checklist

Verify your production deployment with these steps:

- [ ] **Health Check**: Open `https://<render-url>/health` &rarr; returns `{"status":"ok"}`.
- [ ] **CORS Verification**: Open your Vercel app in the browser. Check browser developer console (F12 &rarr; Console) to verify zero CORS errors.
- [ ] **Registration**:
  1. Navigate to `/register`.
  2. Create an account with a strong password (at least 8 chars, uppercase, lowercase, number, symbol).
- [ ] **Login & Authentication**:
  1. Log in with your new account.
  2. Verify that JWT token is stored and profile loads.
- [ ] **Meeting Ingestion**:
  1. Go to Meetings dashboard.
  2. Click **New Meeting** and upload a `.vtt` transcript.
  3. Verify utterances are parsed and stored in Supabase PostgreSQL.
- [ ] **Extraction & Review**:
  1. Click **Process** on the meeting.
  2. Review extracted decisions, premises, and action items in `/review`.
  3. Approve decisions and verify tracker tickets appear in `/mock-tracker`.
- [ ] **Blast Radius & Repair Plans**:
  1. Verify premise monitoring detects premise breaks.
  2. Open `/affected` to trace downstream blast-radius dependency graph.
- [ ] **Persistence Across Restarts**:
  1. In Render dashboard, trigger a manual deploy or restart.
  2. Refresh your Vercel app after the backend restarts.
  3. Confirm that all meetings, decisions, and audit log records remain intact in Supabase.

---

## Free-Tier Constraints & Operational Notes

| Service | Limitation | Behavior & Recommendation |
| :--- | :--- | :--- |
| **Render Web Service** | Inactivity sleep after 15 mins | Free web services spin down after 15 minutes of inactivity. The first incoming request will experience a **cold start** delay (approx. 30–50 seconds) while the container boots. |
| **APScheduler on Render** | Sleeps with service | While Render is sleeping, APScheduler cannot execute background jobs. Scheduled jobs resume automatically once the service is awake. If exact cron times (e.g., 9:00 AM Monday digests) are required, use a free external pinger like [cron-job.org](https://cron-job.org) to ping `/health` or trigger `/reminders/admin/run-digest`. |
| **Supabase Database** | 500 MB storage cap | Decidr stores structured text, decisions, and utterances efficiently. 500 MB accommodates tens of thousands of meeting transcripts. |
| **Supabase Free Pause** | Inactivity pause after 7 days | Free Supabase projects pause after 7 days of zero database queries. Regular use or an automated health check prevents pauses. |
| **Vercel Frontend** | 100 GB bandwidth / mo | Ample for team governance dashboards. |
