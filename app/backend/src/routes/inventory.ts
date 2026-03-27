/** /api/inventory – Inventory table browsing. */

import { Router } from 'express';
import * as db from '../services/db.js';

const router = Router();

router.get('/tables', async (_req, res, next) => {
  try {
    res.json(await db.getInventoryTables());
  } catch (err) { next(err); }
});

router.get('/tables/:name', async (req, res, next) => {
  try {
    const limit = parseInt(req.query.limit as string, 10) || 100;
    const offset = parseInt(req.query.offset as string, 10) || 0;
    const result = await db.getInventoryPreview(req.params.name, limit, offset);
    res.json(result);
  } catch (err) { next(err); }
});

router.post('/tables/:name/refresh', async (req, res, next) => {
  try {
    await db.refreshMaterialisedView(`${req.params.name}_mv`);
    res.status(204).end();
  } catch (err) { next(err); }
});

export default router;
