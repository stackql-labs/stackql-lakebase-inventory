/** CRUD /api/providers – Cloud provider credential mappings. */

import { Router } from 'express';
import * as db from '../services/db.js';
import { executeQuery } from '../services/stackql.js';

const router = Router();

router.get('/', async (_req, res, next) => {
  try {
    res.json(await db.getProviderConfigs());
  } catch (err) { next(err); }
});

router.post('/', async (req, res, next) => {
  try {
    const { provider, env_var_name, secret_scope, secret_key, created_by } = req.body;
    if (!provider || !env_var_name || !secret_scope || !secret_key) {
      res.status(400).json({ error: 'provider, env_var_name, secret_scope, and secret_key are required' });
      return;
    }
    const id = await db.saveProviderConfig({ provider, env_var_name, secret_scope, secret_key, created_by });
    res.status(201).json({ id });
  } catch (err) { next(err); }
});

router.delete('/:id', async (req, res, next) => {
  try {
    await db.deleteProviderConfig(parseInt(req.params.id, 10));
    res.status(204).end();
  } catch (err) { next(err); }
});

router.post('/:id/test', async (_req, res, next) => {
  try {
    const result = await executeQuery('SHOW PROVIDERS');
    res.json({ success: true, message: `StackQL returned ${result.rowCount} providers.` });
  } catch (err) {
    res.json({ success: false, message: (err as Error).message });
  }
});

export default router;
