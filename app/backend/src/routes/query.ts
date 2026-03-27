/** POST /api/query – Execute a StackQL query via pgwire-lite. */

import { Router } from 'express';
import { executeQuery } from '../services/stackql.js';

const router = Router();

router.post('/', async (req, res, next) => {
  try {
    const { sql } = req.body as { sql?: string };
    if (!sql?.trim()) {
      res.status(400).json({ error: 'Missing "sql" in request body' });
      return;
    }
    const result = await executeQuery(sql);
    res.json(result);
  } catch (err) {
    next(err);
  }
});

export default router;
