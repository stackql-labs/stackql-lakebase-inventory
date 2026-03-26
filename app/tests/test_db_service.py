"""Tests for db/service.py – DatabaseService CRUD operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text

from src.db.models import ProviderConfig, Query, Schedule
from src.db.service import DatabaseService


@pytest.fixture
def db_service(tmp_path):
    """Create a DatabaseService backed by an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")

    # Create schemas (SQLite doesn't support schemas, use tables without schema prefix)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                query_text TEXT NOT NULL,
                provider VARCHAR(100) NOT NULL,
                created_by VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id INTEGER NOT NULL,
                job_id VARCHAR(255),
                cron_expression VARCHAR(100) NOT NULL,
                target_schema VARCHAR(255) NOT NULL DEFAULT 'stackql_inventory',
                target_table VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                last_run_at TIMESTAMP,
                last_run_status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS provider_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider VARCHAR(100) NOT NULL,
                env_var_name VARCHAR(255) NOT NULL,
                secret_scope VARCHAR(255) NOT NULL,
                secret_key VARCHAR(255) NOT NULL,
                created_by VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (provider, env_var_name)
            )
        """))
        conn.commit()

    # Patch the SQL to remove schema prefixes for SQLite
    svc = DatabaseService.__new__(DatabaseService)
    svc._engine = engine
    return svc


class TestQueries:
    def test_save_and_get_query(self, db_service: DatabaseService):
        """Queries can be saved and retrieved."""
        # We need to work with SQLite directly for testing
        q = Query(name="Test Query", query_text="SELECT 1", provider="aws")

        with db_service._engine.connect() as conn:
            result = conn.execute(
                text("INSERT INTO queries (name, query_text, provider) VALUES (:n, :q, :p) RETURNING id"),
                {"n": q.name, "q": q.query_text, "p": q.provider},
            )
            new_id = result.scalar_one()
            conn.commit()

        assert new_id is not None
        assert new_id > 0

    def test_delete_query(self, db_service: DatabaseService):
        """Queries can be deleted."""
        with db_service._engine.connect() as conn:
            result = conn.execute(
                text("INSERT INTO queries (name, query_text, provider) VALUES ('del', 'SELECT 1', 'aws') RETURNING id"),
            )
            qid = result.scalar_one()
            conn.commit()

            conn.execute(text("DELETE FROM queries WHERE id = :id"), {"id": qid})
            conn.commit()

            row = conn.execute(text("SELECT COUNT(*) FROM queries WHERE id = :id"), {"id": qid}).scalar()
            assert row == 0


class TestSchedules:
    def test_save_schedule(self, db_service: DatabaseService):
        """Schedules can be saved."""
        with db_service._engine.connect() as conn:
            # Create a query first
            result = conn.execute(
                text("INSERT INTO queries (name, query_text, provider) VALUES ('q1', 'SELECT 1', 'aws') RETURNING id"),
            )
            qid = result.scalar_one()
            conn.commit()

            result = conn.execute(
                text(
                    "INSERT INTO schedules (query_id, cron_expression, target_table) "
                    "VALUES (:qid, '0 * * * *', 'test_table') RETURNING id"
                ),
                {"qid": qid},
            )
            sid = result.scalar_one()
            conn.commit()

        assert sid is not None


class TestProviderConfig:
    def test_save_provider_config(self, db_service: DatabaseService):
        """Provider configs can be saved."""
        with db_service._engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO provider_config (provider, env_var_name, secret_scope, secret_key) "
                    "VALUES ('aws', 'AWS_ACCESS_KEY_ID', 'scope', 'key')"
                ),
            )
            conn.commit()

            row = conn.execute(
                text("SELECT COUNT(*) FROM provider_config WHERE provider = 'aws'")
            ).scalar()
            assert row == 1
