"""AI service – wraps the Anthropic API.

Resolves the API key from Databricks Secrets (or env vars in local dev),
streams chat completions, and extracts SQL from responses.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Generator

logger = logging.getLogger(__name__)

_LOCAL_DEV = os.environ.get("STACKQL_LOCAL_DEV", "").lower() == "true"

QUERY_SYSTEM_PROMPT = """You are a StackQL expert assistant. StackQL lets users query cloud provider APIs using SQL syntax.

Key rules:
- StackQL uses SELECT statements to read cloud resources. The table naming convention is: provider.service.resource
- Always include required WHERE clause parameters (e.g., region for AWS, project for GCP, subscriptionId for Azure)
- Format all SQL in a fenced ```sql code block
- Only generate SELECT queries (no INSERT/UPDATE/DELETE in query mode)
- Use standard SQL syntax (WHERE, GROUP BY, ORDER BY, JOIN, etc.)
- Available providers include: aws, google, azure, databricks, github, cloudflare, okta, and many more

Examples:
- AWS EC2 instances: SELECT instanceId, instanceType, state FROM aws.ec2.instances WHERE region = 'us-east-1'
- GCP VMs: SELECT name, status, machineType FROM google.compute.instances WHERE project = 'my-project' AND zone = 'us-central1-a'
- Azure VMs: SELECT name, properties FROM azure.compute.virtual_machines WHERE subscriptionId = '...' AND resourceGroupName = '...'
"""

RESULTS_SYSTEM_PROMPT = """You are a cloud infrastructure analyst. When presented with query results:

- Summarise what the data shows at a high level
- Flag notable findings: high resource counts, unusual states, potential cost or security concerns
- Suggest follow-up queries that could provide deeper insight
- Do NOT repeat the raw data verbatim – summarise and interpret
- Be concise and actionable
"""


class AIService:
    """Provides AI chat capabilities via the Anthropic API."""

    def _get_api_key(self) -> str:
        """Resolve the Anthropic API key."""
        if _LOCAL_DEV:
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set. Required for AI features in local dev mode."
                )
            return key

        try:
            from databricks.sdk import WorkspaceClient
            ws = WorkspaceClient()
            secret = ws.secrets.get_secret(scope="stackql-inventory", key="anthropic-api-key")
            if secret.value is None:
                raise RuntimeError(
                    "Anthropic API key secret is empty. "
                    "Scope=stackql-inventory, key=anthropic-api-key."
                )
            return secret.value
        except ImportError:
            raise RuntimeError(
                "databricks-sdk is required for secrets resolution. "
                "Set STACKQL_LOCAL_DEV=true for local development."
            )
        except Exception as exc:
            if "NotFound" in type(exc).__name__ or "not found" in str(exc).lower():
                raise RuntimeError(
                    "Anthropic API key not found in Databricks Secrets. "
                    "Scope=stackql-inventory, key=anthropic-api-key."
                ) from exc
            raise

    def stream_chat(
        self, messages: list[dict[str, str]], mode: str
    ) -> Generator[str, None, None]:
        """Stream a chat response from Claude.

        Args:
            messages: Chat history as list of {"role": ..., "content": ...} dicts.
            mode: "query" for StackQL writing assistance, "results" for interpretation.

        Yields:
            Text chunks from the streaming response.
        """
        try:
            import anthropic

            api_key = self._get_api_key()
            client = anthropic.Anthropic(api_key=api_key)
            # Key is now held only by the client object

            system_prompt = QUERY_SYSTEM_PROMPT if mode == "query" else RESULTS_SYSTEM_PROMPT

            with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as exc:
            error_msg = f"AI service error: {exc}"
            logger.error(error_msg)
            yield f"\n\n**Error:** {error_msg}"

    @staticmethod
    def extract_sql_from_response(response: str) -> str | None:
        """Extract the first SQL fenced code block from a response.

        Returns the SQL text stripped of markers, or None if not found.
        """
        match = re.search(r"```sql\s*\n(.*?)```", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
