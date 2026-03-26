# Architecture - StackQL Cloud Inventory

This document describes the system architecture using the C4 model. Each level progressively zooms in: system context, containers, and then the internal components of the Streamlit app. Annotations explain key design decisions at each level.

---

## C4 Level 1 - System Context

Who uses the system, what external systems it interacts with, and where it sits in the broader landscape.

```mermaid
C4Context
    title StackQL Cloud Inventory - System Context

    Person(engineer, "Cloud / Data Engineer", "Defines and schedules inventory queries. Manages provider credentials. Browses inventory data.")
    Person(analyst, "Data Analyst / Consumer", "Queries cloud inventory via DBSQL dashboards or Genie spaces.")

    System(app, "StackQL Cloud Inventory", "Databricks App. Provides a SQL IDE, schedule management, AI query assistant, and inventory browser.")

    System_Ext(aws, "Amazon Web Services", "Queried as a StackQL provider via REST APIs.")
    System_Ext(gcp, "Google Cloud Platform", "Queried as a StackQL provider via REST APIs.")
    System_Ext(azure, "Microsoft Azure", "Queried as a StackQL provider via REST APIs.")
    System_Ext(other_providers, "Other Providers", "Databricks, GitHub, Cloudflare, Okta etc. via StackQL registry.")
    System_Ext(anthropic, "Anthropic API", "Claude - powers the AI query assistant and results interpreter.")

    Rel(engineer, app, "Writes queries, manages schedules and credentials", "HTTPS / Databricks SSO")
    Rel(analyst, app, "Browses inventory data", "HTTPS / Databricks SSO")
    Rel(app, aws, "Queries cloud resources", "StackQL via REST")
    Rel(app, gcp, "Queries cloud resources", "StackQL via REST")
    Rel(app, azure, "Queries cloud resources", "StackQL via REST")
    Rel(app, other_providers, "Queries resources", "StackQL via REST")
    Rel(app, anthropic, "AI query assistance and results interpretation", "HTTPS")
```

### Context annotations

**Why Databricks Apps?** The entire platform runs inside a single Databricks workspace. There is no external web server to operate, no separate auth layer to maintain, and no VPN or private link required to reach Lakebase. The Databricks App serverless runtime handles scaling, auth via workspace SSO, and the service principal lifecycle.

**Why StackQL?** StackQL provides a unified SQL interface across cloud provider REST APIs without requiring SDK knowledge or per-provider scripting. The same SELECT syntax works against AWS, GCP, Azure, and any other provider in the registry. Queries are readable, auditable, and version-controllable.

**Why Claude as the AI backend?** The app is built and operated by StackQL Studios. Using the Anthropic API directly (rather than a gateway or a Databricks-hosted model) gives access to the most capable models with streaming support and keeps the dependency surface minimal. The API key is stored in Databricks Secrets and resolved at call time.

---

## C4 Level 2 - Containers

The major deployable units inside the Databricks workspace and how they communicate.

```mermaid
C4Container
    title StackQL Cloud Inventory - Containers

    Person(engineer, "Cloud / Data Engineer")
    Person(analyst, "Data Analyst")

    System_Boundary(workspace, "Databricks Workspace") {

        Container(streamlit_app, "StackQL Cloud Inventory App", "Python · Streamlit · Databricks Apps", "Serves the SQL IDE, schedule management UI, AI chat panel, inventory browser, and provider config. Runs on serverless app compute.")

        Container(jobs, "Inventory Jobs", "Databricks Jobs · Python", "Scheduled jobs that execute pystackql queries against cloud providers and write results to Lakebase. One job per scheduled query. Provisioned programmatically by the app via the Databricks Jobs SDK.")

        Container(job_runner, "Job Runner Script", "Python · pystackql", "Entry point script executed by each Inventory Job. Resolves secrets, sets provider env vars, runs the StackQL query, writes results to Lakebase, and refreshes materialised views.")

        ContainerDb(lakebase, "Lakebase", "Managed PostgreSQL", "Two schemas: stackql_app (app metadata - queries, schedules, provider config) and stackql_inventory (cloud inventory tables and materialised views written by Jobs).")

        Container(federation, "Lakehouse Federation", "Unity Catalog · JDBC", "Foreign catalog in UC pointing at the stackql_inventory schema in Lakebase. Provides governed, auditable access to inventory data without copying it into Delta.")

        Container(dashboards, "DBSQL Dashboards + Genie", "Databricks SQL", "Dashboards and Genie spaces that query the UC foreign catalog. Consumed by analysts and operational teams.")

        ContainerDb(secrets, "Databricks Secrets", "Secret Scopes", "Stores Lakebase credentials, cloud provider auth env vars, and the Anthropic API key. Referenced by the app and jobs at runtime - never stored in application state.")
    }

    System_Ext(cloud_providers, "Cloud Provider APIs", "AWS · GCP · Azure · others")
    System_Ext(anthropic, "Anthropic API")

    Rel(engineer, streamlit_app, "Uses", "HTTPS · Databricks SSO")
    Rel(analyst, dashboards, "Queries inventory", "DBSQL")
    Rel(streamlit_app, lakebase, "Reads/writes app metadata. Ad-hoc query results for IDE preview.", "SQLAlchemy · psycopg2")
    Rel(streamlit_app, secrets, "Resolves provider credentials and Anthropic API key at runtime", "Databricks SDK SecretsAPI")
    Rel(streamlit_app, jobs, "Creates, updates, pauses, deletes scheduled inventory jobs", "Databricks Jobs SDK")
    Rel(streamlit_app, anthropic, "Streams AI responses for query writing and results interpretation", "HTTPS")
    Rel(jobs, job_runner, "Executes", "Python subprocess")
    Rel(job_runner, secrets, "Resolves provider credentials", "Databricks SDK")
    Rel(job_runner, cloud_providers, "Queries cloud APIs", "pystackql · StackQL binary")
    Rel(job_runner, lakebase, "Writes inventory results. Refreshes materialised views.", "psycopg2")
    Rel(federation, lakebase, "Reads inventory schema via JDBC", "Lakehouse Federation")
    Rel(dashboards, federation, "Queries via UC foreign catalog", "DBSQL")
```

### Container annotations

**Lakebase schema split.** Keeping `stackql_app` (metadata) and `stackql_inventory` (results) in separate Postgres schemas serves two purposes. First, Lakehouse Federation only exposes `stackql_inventory` to UC - app metadata is never surfaced to analysts. Second, if the app is ever rebuilt or redeployed, the inventory data is decoupled from the application state.

**Jobs are provisioned dynamically.** The app does not use a fixed set of pre-defined jobs. When a user schedules a query, the app calls the Databricks Jobs SDK to create a new job, wiring the job runner script with the correct query ID, target table, and secret scope references as environment variables. The Job definition itself does not contain credential values - it references secret scope keys, which Databricks resolves at job runtime. Deleting a schedule deletes the corresponding job.

**No persistent process in the app container.** Streamlit apps on Databricks serverless compute can be stopped between sessions. All durable state lives in Lakebase (metadata) or is managed by Databricks Jobs (scheduling). The app container is stateless.

**Lakehouse Federation over direct DBSQL connection.** Federating Lakebase into UC means inventory data participates in UC governance - column masking, row filters, and access grants work the same as native Delta tables. It also means analysts never need a direct Postgres connection string.

**pystackql binary.** The StackQL binary is downloaded by pystackql on first use to `/tmp/stackql`. In the Databricks App container this path must be writable. If the container restricts execution, the binary can be bundled in the app source. The job runner has the same requirement - test binary execution early in both environments.

---

## C4 Level 3 - Components (Streamlit App)

The internal structure of the Streamlit app and how its parts relate.

```mermaid
C4Component
    title StackQL Cloud Inventory App - Components

    System_Boundary(app, "Databricks App (Streamlit)") {

        Component(main, "main.py", "Streamlit entrypoint", "Sets page config. Declares multi-page navigation. Loads .env for local development.")

        Component(ide_page, "IDE Page", "pages/ide.py", "Two-column layout. Left: Monaco SQL editor, provider selector, run/save toolbar, results dataframe. Right: AI chat panel with mode toggle, streaming responses, and insert-to-editor action for generated SQL.")

        Component(schedules_page, "Schedules Page", "pages/schedules.py", "Lists saved queries with schedule status. Dialog for new schedule: query selector, cron expression with human-readable preview, target table. Provisions and manages Databricks Jobs.")

        Component(inventory_page, "Inventory Browser Page", "pages/inventory.py", "Summary metrics. Table list with row counts and last refresh time. Row preview for selected table. Manual materialised view refresh.")

        Component(providers_page, "Provider Config Page", "pages/providers.py", "Add and manage cloud provider credential mappings (env var name to secret scope/key). Validates secret existence without surfacing values. Test connection per mapping.")

        Component(editor_component, "Editor Component", "components/editor.py", "Thin wrapper around code_editor (Monaco). Manages editor content in session state. Returns (query_text, submitted) to the IDE page.")

        Component(results_component, "Results Table Component", "components/results_table.py", "Wraps st.dataframe with row count caption, execution time, Interpret Results button, and error/empty state handling.")

        Component(db_service, "DB Service", "db/service.py", "All Lakebase CRUD via SQLAlchemy. Functions for queries, schedules, and provider_config. No raw SQL outside this module.")

        Component(db_models, "DB Models", "db/models.py", "Dataclass models: Query, Schedule, ProviderConfig. Transport layer between DB service and UI.")

        Component(query_service, "Query Service", "services/query_service.py", "Resolves provider secrets via SecretsAPI. Injects as env vars. Instantiates pystackql StackQL client. Executes query. Cleans up env vars after execution. Returns DataFrame.")

        Component(job_service, "Job Service", "services/job_service.py", "Wraps Databricks Jobs SDK. create, update, delete, pause/resume, and get run status for inventory jobs. Injects secret scope references (not values) into job environment config.")

        Component(ai_service, "AI Service", "services/ai_service.py", "Resolves Anthropic API key from Databricks Secrets. Maintains system prompts for query-writing and results-interpretation modes. Streams responses via Anthropic Python SDK. Extracts SQL code blocks from responses.")
    }

    Rel(main, ide_page, "Navigates to")
    Rel(main, schedules_page, "Navigates to")
    Rel(main, inventory_page, "Navigates to")
    Rel(main, providers_page, "Navigates to")
    Rel(ide_page, editor_component, "Renders editor, reads query text and submit state")
    Rel(ide_page, results_component, "Renders query results")
    Rel(ide_page, query_service, "Executes ad-hoc queries")
    Rel(ide_page, db_service, "Saves and loads queries")
    Rel(ide_page, ai_service, "Streams chat responses")
    Rel(schedules_page, db_service, "Reads/writes schedules and queries")
    Rel(schedules_page, job_service, "Provisions and manages Databricks Jobs")
    Rel(inventory_page, db_service, "Lists inventory tables and previews rows")
    Rel(providers_page, db_service, "Reads/writes provider_config")
    Rel(query_service, db_service, "Reads provider_config to resolve which secrets to inject")
    Rel(ai_service, db_service, "Reads provider_config for context in query-writing mode")
```

### Component annotations

**Session state ownership.** Each page owns its own session state keys with a page-specific prefix (e.g. `ide_editor_content`, `ide_chat_messages`). The `pending_chat_prompt` key is the only cross-component session state - it is written by the results component and the "Explain Query" button, and read by the chat panel on the next render cycle.

**AI chat modes.** The chat panel has two modes selectable via a toggle at the top of the right column. In **Write Query** mode the system prompt contains StackQL syntax guidance and the selected provider context. In **Interpret Results** mode the system prompt orients the assistant as a cloud infrastructure analyst and the user message includes the result set as a markdown table. Switching modes does not clear chat history - the user can mix modes in a single session.

**Secret injection lifecycle.** `query_service.py` resolves secrets, injects them into `os.environ`, runs the StackQL query, and removes them from `os.environ` in a `finally` block regardless of query outcome. Secrets are never stored in Streamlit session state. The same pattern applies in `ai_service.py` for the Anthropic API key - resolve, use, discard.

**Job service does not store credentials.** When `job_service.py` creates a Databricks Job, the job task environment config references secret scope keys using the Databricks `{{secrets/scope/key}}` interpolation syntax. The resolved values are never written to the job definition. This means the Jobs API response does not contain credential values and audit logs do not expose them.

---

## Data model

The `stackql_app` schema in Lakebase stores application metadata. The `stackql_inventory` schema stores cloud inventory results written by scheduled Jobs.

```mermaid
erDiagram
    queries {
        serial      id           PK
        text        name
        text        description
        text        query_text
        text        provider
        text        created_by
        timestamptz created_at
        timestamptz updated_at
    }

    schedules {
        serial      id              PK
        int         query_id        FK
        text        job_id
        text        cron_expression
        text        target_schema
        text        target_table
        boolean     is_active
        timestamptz last_run_at
        text        last_run_status
        timestamptz created_at
        timestamptz updated_at
    }

    provider_config {
        serial      id           PK
        text        provider
        text        env_var_name
        text        secret_scope
        text        secret_key
        text        created_by
        timestamptz created_at
    }

    queries ||--o{ schedules : "scheduled as"
```

`stackql_inventory` tables are created dynamically by Job runs. Table names are defined by the user at schedule creation time (e.g. `aws_ec2_instances_us_east_1`). Materialised views over these tables are created manually or via the Inventory Browser refresh action.

---

## Scheduled job execution flow

How a single scheduled inventory job runs from trigger to data availability.

```mermaid
sequenceDiagram
    participant DB  as Databricks Jobs
    participant JR  as Job Runner (run_query.py)
    participant SEC as Databricks Secrets
    participant SQ  as StackQL (pystackql)
    participant CP  as Cloud Provider API
    participant LB  as Lakebase (stackql_inventory)
    participant MV  as Materialised View

    DB  ->> JR  : trigger scheduled run
    JR  ->> SEC : resolve provider credential env vars
    SEC -->> JR : secret values
    JR  ->> JR  : inject into os.environ
    JR  ->> SQ  : execute(query_text)
    SQ  ->> CP  : REST API calls
    CP  -->> SQ : JSON responses
    SQ  -->> JR : DataFrame
    JR  ->> JR  : clear env vars
    JR  ->> LB  : write DataFrame to target_table (replace or append)
    JR  ->> MV  : REFRESH MATERIALIZED VIEW (if exists)
    JR  ->> LB  : update schedules.last_run_at, last_run_status
```

---

## Local development capability matrix

| Capability | Works locally | Notes |
|---|---|---|
| Streamlit UI | Yes | Full hot-reload via `streamlit run` or `databricks apps run-local` |
| pystackql query execution | Yes | Binary downloaded to `/tmp/stackql` on first run |
| App metadata (stackql_app schema) | Yes | Local Postgres via Docker substitutes for Lakebase |
| Databricks Secrets API | Yes | Requires `DATABRICKS_HOST` + `DATABRICKS_TOKEN` in `.env` |
| AI chat (Anthropic API) | Yes | Key resolved from workspace secrets or `ANTHROPIC_API_KEY` env var |
| Databricks Jobs SDK | Yes | Creates real jobs in the connected workspace |
| Lakebase (real instance) | No | Local Postgres used as substitute |
| Databricks App SSO / OAuth | No | Auth bypassed locally - no login prompt |
| `DATABRICKS_TOKEN` auto-injection | No | Must be set manually in `.env` |

---

## Infrastructure split

Infrastructure is intentionally split across two tools based on what is being provisioned.

```mermaid
flowchart TD
    subgraph bundles["Databricks Asset Bundles (infra/bundles/)"]
        A[Lakebase instance]
        B[Lakehouse Federation connection]
        C[UC foreign catalog]
        D[UC permissions]
        E[Databricks App deployment]
        F[Secret scope bindings]
        G[Template Job definition]
    end

    subgraph sdeploy["stackql-deploy (infra/stackql-deploy/)"]
        H[AWS demo resources\ne.g. VPC, EC2, IAM]
        I[GCP demo resources\ne.g. networks, instances]
        J[Azure demo resources\ne.g. resource groups, VMs]
    end

    bundles -->|deployed via| K[databricks bundle deploy]
    sdeploy -->|deployed via| L[stackql-deploy build]
```

**Asset Bundles** own everything inside the Databricks workspace: the Lakebase instance, federation, UC catalog, the app itself, and the template Job that `job_service.py` clones for each scheduled query.

**stackql-deploy** owns cloud provider resources that the inventory queries will target in demo and test environments. It uses the stateless IaC pattern (tags as natural keys, no state files). These are optional - in production the inventory queries point at real existing infrastructure.
