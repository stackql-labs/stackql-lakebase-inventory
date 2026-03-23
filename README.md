# stackql-lakebase-inventory
Cloud asset inventory using StackQL materialized views persisted in Databricks Lakebase Postgres, synced to Unity Catalog and surfaced in Dashboards and Genie.


```mermaid
flowchart TB
    subgraph cloud["Cloud providers"]
        direction TB
        dbx[Databricks]
        aws[AWS]
        gcp[Google Cloud]
        az[...]
    end

    sq["StackQL runner\n(materialized views)"]

    subgraph databricks["Databricks platform"]
        pg[("Lakebase Postgres")]
        uc["Unity Catalog\n(Lakehouse Federation)"]
        dash["Dashboards"]
        genie["Genie space"]
    end

    cloud -->|"inventory queries"| sq
    sq -->|"persist views"| pg
    pg -->|"federated query"| uc
    uc --> dash
    uc --> genie
```    

### Generate Credentials

With an authenticated `stackql` session using OAuth creds, generate a short lived token for access to a Lakebase Postgres instance:

```bash
LAKEBASE_TOKEN=`./stackql exec --output text -H "SELECT token FROM databricks_workspace.postgres.credentials WHERE deployment_name = 'dbc-74aa95f7-8c7e' AND endpoint = 'projects/stackql/branches/production/endpoints/primary'"`
```

Open a `stackql` interactive shell (authenticated to cloud providers) with a configured backend of the Lakebase Postgres instance using the generated credentials (the `--export.alias=stackql_export` flag will create all materialized views in a schema named `stackql_export`):

```bash
./stackql \
--sqlBackend="{\"dbEngine\": \"postgres_tcp\", \"sqlDialect\": \"postgres\", \"dsn\": \"postgres://0b7b23de-3e7d-4432-812c-cf517e079a22:${LAKEBASE_TOKEN}@ep-quiet-cell-d60dcvax.database.ap-southeast-2.cloud.databricks.com/databricks_postgres?sslmode=require\"}" \
--export.alias=stackql_export \
shell
```

then run queries to create or refresh materialized views, for example:

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_workspace_assignments
AS
SELECT
w.workspace_id,
w.workspace_name,
w.workspace_status,
JSON_EXTRACT(wa.principal, '$.display_name') as display_name,
JSON_EXTRACT(wa.principal, '$.principal_id') as principal_id,
JSON_EXTRACT(wa.principal, '$.service_principal_name') as service_principal_name,
wa.permissions,
wa.error
FROM databricks_account.provisioning.workspaces w
LEFT JOIN databricks_account.iam.workspace_assignment wa
ON w.workspace_id = wa.workspace_id
WHERE account_id = 'ebfcc5a9-9d49-4c93-b651-b3ee6cf1c9ce';
```

this will create the table `databricks_postgres.stackql_export.vw_workspace_assignments` in the Lakebase instance.  

you can do this directly using `exec` as well, for example:

```bash
./stackql \
--sqlBackend="{\"dbEngine\": \"postgres_tcp\", \"sqlDialect\": \"postgres\", \"dsn\": \"postgres://0b7b23de-3e7d-4432-812c-cf517e079a22:${LAKEBASE_TOKEN}@ep-quiet-cell-d60dcvax.database.ap-southeast-2.cloud.databricks.com/databricks_postgres?sslmode=require\"}" \
--export.alias=stackql_export \
exec \
"SELECT * FROM databricks_account.provisioning.vw_networks WHERE account_id = 'ebfcc5a9-9d49-4c93-b651-b3ee6cf1c9ce'"
```

