"""Job service – wraps the Databricks Jobs SDK.

Creates, updates, pauses, resumes and deletes inventory jobs.
Job tasks reference secrets via Databricks interpolation syntax, never resolved values.
"""

from __future__ import annotations

import logging
from typing import Any

from src.db.models import Query, Schedule

logger = logging.getLogger(__name__)


class JobService:
    """Manages Databricks Jobs for scheduled inventory queries."""

    def __init__(self) -> None:
        try:
            from databricks.sdk import WorkspaceClient
            self._ws = WorkspaceClient()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialise Databricks WorkspaceClient: {exc}"
            ) from exc

    def create_inventory_job(self, query: Query, schedule: Schedule) -> str:
        """Create a Databricks Job for a scheduled query. Returns the job_id."""
        from databricks.sdk.service.jobs import (
            CronSchedule,
            JobSettings,
            PauseStatus,
            PythonWheelTask,
            Task,
            TaskEmailNotifications,
        )

        try:
            job = self._ws.jobs.create(
                name=f"stackql-inventory-{schedule.target_table}",
                tasks=[
                    Task(
                        task_key="run_query",
                        description=f"Execute StackQL query: {query.name}",
                        python_wheel_task=PythonWheelTask(
                            package_name="stackql_inventory",
                            entry_point="run_query",
                            parameters=[
                                "--query-id", str(query.id),
                                "--target-schema", schedule.target_schema,
                                "--target-table", schedule.target_table,
                            ],
                        ),
                    )
                ],
                schedule=CronSchedule(
                    quartz_cron_expression=schedule.cron_expression,
                    timezone_id="UTC",
                    pause_status=PauseStatus.UNPAUSED if schedule.is_active else PauseStatus.PAUSED,
                ),
            )
            job_id = str(job.job_id)
            logger.info("Created Databricks job %s for query %s", job_id, query.name)
            return job_id
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create Databricks job: {exc}. "
                "Check workspace permissions and job quota."
            ) from exc

    def update_inventory_job(self, job_id: str, schedule: Schedule) -> None:
        """Update an existing job's schedule."""
        from databricks.sdk.service.jobs import CronSchedule, PauseStatus

        try:
            self._ws.jobs.update(
                job_id=int(job_id),
                new_settings={
                    "schedule": CronSchedule(
                        quartz_cron_expression=schedule.cron_expression,
                        timezone_id="UTC",
                        pause_status=PauseStatus.UNPAUSED if schedule.is_active else PauseStatus.PAUSED,
                    ),
                },
            )
            logger.info("Updated Databricks job %s", job_id)
        except Exception as exc:
            raise RuntimeError(f"Failed to update Databricks job {job_id}: {exc}") from exc

    def delete_inventory_job(self, job_id: str) -> None:
        """Delete a Databricks Job."""
        try:
            self._ws.jobs.delete(job_id=int(job_id))
            logger.info("Deleted Databricks job %s", job_id)
        except Exception as exc:
            raise RuntimeError(f"Failed to delete Databricks job {job_id}: {exc}") from exc

    def pause_inventory_job(self, job_id: str) -> None:
        """Pause a job by setting its schedule to PAUSED."""
        from databricks.sdk.service.jobs import CronSchedule, PauseStatus

        try:
            job = self._ws.jobs.get(job_id=int(job_id))
            if job.settings and job.settings.schedule:
                self._ws.jobs.update(
                    job_id=int(job_id),
                    new_settings={
                        "schedule": CronSchedule(
                            quartz_cron_expression=job.settings.schedule.quartz_cron_expression,
                            timezone_id="UTC",
                            pause_status=PauseStatus.PAUSED,
                        ),
                    },
                )
            logger.info("Paused Databricks job %s", job_id)
        except Exception as exc:
            raise RuntimeError(f"Failed to pause Databricks job {job_id}: {exc}") from exc

    def resume_inventory_job(self, job_id: str) -> None:
        """Resume a paused job."""
        from databricks.sdk.service.jobs import CronSchedule, PauseStatus

        try:
            job = self._ws.jobs.get(job_id=int(job_id))
            if job.settings and job.settings.schedule:
                self._ws.jobs.update(
                    job_id=int(job_id),
                    new_settings={
                        "schedule": CronSchedule(
                            quartz_cron_expression=job.settings.schedule.quartz_cron_expression,
                            timezone_id="UTC",
                            pause_status=PauseStatus.UNPAUSED,
                        ),
                    },
                )
            logger.info("Resumed Databricks job %s", job_id)
        except Exception as exc:
            raise RuntimeError(f"Failed to resume Databricks job {job_id}: {exc}") from exc

    def get_job_run_status(self, job_id: str) -> dict[str, Any] | None:
        """Get the most recent run status for a job."""
        try:
            runs = self._ws.jobs.list_runs(job_id=int(job_id), limit=1)
            for run in runs:
                return {
                    "run_id": run.run_id,
                    "state": run.state.result_state.value if run.state and run.state.result_state else None,
                    "life_cycle_state": run.state.life_cycle_state.value if run.state and run.state.life_cycle_state else None,
                    "start_time": run.start_time,
                    "end_time": run.end_time,
                }
            return None
        except Exception as exc:
            logger.warning("Failed to get run status for job %s: %s", job_id, exc)
            return None
