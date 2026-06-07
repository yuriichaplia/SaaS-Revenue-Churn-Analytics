CREATE TABLE IF NOT EXISTS plans (
    plan_id TEXT PRIMARY KEY,
    plan_name TEXT NOT NULL,
    monthly_price NUMERIC(10, 2) NOT NULL,
    user_limit INTEGER NOT NULL,
    support_level TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    industry TEXT NOT NULL,
    company_size TEXT NOT NULL,
    region TEXT NOT NULL,
    signup_date DATE NOT NULL,
    acquisition_channel TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    plan_id TEXT NOT NULL REFERENCES plans(plan_id),
    start_date DATE NOT NULL,
    end_date DATE,
    status TEXT NOT NULL,
    billing_cycle TEXT NOT NULL,
    mrr NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    payment_date DATE NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    payment_status TEXT NOT NULL,
    payment_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_usage (
    usage_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    usage_month DATE NOT NULL,
    active_users INTEGER NOT NULL,
    logins INTEGER NOT NULL,
    feature_events INTEGER NOT NULL,
    storage_gb NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    created_date DATE NOT NULL,
    priority TEXT NOT NULL,
    category TEXT NOT NULL,
    resolution_days INTEGER NOT NULL,
    satisfaction_score INTEGER
);

CREATE INDEX idx_subscriptions_customer_id ON subscriptions(customer_id);
CREATE INDEX idx_payments_customer_id ON payments(customer_id);
CREATE INDEX idx_product_usage_customer_month ON product_usage(customer_id, usage_month);
CREATE INDEX idx_support_tickets_customer_id ON support_tickets(customer_id);
