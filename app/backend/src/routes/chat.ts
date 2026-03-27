/** POST /api/chat – AI chat with Server-Sent Events streaming. */

import { Router } from 'express';
import { streamChat } from '../services/ai.js';
import type { ChatMessage } from '../models/types.js';

const router = Router();

router.post('/', async (req, res, next) => {
  try {
    const { messages, mode } = req.body as { messages?: ChatMessage[]; mode?: string };
    if (!messages || !mode) {
      res.status(400).json({ error: 'messages and mode are required' });
      return;
    }
    if (mode !== 'query' && mode !== 'results') {
      res.status(400).json({ error: 'mode must be "query" or "results"' });
      return;
    }

    // Set up SSE headers
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.flushHeaders();

    for await (const chunk of streamChat(messages, mode)) {
      res.write(`data: ${JSON.stringify({ text: chunk })}\n\n`);
    }

    res.write('data: [DONE]\n\n');
    res.end();
  } catch (err) {
    // If headers already sent, write error as SSE event
    if (res.headersSent) {
      res.write(`data: ${JSON.stringify({ error: (err as Error).message })}\n\n`);
      res.end();
    } else {
      next(err);
    }
  }
});

export default router;
