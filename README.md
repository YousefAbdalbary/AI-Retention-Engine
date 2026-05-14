# 🤖 Customer Retention AI — Enterprise Intelligence Platform

> AI-powered customer churn prediction and retention strategy engine built with **XGBoost**, **SHAP explainability**, **Groq LLaMA 3.3 LLM**, **FastAPI**, and a **Vanilla JS** enterprise dashboard.

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
- 📁 **Smart CSV Engine**: Dual-mode ingestion (Formatted records vs. Raw transaction logs)
- 🔌 **CRM Connectors**: Live sync from HubSpot, Stripe, Mixpanel, and Salesforce
- 🔍 **One-Click Lookup**: "Fetch" and "Try" buttons for instant real-time CRM record analysis
- 📊 **Batch Summary**: Automatic KPI overviews (Avg Risk, High Risk Count) for all uploads
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
│                   FastAPI Backend                        │
│                                                         │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │  Fast Path       │  │  Deep Analysis Path          │  │
│  │  /analyze-risk   │  │  /analyze-risk-detailed      │  │
│  │                  │  │                              │  │
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

### 1. Smart CSV Engine (Dual-Mode)
*   **Formatted Mode**: Upload a CSV where each row is a customer already matching the 7 features.
*   **Raw Mode (Transaction Logs)**: Upload a list of every payment/event. The engine **automatically performs Feature Engineering** to group, aggregate, and calculate tenure/risk per user.

### 2 One-Click "Fetch & Try"
Enter a HubSpot or Stripe ID in the Analysis form and click **Fetch** to pull live metrics instantly, or click **Try** in the connector panel to analyze a random live record.

---

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

**Additional response fields:**
```json
{
  "shap_available": true,
  "llm_source": "groq_llama",
  "llm_analysis": {
    "feature_effects": [
      {
        "label": "Cancellation Rate",
        "label_ar": "معدل الإلغاء",
        "value": "0.18",
        "impact": "+12.3%",
        "direction": "increases_churn",
        "relative_strength": 85
      }
    ],
    "llama_report": {
      "source": "groq_llama",
      "english": {
        "churn_risk_summary": "...",
        "behavioral_diagnosis": "...",
        "root_causes_ranked": ["...", "..."],
        "recommended_rescue_strategy": "...",
        "empathy_guidance": "...",
        "suggested_agent_script": "...",
        "executive_takeaway": "..."
      },
      "arabic": { "..." }
    }
  }
}
```

---

#### `GET /api/v1/customers` — Paginated Customer List

Query params: `page`, `page_size`, `search`, `risk`, `vip`, `sort_by`, `sort_dir`

---

#### `GET /api/v1/customer/{customer_id}` — Customer Detail

Returns full customer object with analytics, LLM analysis, action history, monthly risk trends.

---

#### `GET /api/v1/dashboard-overview` — Dashboard KPIs

Returns total customers, risk band counts, revenue at risk, VIP count, alerts, activity feed.

---

#### `GET /api/v1/analytics` — Charts & Segmentation Data

Returns churn distribution, revenue impact, customer segmentation, risk heatmap, monthly trends, AI action distribution.

---

#### `POST /api/v1/customers/upload-csv` — CSV Bulk Upload

```json
{ "csv_text": "user_id,avg_plan_price,...\ncust1,500,..." }
```

---

#### `DELETE /api/v1/customer/{customer_id}` — Remove Customer

---

#### `GET /api/v1/llm-analysis/{customer_id}` — Get LLM Analysis

---

#### `GET /api/v1/realtime` — Realtime Alerts

---

#### `GET /api/v1/health` — Health Check

```json
{
  "status": "ok",
  "model_loaded": true,
  "customers": 3200,
  "shap_available": true,
  "llm_configured": true
}
```

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

## Project Structure

```
enterprise_retention_project/
├── ai-churn-presiction.ipynb          # Full ML training pipeline (Kaggle)
├── README.md                          # This file
├── backend/
│   ├── main.py                        # FastAPI app (all endpoints + LLM + SHAP)
│   ├── requirements.txt               # Python dependencies
│   ├── ai_retention_xgboost_optimized.json  # Trained XGBoost model
│   └── retention_customer_store.json   # Persisted customer data
└── frontend/
    ├── index.html                     # Dashboard HTML structure
    ├── styles.css                     # Premium CSS (glassmorphism, dark/light)
    └── app.js                         # Dashboard logic, charts, API calls
```

---

## Architecture Decisions

### 1. Fast vs Deep Analysis Separation
- **`/analyze-risk`**: Lightweight XGBoost-only prediction (~50ms)
- **`/analyze-risk-detailed`**: SHAP + LLaMA deep analysis (~3-5s)
- Reason: SHAP is computationally expensive, LLM calls cost money/time. Enterprise systems always separate lightweight from advanced inference.

### 2. Structured LLM Output (Not Raw Text)
- LLM returns **structured JSON**, not raw markdown
- Frontend renders structured fields as cards, timelines, and panels
- This is critical for enterprise UX — raw LLM text looks unprofessional

### 3. In-Memory Storage (DB-Ready Architecture)
- Currently uses in-memory dictionaries + synthetic data
- Service layer pattern makes DB integration straightforward later
- No PostgreSQL complexity during development phase

### 4. Bilingual by Default
- All AI outputs include both English and Arabic
- Arabic text is natural/professional, not machine-translated
- RTL layout support throughout the frontend

### 5. SHAP as Optional Dependency
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
| **Backend** | FastAPI 0.115, Pydantic 2.9 |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Charts** | Chart.js |
| **Icons** | Lucide |
| **Server** | Uvicorn (ASGI) |

---

## How Frontend ↔ Backend Communicate

1. **Frontend** collects form inputs and builds a JSON payload matching the `CustomerData` Pydantic model
2. `app.js` calls `fetch()` → `POST /api/v1/analyze-risk` with `Content-Type: application/json`
3. **Backend** validates via Pydantic, runs XGBoost, applies business rules, returns structured JSON
4. **Frontend** renders results as KPI cards, risk rings, collapsible insight sections
5. User clicks **"Run Advanced AI Analysis"** → calls `/api/v1/analyze-risk-detailed`
6. Backend runs SHAP + calls Groq LLaMA → returns enhanced structured insights
7. Frontend re-renders with real SHAP effects and LLM-generated retention strategy

### Why CORS is Required
Browsers block cross-origin requests. FastAPI adds CORS headers via `CORSMiddleware` to allow the frontend (served from the same origin or opened locally) to communicate with the API.

---

## Development Roadmap

### ✅ Phase 1 (Complete)
- Enterprise dashboard with analytics
- Customer table with search/filter/sort/pagination
- AI prediction with structured insights
- Dark/light mode, responsive design

### ✅ Phase 2 (Complete)
- SHAP integration for real feature explainability
- Groq LLaMA 3.3 API integration
- Structured bilingual AI insights (not raw text)
- Next Best Action recommendation engine
- Advanced Analysis endpoint separation

### ✅ Phase 3 (Complete)
- **Data Connector Suite**: HubSpot, Stripe, Mixpanel, and Salesforce integration
- **Smart CSV Engine**: Raw transaction log aggregation and feature engineering
- **Real-time CRM Lookup**: "Fetch" and "Try" buttons for instant record analysis
- **Batch KPI Overviews**: Real-time summary of bulk ingestion results
- **Environment Configuration**: Secure `.env` management for all API keys

### 🔮 Phase 4 (Future)
- PDF export with charts
- WebSocket real-time alerts
- Database integration (PostgreSQL)
- Authentication & role-based access
# AI-Retention-Engine
