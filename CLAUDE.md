# CLAUDE.md - StackQL Cloud Inventory

This file is the primary reference for Claude Code when building, extending, or debugging this project. Read it in full before writing any code. When in doubt, refer back here rather than making assumptions.

---

## Project goal

Build a Databricks-native cloud inventory platform called **StackQL Cloud Inventory**. It is a Streamlit app deployed on Databricks Apps that lets engineers define StackQL queries, test them interactively, schedule them as Databricks Jobs, and surface results via Unity Catalog to DBSQL dashboards and Genie spaces.

The full architecture is described in `ARCHITECTURE.md`. The user-facing overview is in `README.md`. This file contains the implementation instructions.

---

## What to build

### Repository structure

```
stackql-cloud-inventory/
|- app/
|   |- src/
|   |   |- pages/
|   |   |   |- ide.py
|   |   |   |- schedules.py
|   |   |   |- inventory.py
|   |   |   |- providers.py
|   |   |- components/
|   |   |   |- editor.py
|   |   |   |- results_table.py
|   |   |- db/
|   |   |   |- __init__.py
|   |   |   |- models.py
|   |   |   |- service.py
|   |   |- services/
|   |   |   |- __init__.py
|   |   |   |- query_service.py
|   |   |   |- job_service.py
|   |   |   |- ai_service.py
|   |   |- jobs/
|   |   |   |- run_query.py
|   |   |- main.py
|   |- tests/
|   |   |- test_db_service.py
|   |   |- test_query_service.py
|   |   |- test_job_service.py
|   |   |- test_ai_service.py
|   |- requirements.txt
|   |- app.yml
|- infra/
|   |- bundles/
|   |   |- databricks.yml
|   |   |- resources/
|   |       |- jobs/
|   |       |- schemas/
|   |- stackql-deploy/
|       |- stackql_manifest.yml
|       |- resources/
|- scripts/
|   |- init_lakebase.sql
|- .vscode/
|   |- launch.json
|- .gitignore
|- README.md
|- ARCHITECTURE.md
|- CLAUDE.md
```

---

## Technology stack

| Layer | Technology | Notes |
|---|---|---|
| App framework | Streamlit | Databricks Apps serverless runtime |
| SQL editor | streamlit-code-editor | Monaco wrapper. Do not use st.text_area as primary editor. |
| AI assistant | anthropic SDK | Direct API, not via a Databricks-hosted model |
| StackQL execution | pystackql | Wraps the StackQL binary |
| Database | SQLAlchemy 2.x + psycopg2-binary | SQLAlchemy 2.x style only - not legacy 1.x |
| Databricks integration | databricks-sdk | Jobs API and SecretsAPI |
| Cron parsing | croniter | Human-readable cron preview in Schedules page |
| Local dev env loading | python-dotenv | No-op in production |

Python version: **3.11+**. Type hints required throughout.

---

## Lakebase schema

Two schemas in Lakebase. DDL lives in `scripts/init_lakebase.sql`.

**`stackql_app`** - app metadata, managed by the Streamlit app:
- `queries(id, name, description, query_text, provider, created_by, created_at, updated_at)`
- `schedules(id, query_id, job_id, cron_expression, target_schema, target_table, is_active, last_run_at, last_run_status, created_at, updated_at)`
- `provider_config(id, provider, env_var_name, secret_scope, secret_key, created_by, created_at)` - unique on `(provider, env_var_name)`

**`stackql_inventory`** - cloud inventory results, managed by scheduled Jobs:
- Tables created dynamically by Job runs, named by the user at schedule creation time
- Materialised views over those tables for dashboard consumption

---

## Service layer contracts

All business logic goes through services. Pages and components must not contain SQL, SDK calls, or API calls directly.

### `db/models.py`

Dataclass models as the transport layer between service and UI. Define `Query`, `Schedule`, `ProviderConfig`. No SQLAlchemy ORM classes - use raw SQL in `db/service.py` with dataclasses as the return type.

### `db/service.py`

All Lakebase CRUD. Connection string built from `LAKEBASE_*` env vars. Use SQLAlchemy `create_engine` with `pool_pre_ping=True`. Expose:

- `get_queries() -> list[Query]`
- `get_query(id: int) -> Query | None`
- `save_query(query: Query) -> int`
- `update_query(id: int, query: Query) -> None`
- `delete_query(id: int) -> None`
- `get_schedules() -> list[Schedule]`
- `save_schedule(schedule: Schedule) -> int`
- `update_schedule(id: int, schedule: Schedule) -> None`
- `delete_schedule(id: int) -> None`
- `get_provider_config() -> list[ProviderConfig]`
- `save_provider_config(config: ProviderConfig) -> None`
- `delete_provider_config(id: int) -> None`
- `get_inventory_tables() -> list[dict]` - lists tables and row counts in `stackql_inventory` schema
- `get_inventory_preview(table_name: str, limit: int = 100) -> pd.DataFrame`
- `refresh_materialised_view(view_name: str) -> None`

No raw SQL outside this module.

### `services/query_service.py`

Wraps pystackql. Protocol:

1. Call `db_svc.get_provider_config()`, filter by the selected provider
2. For each config entry, call `WorkspaceClient().secrets.get_secret(scope, key)` to resolve the value
3. Inject resolved values into `os.environ`
4. Track which keys were injected
5. Instantiate `StackQL(download_dir="/tmp/stackql")`
6. Call `stackql.execute(query_text)` and coerce the result to a `pd.DataFrame`
7. In a `finally` block, remove all injected keys from `os.environ`
8. Return the DataFrame

Never store resolved secret values in session state, logs, or any persistent store. The `finally` block must run even if execution fails.

If `STACKQL_LOCAL_DEV=true` is set, read credentials from env vars directly (offline fallback for development without workspace access).

### `services/job_service.py`

Wraps Databricks Jobs SDK. Expose:

- `create_inventory_job(query: Query, schedule: Schedule) -> str` - returns `job_id`
- `update_inventory_job(job_id: str, schedule: Schedule) -> None`
- `delete_inventory_job(job_id: str) -> None`
- `pause_inventory_job(job_id: str) -> None`
- `resume_inventory_job(job_id: str) -> None`
- `get_job_run_status(job_id: str) -> dict | None`

When creating a job, the task environment config must reference secret scope keys using Databricks interpolation syntax (`{{secrets/scope/key}}`), not resolved values. The job runner script is `app/src/jobs/run_query.py`.

### `services/ai_service.py`

Wraps the Anthropic API. Protocol:

1. Call `WorkspaceClient().secrets.get_secret("stackql-inventory", "anthropic-api-key")` to resolve the key
2. Instantiate `anthropic.Anthropic(api_key=key)`
3. Pass the key directly to the client - do not set `ANTHROPIC_API_KEY` env var
4. Discard the resolved key after the client is instantiated (it's held by the client object only for the duration of the call)

Expose:
- `stream_chat(messages: list[dict], mode: str) -> Generator[str, None, None]` - mode is `"query"` or `"results"`
- `extract_sql_from_response(response: str) -> str | None` - returns the first SQL fenced code block, stripped of markers, or None

Two system prompts:

**Query writing mode** - orient the assistant as a StackQL expert. Include: StackQL SQL syntax (SELECT only in query mode), table naming convention (`provider.service.resource`), requirement for WHERE clause parameters (region, project, subscriptionId etc.), instruction to format SQL in a fenced `sql` code block.

**Results interpretation mode** - orient the assistant as a cloud infrastructure analyst. Include: focus on summarising what the data shows, flagging notable findings (high counts, unusual states, cost or security concerns), and suggesting follow-up queries. Instruct it not to repeat the data verbatim.

If `STACKQL_LOCAL_DEV=true`, fall back to `os.getenv("ANTHROPIC_API_KEY")`.

### `jobs/run_query.py`

Standalone script executed by Databricks Jobs. Accepts CLI args: `--query-id`, `--target-schema`, `--target-table`. Workflow:

1. Read `LAKEBASE_*` env vars (injected by the job environment config from secret scope)
2. Load the query text from Lakebase `stackql_app.queries` by query ID
3. Resolve provider credentials from the job environment (same secret scope injection pattern)
4. Execute via pystackql
5. Write result DataFrame to `{target_schema}.{target_table}` in Lakebase (replace semantics)
6. Call `REFRESH MATERIALIZED VIEW` if a view named `{target_table}_mv` exists
7. Update `schedules.last_run_at` and `schedules.last_run_status`

---

## UI design

### General

All pages use `layout="wide"`. The IDE page is two-column. All other pages are single-column. No custom CSS unless strictly necessary for the editor component.

### IDE page (`pages/ide.py`)

**Layout:** Two columns, approximately 65/35 width split. Left column contains the editor and results. Right column contains the AI chat panel.

**Left column - editor:**

Use `streamlit-code-editor` (`from code_editor import code_editor`). Configure with:
- `lang="sql"`
- toolbar buttons for Run (maps to submit command) and Clear
- `showLineNumbers: True`
- height as a min/max tuple e.g. `[10, 30]`

Store editor content in `st.session_state["ide_editor_content"]`. When the editor fires a submit command (Run button or Ctrl+Enter), `response["text"]` contains the query.

**Left column - toolbar row** (between editor and results):

- Provider `st.selectbox` populated from `db_svc.get_provider_config()`, unique provider names
- Run button - triggers `query_service.execute(query_text, provider)` with `st.spinner`
- Save Query button - opens `st.dialog` with name and description fields
- Explain Query button - sets `st.session_state["ide_pending_chat_prompt"]` to a pre-built prompt containing the current query text

**Left column - results area:**

On success: `results_table` component renders the DataFrame.
On empty result: `st.info("Query returned no rows.")`
On error: `st.error(error_message)` with the raw StackQL error.

**Left column - sidebar:**

Query library in `st.sidebar`. List saved queries as buttons. Clicking loads query into editor via session state. Delete button with popover confirmation per query.

**Right column - AI chat panel:**

Mode toggle at top: `st.segmented_control` or `st.radio` with options `"Write Query"` and `"Interpret Results"`. Stored in `st.session_state["ide_chat_mode"]`.

Chat history in `st.session_state["ide_chat_messages"]` as `list[dict]` with `role` and `content` keys. Render history on every rerender using `st.chat_message`.

At the top of the right column render loop, check for `st.session_state["ide_pending_chat_prompt"]`. If present, treat it as a submitted user message (append to history, call AI service, clear the key).

`st.chat_input` fixed at the bottom. On submit, append user message and call `ai_service.stream_chat()` via `st.write_stream`.

After each assistant response, check for a SQL code block using `ai_service.extract_sql_from_response()`. If found, render an "Insert into editor" `st.button` that sets `st.session_state["ide_editor_content"]` to the extracted SQL.

**"Interpret Results" pre-populate:**

The results component renders an "Interpret Results" button. Clicking it serialises the current DataFrame as a markdown table (top 20 rows max) and sets `st.session_state["ide_pending_chat_prompt"]` with the data and an interpretation request.

### Schedules page (`pages/schedules.py`)

- Summary: `st.dataframe` of all schedules joined with query names and last run status. Use `st.column_config` for status colour coding.
- "New Schedule" opens `st.dialog`. Fields: query selector (dropdown of saved queries), cron expression (text input with live human-readable preview via `croniter`), target schema (default `stackql_inventory`), target table name.
- On save: `db_svc.save_schedule()` then `job_svc.create_inventory_job()` with `st.spinner`.
- Per-row actions: pause/resume toggle, delete (with `st.popover` confirmation).
- Last run status as coloured indicator: SUCCESS = green, FAILED = red, no runs = grey.

### Inventory browser page (`pages/inventory.py`)

- Top metrics row: total tables, total rows (sum across all inventory tables), last refresh timestamp across all tables.
- Table list as `st.dataframe` with row selection enabled. Columns: table name, row count, last updated, materialised view exists.
- On row selection, render a preview panel below: top 100 rows of the selected table as `st.dataframe`.
- Refresh button per table: calls `db_svc.refresh_materialised_view(table_name + "_mv")`.

### Provider config page (`pages/providers.py`)

- Table of existing mappings: provider, env var name, secret scope, secret key masked as `***`, created by, created at. Delete button per row.
- "Add Mapping" via `st.dialog` or `st.expander`. Fields: provider (free text or select from known list: aws, azure, google, databricks, github, cloudflare), env var name, secret scope, secret key.
- On save: call `SecretsAPI.get_secret(scope, key)` - if it raises `NotFound`, show `st.error` and do not save. If found, call `db_svc.save_provider_config()`.
- Never display resolved secret values anywhere.
- "Test" button per row: resolves the secret, injects the env var, calls `stackql.execute("SHOW PROVIDERS")`, reports pass/fail, cleans up env var. Does not surface the value.

### Components

**`components/editor.py`**

Thin wrapper around `code_editor`. Reads/writes `st.session_state["ide_editor_content"]`. Detects submit command in the response dict. Returns `tuple[str | None, bool]` - `(query_text, submitted)`. All `code_editor` configuration is encapsulated here.

**`components/results_table.py`**

Accepts a `pd.DataFrame`, execution time in seconds, and an error string (mutually exclusive with DataFrame). Renders: row count + execution time caption, `st.dataframe` with `use_container_width=True`, "Interpret Results" button. Handles empty DataFrame and error states. Sets `st.session_state["ide_pending_chat_prompt"]` when "Interpret Results" is clicked.

---

## Environment variables

Set by the Databricks App runtime in production via `app.yml` secret scope bindings. Set in `app/.env` for local development.

```
DATABRICKS_HOST          # auto-injected by App runtime; set in .env locally
DATABRICKS_TOKEN         # auto-injected by App runtime; set in .env locally
LAKEBASE_HOST
LAKEBASE_PORT            # default 5432
LAKEBASE_DATABASE
LAKEBASE_USER
LAKEBASE_PASSWORD
STACKQL_LOCAL_DEV        # set to "true" for offline local dev only - never in production
```

Cloud provider credentials and the Anthropic API key are **not** static env vars. They are resolved at call time from Databricks Secrets via the SDK.

---

## app.yml

The Databricks App manifest. Must declare:
- `command: ["python", "-m", "streamlit", "run", "src/main.py"]`
- `env` entries for all `LAKEBASE_*` vars referencing secret scope keys in `stackql-inventory`

---

## Infra - Databricks Asset Bundles (`infra/bundles/`)

`databricks.yml` must define resources for:
- Lakebase instance
- Lakehouse Federation foreign connection to Lakebase
- UC foreign catalog (`stackql_inventory_catalog`) over the `stackql_inventory` Lakebase schema
- UC grants on the foreign catalog
- The Databricks App referencing `../../app` as source
- App resource bindings for `LAKEBASE_*` secret scope keys
- Template Job definition used as the base when `job_service.py` clones per-schedule jobs

Use `targets` for `dev` and `prod` with variable substitution for instance names, catalog names, and workspace host.

## Infra - stackql-deploy (`infra/stackql-deploy/`)

`stackql_manifest.yml` defines demo/test cloud provider resources (AWS, GCP stacks). Follow the stateless IaC pattern: tags as natural keys, no state files. These are not required for the app to function - they provide targets for inventory queries in demo environments.

---

## Local development setup

### Prerequisites

- Databricks CLI v0.200+
- Python 3.11+
- Docker

### Steps

1. Create and activate a virtual environment in `app/`:
   ```
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Start local Postgres:
   ```
   docker run -d --name stackql-dev-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16
   ```

3. Initialise schema:
   ```
   psql -h localhost -U postgres -f scripts/init_lakebase.sql
   ```

4. Create `app/.env` (git-ignored, never commit):
   ```
   DATABRICKS_HOST=https://<workspace>.azuredatabricks.net
   DATABRICKS_TOKEN=dapi...
   LAKEBASE_HOST=localhost
   LAKEBASE_PORT=5432
   LAKEBASE_DATABASE=postgres
   LAKEBASE_USER=postgres
   LAKEBASE_PASSWORD=postgres
   ```

5. Run:
   ```
   databricks apps run-local --prepare-environment --debug
   ```
   or:
   ```
   cd app && streamlit run src/main.py
   ```

### `.vscode/launch.json`

Provide two configurations:
- `"Streamlit: run app"` - launches `streamlit run src/main.py` with `cwd` set to `app/` and `envFile` pointing at `app/.env`
- `"Databricks: run-local (attach)"` - attaches to the debugger on port 5678 started by `databricks apps run-local --debug`

---

## Coding conventions

- Python 3.11+. Type hints on all function signatures.
- Use `logging` module throughout. No `print()`.
- SQLAlchemy 2.x style only (`Session`, `text()`, `execute()`). Not legacy 1.x.
- No raw SQL in page or component files. All DB operations go through `db/service.py`.
- No SDK calls in page or component files. All Jobs operations go through `job_service.py`. All secrets resolution goes through the relevant service.
- No LLM calls in page or component files. All AI calls go through `ai_service.py`.
- Session state keys are namespaced by page: `ide_*`, `schedules_*`, `inventory_*`, `providers_*`. The single shared key is `ide_pending_chat_prompt`.
- `st.set_page_config` at the top of every page file.
- Chat history (`ide_chat_messages`) is a `list[dict]` with string values only. Do not store SDK objects, DataFrames, or Anthropic response objects in session state.
- SQL extracted from AI responses must be stripped of fenced code block markers before being placed in the editor.
- Secrets must not appear in logs, session state, error messages, or UI. If a secret resolution fails, show the scope and key name in the error - never the value.

---

## Testing

Tests live in `app/tests/`. Use `pytest`. Run with:
```
cd app && pytest tests/ -v
```

Rules:
- Mock `pystackql.StackQL` with a fixture returning a known `pd.DataFrame`
- Mock `databricks.sdk.WorkspaceClient` with `unittest.mock.MagicMock`
- Mock `anthropic.Anthropic` with a fixture returning a known streaming response
- Mock SQLAlchemy sessions for DB service tests
- No live cloud, workspace, or API calls in tests
- Set `STACKQL_LOCAL_DEV=true` in the test environment to short-circuit secrets resolution

---

## Error handling

Handle these explicitly - do not let them surface as unhandled exceptions:

| Failure | Where | How to handle |
|---|---|---|
| pystackql binary download fails | query_service, job runner | Raise `RuntimeError` with message directing user to check `/tmp/stackql` permissions |
| `databricks.sdk.errors.NotFound` on secret lookup | query_service, ai_service | Raise `RuntimeError` with scope/key name and direction to Provider Config page |
| Anthropic API error / rate limit | ai_service | Catch, yield an error string from the generator, let the chat panel display it via `st.error` |
| Lakebase connection failure | db/service.py | Catch on first connection attempt, raise `RuntimeError`. The app entrypoint should catch this and show `st.error` as a top-level banner. |
| Databricks Job creation failure | job_service | Catch SDK errors, re-raise with the specific permission or quota message |
| StackQL query returns empty result | query_service | Return an empty DataFrame - not an error |
| StackQL query returns error | query_service | Raise `RuntimeError` with the raw StackQL error message |
| `code_editor` component load failure | editor component | Catch, show `st.error` with instructions - do not fall back silently to `st.text_area` |

---

## What not to do

- Do not use LangChain, LangGraph, or any other LLM orchestration library. Call the Anthropic API directly.
- Do not use `dbutils.secrets.get()`. Use `WorkspaceClient().secrets.get_secret()` which works both in the workspace and locally with a configured token.
- Do not store resolved secret values in `st.session_state`, module-level variables, or any cache.
- Do not use `@st.cache_data` or `@st.cache_resource` on functions that handle secrets.
- Do not use SQLAlchemy ORM (declarative model classes). Use `text()` with dataclass models.
- Do not use `st.text_area` as the primary SQL editor.
- Do not write SQL in page files.
- Do not write SDK calls in page files.
- Do not use `streamlit-monaco` - use `streamlit-code-editor` which has a more complete API.
- Do not create module-level Lakebase connections or SDK clients. Instantiate them inside service functions where the connection string or credentials are available.
- Do not schedule queries by running a background thread inside the Streamlit app. All scheduling is handled by Databricks Jobs.

---

## Out of scope

Do not build these unless explicitly asked:

- Multi-workspace support
- Custom StackQL provider registration via the UI
- Row-level security on inventory tables
- Email or webhook alerting on Job failures (use Databricks Job notification settings)
- Persisting chat history to Lakebase across sessions
- Monaco autocomplete for StackQL provider/service/resource schema paths
- User-facing admin controls for managing the Lakebase instance or UC federation
