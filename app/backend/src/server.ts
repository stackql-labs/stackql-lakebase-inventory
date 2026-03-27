/** StackQL Cloud Inventory – Express server entry point. */

import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { fileURLToPath } from 'url';
import path from 'path';

import { errorHandler } from './middleware/errors.js';
import { checkConnection } from './services/db.js';
import { startServer as startStackQL, stopServer as stopStackQL } from './services/stackql.js';
import queryRouter from './routes/query.js';
import queriesRouter from './routes/queries.js';
import schedulesRouter from './routes/schedules.js';
import inventoryRouter from './routes/inventory.js';
import chatRouter from './routes/chat.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STATIC_DIR = path.resolve(__dirname, '../static');
const PORT = parseInt(process.env.DATABRICKS_APP_PORT ?? process.env.PORT ?? '3001', 10);

const app = express();

// Middleware
app.use(cors());
app.use(express.json({ limit: '5mb' }));

// API routes
app.use('/api/query', queryRouter);
app.use('/api/queries', queriesRouter);
app.use('/api/schedules', schedulesRouter);
app.use('/api/inventory', inventoryRouter);
app.use('/api/chat', chatRouter);

// Health check
app.get('/api/health', async (_req, res) => {
  try {
    await checkConnection();
    res.json({ status: 'healthy', timestamp: new Date().toISOString() });
  } catch (err) {
    res.status(503).json({ status: 'unhealthy', error: (err as Error).message });
  }
});

// Serve React SPA (production)
app.use(express.static(STATIC_DIR));
app.get('*', (_req, res) => {
  const indexPath = path.join(STATIC_DIR, 'index.html');
  res.sendFile(indexPath, (err) => {
    if (err) {
      res.status(404).json({
        error: 'Frontend not built. Run "npm run build" first.',
      });
    }
  });
});

// Error handler (must be last)
app.use(errorHandler);

// Startup
async function start(): Promise<void> {
  console.log('Starting StackQL Cloud Inventory server...');

  // Start StackQL server in background (don't block if binary not found)
  try {
    await startStackQL();
  } catch (err) {
    console.warn(`StackQL server not started: ${(err as Error).message}`);
    console.warn('Query execution will fail until StackQL is available.');
  }

  // Verify Lakebase connectivity
  try {
    await checkConnection();
    console.log('Lakebase connection verified.');
  } catch (err) {
    console.warn(`Lakebase not available: ${(err as Error).message}`);
    console.warn('Database operations will fail until Lakebase is available.');
  }

  app.listen(PORT, () => {
    console.log(`Server listening on http://localhost:${PORT}`);
  });
}

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down...');
  stopStackQL();
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down...');
  stopStackQL();
  process.exit(0);
});

start().catch((err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
