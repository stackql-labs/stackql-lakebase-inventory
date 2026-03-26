"""Inventory browser page – explore cloud inventory tables in Lakebase."""

from __future__ import annotations

import logging

import streamlit as st

from src.db.service import DatabaseService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
db_svc: DatabaseService = st.session_state.get("db_service")  # type: ignore[assignment]
if db_svc is None:
    st.error("Database service not initialised.")
    st.stop()

st.title("Inventory Browser")

# ---------------------------------------------------------------------------
# Load inventory tables
# ---------------------------------------------------------------------------
try:
    tables = db_svc.get_inventory_tables()
except Exception as exc:
    st.error(f"Failed to load inventory tables: {exc}")
    tables = []

# ---------------------------------------------------------------------------
# Top metrics
# ---------------------------------------------------------------------------
metric_cols = st.columns(3)
total_tables = len(tables)
total_rows = sum(t["row_count"] for t in tables)

with metric_cols[0]:
    st.metric("Tables", total_tables)
with metric_cols[1]:
    st.metric("Total Rows", f"{total_rows:,}")
with metric_cols[2]:
    st.metric("Inventory Schema", "stackql_inventory")

st.divider()

# ---------------------------------------------------------------------------
# Table list
# ---------------------------------------------------------------------------
if not tables:
    st.info("No inventory tables yet. Schedule a query to populate inventory data.")
else:
    import pandas as pd

    table_df = pd.DataFrame(tables)
    table_df.columns = ["Table Name", "Row Count", "Has Materialised View"]

    selection = st.dataframe(
        table_df,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key="inventory_table_selection",
    )

    # Handle row selection
    selected_rows = selection.selection.rows if selection and selection.selection else []

    if selected_rows:
        idx = selected_rows[0]
        selected_table = tables[idx]
        table_name = selected_table["table_name"]

        st.subheader(f"Preview: `{table_name}`")

        # Refresh MV button
        if selected_table["has_materialised_view"]:
            if st.button(f"Refresh Materialised View (`{table_name}_mv`)"):
                with st.spinner("Refreshing..."):
                    try:
                        db_svc.refresh_materialised_view(f"{table_name}_mv")
                        st.success("Materialised view refreshed.")
                    except Exception as exc:
                        st.error(f"Refresh failed: {exc}")

        # Preview data
        try:
            preview_df = db_svc.get_inventory_preview(table_name)
            if preview_df.empty:
                st.info("Table is empty.")
            else:
                st.caption(f"Showing up to 100 rows of **{selected_table['row_count']:,}** total")
                st.dataframe(preview_df, use_container_width=True)
        except Exception as exc:
            st.error(f"Failed to load preview: {exc}")
