"""Shared pytest fixtures for StackQL Cloud Inventory tests."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Ensure local dev mode for all tests
os.environ["STACKQL_LOCAL_DEV"] = "true"


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """A sample DataFrame mimicking StackQL query output."""
    return pd.DataFrame({
        "instance_id": ["i-001", "i-002", "i-003"],
        "instance_type": ["t3.micro", "t3.small", "m5.large"],
        "state": ["running", "stopped", "running"],
        "region": ["us-east-1", "us-east-1", "us-west-2"],
    })


@pytest.fixture
def mock_stackql(sample_dataframe: pd.DataFrame):
    """Mock pystackql.StackQL to return sample data."""
    mock = MagicMock()
    mock.execute.return_value = sample_dataframe.to_dict("records")
    with patch("pystackql.StackQL", return_value=mock):
        yield mock


@pytest.fixture
def mock_workspace_client():
    """Mock databricks.sdk.WorkspaceClient."""
    mock = MagicMock()
    mock.secrets.get_secret.return_value = MagicMock(value="mock-secret-value")
    with patch("databricks.sdk.WorkspaceClient", return_value=mock):
        yield mock


@pytest.fixture
def mock_db_engine():
    """Mock SQLAlchemy engine with in-memory results."""
    from sqlalchemy import create_engine
    engine = create_engine("sqlite:///:memory:")
    return engine
