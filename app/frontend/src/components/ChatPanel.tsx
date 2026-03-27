import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box, TextField, IconButton, ToggleButton, ToggleButtonGroup,
  Typography, Paper, CircularProgress, Button, useTheme,
} from '@mui/material';
import { Send as SendIcon, ContentCopy as CopyIcon } from '@mui/icons-material';
import { streamChat, type ChatMessage } from '../api/client';

interface ChatPanelProps {
  /** When set, automatically sends this prompt as a user message. Cleared after use. */
  pendingPrompt?: string | null;
  onPendingPromptConsumed?: () => void;
  /** Callback to insert SQL into the editor. */
  onInsertSql?: (sql: string) => void;
}

export default function ChatPanel({ pendingPrompt, onPendingPromptConsumed, onInsertSql }: ChatPanelProps) {
  const theme = useTheme();
  const [mode, setMode] = useState<'query' | 'results'>('query');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || streaming) return;

    const userMsg: ChatMessage = { role: 'user', content };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setStreaming(true);

    let fullResponse = '';
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(newMessages, mode, (chunk) => {
        fullResponse += chunk;
        setMessages([...newMessages, { role: 'assistant', content: fullResponse }]);
      }, controller.signal);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        fullResponse += `\n\n**Error:** ${(err as Error).message}`;
        setMessages([...newMessages, { role: 'assistant', content: fullResponse }]);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [messages, mode, streaming]);

  // Handle pending prompt (from "Explain Query" or "Interpret Results" buttons)
  useEffect(() => {
    if (pendingPrompt) {
      sendMessage(pendingPrompt);
      onPendingPromptConsumed?.();
    }
  }, [pendingPrompt]);

  const extractSql = (text: string): string | null => {
    const match = text.match(/```sql\s*\n([\s\S]*?)```/);
    return match ? match[1].trim() : null;
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* Mode toggle */}
      <ToggleButtonGroup
        size="small"
        value={mode}
        exclusive
        onChange={(_, v) => v && setMode(v)}
        sx={{ mb: 1 }}
      >
        <ToggleButton value="query">Write Query</ToggleButton>
        <ToggleButton value="results">Interpret Results</ToggleButton>
      </ToggleButtonGroup>

      {/* Messages */}
      <Box sx={{ flexGrow: 1, overflow: 'auto', mb: 1, minHeight: 0 }}>
        {messages.map((msg, i) => (
          <Paper
            key={i}
            elevation={0}
            sx={{
              p: 1.5,
              mb: 1,
              bgcolor: msg.role === 'user' ? 'action.selected' : 'background.default',
              borderRadius: 2,
            }}
          >
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              {msg.role === 'user' ? 'You' : 'Assistant'}
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>
              {msg.content}
            </Typography>
            {msg.role === 'assistant' && extractSql(msg.content) && onInsertSql && (
              <Button
                size="small"
                startIcon={<CopyIcon />}
                onClick={() => onInsertSql(extractSql(msg.content)!)}
                sx={{ mt: 1 }}
              >
                Insert into Editor
              </Button>
            )}
          </Paper>
        ))}
        {streaming && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1 }}>
            <CircularProgress size={16} />
            <Typography variant="caption" color="text.secondary">Thinking...</Typography>
          </Box>
        )}
        <div ref={bottomRef} />
      </Box>

      {/* Input */}
      <Box sx={{ display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          size="small"
          multiline
          maxRows={3}
          placeholder={mode === 'query' ? 'Ask about StackQL queries...' : 'Ask about results...'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
        />
        <IconButton color="primary" onClick={() => sendMessage(input)} disabled={streaming || !input.trim()}>
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
