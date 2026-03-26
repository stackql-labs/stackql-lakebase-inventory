"""Job service – manages scheduled inventory queries via pystackql.

Uses the StackQL databricks_workspace.jobs provider to create, update,
pause, resume and delete Databricks Jobs. No direct Databricks SDK dependency.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import pandas as pd

from src.db.models import Query, Schedule

logger = logging.getLogger(__name__)


def _get_stackql():
    """Get a StackQL instance."""
    from pystackql import StackQL
    return StackQL(download_dir="/tmp/stackql", output="dict")


def _get_deployment_name() -> str:
    """Extract the deployment name from DATABRICKS_HOST."""
    host = os.environ.get("DATABRICKS_HOST", "")
    # e.g. https://dbc-74aa95f7-8c7e.cloud.databricks.com -> dbc-74aa95f7-8c7e
    host = host.replace("https://", "").replace("http://", "")
    return host.split(".")[0] if host else ""


class JobService:
    """Manages Databricks Jobs for scheduled inventory queries via StackQL."""

    def __init__(self) -> None:
        try:
            self._stackql = _get_stackql()
            self._deployment_name = _get_deployment_name()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialise StackQL for job management: {exc}"
            ) from exc

    def create_inventory_job(self, query: Query, schedule: Schedule) -> str:
        """Create a Databricks Job for a scheduled query. Returns the job_id."""
        job_name = f"stackql-inventory-{schedule.target_table}"

        # Build the task configuration as JSON
        tasks_json = json.dumps([{
            "task_key": "run_query",
            "description": f"Execute StackQL query: {query.name}",
            "python_wheel_task": {
                "package_name": "stackql_inventory",
                "entry_point": "run_query",
                "parameters": [
                    "--query-id", str(query.id),
                    "--target-schema", schedule.target_schema,
                    "--target-table", schedule.target_table,
                ],
            },
        }])

        schedule_json = json.dumps({
            "quartz_cron_expression": schedule.cron_expression,
            "timezone_id": "UTC",
            "pause_status": "UNPAUSED" if schedule.is_active else "PAUSED",
        })

        insert_query = f"""
        INSERT INTO databricks_workspace.jobs.jobs (
            name,
            data__tasks,
            data__schedule,
            deployment_name
        )
        SELECT
            '{job_name}',
            '{tasks_json}',
            '{schedule_json}',
            '{self._deployment_name}'
        """

        try:
            result = self._stackql.executeStmt(insert_query)
            logger.info("Created Databricks job for query %s: %s", query.name, result)

            # Get the job_id by querying for the job we just created
            get_query = f"""
            SELECT job_id
            FROM databricks_workspace.jobs.jobs
            WHERE deployment_name = '{self._deployment_name}'
            AND name = '{job_name}'
            ORDER BY created_time DESC
            LIMIT 1
            """
            rows = self._stackql.execute(get_query)
            if rows and len(rows) > 0 and "job_id" in rows[0]:
                job_id = str(rows[0]["job_id"])
                logger.info("Created Databricks job %s for query %s", job_id, query.name)
                return job_id

            return ""
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create Databricks job: {exc}. "
                "Check workspace permissions and job quota."
            ) from exc

    def update_inventory_job(self, job_id: str, schedule: Schedule) -> None:
        """Update an existing job's schedule."""
        schedule_json = json.dumps({
            "quartz_cron_expression": schedule.cron_expression,
            "timezone_id": "UTC",
            "pause_status": "UNPAUSED" if schedule.is_active else "PAUSED",
        })

        update_query = f"""
        UPDATE databricks_workspace.jobs.jobs
        SET data__new_settings__schedule = '{schedule_json}'
        WHERE job_id = {job_id}
        AND deployment_name = '{self._deployment_name}'
        """

        try:
            self._stackql.executeStmt(update_query)
            logger.info("Updated Databricks job %s", job_id)
        except Exception as exc:
            raise RuntimeError(f"Failed to update Databricks job {job_id}: {exc}") from exc

    def delete_inventory_job(self, job_id: str) -> None:
        """Delete a Databricks Job."""
        delete_query = f"""
        DELETE FROM databricks_workspace.jobs.jobs
        WHERE job_id = {job_id}
        AND deployment_name = '{self._deployment_name}'
        """

        try:
            self._stackql.executeStmt(delete_query)
            logger.info("Deleted Databricks job %s", job_id)
        except Exception as exc:
            raise RuntimeError(f"Failed to delete Databricks job {job_id}: {exc}") from exc

    def pause_inventory_job(self, job_id: str) -> None:
        """Pause a job by updating its schedule to PAUSED."""
        # Get current schedule
        get_query = f"""
        SELECT JSON_EXTRACT(settings, '$.schedule') as schedule
        FROM databricks_workspace.jobs.jobs
        WHERE job_id = {job_id}
        AND deployment_name = '{self._deployment_name}'
        """

        try:
            rows = self._stackql.execute(get_query)
            if rows and len(rows) > 0 and rows[0].get("schedule"):
                current_schedule = json.loads(rows[0]["schedule"]) if isinstance(rows[0]["schedule"], str) else rows[0]["schedule"]
                current_schedule["pause_status"] = "PAUSED"
                schedule_json = json.dumps(current_schedule)

                update_query = f"""
                UPDATE databricks_workspace.jobs.jobs
                SET data__new_settings__schedule = '{schedule_json}'
                WHERE job_id = {job_id}
                AND deployment_name = '{self._deployment_name}'
                """
                self._stackql.executeStmt(update_query)

            logger.info("Paused Databricks job %s", job_id)
        except Exception as exc:
            raise RuntimeError(f"Failed to pause Databricks job {job_id}: {exc}") from exc

    def resume_inventory_job(self, job_id: str) -> None:
        """Resume a paused job."""
        get_query = f"""
        SELECT JSON_EXTRACT(settings, '$.schedule') as schedule
        FROM databricks_workspace.jobs.jobs
        WHERE job_id = {job_id}
        AND deployment_name = '{self._deployment_name}'
        """

        try:
            rows = self._stackql.execute(get_query)
            if rows and len(rows) > 0 and rows[0].get("schedule"):
                current_schedule = json.loads(rows[0]["schedule"]) if isinstance(rows[0]["schedule"], str) else rows[0]["schedule"]
                current_schedule["pause_status"] = "UNPAUSED"
                schedule_json = json.dumps(current_schedule)

                update_query = f"""
                UPDATE databricks_workspace.jobs.jobs
                SET data__new_settings__schedule = '{schedule_json}'
                WHERE job_id = {job_id}
                AND deployment_name = '{self._deployment_name}'
                """
                self._stackql.executeStmt(update_query)

            logger.info("Resumed Databricks job %s", job_id)
        except Exception as exc:
            raise RuntimeError(f"Failed to resume Databricks job {job_id}: {exc}") from exc

    def get_job_run_status(self, job_id: str) -> dict[str, Any] | None:
        """Get the most recent run status for a job."""
        try:
            runs_query = f"""
            SELECT run_id,
                   JSON_EXTRACT(state, '$.result_state') as result_state,
                   JSON_EXTRACT(state, '$.life_cycle_state') as life_cycle_state,
                   start_time,
                   end_time
            FROM databricks_workspace.jobs.runs
            WHERE job_id = {job_id}
            AND deployment_name = '{self._deployment_name}'
            LIMIT 1
            """
            rows = self._stackql.execute(runs_query)
            if rows and len(rows) > 0:
                row = rows[0]
                return {
                    "run_id": row.get("run_id"),
                    "state": row.get("result_state"),
                    "life_cycle_state": row.get("life_cycle_state"),
                    "start_time": row.get("start_time"),
                    "end_time": row.get("end_time"),
                }
            return None
        except Exception as exc:
            logger.warning("Failed to get run status for job %s: %s", job_id, exc)
            return None
