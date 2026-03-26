"""Tests for services/job_service.py – StackQL-based job management."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.db.models import Query, Schedule


@pytest.fixture
def mock_stackql():
    """Mock pystackql.StackQL for job service tests."""
    mock_instance = MagicMock()
    mock_instance.execute.return_value = [{"job_id": "12345"}]
    mock_instance.executeStmt.return_value = [{"message": "ok"}]

    mock_pystackql = MagicMock()
    mock_pystackql.StackQL.return_value = mock_instance

    with patch.dict(sys.modules, {"pystackql": mock_pystackql}):
        with patch.dict(os.environ, {"DATABRICKS_HOST": "https://dbc-test-1234.cloud.databricks.com"}):
            yield mock_instance


class TestJobService:
    def test_create_inventory_job(self, mock_stackql):
        """create_inventory_job returns a job_id string."""
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
        mock_stackql.executeStmt.assert_called_once()

    def test_delete_inventory_job(self, mock_stackql):
        """delete_inventory_job calls StackQL DELETE."""
        from src.services.job_service import JobService
        svc = JobService()
        svc.delete_inventory_job("12345")
        mock_stackql.executeStmt.assert_called_once()
        assert "DELETE" in mock_stackql.executeStmt.call_args[0][0]

    def test_get_job_run_status_no_runs(self, mock_stackql):
        """get_job_run_status returns None when there are no runs."""
        mock_stackql.execute.return_value = []

        from src.services.job_service import JobService
        svc = JobService()
        result = svc.get_job_run_status("12345")
        assert result is None

    def test_pause_inventory_job(self, mock_stackql):
        """pause_inventory_job updates the job schedule to PAUSED."""
        mock_stackql.execute.return_value = [{"schedule": '{"quartz_cron_expression": "0 */6 * * *", "timezone_id": "UTC", "pause_status": "UNPAUSED"}'}]

        from src.services.job_service import JobService
        svc = JobService()
        svc.pause_inventory_job("12345")
        mock_stackql.executeStmt.assert_called_once()
        assert "PAUSED" in mock_stackql.executeStmt.call_args[0][0]

    def test_deployment_name_extraction(self, mock_stackql):
        """deployment_name is extracted from DATABRICKS_HOST."""
        from src.services.job_service import JobService
        svc = JobService()
        assert svc._deployment_name == "dbc-test-1234"
