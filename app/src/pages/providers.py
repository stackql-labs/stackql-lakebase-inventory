"""Provider configuration page – manage cloud provider credential mappings."""

from __future__ import annotations

import logging
import os

import streamlit as st

from src.db.models import ProviderConfig
from src.db.service import DatabaseService

logger = logging.getLogger(__name__)

_LOCAL_DEV = os.environ.get("STACKQL_LOCAL_DEV", "").lower() == "true"

KNOWN_PROVIDERS = ["aws", "azure", "google", "databricks", "github", "cloudflare", "okta"]

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
db_svc: DatabaseService = st.session_state.get("db_service")  # type: ignore[assignment]
if db_svc is None:
    st.error("Database service not initialised.")
    st.stop()

st.title("Provider Configuration")
st.caption("Map cloud provider environment variables to Databricks secret scope/key pairs.")

# ---------------------------------------------------------------------------
# Add Mapping dialog
# ---------------------------------------------------------------------------
if st.button("Add Mapping", type="primary"):
    @st.dialog("Add Provider Mapping")
    def _add_mapping_dialog() -> None:
        provider = st.selectbox("Provider", KNOWN_PROVIDERS + ["other"])
        if provider == "other":
            provider = st.text_input("Custom provider name")

        env_var_name = st.text_input("Environment variable name", placeholder="e.g. AWS_ACCESS_KEY_ID")
        secret_scope = st.text_input("Secret scope", value="stackql-inventory")
        secret_key = st.text_input("Secret key", placeholder="e.g. aws-access-key-id")

        if st.button("Save", type="primary"):
            if not all([provider, env_var_name, secret_scope, secret_key]):
                st.error("All fields are required.")
                return

            # Validate secret exists (skip in local dev)
            if not _LOCAL_DEV:
                try:
                    from databricks.sdk import WorkspaceClient
                    ws = WorkspaceClient()
                    ws.secrets.get_secret(scope=secret_scope, key=secret_key)
                except Exception as exc:
                    if "NotFound" in type(exc).__name__ or "not found" in str(exc).lower():
                        st.error(
                            f"Secret not found: scope=`{secret_scope}`, key=`{secret_key}`. "
                            "Create the secret in Databricks first."
                        )
                        return
                    st.warning(f"Could not validate secret (proceeding): {exc}")

            config = ProviderConfig(
                provider=provider,
                env_var_name=env_var_name,
                secret_scope=secret_scope,
                secret_key=secret_key,
            )
            db_svc.save_provider_config(config)
            st.success(f"Saved mapping: `{env_var_name}` → `{secret_scope}/{secret_key}`")
            st.rerun()

    _add_mapping_dialog()

# ---------------------------------------------------------------------------
# Existing mappings table
# ---------------------------------------------------------------------------
configs = db_svc.get_provider_config()

if not configs:
    st.info("No provider mappings configured yet. Click **Add Mapping** to create one.")
else:
    import pandas as pd

    rows = []
    for c in configs:
        rows.append({
            "ID": c.id,
            "Provider": c.provider,
            "Env Var": c.env_var_name,
            "Secret Scope": c.secret_scope,
            "Secret Key": "***",
            "Created By": c.created_by or "—",
            "Created At": str(c.created_at or "—"),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # Per-row actions
    st.subheader("Actions")
    for c in configs:
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.text(f"{c.provider}: {c.env_var_name}")
        with cols[1]:
            if st.button("Test", key=f"test_prov_{c.id}"):
                with st.spinner("Testing connection..."):
                    injected = False
                    try:
                        # Resolve and inject
                        if _LOCAL_DEV:
                            value = os.environ.get(c.env_var_name)
                            if not value:
                                st.warning(f"`{c.env_var_name}` not set in environment.")
                                continue
                        else:
                            from databricks.sdk import WorkspaceClient
                            ws = WorkspaceClient()
                            secret = ws.secrets.get_secret(scope=c.secret_scope, key=c.secret_key)
                            os.environ[c.env_var_name] = secret.value
                            injected = True

                        # Test StackQL
                        from pystackql import StackQL
                        stackql = StackQL(download_dir="/tmp/stackql")
                        result = stackql.execute("SHOW PROVIDERS")
                        st.success(f"Connection test passed for `{c.env_var_name}`")
                    except Exception as exc:
                        st.error(f"Test failed: {exc}")
                    finally:
                        if injected:
                            os.environ.pop(c.env_var_name, None)
        with cols[2]:
            with st.popover(":material/delete:"):
                st.caption(f"Delete `{c.env_var_name}`?")
                if st.button("Confirm", key=f"del_prov_{c.id}", type="primary"):
                    db_svc.delete_provider_config(c.id)  # type: ignore[arg-type]
                    st.rerun()
