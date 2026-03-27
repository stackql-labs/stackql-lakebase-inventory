/** Typed fetch wrappers for the backend API. */

export interface QueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
  executionTime: number;
}

export interface SavedQuery {
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

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error ?? `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Query Execution ──────────────────────────────────────────────────

export async function executeQuery(sql: string): Promise<QueryResult> {
  return jsonFetch<QueryResult>('/api/query', {
    method: 'POST',
    body: JSON.stringify({ sql }),
  });
}

// ── Saved Queries CRUD ───────────────────────────────────────────────

export async function getQueries(): Promise<SavedQuery[]> {
  return jsonFetch('/api/queries');
}

export async function getQuery(id: number): Promise<SavedQuery> {
  return jsonFetch(`/api/queries/${id}`);
}

export async function saveQuery(q: Omit<SavedQuery, 'id' | 'created_at' | 'updated_at'>): Promise<{ id: number }> {
  return jsonFetch('/api/queries', { method: 'POST', body: JSON.stringify(q) });
}

export async function updateQuery(id: number, q: Partial<SavedQuery>): Promise<void> {
  return jsonFetch(`/api/queries/${id}`, { method: 'PUT', body: JSON.stringify(q) });
}

export async function deleteQuery(id: number): Promise<void> {
  return jsonFetch(`/api/queries/${id}`, { method: 'DELETE' });
}

// ── Schedules CRUD ───────────────────────────────────────────────────

export async function getSchedules(): Promise<Schedule[]> {
  return jsonFetch('/api/schedules');
}

export async function createSchedule(s: {
  query_id: number;
  cron_expression: string;
  target_table: string;
  target_schema?: string;
}): Promise<{ id: number }> {
  return jsonFetch('/api/schedules', { method: 'POST', body: JSON.stringify(s) });
}

export async function pauseSchedule(id: number): Promise<void> {
  return jsonFetch(`/api/schedules/${id}/pause`, { method: 'PATCH' });
}

export async function resumeSchedule(id: number): Promise<void> {
  return jsonFetch(`/api/schedules/${id}/resume`, { method: 'PATCH' });
}

export async function deleteSchedule(id: number): Promise<void> {
  return jsonFetch(`/api/schedules/${id}`, { method: 'DELETE' });
}

// ── Provider Config CRUD ─────────────────────────────────────────────

export async function getProviders(): Promise<ProviderConfig[]> {
  return jsonFetch('/api/providers');
}

export async function saveProvider(c: Omit<ProviderConfig, 'id' | 'created_at'>): Promise<{ id: number }> {
  return jsonFetch('/api/providers', { method: 'POST', body: JSON.stringify(c) });
}

export async function deleteProvider(id: number): Promise<void> {
  return jsonFetch(`/api/providers/${id}`, { method: 'DELETE' });
}

export async function testProvider(id: number): Promise<{ success: boolean; message: string }> {
  return jsonFetch(`/api/providers/${id}/test`, { method: 'POST' });
}

// ── Inventory ────────────────────────────────────────────────────────

export async function getInventoryTables(): Promise<InventoryTable[]> {
  return jsonFetch('/api/inventory/tables');
}

export async function getInventoryPreview(
  tableName: string,
  limit = 100,
  offset = 0
): Promise<{ columns: string[]; rows: Record<string, unknown>[]; total: number }> {
  return jsonFetch(`/api/inventory/tables/${tableName}?limit=${limit}&offset=${offset}`);
}

export async function refreshInventoryTable(tableName: string): Promise<void> {
  return jsonFetch(`/api/inventory/tables/${tableName}/refresh`, { method: 'POST' });
}

// ── AI Chat (SSE) ────────────────────────────────────────────────────

export async function streamChat(
  messages: ChatMessage[],
  mode: 'query' | 'results',
  onChunk: (text: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, mode }),
    signal,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error ?? `HTTP ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const payload = line.slice(6);
        if (payload === '[DONE]') return;
        try {
          const parsed = JSON.parse(payload) as { text?: string; error?: string };
          if (parsed.error) throw new Error(parsed.error);
          if (parsed.text) onChunk(parsed.text);
        } catch {
          // Skip malformed SSE lines
        }
      }
    }
  }
}
