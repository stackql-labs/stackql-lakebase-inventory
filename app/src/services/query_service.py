"""Query execution service – wraps pystackql.

Verifies provider credentials are in os.environ and executes StackQL queries.
Credentials come from .env (local dev) or app.yml secret bindings (production).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.db.service import DatabaseService

logger = logging.getLogger(__name__)


class QueryService:
    """Executes StackQL queries with automatic credential injection and cleanup."""

    def __init__(self, db_service: DatabaseService) -> None:
        self._db = db_service

    def execute(self, query_text: str, provider: str) -> pd.DataFrame:
        """Execute a StackQL query, returning results as a DataFrame.

        Raises RuntimeError on binary download failure or query error.
        Returns an empty DataFrame for queries with no results.
        """
        injected_keys: list[str] = []
        try:
            # Resolve and inject provider credentials
            injected_keys = self._inject_credentials(provider)

            # Instantiate StackQL
            try:
                from pystackql import StackQL
                stackql = StackQL(download_dir="/tmp/stackql")
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to initialise StackQL binary. Check /tmp/stackql permissions. Error: {exc}"
                ) from exc

            # Execute query
            logger.info("Executing StackQL query for provider=%s", provider)
            result = stackql.execute(query_text)

            # Coerce to DataFrame
            if isinstance(result, pd.DataFrame):
                df = result
            elif isinstance(result, list):
                df = pd.DataFrame(result)
            elif isinstance(result, dict) and "error" in result:
                raise RuntimeError(result["error"])
            else:
                df = pd.DataFrame(result) if result else pd.DataFrame()

            # Check for error column in results
            if not df.empty and "error" in df.columns:
                error_msg = df["error"].iloc[0]
                if error_msg:
                    raise RuntimeError(str(error_msg))

            return df

        finally:
            self._cleanup_env(injected_keys)

    def _inject_credentials(self, provider: str) -> list[str]:
        """Verify provider credentials are available in os.environ.

        In local dev: credentials are set in .env and loaded by python-dotenv.
        In production: the Databricks App runtime injects secrets as env vars
        via app.yml bindings. Either way, we check env vars are present.

        Returns list of keys that were verified (for logging only).
        """
        configs = self._db.get_provider_config()
        provider_configs = [c for c in configs if c.provider == provider]

        if not provider_configs:
            logger.warning("No provider config found for provider=%s", provider)
            return []

        verified: list[str] = []

        for config in provider_configs:
            value = os.environ.get(config.env_var_name)
            if value:
                logger.debug("Credential available: %s", config.env_var_name)
                verified.append(config.env_var_name)
            else:
                logger.warning(
                    "Credential %s not found in environment. "
                    "Set it in .env for local dev or configure app.yml for production.",
                    config.env_var_name,
                )

        return verified

    @staticmethod
    def _cleanup_env(keys: list[str]) -> None:
        """Remove injected keys from os.environ."""
        for key in keys:
            os.environ.pop(key, None)
            logger.debug("Cleaned up credential: %s", key)
