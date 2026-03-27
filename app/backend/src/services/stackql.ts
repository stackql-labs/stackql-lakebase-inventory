/** StackQL service – manages server subprocess and query execution via pgwire-lite. */

import { spawn, type ChildProcess } from 'child_process';
import { runQuery } from '@stackql/pgwire-lite';
import type { QueryResult } from '../models/types.js';

let serverProcess: ChildProcess | null = null;
let isReady = false;

const STACKQL_PORT = parseInt(process.env.STACKQL_PORT ?? '5444', 10);

const pgwireOptions = {
  user: 'stackql',
  database: 'stackql',
  host: 'localhost',
  port: STACKQL_PORT,
  useTLS: false,
};

/** Start the StackQL server as a child process. */
export async function startServer(): Promise<void> {
  if (serverProcess) return;

  console.log(`Starting StackQL server on port ${STACKQL_PORT}...`);

  serverProcess = spawn('stackql', ['srv', `--pgsrv.port=${STACKQL_PORT}`], {
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  serverProcess.stdout?.on('data', (data: Buffer) => {
    console.log(`[stackql] ${data.toString().trim()}`);
  });

  serverProcess.stderr?.on('data', (data: Buffer) => {
    console.error(`[stackql] ${data.toString().trim()}`);
  });

  serverProcess.on('exit', (code) => {
    console.log(`StackQL server exited with code ${code}`);
    serverProcess = null;
    isReady = false;
  });

  // Wait for the server to be ready (retry connection)
  const maxRetries = 30;
  for (let i = 0; i < maxRetries; i++) {
    try {
      await runQuery(pgwireOptions, 'SELECT 1');
      isReady = true;
      console.log('StackQL server is ready.');
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
  throw new Error('StackQL server failed to start within 30 seconds');
}

/** Stop the StackQL server. */
export function stopServer(): void {
  if (serverProcess) {
    serverProcess.kill('SIGTERM');
    serverProcess = null;
    isReady = false;
  }
}

/** Execute a StackQL query and return structured results. */
export async function executeQuery(sql: string): Promise<QueryResult> {
  if (!isReady) {
    throw new Error('StackQL server is not running. Call startServer() first.');
  }

  const start = performance.now();
  const result = await runQuery(pgwireOptions, sql);
  const executionTime = (performance.now() - start) / 1000;

  const data = result.data ?? [];
  const columns = data.length > 0 ? Object.keys(data[0] as Record<string, unknown>) : [];

  return {
    columns,
    rows: data as Record<string, unknown>[],
    rowCount: data.length,
    executionTime: Math.round(executionTime * 1000) / 1000,
  };
}
