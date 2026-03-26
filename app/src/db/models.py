"""Dataclass models for the StackQL Cloud Inventory application."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Query:
    """A saved StackQL query."""

    name: str
    query_text: str
    provider: str
    description: str | None = None
    created_by: str | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Schedule:
    """A scheduled inventory job tied to a saved query."""

    query_id: int
    cron_expression: str
    target_table: str
    target_schema: str = "stackql_inventory"
    job_id: str | None = None
    is_active: bool = True
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ProviderConfig:
    """Maps a provider env var to a Databricks secret scope/key."""

    provider: str
    env_var_name: str
    secret_scope: str
    secret_key: str
    created_by: str | None = None
    id: int | None = None
    created_at: datetime | None = None
