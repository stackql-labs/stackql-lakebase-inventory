/** CRUD /api/queries – Saved StackQL queries. */

import { Router } from 'express';
import * as db from '../services/db.js';

const router = Router();

router.get('/', async (_req, res, next) => {
  try {
    const queries = await db.getQueries();
    res.json(queries);
  } catch (err) { next(err); }
});

router.get('/:id', async (req, res, next) => {
  try {
    const query = await db.getQuery(parseInt(req.params.id, 10));
    if (!query) { res.status(404).json({ error: 'Query not found' }); return; }
    res.json(query);
  } catch (err) { next(err); }
});

router.post('/', async (req, res, next) => {
  try {
    const { name, description, query_text, provider, created_by } = req.body;
    if (!name || !query_text || !provider) {
      res.status(400).json({ error: 'name, query_text, and provider are required' });
      return;
    }
    const id = await db.saveQuery({ name, description, query_text, provider, created_by });
    res.status(201).json({ id });
  } catch (err) { next(err); }
});

router.put('/:id', async (req, res, next) => {
  try {
    const { name, description, query_text, provider } = req.body;
    await db.updateQuery(parseInt(req.params.id, 10), { name, description, query_text, provider });
    res.status(204).end();
  } catch (err) { next(err); }
});

router.delete('/:id', async (req, res, next) => {
  try {
    await db.deleteQuery(parseInt(req.params.id, 10));
    res.status(204).end();
  } catch (err) { next(err); }
});

export default router;
