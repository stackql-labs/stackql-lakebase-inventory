"""SQL IDE page – Monaco editor with AI chat panel."""

from __future__ import annotations

import logging
import time

import streamlit as st

from src.components.editor import render_editor
from src.components.results_table import render_results
from src.db.service import DatabaseService
from src.services.ai_service import AIService
from src.services.query_service import QueryService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
for key, default in [
    ("ide_editor_content", ""),
    ("ide_chat_messages", []),
    ("ide_chat_mode", "Write Query"),
    ("ide_result_df", None),
    ("ide_result_error", None),
    ("ide_result_time", None),
    ("ide_pending_chat_prompt", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
db_svc: DatabaseService = st.session_state.get("db_service")  # type: ignore[assignment]
if db_svc is None:
    st.error("Database service not initialised.")
    st.stop()

query_svc = QueryService(db_svc)
ai_svc = AIService()

# ---------------------------------------------------------------------------
# Sidebar – Query library
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Saved Queries")
    queries = db_svc.get_queries()
    if not queries:
        st.caption("No saved queries yet.")
    for q in queries:
        col_name, col_del = st.columns([4, 1])
        with col_name:
            if st.button(q.name, key=f"load_q_{q.id}", use_container_width=True):
                st.session_state["ide_editor_content"] = q.query_text
                st.rerun()
        with col_del:
            with st.popover(":material/delete:", use_container_width=True):
                st.caption(f"Delete **{q.name}**?")
                if st.button("Confirm", key=f"del_q_{q.id}", type="primary"):
                    db_svc.delete_query(q.id)  # type: ignore[arg-type]
                    st.rerun()

# ---------------------------------------------------------------------------
# Main layout – two columns
# ---------------------------------------------------------------------------
left_col, right_col = st.columns([0.65, 0.35], gap="medium")

# ===== LEFT COLUMN =====
with left_col:
    st.subheader("StackQL Editor")

    # Editor
    query_text, submitted = render_editor()

    # Toolbar row
    toolbar_cols = st.columns([2, 1, 1, 1])

    # Provider selector
    provider_configs = db_svc.get_provider_config()
    provider_names = sorted({c.provider for c in provider_configs}) if provider_configs else ["aws", "google", "azure"]
    with toolbar_cols[0]:
        selected_provider = st.selectbox("Provider", provider_names, key="ide_provider", label_visibility="collapsed")

    # Run button
    with toolbar_cols[1]:
        run_clicked = st.button("Run", type="primary", use_container_width=True)

    # Save Query button
    with toolbar_cols[2]:
        save_clicked = st.button("Save Query", use_container_width=True)

    # Explain Query button
    with toolbar_cols[3]:
        explain_clicked = st.button("Explain Query", use_container_width=True)

    # Handle Run
    if (submitted or run_clicked) and query_text:
        with st.spinner("Executing query..."):
            start = time.time()
            try:
                df = query_svc.execute(query_text, selected_provider)
                st.session_state["ide_result_df"] = df
                st.session_state["ide_result_error"] = None
                st.session_state["ide_result_time"] = time.time() - start
            except RuntimeError as exc:
                st.session_state["ide_result_df"] = None
                st.session_state["ide_result_error"] = str(exc)
                st.session_state["ide_result_time"] = None

    # Handle Save Query
    if save_clicked:
        @st.dialog("Save Query")
        def _save_dialog() -> None:
            name = st.text_input("Query name")
            description = st.text_area("Description (optional)")
            if st.button("Save", type="primary"):
                if not name:
                    st.error("Name is required.")
                    return
                from src.db.models import Query as QueryModel
                q = QueryModel(
                    name=name,
                    description=description or None,
                    query_text=st.session_state.get("ide_editor_content", ""),
                    provider=selected_provider,
                )
                db_svc.save_query(q)
                st.success(f"Saved query: {name}")
                st.rerun()
        _save_dialog()

    # Handle Explain Query
    if explain_clicked and query_text:
        st.session_state["ide_pending_chat_prompt"] = (
            f"Please explain the following StackQL query:\n\n```sql\n{query_text}\n```"
        )
        st.session_state["ide_chat_mode"] = "Write Query"

    # Results area
    render_results(
        df=st.session_state.get("ide_result_df"),
        execution_time=st.session_state.get("ide_result_time"),
        error=st.session_state.get("ide_result_error"),
    )

# ===== RIGHT COLUMN – AI Chat =====
with right_col:
    st.subheader("AI Assistant")

    # Mode toggle
    mode = st.segmented_control(
        "Mode",
        options=["Write Query", "Interpret Results"],
        default=st.session_state["ide_chat_mode"],
        key="ide_chat_mode_ctrl",
        label_visibility="collapsed",
    )
    if mode:
        st.session_state["ide_chat_mode"] = mode

    # Render chat history
    for msg in st.session_state["ide_chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Check for pending chat prompt (from Explain Query or Interpret Results)
    pending = st.session_state.get("ide_pending_chat_prompt")
    if pending:
        st.session_state["ide_pending_chat_prompt"] = None
        # Append as user message
        st.session_state["ide_chat_messages"].append({"role": "user", "content": pending})
        with st.chat_message("user"):
            st.markdown(pending)

        # Stream AI response
        ai_mode = "query" if st.session_state["ide_chat_mode"] == "Write Query" else "results"
        with st.chat_message("assistant"):
            response_text = st.write_stream(
                ai_svc.stream_chat(st.session_state["ide_chat_messages"], ai_mode)
            )
        st.session_state["ide_chat_messages"].append({"role": "assistant", "content": response_text})

        # Check for SQL in response
        sql = ai_svc.extract_sql_from_response(response_text)
        if sql:
            if st.button("Insert into editor", key="insert_sql_pending"):
                st.session_state["ide_editor_content"] = sql
                st.rerun()

    # Chat input
    user_input = st.chat_input("Ask about StackQL queries or results...", key="ide_chat_input")
    if user_input:
        st.session_state["ide_chat_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        ai_mode = "query" if st.session_state["ide_chat_mode"] == "Write Query" else "results"
        with st.chat_message("assistant"):
            response_text = st.write_stream(
                ai_svc.stream_chat(st.session_state["ide_chat_messages"], ai_mode)
            )
        st.session_state["ide_chat_messages"].append({"role": "assistant", "content": response_text})

        # Check for SQL in response
        sql = ai_svc.extract_sql_from_response(response_text)
        if sql:
            if st.button("Insert into editor", key="insert_sql_chat"):
                st.session_state["ide_editor_content"] = sql
                st.rerun()
