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
export DATABRICKS_TOKEN=xxx # use a PAT for user data plane operations

AUTH='{ "databricks_workspace": { "type": "bearer", "credentialsenvvar": "DATABRICKS_TOKEN" }}'
LAKEBASE_TOKEN=`./stackql exec --auth="${AUTH}" --output text -H "SELECT token FROM databricks_workspace.postgres.credentials WHERE deployment_name = 'dbc-74aa95f7-8c7e' AND endpoint = 'projects/stackql/branches/production/endpoints/primary'"`
```

Open a `stackql` interactive shell (authenticated to cloud providers) with a configured backend of the Lakebase Postgres instance using the generated credentials (the `--export.alias=stackql_export` flag will create all materialized views in a schema named `stackql_export`):

--auth="${AUTH}" \


```bash
./stackql \
--sqlBackend="{\"dbEngine\": \"postgres_tcp\", \"sqlDialect\": \"postgres\", \"dsn\": \"postgres://javen%40stackql.io:${LAKEBASE_TOKEN}@ep-quiet-cell-d60dcvax.database.ap-southeast-2.cloud.databricks.com/stackql?sslmode=require\"}" \
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
json_extract_path_text(wa.principal, 'display_name') as display_name,
json_extract_path_text(wa.principal, 'principal_id') as principal_id,
json_extract_path_text(wa.principal, 'service_principal_name') as service_principal_name,
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
"SELECT ..."
```

## additional queries

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_workspaces
AS
SELECT
  w.account_id,
  w.workspace_id,
  w.workspace_name,
  w.workspace_status,
  w.workspace_status_message,
  w.cloud,
  w.aws_region,
  w.location,
  w.deployment_name,
  w.pricing_tier,
  w.compute_mode,
  w.storage_mode,
  w.credentials_id,
  w.storage_configuration_id,
  w.network_id,
  w.network_connectivity_config_id,
  w.managed_services_customer_managed_key_id,
  w.storage_customer_managed_key_id,
  w.private_access_settings_id,
  w.creation_time,
  w.custom_tags
FROM databricks_account.provisioning.workspaces w
WHERE account_id = 'ebfcc5a9-9d49-4c93-b651-b3ee6cf1c9ce';
```

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_storage_configs
AS
SELECT
    s.account_id,
    s.storage_configuration_id,
    s.storage_configuration_name,
    s.creation_time,
    s.role_arn,
    split_part(s.role_arn, '/', -1) as role_name,
    json_extract_path_text(s.root_bucket_info, 'bucket_name') as root_bucket_name
FROM databricks_account.provisioning.storage s
WHERE account_id = 'ebfcc5a9-9d49-4c93-b651-b3ee6cf1c9ce';
```

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_credentials
AS
SELECT
    c.account_id,
    c.credentials_id,
    c.credentials_name,
    c.creation_time,
    json_extract_path_text(c.aws_credentials, 'sts_role', 'role_arn') as aws_role_arn,
    split_part(json_extract_path_text(c.aws_credentials, 'sts_role', 'role_arn'), '/', -1) as aws_role_name
FROM databricks_account.provisioning.credentials c
WHERE account_id = 'ebfcc5a9-9d49-4c93-b651-b3ee6cf1c9ce';
```

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_metastore_storage_credentials
AS
SELECT
  m.name,
  m.default_data_access_config_id,
  m.global_metastore_id,
  m.metastore_id,
  m.storage_root_credential_id,
  m.delta_sharing_organization_name,
  m.storage_root_credential_name,
  m.cloud,
  m.created_at,
  m.created_by,
  m.delta_sharing_recipient_token_lifetime_in_seconds,
  m.delta_sharing_scope,
  m.external_access_enabled,
  m.owner,
  m.privilege_model_version,
  m.region,
  m.storage_root,
  m.updated_at,
  m.updated_by,
  sc.id AS storage_credential_id,
  sc.name AS storage_credential_name,
  sc.full_name,
  json_extract_path_text(sc.aws_iam_role, 'external_id') as external_id,
  json_extract_path_text(sc.aws_iam_role, 'role_arn') as role_arn,
  split_part(json_extract_path_text(sc.aws_iam_role, 'role_arn'), '/', -1) as role_name,
  json_extract_path_text(sc.aws_iam_role, 'unity_catalog_iam_arn') as unity_catalog_iam_arn,
  sc.azure_managed_identity,
  sc.azure_service_principal,
  sc.cloudflare_api_token,
  sc.comment,
  sc.created_at AS sc_created_at,
  sc.created_by AS sc_created_by,
  sc.databricks_gcp_service_account,
  sc.isolation_mode,
  sc.owner AS sc_owner,
  sc.read_only,
  sc.updated_at AS sc_updated_at,
  sc.updated_by AS sc_updated_by,
  sc.used_for_managed_storage
FROM databricks_account.catalog.account_metastores m
LEFT JOIN databricks_account.catalog.account_storage_credentials sc
  ON sc.metastore_id = m.metastore_id
  AND sc.account_id = 'ebfcc5a9-9d49-4c93-b651-b3ee6cf1c9ce'
WHERE m.account_id = 'ebfcc5a9-9d49-4c93-b651-b3ee6cf1c9ce';
```

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_workspace_settings
AS
SELECT
  w.deployment_name,
  (jsonb_build_object(
    'enableWebTerminal', c.enableWebTerminal,
    'enableTokensConfig', c.enableTokensConfig,
    'maxTokenLifetimeDays', c.maxTokenLifetimeDays,
    'enableWorkspaceFilesystem', c.enableWorkspaceFilesystem,
    'enableExportNotebook', c.enableExportNotebook,
    'enableNotebookTableClipboard', c.enableNotebookTableClipboard,
    'enableResultsDownloading', c.enableResultsDownloading,
    'enableDcs', c.enableDcs,
    'enableGp3', c.enableGp3,
    'mlflowRunArtifactDownloadEnabled', c.mlflowRunArtifactDownloadEnabled,
    'enableUploadDataUis', c.enableUploadDataUis,
    'storeInteractiveNotebookResultsInCustomerAccount', c.storeInteractiveNotebookResultsInCustomerAccount,
    'enableDeprecatedGlobalInitScripts', c.enableDeprecatedGlobalInitScripts,
    'rStudioUserDefaultHomeBase', c.rStudioUserDefaultHomeBase,
    'enforceUserIsolation', c.enforceUserIsolation,
    'enableProjectsAllowList', c.enableProjectsAllowList,
    'projectsAllowListPermissions', c.projectsAllowListPermissions,
    'projectsAllowList', c.projectsAllowList,
    'reposIpynbResultsExportPermissions', c.reposIpynbResultsExportPermissions,
    'enableDbfsFileBrowser', c.enableDbfsFileBrowser,
    'enableDatabricksAutologgingAdminConf', c.enableDatabricksAutologgingAdminConf,
    'mlflowModelServingEndpointCreationEnabled', c.mlflowModelServingEndpointCreationEnabled,
    'enableVerboseAuditLogs', c.enableVerboseAuditLogs,
    'enableFileStoreEndpoint', c.enableFileStoreEndpoint,
    'loginLogo', c.loginLogo,
    'productName', c.productName,
    'homePageLogo', c.homePageLogo,
    'homePageLogoWidth', c.homePageLogoWidth,
    'homePageWelcomeMessage', c.homePageWelcomeMessage,
    'sidebarLogoText', c.sidebarLogoText,
    'sidebarLogoActive', c.sidebarLogoActive,
    'sidebarLogoInactive', c.sidebarLogoInactive,
    'customReferences', c.customReferences,
    'loginLogoWidth', c.loginLogoWidth,
    'enforceWorkspaceViewAcls', c.enforceWorkspaceViewAcls,
    'enforceClusterViewAcls', c.enforceClusterViewAcls,
    'enableJobViewAcls', c.enableJobViewAcls,
    'enableHlsRuntime', c.enableHlsRuntime,
    'enableEnforceImdsV2', c.enableEnforceImdsV2,
    'enableJobsEmailsV2', c.enableJobsEmailsV2,
    'enableProjectTypeInWorkspace', c.enableProjectTypeInWorkspace,
    'mlflowModelRegistryEmailNotificationsEnabled', c.mlflowModelRegistryEmailNotificationsEnabled,
    'heapAnalyticsAdminConsent', c.heapAnalyticsAdminConsent,
    'jobsListBackendPaginationEnabled', c.jobsListBackendPaginationEnabled,
    'jobsListBackendPaginationOptOut', c.jobsListBackendPaginationOptOut
  )) AS settings_object
FROM databricks_account.provisioning.workspaces w
LEFT JOIN databricks_workspace.settings.workspace_config c
  ON c.deployment_name = w.deployment_name
  AND c.keys = 'enableWebTerminal,enableTokensConfig,maxTokenLifetimeDays,enableWorkspaceFilesystem,enableExportNotebook,enableNotebookTableClipboard,enableResultsDownloading,enableDcs,enableGp3,mlflowRunArtifactDownloadEnabled,enableUploadDataUis,storeInteractiveNotebookResultsInCustomerAccount,enableDeprecatedGlobalInitScripts,rStudioUserDefaultHomeBase,enforceUserIsolation,enableProjectsAllowList,projectsAllowListPermissions,projectsAllowList,reposIpynbResultsExportPermissions,enableDbfsFileBrowser,enableDatabricksAutologgingAdminConf,mlflowModelServingEndpointCreationEnabled,enableVerboseAuditLogs,enableFileStoreEndpoint,loginLogo,productName,homePageLogo,homePageLogoWidth,homePageWelcomeMessage,sidebarLogoText,sidebarLogoActive,sidebarLogoInactive,customReferences,loginLogoWidth,enforceWorkspaceViewAcls,enforceClusterViewAcls,enableJobViewAcls,enableHlsRuntime,enableEnforceImdsV2,enableJobsEmailsV2,enableProjectTypeInWorkspace,mlflowModelRegistryEmailNotificationsEnabled,heapAnalyticsAdminConsent,jobsListBackendPaginationEnabled,jobsListBackendPaginationOptOut'
WHERE account_id = 'ebfcc5a9-9d49-4c93-b651-b3ee6cf1c9ce';
```

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_catalog_names
AS
SELECT
name,
metastore_id,
connection_name,
full_name,
provider_name,
share_name,
browse_only,
catalog_type,
comment,
created_at,
created_by,
effective_predictive_optimization_flag,
enable_predictive_optimization,
isolation_mode,
options,
owner,
properties,
provisioning_info,
securable_type,
storage_location,
storage_root,
updated_at,
updated_by
FROM databricks_workspace.catalog.catalogs
WHERE deployment_name IN ('dbc-74aa95f7-8c7e', 'dbc-4c2df2f4-018b');
```

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_s3_buckets
AS
SELECT
    json_extract_path_text(detail.Properties, 'AccelerateConfiguration') as accelerate_configuration,
    json_extract_path_text(detail.Properties, 'AccessControl') as access_control,
    json_extract_path_text(detail.Properties, 'AnalyticsConfigurations') as analytics_configurations,
    json_extract_path_text(detail.Properties, 'BucketEncryption') as bucket_encryption,
    json_extract_path_text(detail.Properties, 'BucketName') as bucket_name,
    json_extract_path_text(detail.Properties, 'CorsConfiguration') as cors_configuration,
    json_extract_path_text(detail.Properties, 'IntelligentTieringConfigurations') as intelligent_tiering_configurations,
    json_extract_path_text(detail.Properties, 'InventoryConfigurations') as inventory_configurations,
    json_extract_path_text(detail.Properties, 'LifecycleConfiguration') as lifecycle_configuration,
    json_extract_path_text(detail.Properties, 'LoggingConfiguration') as logging_configuration,
    json_extract_path_text(detail.Properties, 'MetricsConfigurations') as metrics_configurations,
    json_extract_path_text(detail.Properties, 'NotificationConfiguration') as notification_configuration,
    json_extract_path_text(detail.Properties, 'ObjectLockConfiguration') as object_lock_configuration,
    json_extract_path_text(detail.Properties, 'ObjectLockEnabled') as object_lock_enabled,
    json_extract_path_text(detail.Properties, 'OwnershipControls') as ownership_controls,
    json_extract_path_text(detail.Properties, 'PublicAccessBlockConfiguration') as public_access_block_configuration,
    json_extract_path_text(detail.Properties, 'ReplicationConfiguration') as replication_configuration,
    json_extract_path_text(detail.Properties, 'Tags') as tags,        
    json_extract_path_text(detail.Properties, 'VersioningConfiguration') as versioning_configuration,
    json_extract_path_text(detail.Properties, 'WebsiteConfiguration') as website_configuration,
    json_extract_path_text(detail.Properties, 'Arn') as arn,
    json_extract_path_text(detail.Properties, 'DomainName') as domain_name,
    json_extract_path_text(detail.Properties, 'DualStackDomainName') as dual_stack_domain_name,
    json_extract_path_text(detail.Properties, 'RegionalDomainName') as regional_domain_name,
    json_extract_path_text(detail.Properties, 'WebsiteURL') as website_url
FROM awscc.cloud_control.resources listing
LEFT JOIN awscc.cloud_control.resource detail
  ON detail.Identifier = listing.Identifier
  AND detail.region = listing.region
WHERE listing.TypeName = 'AWS::S3::Bucket'
  AND detail.TypeName = 'AWS::S3::Bucket'
  AND listing.region = 'ap-southeast-2';
```

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_iam_roles
AS
SELECT
json_extract_path_text(detail.Properties, 'Arn') as arn,
json_extract_path_text(detail.Properties, 'AssumeRolePolicyDocument') as assume_role_policy_document,
json_extract_path_text(detail.Properties, 'Description') as description,
json_extract_path_text(detail.Properties, 'ManagedPolicyArns') as managed_policy_arns,
json_extract_path_text(detail.Properties, 'MaxSessionDuration') as max_session_duration,
json_extract_path_text(detail.Properties, 'Path') as path,
json_extract_path_text(detail.Properties, 'PermissionsBoundary') as permissions_boundary,
json_extract_path_text(detail.Properties, 'Policies') as policies,
json_extract_path_text(detail.Properties, 'RoleId') as role_id,
json_extract_path_text(detail.Properties, 'RoleName') as role_name,
json_extract_path_text(detail.Properties, 'Tags') as tags
FROM awscc.cloud_control.resources listing
LEFT JOIN awscc.cloud_control.resource detail
ON detail.Identifier = listing.Identifier
AND detail.region = listing.region
WHERE listing.TypeName = 'AWS::IAM::Role'
AND detail.TypeName = 'AWS::IAM::Role'
AND listing.region = 'us-east-1';
```

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_google_projects
AS
SELECT
name,
displayName as display_name,
projectId as project_id,
state,
'organizations/141318256085' as parent_node,
'organization' as parent_type
FROM google.cloudresourcemanager.projects
WHERE parent = 'organizations/141318256085'
UNION ALL
SELECT
name,
displayName as display_name,
projectId as project_id,
state,
'organizations/141318256085' as parent_node,
'organization' as parent_type
FROM google.cloudresourcemanager.projects
WHERE parent IN ('folders/37437622524', 'folders/1067621535264', 'folders/542480258531');
```

```sql
CREATE OR REPLACE MATERIALIZED VIEW vw_google_buckets
AS
SELECT
id,
name,
acl,
autoclass,
billing,
cors,
customPlacementConfig,
defaultEventBasedHold,
defaultObjectAcl,
encryption,
etag,
generation,
hardDeleteTime,
hierarchicalNamespace,
iamConfiguration,
ipFilter,
kind,
labels,
lifecycle,
location,
locationType,
logging,
metageneration,
objectRetention,
owner,
projectNumber,
retentionPolicy,
rpo,
satisfiesPZI,
satisfiesPZS,
selfLink,
softDeletePolicy,
softDeleteTime,
storageClass,
timeCreated,
updated,
versioning,
website,
project
FROM google.storage.buckets
WHERE project IN ('stackql','gcp-dataflow-training','fullstackchronicles','stackql-demo','stackql-robot','stackql-terraform');
```