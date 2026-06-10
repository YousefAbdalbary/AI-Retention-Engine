# 🤖 Customer Retention AI — Enterprise Intelligence Platform

> AI-powered customer churn prediction and retention strategy engine built with **XGBoost**, **SHAP explainability**, **Groq LLaMA 3.3 LLM**, **FastAPI** (Modular Architecture), and a **Vanilla JS** enterprise dashboard.

[![Python](https://img.shields.io/badge/Python-3.12-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)]()
[![XGBoost](https://img.shields.io/badge/XGBoost-2.1-orange)]()
[![LLaMA](https://img.shields.io/badge/LLaMA_3.3-Groq-purple)]()

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [ML Pipeline](#ml-pipeline)
  - [Feature Definitions](#2-detailed-feature-definitions-the-7-pillars)
  - [Model Training](#3-model-training)
- [Data Ingestion Suite](#-data-ingestion-suite)
  - [Smart CSV Engine](#2-smart-csv-engine-dual-mode)
- [Preparing Test Data](#️-preparing-test-data-csv-templates)
- [API Reference](#api-reference)
- [Frontend Dashboard](#frontend-dashboard)
- [How to Run & Test](#-how-to-run--test)
- [Project Structure](#project-structure)
- [Architecture Decisions](#architecture-decisions)
- [Technology Stack](#technology-stack)

---

## Overview

This project is a **full-stack AI retention intelligence platform** that:

1. **Predicts customer churn** using a trained XGBoost model (97% accuracy, 0.972 AUC)
2. **Explains predictions** using SHAP (SHapley Additive exPlanations) feature analysis
3. **Generates bilingual retention strategies** (English + Arabic) via Groq LLaMA 3.3 70B
4. **Visualizes everything** in a premium enterprise dashboard with real-time analytics

### Key Features

- ⚡ **Fast Path**: Instant XGBoost churn prediction (`/api/v1/analyze-risk`)
- 🧠 **Deep Analysis**: SHAP + LLaMA structured insights (`/api/v1/analyze-risk-detailed`)
- 📊 **Enterprise Dashboard**: KPI cards, charts, customer tables, risk heatmaps
- 🌐 **Bilingual**: Full Arabic + English support across all AI outputs
- 📁 **Smart File Engine**: Dual-mode ingestion via Drag & Drop (Supports `.csv`, `.xlsx`, `.xls`)
- 🔌 **CRM Connectors**: Live sync from HubSpot, Stripe, Mixpanel, and Salesforce
- ✉️ **Hyper-Personalized AI Emails**: Generates highly targeted retention emails injecting exact customer metrics (NPS, feature usage, name) via strict LLM prompting.
- 🌙 **Dark/Light Mode**: Premium theme switching

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend (Vanilla JS)                 │
│  index.html + styles.css + app.js                       │
│  Chart.js | Lucide Icons | Responsive Design            │
└──────────────────────┬──────────────────────────────────┘
                       │ fetch() JSON API calls
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend (Modular)             │
│                                                         │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │  Fast Path       │  │  Deep Analysis Path          │  │
│  │  /analyze-risk   │  │  /analyze-risk-detailed      │  │
│  │  XGBoost Only    │  │  XGBoost + SHAP + LLaMA     │  │
│  │  ~50ms           │  │  ~3-5 seconds                │  │
│  └─────────────────┘  └──────────────────────────────┘  │
│                                                         │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │ XGBoost  │  │ SHAP Tree  │  │ Groq LLaMA 3.3   │    │
│  │ Model    │  │ Explainer  │  │ 70B Versatile    │    │
│  └──────────┘  └────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### Endpoint Separation (Enterprise Pattern)

| Endpoint | Purpose | Speed | Cost |
|---|---|---|---|
| `POST /api/v1/analyze-risk` | Fast prediction | ~50ms | Free |
| `POST /api/v1/analyze-risk-detailed` | SHAP + LLM deep analysis | ~3-5s | LLM API call |

This separation is critical for enterprise scalability — basic scoring runs on every request while expensive SHAP/LLM analysis is triggered on-demand.

---

## ML Pipeline

The XGBoost model was trained on the **KKBox Churn Prediction Challenge** dataset from Kaggle.

### Training Pipeline (Kaggle Notebook)

The complete training pipeline is in `ai-churn-presiction.ipynb`:

#### 1. Data Extraction & Sampling
- Extracted `train_v2.csv` and `transactions_v2.csv` from the KKBox competition
- Downsampled to **20,000 users** with stratified sampling (preserving churn ratio)
- Filtered **23,583 transaction records** for sampled users

#### 2. Detailed Feature Definitions (The 7 Pillars)
Every customer record analyzed by the model must provide or be reduced to these **7 core features**.

| Feature | Type | Definition | Why it matters |
|---|---|---|---|
| `avg_plan_price` | Float | The average cost of the user's subscription plans. | High prices increase churn probability if value perception drops. |
| `total_amount_paid`| Float | Total cumulative revenue collected from the customer. | Indicates historical loyalty and lifetime value (LTV). |
| `total_transactions`| Int | Total number of successful payment events. | Frequency of engagement; more transactions usually mean higher stickiness. |
| `billing_tenure_days`| Int | Days between the first seen transaction and today. | Long-term customers are less likely to churn suddenly (Tenure Effect). |
| `auto_renew_count` | Int | How many times the subscription successfully auto-renewed. | Strongest indicator of passive loyalty and "set-and-forget" behavior. |
| `total_cancellations`| Int | Count of manual cancellations or payment failures. | Direct signal of intent to leave or financial friction. |
| `cancel_rate` | Float | `cancellations / transactions` (Computed automatically). | Normalized risk; high rates flag unstable accounts regardless of size. |

---

## 🔌 Data Ingestion Suite

The platform supports two primary ways to feed data into the AI engine.

### 1. Smart File Engine (Dual-Mode Excel/CSV)
The platform now natively supports binary Excel (`.xlsx`, `.xls`) and `.csv` files via pandas and openpyxl, seamlessly ingested via the Drag & Drop zone.
*   **Formatted Mode**: Upload a file where each row is a customer already matching the 7 features.
*   **Raw Mode (Transaction Logs)**: Upload a list of every payment/event. The engine **automatically performs Feature Engineering** to group, aggregate, and calculate tenure/risk per user.

### 2. One-Click "Fetch & Try"
Enter a HubSpot or Stripe ID in the Analysis form and click **Fetch** to pull live metrics instantly, or click **Try** in the connector panel to analyze a random live record.

---

## 🛠️ Preparing Test Data (CSV Templates)

If you are not using a live CRM sync, you can upload test data via CSV. The engine supports two distinct formats.

### 1. "Ready" Mode (Pre-calculated Features)
Use this if you already have a summary of customer behavior.

**Table Representation:**
| user_id | avg_plan_price | total_amount_paid | total_transactions | billing_tenure_days | auto_renew_count | total_cancellations |
|---|---|---|---|---|---|---|
| cust_001 | 499.0 | 1497.0 | 3 | 90 | 2 | 0 |
| cust_002 | 99.0 | 198.0 | 2 | 30 | 0 | 1 |

**CSV Format:**
```csv
user_id,avg_plan_price,total_amount_paid,total_transactions,billing_tenure_days,auto_renew_count,total_cancellations
cust_001,499.0,1497.0,3,90,2,0
cust_002,99.0,198.0,2,30,0,1
```

### 2. "Raw" Mode (Transaction Logs)
Use this if you have a list of raw payment events. The engine automatically aggregates these.

**Table Representation:**
| customer_id | transaction_date | amount | plan_name | is_cancellation | is_auto_renew |
|---|---|---|---|---|---|
| user_A | 2024-01-01 | 500 | Premium | 0 | 1 |
| user_A | 2024-02-01 | 500 | Premium | 0 | 1 |
| user_B | 2024-01-15 | 100 | Basic | 1 | 0 |

**CSV Format:**
```csv
customer_id,transaction_date,amount,plan_name,is_cancellation,is_auto_renew
user_A,2024-01-01,500,Premium,0,1
user_A,2024-02-01,500,Premium,0,1
user_B,2024-01-15,100,Basic,1,0
```

---

#### 3. Model Training
- **Algorithm**: XGBoost with RandomizedSearchCV hyperparameter optimization
- **Best Parameters**: `max_depth=6, learning_rate=0.05, scale_pos_weight=5, subsample=0.9, colsample_bytree=0.8`
- **Early Stopping**: Stopped at tree #28 (out of 1000 max)

#### 4. Results

| Metric | Value |
|---|---|
| **Accuracy** | 97% |
| **ROC-AUC** | 0.972 |
| **Precision (churn)** | 87.4% |
| **Recall (churn)** | 82.5% |
| **F1 (churn)** | 0.85 |
| **Optimal Threshold** | 0.633 |

#### 5. Threshold Optimization
- Used `precision_recall_curve` on validation set to find optimal F1 threshold
- Optimal threshold: **0.633** (vs default 0.5)
- Improved precision from 86.2% → 87.4%

#### 6. Action Engine
- `RetentionActionEngine` class maps predictions to business decisions:
  - `NO_ACTION` — risk below threshold
  - `AUTOMATED_EMAIL` — above threshold, standard customer
  - `HUMAN_ESCALATION` — above threshold, VIP customer

#### 7. SHAP + LLaMA Analysis
- SHAP `TreeExplainer` computes per-feature contribution to each prediction
- Top churn drivers are fed to LLaMA 3.3 70B for bilingual narrative generation
- Combined output: quantitative SHAP + qualitative LLM reasoning

---

## API Reference

### Base URL
```
http://127.0.0.1:8000
```

### Endpoints

#### `POST /api/v1/analyze-risk` — Fast Prediction

**Request:**
```json
{
  "user_id": "cust_1042",
  "total_transactions": 42,
  "total_cancellations": 7,
  "auto_renew_count": 14,
  "total_amount_paid": 1234.56,
  "avg_plan_price": 799.99,
  "billing_tenure_days": 210
}
```

**Response:**
```json
{
  "customer_id": "cust_1042",
  "churn_risk_percentage": 37.21,
  "is_vip": true,
  "decision": "TRIGGER_LLAMA_AND_ALERT_HUMAN",
  "priority": "CRITICAL",
  "confidence_score": 82.5,
  "priority_score": 72,
  "structured": true,
  "llm_analysis": { "..." }
}
```

---

#### `POST /api/v1/analyze-risk-detailed` — SHAP + LLM Deep Analysis

Same request body as above. Runs:
1. XGBoost prediction
2. SHAP feature effect computation
3. Groq LLaMA 3.3 API call with SHAP context
4. Structured bilingual insights generation

---

#### Core Sub-Routers
- **`/api/v1/customers`**: Management endpoints (GET all, GET one, DELETE, upload CSV)
- **`/api/v1/dashboard-overview`** & **`/api/v1/analytics`**: Dashboard KPI and Chart aggregations
- **`/api/v1/email`**: Bulk email dispatching, trigger campaigns, email statuses
- **`/api/v1/connectors`**: Status, Lookup, and Sync endpoints for HubSpot, Mixpanel, etc.
- **`/api/v1/health`**: System and configuration health checking

---

## Frontend Dashboard

The frontend is a **Vanilla JS single-page application** served through FastAPI static files.

### Views

| View | Description |
|---|---|
| **Overview** | KPI cards, churn distribution chart, retention trends, revenue impact, AI action distribution |
| **All Customers** | Searchable, sortable, filterable customer table with pagination, risk heatmap, segmentation chart |
| **AI Analysis** | Single customer scoring form, CSV upload, structured AI insights panel with Advanced Analysis button |
| **Realtime** | Live alerts, activity feed, VIP vs non-VIP chart |

### Features
- **Customer Drawer**: Click any customer row to open a detail panel with full analytics
- **Dark/Light Mode**: Toggle with theme persistence
- **PDF Reports**: Per-customer and overview reports via print dialog
- **Bilingual Display**: English + Arabic shown side-by-side throughout
- **Responsive**: Adapts to mobile, tablet, and desktop

### 💼 Sales Persona & CRM Transformation
The dashboard has undergone a complete UI/UX overhaul to pivot from a technical data-science tool into an action-oriented **Sales & Renewals CRM**.

#### 1. Terminology & Framing
- **Shift to Positive Framing**: Negative phrasing like "Risk" or "Churn" was replaced with sales-friendly terms like "Account Health" (صحة الحساب), "Sales Insights" (رؤى المبيعات), and "Renewal Opportunities".
- **Risk Level Clarity**: Risk levels are now explicitly labeled with English equivalents for absolute clarity: `(Low)`, `(Medium)`, `(High)`, and `(Critical)`.

#### 2. Advanced Customer Intelligence Metrics
The Customer Profile Snapshot now auto-generates (or parses) advanced behavioral metrics with intuitive explanatory tooltips:
- **Loyalty Score (مؤشر الولاء)**
- **Email Open Rate (معدل فتح البريد)**
- **Feature Usage Score (استخدام الميزات)**

#### 3. Enhanced Overview Dashboard (نظرة عامة)
- **Sales KPIs**: The top metrics cards explicitly display exact consumer counts across all 4 risk tiers alongside pipeline metrics.
- **Top Deals at Risk**: Added a new live widget at the bottom of the overview that lists the highest-revenue accounts in critical danger.
- **VIP Accounts Ratio (نسبة عملاء VIP)**: A dedicated doughnut chart breaking down the pipeline ratio of strategic VIP accounts versus standard accounts.

#### 4. Action-Oriented Customer Table (جدول العملاء)
- **Staggered Communication Cadence**: The communication timeline is now staggered into a precise **1 Day, 3 Days, and 7 Days** follow-up cadence.
- **LLM-Driven Action Steps**: The text inside each communication step is no longer static; it is dynamically populated from the `recommended_actions_ar` list generated by the Groq LLaMA 3.3 LLM for each specific consumer.
- **Gamified Urgency (Glowing Rows)**: Rows that require immediate intervention today (High/Critical priority) are highlighted with a dynamic, subtle red glowing border to draw the sales agent's eye.
- **Quick Action Icons**: Added a prominent **Contact (تواصل)** button to the "Actions" column. For high-priority accounts, it renders as a striking brand-colored phone icon. For stable clients, it's a standard mail icon. Both are perfectly aligned 32x32px squares.
- **Advanced Filters**: Adjusted the Advanced Filters UI to maintain structural integrity and focus on Action Due Dates rather than pure analytical risk.

---

## 🚀 How to Run & Test

Follow these steps to get the environment up and running for testing.

### 1. Prerequisites
- **Python 3.10+** (Verify with `python --version`)
- **Git** (to clone/manage the repo)

### 2. Installation
1.  **Clone the repository** (if not already local).
2.  **Install dependencies**:
    ```bash
    pip install -r backend/requirements.txt
    ```

### 3. Environment Setup
1.  Navigate to the `backend/` directory.
2.  Open `.env` and paste your API keys:
    - `HUBSPOT_API_KEY` (for CRM sync)
    - `STRIPE_SECRET_KEY` (for billing sync)
    - `LLAMA_API_KEY` (for Groq AI insights)
    - `SENDER_EMAIL/PASSWORD` (for retention email alerts)

### 4. Running the Server
From the project root:
```bash
uvicorn backend.main:app --reload --port 8000
```
*The reloader is active, so changes to backend code will refresh the server automatically.*

### 5. Testing the Integration
1.  **Open Dashboard**: Go to `http://127.0.0.1:8000`.
2.  **Test Live Sync**: Go to the **Analysis** tab, find **HubSpot** in the "Data Sources" panel, and click **Test**. If it turns green (LIVE), click **Try** to pull a real record.
3.  **Test CSV Upload**:
    - Download the `test_ready.csv` example above.
    - Go to **Smart CSV Batch Analysis** in the dashboard.
    - Drag and drop your file into the **Formatted Data** tab.
    - Click **Upload & Score**.
4.  **Verify Results**: Check the **Batch Analysis Summary** that appears to see the aggregate risk of your test data.

---

## Project Structure (Refactored Modular Architecture)

The backend has been completely modularized for enterprise scalability. 

```
enterprise_retention_project/
├── ai-churn-presiction.ipynb          # Full ML training pipeline (Kaggle)
├── README.md                          # This file
├── backend/
│   ├── main.py                        # Minimal FastAPI entry point
│   ├── requirements.txt               # Python dependencies
│   ├── ai_retention_xgboost_optimized.json  # Trained XGBoost model
│   ├── retention_customer_store.json   # Persisted customer data
│   │
│   ├── api/
│   │   └── routers/                   # Modular API endpoints
│   │       ├── risk.py                # Prediction & Analysis endpoints
│   │       ├── customers.py           # Customer CRUD & CSV Uploads
│   │       ├── dashboard.py           # Real-time analytics & KPIs
│   │       ├── emails.py              # Automated email campaign handlers
│   │       ├── connectors_api.py      # HubSpot, Mixpanel integrations
│   │       └── health.py              # System health
│   │
│   ├── core/
│   │   └── config.py                  # Env vars, constants, and logging
│   │
│   ├── models/
│   │   └── schemas.py                 # Pydantic schemas (CustomerData, etc.)
│   │
│   ├── services/                      # Core Business Logic
│   │   ├── ml_engine.py               # XGBoost predictions and SHAP
│   │   ├── llm_engine.py              # Groq LLaMA integration & structured JSON
│   │   ├── store.py                   # State & JSON persistence
│   │   ├── email_service.py           # SMTP integration
│   │   └── connectors.py              # External CRM API fetching
│   │
│   └── utils/
│       └── helpers.py                 # Math, logic, and data timeline formatting
│
└── frontend/
    ├── index.html                     # Dashboard HTML structure
    ├── styles.css                     # Premium CSS (glassmorphism, dark/light)
    └── app.js                         # Dashboard logic, charts, API calls
```

---

## Architecture Decisions

### 1. Modular FastApi Backend (New in v4.0)
The previous monolithic `main.py` was separated into `core/`, `models/`, `utils/`, `services/`, and `api/routers/`. This promotes separation of concerns, easier testing, and rapid future feature addition without breaking existing pipelines.

### 2. Fast vs Deep Analysis Separation
- **`/analyze-risk`**: Lightweight XGBoost-only prediction (~50ms)
- **`/analyze-risk-detailed`**: SHAP + LLaMA deep analysis (~3-5s)
- Reason: SHAP is computationally expensive, LLM calls cost money/time. Enterprise systems always separate lightweight from advanced inference.

### 3. Structured LLM Output (Not Raw Text)
- LLM returns **structured JSON**, not raw markdown
- Frontend renders structured fields as cards, timelines, and panels
- This is critical for enterprise UX — raw LLM text looks unprofessional

### 4. In-Memory Storage (DB-Ready Architecture)
- Currently uses in-memory dictionaries + synthetic data backed by JSON
- The `services/store.py` pattern makes DB integration (like PostgreSQL) trivial later.

### 5. Bilingual by Default
- All AI outputs include both English and Arabic
- Arabic text is natural/professional, not machine-translated
- RTL layout support throughout the frontend

### 6. SHAP as Optional Dependency
- SHAP import is conditional (`try/except`)
- System works without SHAP (falls back to rule-based feature effects)
- When available, real SHAP values provide genuine model explainability

---

## Technology Stack

| Layer | Technology |
|---|---|
| **ML Model** | XGBoost 2.1 (trained on KKBox dataset) |
| **Explainability** | SHAP TreeExplainer |
| **LLM** | LLaMA 3.3 70B via Groq API |
| **Backend** | FastAPI 0.115, Pydantic 2.9 (Modular Architecture) |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Charts** | Chart.js |
| **Icons** | Lucide |
| **Server** | Uvicorn (ASGI) |
