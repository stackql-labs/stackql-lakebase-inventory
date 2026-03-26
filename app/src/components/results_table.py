"""Results table component – renders query results or errors.

Displays a DataFrame with row count, execution time, and an
"Interpret Results" button that feeds data to the AI chat panel.
"""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def render_results(
    df: pd.DataFrame | None = None,
    execution_time: float | None = None,
    error: str | None = None,
) -> None:
    """Render query results or an error message.

    Args:
        df: Query result DataFrame (mutually exclusive with error).
        execution_time: Seconds taken for query execution.
        error: Error message to display instead of results.
    """
    if error:
        st.error(error)
        return

    if df is None:
        return

    if df.empty:
        st.info("Query returned no rows.")
        return

    # Caption with row count and execution time
    caption_parts = [f"**{len(df):,} rows**"]
    if execution_time is not None:
        caption_parts.append(f"in {execution_time:.2f}s")
    st.caption(" ".join(caption_parts))

    # Render the DataFrame
    st.dataframe(df, use_container_width=True)

    # Interpret Results button
    if st.button("Interpret Results", key="interpret_results_btn", type="secondary"):
        # Serialise top 20 rows as markdown for the AI
        preview = df.head(20).to_markdown(index=False)
        prompt = (
            "Please interpret the following cloud inventory query results:\n\n"
            f"```\n{preview}\n```\n\n"
            f"Total rows: {len(df):,}. "
            "Summarise key findings, flag anything notable, and suggest follow-up queries."
        )
        st.session_state["ide_pending_chat_prompt"] = prompt
        st.session_state["ide_chat_mode"] = "Interpret Results"
        st.rerun()
