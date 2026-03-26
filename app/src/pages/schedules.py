"""Schedules page – manage scheduled inventory jobs."""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st
from croniter import croniter

from src.db.models import Schedule
from src.db.service import DatabaseService
from src.services.job_service import JobService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
db_svc: DatabaseService = st.session_state.get("db_service")  # type: ignore[assignment]
if db_svc is None:
    st.error("Database service not initialised.")
    st.stop()

st.title("Schedules")

# ---------------------------------------------------------------------------
# New Schedule dialog
# ---------------------------------------------------------------------------
if st.button("New Schedule", type="primary"):
    @st.dialog("Create Schedule")
    def _new_schedule_dialog() -> None:
        queries = db_svc.get_queries()
        if not queries:
            st.warning("Save a query first in the SQL IDE.")
            return

        query_options = {q.name: q for q in queries}
        selected_name = st.selectbox("Query", list(query_options.keys()))
        selected_query = query_options[selected_name]

        cron_expr = st.text_input("Cron expression", value="0 */6 * * *", help="Standard cron syntax")

        # Live cron preview
        if cron_expr:
            try:
                cron = croniter(cron_expr)
                next_runs = [str(cron.get_next()) for _ in range(3)]
                st.caption(f"Next runs: {', '.join(next_runs)}")
            except (ValueError, KeyError):
                st.error("Invalid cron expression.")

        target_schema = st.text_input("Target schema", value="stackql_inventory")
        target_table = st.text_input("Target table name", placeholder="e.g. aws_ec2_instances")

        if st.button("Create", type="primary"):
            if not target_table:
                st.error("Target table name is required.")
                return

            schedule = Schedule(
                query_id=selected_query.id,  # type: ignore[arg-type]
                cron_expression=cron_expr,
                target_schema=target_schema,
                target_table=target_table,
            )

            with st.spinner("Creating job..."):
                try:
                    job_svc = JobService()
                    job_id = job_svc.create_inventory_job(selected_query, schedule)
                    schedule.job_id = job_id
                except RuntimeError as exc:
                    st.warning(f"Job creation skipped (Databricks not available): {exc}")

                db_svc.save_schedule(schedule)
                st.success(f"Schedule created for **{selected_name}** → `{target_schema}.{target_table}`")
                st.rerun()

    _new_schedule_dialog()

# ---------------------------------------------------------------------------
# Schedules table
# ---------------------------------------------------------------------------
schedules = db_svc.get_schedules()
queries = {q.id: q.name for q in db_svc.get_queries()}

if not schedules:
    st.info("No schedules configured yet. Click **New Schedule** to create one.")
else:
    rows = []
    for s in schedules:
        query_name = queries.get(s.query_id, f"Query #{s.query_id}")
        rows.append({
            "ID": s.id,
            "Query": query_name,
            "Cron": s.cron_expression,
            "Target": f"{s.target_schema}.{s.target_table}",
            "Active": s.is_active,
            "Last Run": str(s.last_run_at or "—"),
            "Status": s.last_run_status or "—",
            "Job ID": s.job_id or "—",
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Status": st.column_config.TextColumn(
                "Status",
                help="Last run status",
            ),
            "Active": st.column_config.CheckboxColumn("Active"),
        },
    )

    # Per-row actions
    st.subheader("Actions")
    for s in schedules:
        query_name = queries.get(s.query_id, f"Query #{s.query_id}")
        cols = st.columns([3, 1, 1, 1])
        with cols[0]:
            st.text(f"{query_name} → {s.target_table}")
        with cols[1]:
            label = "Pause" if s.is_active else "Resume"
            if st.button(label, key=f"toggle_{s.id}"):
                s.is_active = not s.is_active
                db_svc.update_schedule(s.id, s)  # type: ignore[arg-type]
                if s.job_id:
                    try:
                        job_svc = JobService()
                        if s.is_active:
                            job_svc.resume_inventory_job(s.job_id)
                        else:
                            job_svc.pause_inventory_job(s.job_id)
                    except RuntimeError:
                        pass
                st.rerun()
        with cols[2]:
            with st.popover(":material/delete:"):
                st.caption(f"Delete schedule for **{query_name}**?")
                if st.button("Confirm Delete", key=f"del_sched_{s.id}", type="primary"):
                    if s.job_id:
                        try:
                            job_svc = JobService()
                            job_svc.delete_inventory_job(s.job_id)
                        except RuntimeError:
                            pass
                    db_svc.delete_schedule(s.id)  # type: ignore[arg-type]
                    st.rerun()
