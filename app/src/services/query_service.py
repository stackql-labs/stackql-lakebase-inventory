"""Query execution service – wraps pystackql.

Resolves provider credentials from Databricks Secrets (or env vars in local dev),
injects them into os.environ for the duration of query execution, and cleans up afterwards.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.db.service import DatabaseService

logger = logging.getLogger(__name__)

_LOCAL_DEV = os.environ.get("STACKQL_LOCAL_DEV", "").lower() == "true"


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
        """Resolve secrets and inject into os.environ. Returns list of injected keys."""
        configs = self._db.get_provider_config()
        provider_configs = [c for c in configs if c.provider == provider]

        if not provider_configs:
            logger.warning("No provider config found for provider=%s", provider)
            return []

        injected: list[str] = []

        for config in provider_configs:
            if _LOCAL_DEV:
                # In local dev, credentials should already be in env
                value = os.environ.get(config.env_var_name)
                if value:
                    logger.debug("Local dev: %s already set", config.env_var_name)
                else:
                    logger.warning("Local dev: %s not found in environment", config.env_var_name)
                continue

            # Resolve from Databricks Secrets
            try:
                from databricks.sdk import WorkspaceClient
                ws = WorkspaceClient()
                secret = ws.secrets.get_secret(scope=config.secret_scope, key=config.secret_key)
                value = secret.value
                if value is None:
                    raise RuntimeError(
                        f"Secret value is empty for scope={config.secret_scope}, "
                        f"key={config.secret_key}. Check Provider Config page."
                    )
            except ImportError:
                raise RuntimeError(
                    "databricks-sdk is required for secrets resolution. "
                    "Set STACKQL_LOCAL_DEV=true for local development."
                )
            except Exception as exc:
                if "NotFound" in type(exc).__name__ or "not found" in str(exc).lower():
                    raise RuntimeError(
                        f"Secret not found: scope={config.secret_scope}, key={config.secret_key}. "
                        "Configure secrets on the Provider Config page."
                    ) from exc
                raise

            os.environ[config.env_var_name] = value
            injected.append(config.env_var_name)
            logger.debug("Injected credential: %s", config.env_var_name)

        return injected

    @staticmethod
    def _cleanup_env(keys: list[str]) -> None:
        """Remove injected keys from os.environ."""
        for key in keys:
            os.environ.pop(key, None)
            logger.debug("Cleaned up credential: %s", key)
