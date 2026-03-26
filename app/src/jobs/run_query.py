"""Standalone job runner script executed by Databricks Jobs.

Usage:
    python -m app.src.jobs.run_query --query-id 1 --target-schema stackql_inventory --target-table my_table
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _build_connection_url() -> str:
    host = os.environ["LAKEBASE_HOST"]
    port = os.environ.get("LAKEBASE_PORT", "5432")
    database = os.environ["LAKEBASE_DATABASE"]
    user = os.environ["LAKEBASE_USER"]
    password = os.environ["LAKEBASE_PASSWORD"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def run(query_id: int, target_schema: str, target_table: str) -> None:
    """Execute a saved query and write results to Lakebase."""
    engine = create_engine(_build_connection_url(), pool_pre_ping=True)

    # 1. Load query text
    with Session(engine) as session:
        row = session.execute(
            text("SELECT query_text, provider FROM stackql_app.queries WHERE id = :id"),
            {"id": query_id},
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Query ID {query_id} not found in stackql_app.queries")
        query_text = row.query_text
        provider = row.provider

    logger.info("Loaded query %d (provider=%s)", query_id, provider)

    # 2. Provider credentials should already be injected by job env config
    # 3. Execute via pystackql
    try:
        from pystackql import StackQL
        stackql = StackQL(download_dir="/tmp/stackql")
    except Exception as exc:
        _update_schedule_status(engine, query_id, "FAILED")
        raise RuntimeError(f"Failed to initialise StackQL: {exc}") from exc

    result = stackql.execute(query_text)

    if isinstance(result, pd.DataFrame):
        df = result
    elif isinstance(result, list):
        df = pd.DataFrame(result)
    else:
        df = pd.DataFrame(result) if result else pd.DataFrame()

    if not df.empty and "error" in df.columns:
        error_msg = df["error"].iloc[0]
        if error_msg:
            _update_schedule_status(engine, query_id, "FAILED")
            raise RuntimeError(f"StackQL query error: {error_msg}")

    logger.info("Query returned %d rows", len(df))

    # 4. Write results to target table (replace semantics)
    with engine.connect() as conn:
        # Ensure schema exists
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {target_schema}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {target_schema}.{target_table}"))
        conn.commit()

    df.to_sql(target_table, engine, schema=target_schema, if_exists="replace", index=False)
    logger.info("Wrote results to %s.%s", target_schema, target_table)

    # 5. Refresh materialised view if it exists
    mv_name = f"{target_table}_mv"
    with Session(engine) as session:
        mv_exists = session.execute(
            text(
                "SELECT COUNT(*) as cnt FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :mv"
            ),
            {"schema": target_schema, "mv": mv_name},
        ).scalar()
        if mv_exists and mv_exists > 0:
            session.execute(text(f"REFRESH MATERIALIZED VIEW {target_schema}.{mv_name}"))
            session.commit()
            logger.info("Refreshed materialised view %s.%s", target_schema, mv_name)

    # 6. Update schedule status
    _update_schedule_status(engine, query_id, "SUCCESS")


def _update_schedule_status(engine, query_id: int, status: str) -> None:
    """Update last_run_at and last_run_status for schedules linked to this query."""
    with Session(engine) as session:
        session.execute(
            text(
                "UPDATE stackql_app.schedules SET last_run_at = :now, last_run_status = :status, "
                "updated_at = :now WHERE query_id = :query_id"
            ),
            {
                "now": datetime.now(timezone.utc),
                "status": status,
                "query_id": query_id,
            },
        )
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="StackQL Inventory Job Runner")
    parser.add_argument("--query-id", type=int, required=True)
    parser.add_argument("--target-schema", type=str, default="stackql_inventory")
    parser.add_argument("--target-table", type=str, required=True)
    args = parser.parse_args()

    try:
        run(args.query_id, args.target_schema, args.target_table)
    except Exception:
        logger.exception("Job failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
