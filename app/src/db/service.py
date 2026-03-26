"""Database service – all Lakebase CRUD operations.

Uses SQLAlchemy 2.x with raw SQL via text(). Returns dataclass models.
No raw SQL should exist outside this module.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.db.models import ProviderConfig, Query, Schedule

logger = logging.getLogger(__name__)


def _build_connection_url() -> str:
    host = os.environ.get("LAKEBASE_HOST", "localhost")
    port = os.environ.get("LAKEBASE_PORT", "5432")
    database = os.environ.get("LAKEBASE_DATABASE", "postgres")
    user = os.environ.get("LAKEBASE_USER", "postgres")
    password = os.environ.get("LAKEBASE_PASSWORD", "postgres")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def _get_engine() -> Engine:
    url = _build_connection_url()
    return create_engine(url, pool_pre_ping=True)


class DatabaseService:
    """Encapsulates all Lakebase database operations."""

    def __init__(self, engine: Engine | None = None) -> None:
        if engine is not None:
            self._engine = engine
        else:
            try:
                self._engine = _get_engine()
                # Verify connectivity
                with self._engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to connect to Lakebase: {exc}. "
                    "Check LAKEBASE_* environment variables."
                ) from exc

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_queries(self) -> list[Query]:
        with Session(self._engine) as session:
            rows = session.execute(
                text("SELECT id, name, description, query_text, provider, created_by, created_at, updated_at FROM stackql_app.queries ORDER BY updated_at DESC")
            ).fetchall()
            return [
                Query(
                    id=r.id, name=r.name, description=r.description,
                    query_text=r.query_text, provider=r.provider,
                    created_by=r.created_by, created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]

    def get_query(self, query_id: int) -> Query | None:
        with Session(self._engine) as session:
            row = session.execute(
                text("SELECT id, name, description, query_text, provider, created_by, created_at, updated_at FROM stackql_app.queries WHERE id = :id"),
                {"id": query_id},
            ).fetchone()
            if row is None:
                return None
            return Query(
                id=row.id, name=row.name, description=row.description,
                query_text=row.query_text, provider=row.provider,
                created_by=row.created_by, created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def save_query(self, query: Query) -> int:
        with Session(self._engine) as session:
            result = session.execute(
                text(
                    "INSERT INTO stackql_app.queries (name, description, query_text, provider, created_by) "
                    "VALUES (:name, :description, :query_text, :provider, :created_by) RETURNING id"
                ),
                {
                    "name": query.name,
                    "description": query.description,
                    "query_text": query.query_text,
                    "provider": query.provider,
                    "created_by": query.created_by,
                },
            )
            new_id = result.scalar_one()
            session.commit()
            return new_id

    def update_query(self, query_id: int, query: Query) -> None:
        with Session(self._engine) as session:
            session.execute(
                text(
                    "UPDATE stackql_app.queries SET name = :name, description = :description, "
                    "query_text = :query_text, provider = :provider, updated_at = NOW() WHERE id = :id"
                ),
                {
                    "id": query_id,
                    "name": query.name,
                    "description": query.description,
                    "query_text": query.query_text,
                    "provider": query.provider,
                },
            )
            session.commit()

    def delete_query(self, query_id: int) -> None:
        with Session(self._engine) as session:
            session.execute(
                text("DELETE FROM stackql_app.queries WHERE id = :id"),
                {"id": query_id},
            )
            session.commit()

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    def get_schedules(self) -> list[Schedule]:
        with Session(self._engine) as session:
            rows = session.execute(
                text(
                    "SELECT id, query_id, job_id, cron_expression, target_schema, target_table, "
                    "is_active, last_run_at, last_run_status, created_at, updated_at "
                    "FROM stackql_app.schedules ORDER BY created_at DESC"
                )
            ).fetchall()
            return [
                Schedule(
                    id=r.id, query_id=r.query_id, job_id=r.job_id,
                    cron_expression=r.cron_expression, target_schema=r.target_schema,
                    target_table=r.target_table, is_active=r.is_active,
                    last_run_at=r.last_run_at, last_run_status=r.last_run_status,
                    created_at=r.created_at, updated_at=r.updated_at,
                )
                for r in rows
            ]

    def save_schedule(self, schedule: Schedule) -> int:
        with Session(self._engine) as session:
            result = session.execute(
                text(
                    "INSERT INTO stackql_app.schedules "
                    "(query_id, job_id, cron_expression, target_schema, target_table, is_active) "
                    "VALUES (:query_id, :job_id, :cron_expression, :target_schema, :target_table, :is_active) "
                    "RETURNING id"
                ),
                {
                    "query_id": schedule.query_id,
                    "job_id": schedule.job_id,
                    "cron_expression": schedule.cron_expression,
                    "target_schema": schedule.target_schema,
                    "target_table": schedule.target_table,
                    "is_active": schedule.is_active,
                },
            )
            new_id = result.scalar_one()
            session.commit()
            return new_id

    def update_schedule(self, schedule_id: int, schedule: Schedule) -> None:
        with Session(self._engine) as session:
            session.execute(
                text(
                    "UPDATE stackql_app.schedules SET query_id = :query_id, job_id = :job_id, "
                    "cron_expression = :cron_expression, target_schema = :target_schema, "
                    "target_table = :target_table, is_active = :is_active, "
                    "last_run_at = :last_run_at, last_run_status = :last_run_status, "
                    "updated_at = NOW() WHERE id = :id"
                ),
                {
                    "id": schedule_id,
                    "query_id": schedule.query_id,
                    "job_id": schedule.job_id,
                    "cron_expression": schedule.cron_expression,
                    "target_schema": schedule.target_schema,
                    "target_table": schedule.target_table,
                    "is_active": schedule.is_active,
                    "last_run_at": schedule.last_run_at,
                    "last_run_status": schedule.last_run_status,
                },
            )
            session.commit()

    def delete_schedule(self, schedule_id: int) -> None:
        with Session(self._engine) as session:
            session.execute(
                text("DELETE FROM stackql_app.schedules WHERE id = :id"),
                {"id": schedule_id},
            )
            session.commit()

    # ------------------------------------------------------------------
    # Provider Config
    # ------------------------------------------------------------------

    def get_provider_config(self) -> list[ProviderConfig]:
        with Session(self._engine) as session:
            rows = session.execute(
                text(
                    "SELECT id, provider, env_var_name, secret_scope, secret_key, created_by, created_at "
                    "FROM stackql_app.provider_config ORDER BY provider, env_var_name"
                )
            ).fetchall()
            return [
                ProviderConfig(
                    id=r.id, provider=r.provider, env_var_name=r.env_var_name,
                    secret_scope=r.secret_scope, secret_key=r.secret_key,
                    created_by=r.created_by, created_at=r.created_at,
                )
                for r in rows
            ]

    def save_provider_config(self, config: ProviderConfig) -> None:
        with Session(self._engine) as session:
            session.execute(
                text(
                    "INSERT INTO stackql_app.provider_config "
                    "(provider, env_var_name, secret_scope, secret_key, created_by) "
                    "VALUES (:provider, :env_var_name, :secret_scope, :secret_key, :created_by) "
                    "ON CONFLICT (provider, env_var_name) DO UPDATE SET "
                    "secret_scope = EXCLUDED.secret_scope, secret_key = EXCLUDED.secret_key"
                ),
                {
                    "provider": config.provider,
                    "env_var_name": config.env_var_name,
                    "secret_scope": config.secret_scope,
                    "secret_key": config.secret_key,
                    "created_by": config.created_by,
                },
            )
            session.commit()

    def delete_provider_config(self, config_id: int) -> None:
        with Session(self._engine) as session:
            session.execute(
                text("DELETE FROM stackql_app.provider_config WHERE id = :id"),
                {"id": config_id},
            )
            session.commit()

    # ------------------------------------------------------------------
    # Inventory browsing
    # ------------------------------------------------------------------

    def get_inventory_tables(self) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            rows = session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'stackql_inventory' AND table_type = 'BASE TABLE' "
                    "ORDER BY table_name"
                )
            ).fetchall()
            result: list[dict[str, Any]] = []
            for r in rows:
                count_row = session.execute(
                    text(f"SELECT COUNT(*) as cnt FROM stackql_inventory.{r.table_name}")
                ).fetchone()
                # Check if a materialised view exists
                mv_row = session.execute(
                    text(
                        "SELECT COUNT(*) as cnt FROM information_schema.tables "
                        "WHERE table_schema = 'stackql_inventory' AND table_name = :mv_name"
                    ),
                    {"mv_name": f"{r.table_name}_mv"},
                ).fetchone()
                result.append({
                    "table_name": r.table_name,
                    "row_count": count_row.cnt if count_row else 0,
                    "has_materialised_view": (mv_row.cnt if mv_row else 0) > 0,
                })
            return result

    def get_inventory_preview(self, table_name: str, limit: int = 100) -> pd.DataFrame:
        # Sanitise table name to prevent injection
        if not table_name.isidentifier():
            raise ValueError(f"Invalid table name: {table_name}")
        with self._engine.connect() as conn:
            return pd.read_sql(
                text(f"SELECT * FROM stackql_inventory.{table_name} LIMIT :limit"),
                conn,
                params={"limit": limit},
            )

    def refresh_materialised_view(self, view_name: str) -> None:
        if not view_name.isidentifier():
            raise ValueError(f"Invalid view name: {view_name}")
        with Session(self._engine) as session:
            session.execute(text(f"REFRESH MATERIALIZED VIEW stackql_inventory.{view_name}"))
            session.commit()
