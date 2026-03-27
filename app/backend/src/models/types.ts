/** Shared TypeScript interfaces for the StackQL Cloud Inventory app. */

export interface Query {
  id?: number;
  name: string;
  description?: string | null;
  query_text: string;
  provider: string;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface Schedule {
  id?: number;
  query_id: number;
  job_id?: string | null;
  cron_expression: string;
  target_schema: string;
  target_table: string;
  is_active: boolean;
  last_run_at?: string | null;
  last_run_status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  /** Joined from queries table for display */
  query_name?: string;
}

export interface ProviderConfig {
  id?: number;
  provider: string;
  env_var_name: string;
  secret_scope: string;
  secret_key: string;
  created_by?: string | null;
  created_at?: string | null;
}

export interface InventoryTable {
  table_name: string;
  row_count: number;
  has_materialised_view: boolean;
}

export interface QueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
  executionTime: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
