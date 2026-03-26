"""Tests for services/query_service.py – StackQL query execution."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.db.models import ProviderConfig
from src.services.query_service import QueryService


@pytest.fixture
def mock_db_service():
    svc = MagicMock()
    svc.get_provider_config.return_value = [
        ProviderConfig(
            provider="aws",
            env_var_name="AWS_ACCESS_KEY_ID",
            secret_scope="stackql-inventory",
            secret_key="aws-access-key",
        ),
    ]
    return svc


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "instance_id": ["i-001", "i-002"],
        "state": ["running", "stopped"],
    })


class TestQueryService:
    @patch.dict(os.environ, {"STACKQL_LOCAL_DEV": "true", "AWS_ACCESS_KEY_ID": "test"})
    def test_execute_returns_dataframe(self, mock_db_service, sample_df):
        """execute() returns a DataFrame on success."""
        mock_stackql_cls = MagicMock()
        mock_stackql_instance = MagicMock()
        mock_stackql_instance.execute.return_value = sample_df.to_dict("records")
        mock_stackql_cls.return_value = mock_stackql_instance

        mock_pystackql = MagicMock()
        mock_pystackql.StackQL = mock_stackql_cls

        with patch.dict(sys.modules, {"pystackql": mock_pystackql}):
            svc = QueryService(mock_db_service)
            result = svc.execute("SELECT * FROM aws.ec2.instances WHERE region = 'us-east-1'", "aws")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    @patch.dict(os.environ, {"STACKQL_LOCAL_DEV": "true"})
    def test_cleanup_env_always_runs(self, mock_db_service):
        """Environment variables are cleaned up even on failure."""
        svc = QueryService(mock_db_service)
        injected = ["TEST_KEY_1", "TEST_KEY_2"]
        os.environ["TEST_KEY_1"] = "val1"
        os.environ["TEST_KEY_2"] = "val2"

        svc._cleanup_env(injected)

        assert "TEST_KEY_1" not in os.environ
        assert "TEST_KEY_2" not in os.environ

    @patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "local-key"})
    def test_inject_credentials_verifies_env(self, mock_db_service):
        """Credentials are verified from env vars."""
        svc = QueryService(mock_db_service)
        verified = svc._inject_credentials("aws")
        assert "AWS_ACCESS_KEY_ID" in verified

    def test_inject_credentials_missing_env(self, mock_db_service):
        """Missing env var returns empty list but does not error."""
        os.environ.pop("AWS_ACCESS_KEY_ID", None)
        svc = QueryService(mock_db_service)
        verified = svc._inject_credentials("aws")
        assert verified == []

    def test_extract_empty_provider_config(self):
        """No error when provider has no config entries."""
        mock_db = MagicMock()
        mock_db.get_provider_config.return_value = []
        svc = QueryService(mock_db)
        injected = svc._inject_credentials("unknown_provider")
        assert injected == []
