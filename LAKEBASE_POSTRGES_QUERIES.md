```sql
/* vw_projects */
SELECT
  SPLIT_PART(name, '/', -1) as name,
  create_time,
  initial_endpoint_spec,
  spec,  
  JSON_EXTRACT(status, '$.compute_last_active_time') AS compute_last_active_time,
  JSON_EXTRACT(status, '$.default_endpoint_settings.autoscaling_limit_min_cu') AS min_cu,
  JSON_EXTRACT(status, '$.default_endpoint_settings.autoscaling_limit_max_cu') AS max_cu,
  JSON_EXTRACT(status, '$.default_endpoint_settings.suspend_timeout_duration') AS suspend_timeout_duration,
  JSON_EXTRACT(status, '$.display_name') AS display_name,
  JSON_EXTRACT(status, '$.enable_pg_native_login') AS enable_pg_native_login,
  JSON_EXTRACT(status, '$.history_retention_duration') AS history_retention_duration,
  JSON_EXTRACT(status, '$.owner') AS owner,
  JSON_EXTRACT(status, '$.pg_version') AS pg_version,
  uid,
  update_time
FROM databricks_workspace.postgres.projects
WHERE deployment_name = 'dbc-74aa95f7-8c7e';

SELECT name, owner, pg_version, min_cu, max_cu 
FROM databricks_workspace.postgres.vw_projects
WHERE deployment_name = 'dbc-74aa95f7-8c7e';
```

```sql
/* vw_branches */
SELECT
SPLIT_PART(name, '/', -1) as name,
create_time,
project_id,
spec,
JSON_EXTRACT(status, '$.branch_id') as branch_id,
JSON_EXTRACT(status, '$.current_state') as current_state,
JSON_EXTRACT(status, '$.default') as default,
JSON_EXTRACT(status, '$.is_protected') as is_protected,
JSON_EXTRACT(status, '$.logical_size_bytes') as logical_size_bytes,
JSON_EXTRACT(status, '$.state_change_time') as state_change_time,
uid,
update_time
FROM databricks_workspace.postgres.branches
WHERE project_id = 'stackql'
AND deployment_name = 'dbc-74aa95f7-8c7e';

SELECT name, project_id, branch_id, current_state 
FROM databricks_workspace.postgres.vw_branches
WHERE project_id = 'stackql'
AND deployment_name = 'dbc-74aa95f7-8c7e';
```

```sql
/* vw_databases */
SELECT
SPLIT_PART(name, '/', -1) as name,
project_id,
branch_id,
spec,
JSON_EXTRACT(status, '$.postgres_database') as postgres_database,
SPLIT_PART(JSON_EXTRACT(status, '$.role'), '/', -1) as role
FROM databricks_workspace.postgres.databases
WHERE deployment_name = 'dbc-74aa95f7-8c7e'
AND project_id = 'stackql'
AND branch_id = 'production';

SELECT name, project_id, branch_id, postgres_database, role 
FROM databricks_workspace.postgres.vw_databases
WHERE deployment_name = 'dbc-74aa95f7-8c7e'
AND project_id = 'stackql'
AND branch_id = 'production';
```

```sql
/* vw_roles */
SELECT
SPLIT_PART(name, '/', -1) as name,
create_time,
project_id,
branch_id,
spec,
JSON_EXTRACT(status, '$.attributes.bypassrls') as bypassrls,
JSON_EXTRACT(status, '$.attributes.createdb') as createdb,
JSON_EXTRACT(status, '$.attributes.createrole') as createrole,
JSON_EXTRACT(status, '$.auth_method') as auth_method,
JSON_EXTRACT(status, '$.identity_type') as identity_type,
JSON_EXTRACT(status, '$.membership_roles') as membership_roles,
JSON_EXTRACT(status, '$.postgres_role') as postgres_role,
update_time
FROM databricks_workspace.postgres.roles
WHERE project_id = 'stackql'
AND branch_id = 'production'
AND deployment_name = 'dbc-74aa95f7-8c7e';

SELECT name, project_id, branch_id, createdb, createrole, auth_method, identity_type, membership_roles, postgres_role  
FROM databricks_workspace.postgres.vw_roles
WHERE deployment_name = 'dbc-74aa95f7-8c7e'
AND project_id = 'stackql'
AND branch_id = 'production';
```

```sql
/* vw_endpoints */
SELECT
SPLIT_PART(name, '/', -1) as name,
create_time,
project_id,
branch_id,
spec,
JSON_EXTRACT(status, '$.autoscaling_limit_max_cu') as max_cu,
JSON_EXTRACT(status, '$.autoscaling_limit_min_cu') as min_cu,
JSON_EXTRACT(status, '$.current_state') as current_state,
JSON_EXTRACT(status, '$.disabled') as disabled,
JSON_EXTRACT(status, '$.endpoint_type') as endpoint_type,
JSON_EXTRACT(status, '$.last_active_time') as last_active_time,
JSON_EXTRACT(status, '$.settings') as settings,
JSON_EXTRACT(status, '$.group.enable_readable_secondaries') as group_enable_readable_secondaries,
JSON_EXTRACT(status, '$.group.max') as group_max,
JSON_EXTRACT(status, '$.group.min') as group_min,
JSON_EXTRACT(status, '$.hosts.host') as host,
JSON_EXTRACT(status, '$.hosts.read_write_pooled_host') as read_write_pooled_host,
uid,
update_time
FROM databricks_workspace.postgres.endpoints
WHERE project_id = 'stackql'
AND branch_id = 'production'
AND deployment_name = 'dbc-74aa95f7-8c7e';

SELECT name, project_id, branch_id, min_cu, max_cu, current_state, endpoint_type, host
FROM databricks_workspace.postgres.vw_endpoints
WHERE deployment_name = 'dbc-74aa95f7-8c7e'
AND project_id = 'stackql'
AND branch_id = 'production';
```

```sql
/* vw_endpoints */
SELECT token FROM databricks_workspace.postgres.credentials WHERE deployment_name = 'dbc-74aa95f7-8c7e' 
AND endpoint = 'projects/stackql/branches/production/endpoints/primary';
```