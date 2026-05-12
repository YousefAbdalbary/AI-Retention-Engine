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
- [API Reference](#api-reference)
- [Frontend Dashboard](#frontend-dashboard)
- [Setup & Run](#setup--run)
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
- 📈 **3,200 synthetic customers** pre-loaded for demo analytics
- 📁 **CSV Bulk Upload**: Batch customer analysis
- 🎯 **Next Best Action (NBA)**: AI-recommended retention offers ranked by effectiveness
- 📋 **PDF/Print Reports**: Per-customer and overview reports
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

#### 2. Feature Engineering (RFM Analysis)
| Feature | Description |
|---|---|
| `total_transactions` | Count of payment transactions |
| `total_cancellations` | Sum of cancellation events |
| `auto_renew_count` | Count of auto-renewal transactions |
| `total_amount_paid` | Cumulative revenue |
| `avg_plan_price` | Average subscription plan price |
| `billing_tenure_days` | Days between first and last transaction |
| `cancel_rate` | Cancellation rate = cancellations / transactions |

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
  "billing_tenure_days": 210,
  "cancel_rate": 0.18
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

## Setup & Run

### Prerequisites
- Python 3.10+
- pip

### 1. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### 2. Run the Backend

From the `backend/` directory:

```bash
uvicorn main:app --reload --port 8000
```

### 3. Open the Dashboard

Navigate to:
```
http://127.0.0.1:8000
```

The frontend is automatically served by FastAPI as static files.

### 4. Health Check

```
http://127.0.0.1:8000/api/v1/health
```

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

### 🔮 Phase 3 (Future)
- CSV bulk upload improvements
- PDF export with charts
- WebSocket real-time alerts
- Database integration (PostgreSQL)
- Authentication & role-based access
# AI-Retention-Engine
