-- StackQL Cloud Inventory - Lakebase Schema Initialisation
-- Run against the Lakebase Postgres instance to create application metadata tables.

-- Schema for app metadata (queries, schedules, provider config)
CREATE SCHEMA IF NOT EXISTS stackql_app;

-- Schema for cloud inventory results (tables created dynamically by jobs)
CREATE SCHEMA IF NOT EXISTS stackql_inventory;

-- Saved StackQL queries
CREATE TABLE IF NOT EXISTS stackql_app.queries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    query_text TEXT NOT NULL,
    provider VARCHAR(100) NOT NULL,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Scheduled inventory jobs
CREATE TABLE IF NOT EXISTS stackql_app.schedules (
    id SERIAL PRIMARY KEY,
    query_id INTEGER NOT NULL REFERENCES stackql_app.queries(id) ON DELETE CASCADE,
    job_id VARCHAR(255),
    cron_expression VARCHAR(100) NOT NULL,
    target_schema VARCHAR(255) NOT NULL DEFAULT 'stackql_inventory',
    target_table VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_run_status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Provider credential mappings (env var -> Databricks secret)
CREATE TABLE IF NOT EXISTS stackql_app.provider_config (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(100) NOT NULL,
    env_var_name VARCHAR(255) NOT NULL,
    secret_scope VARCHAR(255) NOT NULL,
    secret_key VARCHAR(255) NOT NULL,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (provider, env_var_name)
);
