/** Database service – all Lakebase CRUD operations via node-postgres. */

import pg from 'pg';
import type { Query, Schedule, ProviderConfig, InventoryTable } from '../models/types.js';

const { Pool } = pg;

let pool: pg.Pool | null = null;

export function getPool(): pg.Pool {
  if (!pool) {
    pool = new Pool({
      host: process.env.LAKEBASE_HOST ?? 'localhost',
      port: parseInt(process.env.LAKEBASE_PORT ?? '5432', 10),
      database: process.env.LAKEBASE_DATABASE ?? 'postgres',
      user: process.env.LAKEBASE_USER ?? 'postgres',
      password: process.env.LAKEBASE_PASSWORD ?? 'postgres',
      max: 10,
      idleTimeoutMillis: 30000,
    });
  }
  return pool;
}

export async function checkConnection(): Promise<void> {
  const client = await getPool().connect();
  try {
    await client.query('SELECT 1');
  } finally {
    client.release();
  }
}

// ── Queries CRUD ─────────────────────────────────────────────────────

export async function getQueries(): Promise<Query[]> {
  const { rows } = await getPool().query(
    `SELECT id, name, description, query_text, provider, created_by, created_at, updated_at
     FROM stackql_app.queries ORDER BY updated_at DESC`
  );
  return rows;
}

export async function getQuery(id: number): Promise<Query | null> {
  const { rows } = await getPool().query(
    `SELECT id, name, description, query_text, provider, created_by, created_at, updated_at
     FROM stackql_app.queries WHERE id = $1`,
    [id]
  );
  return rows[0] ?? null;
}

export async function saveQuery(q: Omit<Query, 'id' | 'created_at' | 'updated_at'>): Promise<number> {
  const { rows } = await getPool().query(
    `INSERT INTO stackql_app.queries (name, description, query_text, provider, created_by)
     VALUES ($1, $2, $3, $4, $5) RETURNING id`,
    [q.name, q.description ?? null, q.query_text, q.provider, q.created_by ?? null]
  );
  return rows[0].id;
}

export async function updateQuery(id: number, q: Omit<Query, 'id' | 'created_at' | 'updated_at'>): Promise<void> {
  await getPool().query(
    `UPDATE stackql_app.queries
     SET name = $1, description = $2, query_text = $3, provider = $4, updated_at = NOW()
     WHERE id = $5`,
    [q.name, q.description ?? null, q.query_text, q.provider, id]
  );
}

export async function deleteQuery(id: number): Promise<void> {
  await getPool().query('DELETE FROM stackql_app.queries WHERE id = $1', [id]);
}

// ── Schedules CRUD ───────────────────────────────────────────────────

export async function getSchedules(): Promise<Schedule[]> {
  const { rows } = await getPool().query(
    `SELECT s.id, s.query_id, s.job_id, s.cron_expression, s.target_schema, s.target_table,
            s.is_active, s.last_run_at, s.last_run_status, s.created_at, s.updated_at,
            q.name AS query_name
     FROM stackql_app.schedules s
     LEFT JOIN stackql_app.queries q ON q.id = s.query_id
     ORDER BY s.created_at DESC`
  );
  return rows;
}

export async function saveSchedule(s: Omit<Schedule, 'id' | 'created_at' | 'updated_at' | 'query_name'>): Promise<number> {
  const { rows } = await getPool().query(
    `INSERT INTO stackql_app.schedules
     (query_id, job_id, cron_expression, target_schema, target_table, is_active)
     VALUES ($1, $2, $3, $4, $5, $6) RETURNING id`,
    [s.query_id, s.job_id ?? null, s.cron_expression, s.target_schema, s.target_table, s.is_active]
  );
  return rows[0].id;
}

export async function updateSchedule(
  id: number,
  s: Partial<Pick<Schedule, 'is_active' | 'job_id' | 'last_run_at' | 'last_run_status' | 'cron_expression' | 'target_table'>>
): Promise<void> {
  const sets: string[] = [];
  const vals: unknown[] = [];
  let i = 1;

  for (const [key, val] of Object.entries(s)) {
    sets.push(`${key} = $${i}`);
    vals.push(val);
    i++;
  }
  sets.push(`updated_at = NOW()`);
  vals.push(id);

  await getPool().query(
    `UPDATE stackql_app.schedules SET ${sets.join(', ')} WHERE id = $${i}`,
    vals
  );
}

export async function deleteSchedule(id: number): Promise<void> {
  await getPool().query('DELETE FROM stackql_app.schedules WHERE id = $1', [id]);
}

// ── Provider Config CRUD ─────────────────────────────────────────────

export async function getProviderConfigs(): Promise<ProviderConfig[]> {
  const { rows } = await getPool().query(
    `SELECT id, provider, env_var_name, secret_scope, secret_key, created_by, created_at
     FROM stackql_app.provider_config ORDER BY provider, env_var_name`
  );
  return rows;
}

export async function saveProviderConfig(c: Omit<ProviderConfig, 'id' | 'created_at'>): Promise<number> {
  const { rows } = await getPool().query(
    `INSERT INTO stackql_app.provider_config (provider, env_var_name, secret_scope, secret_key, created_by)
     VALUES ($1, $2, $3, $4, $5)
     ON CONFLICT (provider, env_var_name) DO UPDATE
       SET secret_scope = EXCLUDED.secret_scope, secret_key = EXCLUDED.secret_key
     RETURNING id`,
    [c.provider, c.env_var_name, c.secret_scope, c.secret_key, c.created_by ?? null]
  );
  return rows[0].id;
}

export async function deleteProviderConfig(id: number): Promise<void> {
  await getPool().query('DELETE FROM stackql_app.provider_config WHERE id = $1', [id]);
}

// ── Inventory Browsing ───────────────────────────────────────────────

export async function getInventoryTables(): Promise<InventoryTable[]> {
  const { rows: tableRows } = await getPool().query(
    `SELECT table_name FROM information_schema.tables
     WHERE table_schema = 'stackql_inventory' AND table_type = 'BASE TABLE'
     ORDER BY table_name`
  );

  const results: InventoryTable[] = [];
  for (const t of tableRows) {
    const { rows: countRows } = await getPool().query(
      `SELECT COUNT(*)::int AS cnt FROM stackql_inventory.${t.table_name}`
    );
    const { rows: mvRows } = await getPool().query(
      `SELECT COUNT(*)::int AS cnt FROM information_schema.tables
       WHERE table_schema = 'stackql_inventory' AND table_name = $1`,
      [`${t.table_name}_mv`]
    );
    results.push({
      table_name: t.table_name,
      row_count: countRows[0]?.cnt ?? 0,
      has_materialised_view: (mvRows[0]?.cnt ?? 0) > 0,
    });
  }
  return results;
}

export async function getInventoryPreview(
  tableName: string,
  limit = 100,
  offset = 0
): Promise<{ columns: string[]; rows: Record<string, unknown>[]; total: number }> {
  if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(tableName)) {
    throw new Error(`Invalid table name: ${tableName}`);
  }
  const { rows: countRows } = await getPool().query(
    `SELECT COUNT(*)::int AS cnt FROM stackql_inventory.${tableName}`
  );
  const { rows, fields } = await getPool().query(
    `SELECT * FROM stackql_inventory.${tableName} LIMIT $1 OFFSET $2`,
    [limit, offset]
  );
  return {
    columns: fields.map(f => f.name),
    rows,
    total: countRows[0]?.cnt ?? 0,
  };
}

export async function refreshMaterialisedView(viewName: string): Promise<void> {
  if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(viewName)) {
    throw new Error(`Invalid view name: ${viewName}`);
  }
  await getPool().query(`REFRESH MATERIALIZED VIEW stackql_inventory.${viewName}`);
}
