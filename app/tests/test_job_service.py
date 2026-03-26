"""Tests for services/job_service.py – Databricks Jobs SDK wrapper."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from src.db.models import Query, Schedule


@pytest.fixture(autouse=True)
def mock_databricks_sdk():
    """Mock the entire databricks.sdk module to avoid cryptography import issues."""
    mock_sdk = MagicMock()
    mock_ws = MagicMock()
    mock_sdk.WorkspaceClient.return_value = mock_ws

    # Mock job service sub-modules
    mock_jobs_module = MagicMock()
    mock_sdk.service.jobs = mock_jobs_module

    modules = {
        "databricks": MagicMock(),
        "databricks.sdk": mock_sdk,
        "databricks.sdk.service": MagicMock(),
        "databricks.sdk.service.jobs": mock_jobs_module,
    }

    with patch.dict(sys.modules, modules):
        yield mock_ws


class TestJobService:
    def test_create_inventory_job(self, mock_databricks_sdk):
        """create_inventory_job returns a job_id string."""
        mock_databricks_sdk.jobs.create.return_value = MagicMock(job_id=12345)

        from src.services.job_service import JobService
        svc = JobService()

        query = Query(id=1, name="Test", query_text="SELECT 1", provider="aws")
        schedule = Schedule(
            query_id=1,
            cron_expression="0 */6 * * *",
            target_table="test_table",
        )

        job_id = svc.create_inventory_job(query, schedule)
        assert job_id == "12345"

    def test_delete_inventory_job(self, mock_databricks_sdk):
        """delete_inventory_job calls the SDK delete method."""
        from src.services.job_service import JobService
        svc = JobService()
        svc.delete_inventory_job("12345")
        mock_databricks_sdk.jobs.delete.assert_called_once_with(job_id=12345)

    def test_get_job_run_status_no_runs(self, mock_databricks_sdk):
        """get_job_run_status returns None when there are no runs."""
        mock_databricks_sdk.jobs.list_runs.return_value = iter([])

        from src.services.job_service import JobService
        svc = JobService()
        result = svc.get_job_run_status("12345")
        assert result is None

    def test_pause_inventory_job(self, mock_databricks_sdk):
        """pause_inventory_job updates the job schedule to PAUSED."""
        mock_job = MagicMock()
        mock_job.settings.schedule.quartz_cron_expression = "0 */6 * * *"
        mock_databricks_sdk.jobs.get.return_value = mock_job

        from src.services.job_service import JobService
        svc = JobService()
        svc.pause_inventory_job("12345")
        mock_databricks_sdk.jobs.update.assert_called_once()
