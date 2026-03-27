/** CRUD /api/schedules – Scheduled inventory jobs. */

import { Router } from 'express';
import * as db from '../services/db.js';

const router = Router();

router.get('/', async (_req, res, next) => {
  try {
    res.json(await db.getSchedules());
  } catch (err) { next(err); }
});

router.post('/', async (req, res, next) => {
  try {
    const { query_id, cron_expression, target_schema, target_table } = req.body;
    if (!query_id || !cron_expression || !target_table) {
      res.status(400).json({ error: 'query_id, cron_expression, and target_table are required' });
      return;
    }
    const id = await db.saveSchedule({
      query_id,
      cron_expression,
      target_schema: target_schema ?? 'stackql_inventory',
      target_table,
      is_active: true,
    });
    res.status(201).json({ id });
  } catch (err) { next(err); }
});

router.patch('/:id/pause', async (req, res, next) => {
  try {
    await db.updateSchedule(parseInt(req.params.id, 10), { is_active: false });
    res.status(204).end();
  } catch (err) { next(err); }
});

router.patch('/:id/resume', async (req, res, next) => {
  try {
    await db.updateSchedule(parseInt(req.params.id, 10), { is_active: true });
    res.status(204).end();
  } catch (err) { next(err); }
});

router.delete('/:id', async (req, res, next) => {
  try {
    await db.deleteSchedule(parseInt(req.params.id, 10));
    res.status(204).end();
  } catch (err) { next(err); }
});

export default router;
