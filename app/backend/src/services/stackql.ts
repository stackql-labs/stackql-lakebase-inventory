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

  // Wrap spawn in a promise so we can catch ENOENT (binary not found)
  await new Promise<void>((resolve, reject) => {
    const proc = spawn('stackql', ['srv', `--pgsrv.port=${STACKQL_PORT}`], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    // Handle spawn errors (e.g. binary not found)
    proc.on('error', (err: NodeJS.ErrnoException) => {
      serverProcess = null;
      if (err.code === 'ENOENT') {
        reject(new Error(
          'stackql binary not found in PATH. Install it or set STACKQL_PORT to point to an existing server.'
        ));
      } else {
        reject(err);
      }
    });

    proc.stdout?.on('data', (data: Buffer) => {
      console.log(`[stackql] ${data.toString().trim()}`);
    });

    proc.stderr?.on('data', (data: Buffer) => {
      console.error(`[stackql] ${data.toString().trim()}`);
    });

    proc.on('exit', (code) => {
      console.log(`StackQL server exited with code ${code}`);
      serverProcess = null;
      isReady = false;
    });

    serverProcess = proc;

    // Give the process a moment to fail or start, then resolve
    // so we can proceed to the readiness check loop
    setTimeout(resolve, 500);
  });

  // Wait for the server to be ready (retry connection)
  const maxRetries = 30;
  for (let i = 0; i < maxRetries; i++) {
    // If process died during startup, bail out
    if (!serverProcess) {
      throw new Error('StackQL server process exited during startup.');
    }
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
    throw new Error('StackQL server is not running. Install the stackql binary or start it manually.');
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
