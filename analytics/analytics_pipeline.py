from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


load_dotenv()

REF_MONTH = pd.Timestamp("2024-12-01")
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

OUTPUT_CSV_DIR = PROJECT_ROOT / "output_csv"
OUTPUT_CHARTS_DIR = PROJECT_ROOT / "output_charts"
SUMMARY_PATH = PROJECT_ROOT / "analytics_summary.json"

PALETTE = ["#243f5f", "#3c6656", "#9a7a35", "#9a6542", "#59636f", "#356f73"]
BG = "#f4f1e9"
PAPER = "#fffdf8"
LINE = "#d7cfbf"
TEXT = "#22262b"
MUTED = "#70716b"


SQL = {
    "monthly_revenue": """
        SELECT
            DATE_TRUNC('month', payment_date)::date AS month,
            ROUND(SUM(amount)::numeric, 2) AS revenue,
            COUNT(DISTINCT customer_id) AS paying_customers
        FROM payments
        WHERE payment_status = 'Paid'
        GROUP BY 1
        ORDER BY 1;
    """,

    "mrr_by_month": """
        SELECT
            DATE_TRUNC('month', start_date)::date AS month,
            ROUND(SUM(mrr)::numeric, 2) AS mrr,
            COUNT(DISTINCT customer_id) AS active_customers
        FROM subscriptions
        WHERE status IN ('Active', 'Churned')
        GROUP BY 1
        ORDER BY 1;
    """,

    "plan_performance": """
        SELECT
            p.plan_name,
            COUNT(DISTINCT s.customer_id) AS customers,
            ROUND(SUM(s.mrr)::numeric, 2) AS mrr,
            ROUND(AVG(s.mrr)::numeric, 2) AS arpu
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.plan_id
        WHERE s.start_date <= '2024-12-31'
        GROUP BY p.plan_name
        ORDER BY mrr DESC;
    """,

    "churn_by_plan": """
        SELECT
            p.plan_name,
            COUNT(*) FILTER (WHERE s.status = 'Churned') AS churned_subscriptions,
            COUNT(*) AS total_subscriptions,
            ROUND(
                COUNT(*) FILTER (WHERE s.status = 'Churned')::numeric
                / NULLIF(COUNT(*)::numeric, 0) * 100,
                1
            ) AS churn_rate
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.plan_id
        GROUP BY p.plan_name
        ORDER BY churn_rate DESC;
    """,

    "customer_health": """
        WITH latest_usage AS (
            SELECT DISTINCT ON (customer_id)
                customer_id,
                usage_month,
                active_users,
                logins,
                feature_events
            FROM product_usage
            ORDER BY customer_id, usage_month DESC
        ),
        ticket_summary AS (
            SELECT
                customer_id,
                COUNT(*) AS tickets,
                AVG(resolution_days) AS avg_resolution_days,
                AVG(satisfaction_score) AS avg_satisfaction
            FROM support_tickets
            GROUP BY customer_id
        ),
        revenue AS (
            SELECT
                customer_id,
                SUM(amount) AS total_revenue
            FROM payments
            WHERE payment_status = 'Paid'
            GROUP BY customer_id
        ),
        latest_plan AS (
            SELECT DISTINCT ON (s.customer_id)
                s.customer_id,
                p.plan_name,
                s.status,
                s.mrr
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.plan_id
            ORDER BY s.customer_id, s.start_date DESC
        )
        SELECT
            c.customer_id,
            c.company_name,
            c.industry,
            c.company_size,
            c.region,
            c.acquisition_channel,
            lp.plan_name,
            lp.status,
            lp.mrr,
            COALESCE(lu.active_users, 0) AS active_users,
            COALESCE(lu.logins, 0) AS logins,
            COALESCE(lu.feature_events, 0) AS feature_events,
            COALESCE(ts.tickets, 0) AS tickets,
            COALESCE(ts.avg_resolution_days, 0) AS avg_resolution_days,
            COALESCE(ts.avg_satisfaction, 0) AS avg_satisfaction,
            COALESCE(r.total_revenue, 0) AS total_revenue
        FROM customers c
        LEFT JOIN latest_plan lp ON c.customer_id = lp.customer_id
        LEFT JOIN latest_usage lu ON c.customer_id = lu.customer_id
        LEFT JOIN ticket_summary ts ON c.customer_id = ts.customer_id
        LEFT JOIN revenue r ON c.customer_id = r.customer_id;
    """,

    "region": """
        SELECT
            c.region,
            COUNT(DISTINCT c.customer_id) AS customers,
            ROUND(SUM(pay.amount)::numeric, 2) AS revenue
        FROM customers c
        JOIN payments pay ON c.customer_id = pay.customer_id
        WHERE pay.payment_status = 'Paid'
        GROUP BY c.region
        ORDER BY revenue DESC;
    """,

    "raw_customers": "SELECT * FROM customers;",
    "raw_subscriptions": "SELECT * FROM subscriptions;",
    "raw_payments": "SELECT * FROM payments;",
    "raw_usage": "SELECT * FROM product_usage;",
    "raw_tickets": "SELECT * FROM support_tickets;",
}


def db_engine():
    database = os.getenv("DATABASE") or os.getenv("DB_NAME")

    required = {
        "DB_USER": os.getenv("DB_USER"),
        "DB_HOST": os.getenv("DB_HOST"),
        "DATABASE or DB_NAME": database,
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
        "DB_PORT": os.getenv("DB_PORT", "5432"),
    }

    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing database environment variables: {', '.join(missing)}")

    url = URL.create(
        "postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=database,
    )

    return create_engine(url)


def load_data(engine):
    data = {}

    with engine.connect() as conn:
        for name, query in SQL.items():
            data[name] = pd.read_sql_query(query, conn)

    return data


def clean_numbers(df):
    df = df.copy()

    text_columns = {
        "customer_id",
        "company_name",
        "industry",
        "company_size",
        "region",
        "acquisition_channel",
        "plan_name",
        "status",
        "plan_id",
        "subscription_id",
        "payment_id",
        "usage_id",
        "ticket_id",
        "payment_status",
        "payment_type",
        "billing_cycle",
        "support_level",
        "priority",
        "category",
    }

    for col in df.columns:
        if col in text_columns:
            continue

        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass

    return df


def prepare(data):
    data = {name: clean_numbers(df) for name, df in data.items()}

    for key in ["monthly_revenue", "mrr_by_month"]:
        data[key]["month"] = pd.to_datetime(data[key]["month"])

    data["raw_customers"]["signup_date"] = pd.to_datetime(data["raw_customers"]["signup_date"])
    data["raw_subscriptions"]["start_date"] = pd.to_datetime(data["raw_subscriptions"]["start_date"])
    data["raw_subscriptions"]["end_date"] = pd.to_datetime(data["raw_subscriptions"]["end_date"])
    data["raw_payments"]["payment_date"] = pd.to_datetime(data["raw_payments"]["payment_date"])
    data["raw_usage"]["usage_month"] = pd.to_datetime(data["raw_usage"]["usage_month"])

    return data


def calculate_kpis(data):
    payments = data["raw_payments"]
    subscriptions = data["raw_subscriptions"]
    health = data["customer_health"]

    paid = payments[payments["payment_status"] == "Paid"].copy()
    latest_month = pd.Timestamp("2024-12-01")

    current_subs = subscriptions[
        (subscriptions["start_date"].dt.to_period("M").dt.to_timestamp() == latest_month)
        & (subscriptions["status"].isin(["Active", "Churned"]))
    ]

    current_mrr = current_subs[current_subs["status"] == "Active"]["mrr"].sum()
    active_customers = current_subs[current_subs["status"] == "Active"]["customer_id"].nunique()
    churned_customers = subscriptions[subscriptions["status"] == "Churned"]["customer_id"].nunique()
    total_customers = data["raw_customers"]["customer_id"].nunique()

    avg_arpu = current_mrr / active_customers if active_customers else 0
    churn_rate = churned_customers / total_customers * 100 if total_customers else 0

    high_risk = health[
        (health["status"] == "Active")
        & (
            (health["active_users"] < health["active_users"].median())
            | (health["tickets"] > health["tickets"].quantile(0.75))
        )
    ]

    return {
        "total_revenue": round(float(paid["amount"].sum()), 2),
        "current_mrr": round(float(current_mrr), 2),
        "arr": round(float(current_mrr * 12), 2),
        "active_customers": int(active_customers),
        "total_customers": int(total_customers),
        "churned_customers": int(churned_customers),
        "customer_churn_rate": round(float(churn_rate), 1),
        "arpu": round(float(avg_arpu), 2),
        "high_risk_customers": int(high_risk["customer_id"].nunique()),
        "payment_failure_rate": round(float((payments["payment_status"] == "Failed").mean() * 100), 1),
    }


def build_cohort(data):
    subs = data["raw_subscriptions"].copy()

    subs = subs.dropna(subset=["customer_id", "start_date"])
    subs["start_date"] = pd.to_datetime(subs["start_date"], errors="coerce")
    subs = subs.dropna(subset=["start_date"])

    subs["cohort_date"] = subs.groupby("customer_id")["start_date"].transform("min")

    subs["cohort_year"] = subs["cohort_date"].dt.year
    subs["cohort_month_num"] = subs["cohort_date"].dt.month

    subs["period_year"] = subs["start_date"].dt.year
    subs["period_month_num"] = subs["start_date"].dt.month

    subs["period_number"] = (
        (subs["period_year"] - subs["cohort_year"]) * 12
        + (subs["period_month_num"] - subs["cohort_month_num"])
    ).astype(int)

    subs["cohort_month"] = subs["cohort_date"].dt.to_period("M").astype(str)

    active = subs[subs["status"].isin(["Active", "Churned"])].copy()

    pivot = (
        active.groupby(["cohort_month", "period_number"])["customer_id"]
        .nunique()
        .unstack()
        .sort_index()
    )

    if 0 not in pivot.columns:
        return pd.DataFrame()

    cohort_sizes = pivot[0].replace(0, np.nan)
    retention = pivot.divide(cohort_sizes, axis=0).round(3) * 100

    return retention.iloc[:, :13]


def customer_segments(health):
    df = health.copy()
    features = ["mrr", "active_users", "logins", "feature_events", "tickets", "total_revenue"]
    df[features] = df[features].fillna(0)

    scaled = StandardScaler().fit_transform(df[features])
    scores = {}

    for k in range(2, 7):
        model = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = model.fit_predict(scaled)
        scores[k] = float(silhouette_score(scaled, labels))

    best_k = max(scores, key=scores.get)

    final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df["cluster"] = final.fit_predict(scaled)

    means = df.groupby("cluster")[["mrr", "active_users", "tickets", "total_revenue"]].mean()
    ordered = means["total_revenue"].sort_values(ascending=False).index.tolist()

    labels = ["Enterprise Value", "Healthy Accounts", "Growth Potential", "Low Usage Risk", "Support Heavy", "Low Value"]
    mapping = {cluster: labels[i] if i < len(labels) else f"Segment {i + 1}" for i, cluster in enumerate(ordered)}
    df["segment"] = df["cluster"].map(mapping)

    return df, scores, best_k


def segment_summary(segments):
    return (
        segments.groupby("segment")
        .agg(
            customers=("customer_id", "count"),
            avg_mrr=("mrr", "mean"),
            avg_active_users=("active_users", "mean"),
            avg_tickets=("tickets", "mean"),
            total_revenue=("total_revenue", "sum"),
        )
        .round(1)
        .reset_index()
        .sort_values("total_revenue", ascending=False)
        .to_dict(orient="records")
    )


def cohort_json(retention):
    return {
        "headers": [f"M+{int(col)}" for col in retention.columns],
        "rows": [
            {
                "label": str(idx),
                "vals": [None if pd.isna(v) else round(float(v), 1) for v in row.values],
            }
            for idx, row in retention.iterrows()
        ],
    }


def set_style():
    plt.rcParams.update({
        "figure.facecolor": BG,
        "savefig.facecolor": BG,
        "axes.facecolor": PAPER,
        "axes.edgecolor": LINE,
        "axes.labelcolor": MUTED,
        "axes.titlecolor": TEXT,
        "text.color": TEXT,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "grid.color": LINE,
        "grid.alpha": 0.75,
        "font.family": "DejaVu Sans",
    })


def clean_ax(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y")
    ax.set_axisbelow(True)


def money(value, _):
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


def save_charts(data, retention, segments):
    OUTPUT_CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    set_style()

    monthly = data["monthly_revenue"]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(monthly["month"], monthly["revenue"], color=PALETTE[0], lw=2.4)
    ax.fill_between(monthly["month"], monthly["revenue"], color=PALETTE[0], alpha=0.10)
    ax.set_title("Monthly revenue")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(money))
    clean_ax(ax)
    fig.tight_layout()
    fig.savefig(OUTPUT_CHARTS_DIR / "monthly_revenue.png", dpi=150)
    plt.close(fig)

    mrr = data["mrr_by_month"]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(mrr["month"], mrr["mrr"], color=PALETTE[1], lw=2.4)
    ax.fill_between(mrr["month"], mrr["mrr"], color=PALETTE[1], alpha=0.10)
    ax.set_title("MRR trend")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(money))
    clean_ax(ax)
    fig.tight_layout()
    fig.savefig(OUTPUT_CHARTS_DIR / "mrr_trend.png", dpi=150)
    plt.close(fig)

    plan = data["plan_performance"].sort_values("mrr")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(plan["plan_name"], plan["mrr"], color=PALETTE[:len(plan)])
    ax.set_title("MRR by plan")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(money))
    clean_ax(ax)
    fig.tight_layout()
    fig.savefig(OUTPUT_CHARTS_DIR / "plan_mrr.png", dpi=150)
    plt.close(fig)

    plot_ret = retention.tail(18)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.heatmap(
        plot_ret,
        cmap=sns.light_palette(PALETTE[0], as_cmap=True),
        linewidths=0.35,
        linecolor=PAPER,
        ax=ax,
        cbar_kws={"label": "Retention %"},
    )
    ax.set_title("Subscription cohort retention")
    fig.tight_layout()
    fig.savefig(OUTPUT_CHARTS_DIR / "cohort_retention.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for name, group in segments.groupby("segment"):
        ax.scatter(group["active_users"], group["total_revenue"], s=18, alpha=0.45, label=name)
    ax.set_title("Customer health segments")
    ax.set_xlabel("Active users")
    ax.set_ylabel("Total revenue")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(money))
    ax.legend(frameon=False, fontsize=8)
    clean_ax(ax)
    fig.tight_layout()
    fig.savefig(OUTPUT_CHARTS_DIR / "customer_segments.png", dpi=150)
    plt.close(fig)


def json_safe(value: Any):
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if pd.isna(value):
        return None
    return value


def build_summary(data, kpis, retention, segments, scores, best_k):
    monthly = data["monthly_revenue"].copy()
    monthly["month"] = monthly["month"].dt.strftime("%Y-%m")

    mrr = data["mrr_by_month"].copy()
    mrr["month"] = mrr["month"].dt.strftime("%Y-%m")

    high_risk = (
        data["customer_health"]
        .sort_values(["tickets", "active_users"], ascending=[False, True])
        .head(12)
    )

    return json_safe({
        "kpis": kpis,
        "monthly_revenue": monthly.to_dict(orient="records"),
        "mrr_by_month": mrr.to_dict(orient="records"),
        "plan_performance": data["plan_performance"].to_dict(orient="records"),
        "churn_by_plan": data["churn_by_plan"].to_dict(orient="records"),
        "region_performance": data["region"].to_dict(orient="records"),
        "customer_segments": segment_summary(segments),
        "high_risk_customers": high_risk.to_dict(orient="records"),
        "cohort": cohort_json(retention),
        "silhouette_scores": scores,
        "best_k": best_k,
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "reference_month": REF_MONTH.strftime("%Y-%m"),
        },
    })


def save_outputs(data, retention, segments, summary):
    OUTPUT_CSV_DIR.mkdir(parents=True, exist_ok=True)

    data["customer_health"].to_csv(OUTPUT_CSV_DIR / "customer_health.csv", index=False)
    segments.to_csv(OUTPUT_CSV_DIR / "customer_segments.csv", index=False)
    retention.to_csv(OUTPUT_CSV_DIR / "cohort_retention.csv")

    with SUMMARY_PATH.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, allow_nan=False)


def run():
    engine = db_engine()
    data = prepare(load_data(engine))

    kpi_values = calculate_kpis(data)
    retention = build_cohort(data)
    segments, scores, best_k = customer_segments(data["customer_health"])

    summary = build_summary(data, kpi_values, retention, segments, scores, best_k)

    save_outputs(data, retention, segments, summary)
    save_charts(data, retention, segments)

    print("KPIs")
    for key, value in kpi_values.items():
        print(f"{key}: {value}")

    print(f"\nCSV: {OUTPUT_CSV_DIR}")
    print(f"Charts: {OUTPUT_CHARTS_DIR}")
    print(f"JSON: {SUMMARY_PATH}")


if __name__ == "__main__":
    run()
