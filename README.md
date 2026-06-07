# SaaS Churn & Revenue Analytics Dashboard

End-to-end SaaS analytics project for a junior / mid-level Data Analyst portfolio.

The project generates synthetic subscription data, loads it into PostgreSQL, calculates SaaS KPIs with SQL and Python, creates cohort retention and customer health segmentation, and displays the results in a dynamic Chart.js dashboard.

## Tech Stack

- Python
- PostgreSQL
- SQL
- pandas / NumPy
- scikit-learn
- matplotlib / seaborn
- SQLAlchemy / psycopg2
- HTML / CSS / JavaScript
- Chart.js

## Project Structure

```text
saas-churn-analytics/
├── analytics/
│   └── analytics_pipeline.py
├── dashboard/
│   ├── index.html
│   ├── main.css
│   └── script.js
├── output_charts/
├── output_csv/
├── sql/
│   └── schema.sql
├── generate_data.py
├── analytics_summary.json
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Business Questions

- What is current MRR and ARR?
- Which plan generates the most recurring revenue?
- Which plans have the highest churn?
- Which regions contribute the most revenue?
- Which customers are at risk of churn?
- How does customer retention behave by signup cohort?
- Which customer health segments should the business prioritize?

## Main KPIs

- Total revenue
- Current MRR
- ARR
- ARPU
- Active customers
- Customer churn rate
- High-risk customers
- Payment failure rate

## Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy the environment file:

```bash
copy .env .env
```

Update `.env` with your PostgreSQL credentials.

## Run

Create the database manually:

```sql
CREATE DATABASE saas_analytics;
```

Create tables:

```bash
psql -U postgres -d saas_analytics -f sql/schema.sql
```

Generate synthetic SaaS data:

```bash
python generate_data.py
```

Run analytics:

```bash
python analytics/analytics_pipeline.py
```

Open the dashboard:

```bash
python -m http.server
```

Then visit:

```text
http://localhost:8000/dashboard/index.html
```

## Notes

The dataset is synthetic. The customer health segments and churn flags are intended for analytics demonstration, not production-level churn prediction.

## Portfolio Summary

This project demonstrates SQL analytics, SaaS KPI design, PostgreSQL data modeling, Python data pipelines, cohort retention, customer segmentation, and dashboard storytelling.
