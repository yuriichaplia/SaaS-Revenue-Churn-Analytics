from __future__ import annotations

import io
import os
import random
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv


load_dotenv()

SEED = 42
START = pd.Timestamp("2022-01-01")
END = pd.Timestamp("2024-12-31")
MONTHS = pd.date_range(START, END, freq="MS")
N_CUSTOMERS = 1800

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_CSV_DIR = BASE_DIR / "output_csv"

PLANS = [
    {"plan_id": "P_FREE", "plan_name": "Free", "monthly_price": 0.00, "user_limit": 3, "support_level": "Community"},
    {"plan_id": "P_STARTER", "plan_name": "Starter", "monthly_price": 29.00, "user_limit": 10, "support_level": "Email"},
    {"plan_id": "P_PRO", "plan_name": "Pro", "monthly_price": 79.00, "user_limit": 50, "support_level": "Priority"},
    {"plan_id": "P_BUSINESS", "plan_name": "Business", "monthly_price": 199.00, "user_limit": 200, "support_level": "Dedicated"},
    {"plan_id": "P_ENTERPRISE", "plan_name": "Enterprise", "monthly_price": 599.00, "user_limit": 1000, "support_level": "Dedicated"},
]

INDUSTRIES = ["SaaS", "Finance", "Healthcare", "Education", "Retail", "Manufacturing", "Media", "Consulting"]
SIZES = ["1-10", "11-50", "51-200", "201-1000", "1000+"]
REGIONS = ["North America", "Europe", "Asia-Pacific", "Latin America"]
CHANNELS = ["Organic", "Paid Search", "Referral", "Outbound", "Partner"]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]
TICKET_CATEGORIES = ["Billing", "Technical", "Account", "Feature Request", "Bug"]


def db_connection():
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

    return psycopg2.connect(
        user=os.getenv("DB_USER"),
        host=os.getenv("DB_HOST"),
        database=database,
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )


def reset_seed():
    random.seed(SEED)
    np.random.seed(SEED)


def weighted_choice(values, weights):
    return random.choices(values, weights=weights, k=1)[0]


def random_signup_date():
    days = (END - START).days
    return START + pd.Timedelta(days=random.randint(0, days))


def build_plans():
    return pd.DataFrame(PLANS)


def build_customers():
    rows = []

    for i in range(1, N_CUSTOMERS + 1):
        size = weighted_choice(SIZES, [32, 30, 22, 12, 4])
        channel = weighted_choice(CHANNELS, [35, 22, 20, 13, 10])

        rows.append({
            "customer_id": f"C{i:05d}",
            "company_name": f"Company {i}",
            "industry": random.choice(INDUSTRIES),
            "company_size": size,
            "region": weighted_choice(REGIONS, [42, 30, 20, 8]),
            "signup_date": random_signup_date().date().isoformat(),
            "acquisition_channel": channel,
        })

    return pd.DataFrame(rows)


def initial_plan(company_size):
    if company_size == "1-10":
        return weighted_choice(["P_FREE", "P_STARTER", "P_PRO"], [45, 40, 15])
    if company_size == "11-50":
        return weighted_choice(["P_STARTER", "P_PRO", "P_BUSINESS"], [40, 48, 12])
    if company_size == "51-200":
        return weighted_choice(["P_PRO", "P_BUSINESS", "P_ENTERPRISE"], [45, 42, 13])
    if company_size == "201-1000":
        return weighted_choice(["P_BUSINESS", "P_ENTERPRISE"], [60, 40])
    return weighted_choice(["P_BUSINESS", "P_ENTERPRISE"], [25, 75])


def plan_price(plan_id):
    return next(plan["monthly_price"] for plan in PLANS if plan["plan_id"] == plan_id)


def churn_probability(plan_id, channel, usage_score, ticket_pressure):
    base = {
        "P_FREE": 0.055,
        "P_STARTER": 0.040,
        "P_PRO": 0.028,
        "P_BUSINESS": 0.020,
        "P_ENTERPRISE": 0.014,
    }[plan_id]

    if channel == "Paid Search":
        base += 0.012
    if channel == "Referral":
        base -= 0.007

    base += max(0, 0.025 - usage_score * 0.020)
    base += ticket_pressure * 0.006

    return min(max(base, 0.004), 0.12)


def build_subscription_history(customers):
    subscriptions = []
    payments = []
    usage = []
    tickets = []

    sub_no = 1
    payment_no = 1
    usage_no = 1
    ticket_no = 1

    for _, customer in customers.iterrows():
        signup = pd.Timestamp(customer["signup_date"]).to_period("M").to_timestamp()
        plan_id = initial_plan(customer["company_size"])
        current_start = signup
        active = True

        ticket_pressure = np.random.poisson(0.7)
        usage_score = random.uniform(0.25, 1.15)

        for month in MONTHS:
            if month < signup or not active:
                continue

            age_months = max(1, (month.to_period("M") - signup.to_period("M")).n + 1)

            if age_months > 3 and random.random() < 0.018:
                if plan_id == "P_STARTER":
                    plan_id = "P_PRO"
                elif plan_id == "P_PRO":
                    plan_id = "P_BUSINESS"
                elif plan_id == "P_BUSINESS" and random.random() < 0.22:
                    plan_id = "P_ENTERPRISE"

            if age_months > 5 and random.random() < 0.010:
                if plan_id == "P_ENTERPRISE":
                    plan_id = "P_BUSINESS"
                elif plan_id == "P_BUSINESS":
                    plan_id = "P_PRO"
                elif plan_id == "P_PRO":
                    plan_id = "P_STARTER"

            price = plan_price(plan_id)
            churned_this_month = age_months > 2 and random.random() < churn_probability(
                plan_id, customer["acquisition_channel"], usage_score, ticket_pressure
            )

            status = "Churned" if churned_this_month else "Active"
            end_date = (month + pd.offsets.MonthEnd(0)).date().isoformat() if churned_this_month else None

            subscriptions.append({
                "subscription_id": f"S{sub_no:06d}",
                "customer_id": customer["customer_id"],
                "plan_id": plan_id,
                "start_date": current_start.date().isoformat(),
                "end_date": end_date,
                "status": status,
                "billing_cycle": weighted_choice(["Monthly", "Annual"], [82, 18]),
                "mrr": price,
            })

            payment_status = weighted_choice(["Paid", "Failed", "Refunded"], [95, 4, 1])
            payments.append({
                "payment_id": f"PAY{payment_no:07d}",
                "subscription_id": f"S{sub_no:06d}",
                "customer_id": customer["customer_id"],
                "payment_date": (month + pd.Timedelta(days=random.randint(0, 25))).date().isoformat(),
                "amount": price if payment_status == "Paid" else 0,
                "payment_status": payment_status,
                "payment_type": "Subscription",
            })

            active_users = max(1, int(np.random.normal(usage_score * 28, 9)))
            logins = max(1, int(active_users * np.random.normal(9, 2)))
            feature_events = max(1, int(logins * np.random.normal(5, 1.5)))
            storage = max(0.5, round(active_users * random.uniform(0.4, 2.2), 2))

            usage.append({
                "usage_id": f"U{usage_no:08d}",
                "customer_id": customer["customer_id"],
                "usage_month": month.date().isoformat(),
                "active_users": active_users,
                "logins": logins,
                "feature_events": feature_events,
                "storage_gb": storage,
            })

            if random.random() < 0.16 + ticket_pressure * 0.04:
                priority = weighted_choice(PRIORITIES, [45, 35, 15, 5])
                tickets.append({
                    "ticket_id": f"T{ticket_no:07d}",
                    "customer_id": customer["customer_id"],
                    "created_date": (month + pd.Timedelta(days=random.randint(0, 27))).date().isoformat(),
                    "priority": priority,
                    "category": random.choice(TICKET_CATEGORIES),
                    "resolution_days": max(1, int(np.random.exponential(2.7))),
                    "satisfaction_score": random.choice([1, 2, 3, 4, 5]) if random.random() < 0.82 else None,
                })
                ticket_no += 1

            sub_no += 1
            payment_no += 1
            usage_no += 1
            usage_score = max(0.05, min(1.6, usage_score + np.random.normal(0.01, 0.09)))

            if churned_this_month:
                active = False

    return (
        pd.DataFrame(subscriptions),
        pd.DataFrame(payments),
        pd.DataFrame(usage),
        pd.DataFrame(tickets),
    )


def copy_dataframe(conn, df, table_name):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    columns = ", ".join(df.columns)
    copy_sql = f"COPY {table_name} ({columns}) FROM STDIN WITH CSV"

    with conn.cursor() as cursor:
        cursor.copy_expert(copy_sql, buffer)


def clear_tables(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            TRUNCATE TABLE
                support_tickets,
                product_usage,
                payments,
                subscriptions,
                customers,
                plans
            RESTART IDENTITY CASCADE;
        """)


def load_to_postgres(tables):
    with db_connection() as conn:
        clear_tables(conn)
        copy_dataframe(conn, tables["plans"], "plans")
        copy_dataframe(conn, tables["customers"], "customers")
        copy_dataframe(conn, tables["subscriptions"], "subscriptions")
        copy_dataframe(conn, tables["payments"], "payments")
        copy_dataframe(conn, tables["product_usage"], "product_usage")
        copy_dataframe(conn, tables["support_tickets"], "support_tickets")
        conn.commit()


def save_raw_csv(tables):
    OUTPUT_CSV_DIR.mkdir(parents=True, exist_ok=True)

    for name, df in tables.items():
        df.to_csv(OUTPUT_CSV_DIR / f"raw_{name}.csv", index=False)


def generate_tables():
    reset_seed()

    plans = build_plans()
    customers = build_customers()
    subscriptions, payments, usage, tickets = build_subscription_history(customers)

    tickets["satisfaction_score"] = (
        tickets["satisfaction_score"]
        .astype("Int64")
        .astype(str)
        .replace("<NA>", "")
    )

    return {
        "plans": plans,
        "customers": customers,
        "subscriptions": subscriptions,
        "payments": payments,
        "product_usage": usage,
        "support_tickets": tickets,
    }


def run(save_csv=False):
    tables = generate_tables()

    for name, df in tables.items():
        print(f"{name}: {len(df):,}")

    load_to_postgres(tables)

    if save_csv:
        save_raw_csv(tables)
        print(f"Raw CSV files saved to {OUTPUT_CSV_DIR}")

    print("Data loaded into PostgreSQL")


if __name__ == "__main__":
    run(save_csv=False)
