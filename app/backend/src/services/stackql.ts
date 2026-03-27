/** StackQL service – manages server subprocess and query execution via pgwire-lite. */

import { spawn, execSync, type ChildProcess } from 'child_process';
import { existsSync, chmodSync, createWriteStream } from 'fs';
import { pipeline } from 'stream/promises';
import path from 'path';
import { runQuery } from '@stackql/pgwire-lite';
import type { QueryResult } from '../models/types.js';

let serverProcess: ChildProcess | null = null;
let isReady = false;

const STACKQL_PORT = parseInt(process.env.STACKQL_PORT ?? '5444', 10);
const STACKQL_BIN = path.resolve(process.cwd(), 'stackql');
const DOWNLOAD_URL = 'https://releases.stackql.io/stackql/latest/stackql_linux_amd64.zip';

const pgwireOptions = {
  user: 'stackql',
  database: 'stackql',
  host: 'localhost',
  port: STACKQL_PORT,
  useTLS: false,
};

/** Resolve the stackql binary path — download if not present. */
async function ensureBinary(): Promise<string> {
  // Check if already in PATH
  try {
    const pathBin = execSync('which stackql', { encoding: 'utf-8' }).trim();
    if (pathBin) {
      console.log(`Using stackql from PATH: ${pathBin}`);
      return pathBin;
    }
  } catch {
    // Not in PATH, continue to local check/download
  }

  // Check local binary next to .stackql/ dir
  if (existsSync(STACKQL_BIN)) {
    console.log(`Using local stackql binary: ${STACKQL_BIN}`);
    return STACKQL_BIN;
  }

  // Download to cwd (binary sits alongside .stackql/ provider cache dir)
  const cwd = process.cwd();
  console.log(`Downloading latest stackql binary from ${DOWNLOAD_URL}...`);

  const zipPath = path.join(cwd, 'stackql.zip');

  const res = await fetch(DOWNLOAD_URL);
  if (!res.ok || !res.body) {
    throw new Error(`Failed to download stackql: HTTP ${res.status}`);
  }

  const fileStream = createWriteStream(zipPath);
  await pipeline(res.body as unknown as NodeJS.ReadableStream, fileStream);

  // Unzip to cwd — produces ./stackql binary
  execSync(`unzip -o "${zipPath}" -d "${cwd}"`, { stdio: 'pipe' });
  chmodSync(STACKQL_BIN, 0o755);

  // Clean up zip
  try { execSync(`rm "${zipPath}"`, { stdio: 'pipe' }); } catch { /* ignore */ }

  console.log(`Downloaded stackql to ${STACKQL_BIN}`);
  return STACKQL_BIN;
}

/** Start the StackQL server as a child process. */
export async function startServer(): Promise<void> {
  if (serverProcess) return;

  const binaryPath = await ensureBinary();

  console.log(`Starting StackQL server on port ${STACKQL_PORT}...`);

  // Wrap spawn in a promise so we can catch ENOENT
  await new Promise<void>((resolve, reject) => {
    const proc = spawn(binaryPath, ['srv', `--pgsrv.port=${STACKQL_PORT}`], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    proc.on('error', (err: NodeJS.ErrnoException) => {
      serverProcess = null;
      reject(err);
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
    setTimeout(resolve, 500);
  });

  // Wait for the server to be ready (retry connection)
  const maxRetries = 30;
  for (let i = 0; i < maxRetries; i++) {
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
    throw new Error('StackQL server is not running.');
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
