"""Tests for services/ai_service.py – Anthropic API wrapper."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.services.ai_service import AIService


class TestAIService:
    def test_extract_sql_from_response_with_sql(self):
        """extract_sql_from_response extracts SQL from fenced code blocks."""
        response = (
            "Here's a query:\n\n"
            "```sql\n"
            "SELECT instance_id, state\n"
            "FROM aws.ec2.instances\n"
            "WHERE region = 'us-east-1'\n"
            "```\n\n"
            "This will list all EC2 instances."
        )
        sql = AIService.extract_sql_from_response(response)
        assert sql is not None
        assert "SELECT instance_id" in sql
        assert "```" not in sql

    def test_extract_sql_from_response_no_sql(self):
        """extract_sql_from_response returns None when no SQL block exists."""
        response = "There's no SQL in this response."
        sql = AIService.extract_sql_from_response(response)
        assert sql is None

    def test_extract_sql_from_response_multiple_blocks(self):
        """extract_sql_from_response returns only the first SQL block."""
        response = (
            "```sql\nSELECT 1\n```\n\n"
            "```sql\nSELECT 2\n```"
        )
        sql = AIService.extract_sql_from_response(response)
        assert sql == "SELECT 1"

    @patch.dict(os.environ, {"STACKQL_LOCAL_DEV": "true", "ANTHROPIC_API_KEY": "test-key"})
    def test_get_api_key_local_dev(self):
        """In local dev, API key is read from environment."""
        svc = AIService()
        key = svc._get_api_key()
        assert key == "test-key"

    @patch.dict(os.environ, {"STACKQL_LOCAL_DEV": "true"}, clear=False)
    def test_get_api_key_missing_raises(self):
        """Missing ANTHROPIC_API_KEY in local dev raises RuntimeError."""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        svc = AIService()
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY not set"):
            svc._get_api_key()

    @patch.dict(os.environ, {"STACKQL_LOCAL_DEV": "true", "ANTHROPIC_API_KEY": "test-key"})
    def test_stream_chat_yields_strings(self):
        """stream_chat yields string chunks."""
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = iter(["Hello", " world"])

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream

        with patch("anthropic.Anthropic", return_value=mock_client):
            svc = AIService()
            chunks = list(svc.stream_chat([{"role": "user", "content": "test"}], "query"))

        assert chunks == ["Hello", " world"]
