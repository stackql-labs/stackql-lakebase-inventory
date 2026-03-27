import React, { useState, useCallback, useRef } from 'react';
import {
  Box, Button,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Snackbar, Alert,
} from '@mui/material';
import {
  PlayArrow as RunIcon,
  Save as SaveIcon,
  Psychology as ExplainIcon,
  Analytics as InterpretIcon,
} from '@mui/icons-material';
import SqlEditor, { type SqlEditorHandle } from '../components/SqlEditor';
import ResultsGrid from '../components/ResultsGrid';
import ChatPanel from '../components/ChatPanel';
import QueryLibrary from '../components/QueryLibrary';
import ResourceBrowser from '../components/ResourceBrowser';
import { executeQuery, saveQuery, type QueryResult, type SavedQuery } from '../api/client';

export default function IdePage() {
  const editorRef = useRef<SqlEditorHandle>(null);
  const [sql, setSql] = useState('');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  // Save dialog state
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveDesc, setSaveDesc] = useState('');

  // Toast
  const [toast, setToast] = useState<{ message: string; severity: 'success' | 'error' } | null>(null);

  const handleExecute = useCallback(async () => {
    if (!sql.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await executeQuery(sql);
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [sql]);

  const handleSave = async () => {
    if (!saveName.trim() || !sql.trim()) return;
    try {
      await saveQuery({ name: saveName, description: saveDesc, query_text: sql });
      setSaveOpen(false);
      setSaveName('');
      setSaveDesc('');
      setToast({ message: 'Query saved!', severity: 'success' });
    } catch (err) {
      setToast({ message: (err as Error).message, severity: 'error' });
    }
  };

  const handleSelectQuery = (q: SavedQuery) => {
    setSql(q.query_text);
  };

  const handleExplain = () => {
    if (!sql.trim()) return;
    setPendingPrompt(`Explain this StackQL query:\n\n\`\`\`sql\n${sql}\n\`\`\``);
  };

  const handleInterpret = () => {
    if (!result || result.rowCount === 0) return;
    const preview = result.rows.slice(0, 20);
    const table = [
      `| ${result.columns.join(' | ')} |`,
      `| ${result.columns.map(() => '---').join(' | ')} |`,
      ...preview.map((row) => `| ${result.columns.map((c) => String(row[c] ?? '')).join(' | ')} |`),
    ].join('\n');
    setPendingPrompt(
      `Interpret these query results (${result.rowCount} total rows, showing first ${preview.length}):\n\n${table}`
    );
  };

  const handleInsertSql = (newSql: string) => {
    setSql(newSql);
  };

  const handleInsertResource = (fqn: string) => {
    editorRef.current?.insertAtCursor(fqn);
  };

  return (
    <Box sx={{ display: 'flex', gap: 2, height: 'calc(100vh - 100px)' }}>
      {/* Left: Resource Browser + Editor + Results */}
      <Box sx={{ flex: '1 1 65%', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top row: Query Library + Resource Browser side by side */}
        <Box sx={{ display: 'flex', gap: 1, mb: 1, minHeight: 0, maxHeight: '40%' }}>
          <Box sx={{ flex: '1 1 50%', overflow: 'auto' }}>
            <QueryLibrary onSelect={handleSelectQuery} />
          </Box>
          <Box sx={{ flex: '1 1 50%', overflow: 'auto' }}>
            <ResourceBrowser onInsertResource={handleInsertResource} />
          </Box>
        </Box>

        {/* Editor */}
        <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, overflow: 'hidden', mb: 1 }}>
          <SqlEditor ref={editorRef} value={sql} onChange={setSql} onExecute={handleExecute} />
        </Box>

        {/* Toolbar */}
        <Box sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <RunIcon />}
            onClick={handleExecute}
            disabled={loading || !sql.trim()}
          >
            Run
          </Button>
          <Button variant="outlined" startIcon={<SaveIcon />} onClick={() => setSaveOpen(true)} disabled={!sql.trim()}>
            Save
          </Button>
          <Button variant="outlined" startIcon={<ExplainIcon />} onClick={handleExplain} disabled={!sql.trim()}>
            Explain
          </Button>
          {result && result.rowCount > 0 && (
            <Button variant="outlined" startIcon={<InterpretIcon />} onClick={handleInterpret}>
              Interpret Results
            </Button>
          )}
        </Box>

        {/* Results */}
        <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'auto' }}>
          <ResultsGrid result={result} error={error} />
        </Box>
      </Box>

      {/* Right: Chat Panel */}
      <Box sx={{ flex: '1 1 35%', minWidth: 300, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <ChatPanel
          pendingPrompt={pendingPrompt}
          onPendingPromptConsumed={() => setPendingPrompt(null)}
          onInsertSql={handleInsertSql}
        />
      </Box>

      {/* Save Dialog */}
      <Dialog open={saveOpen} onClose={() => setSaveOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Save Query</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus fullWidth label="Name" value={saveName}
            onChange={(e) => setSaveName(e.target.value)} sx={{ mt: 1, mb: 2 }}
          />
          <TextField
            fullWidth label="Description" value={saveDesc}
            onChange={(e) => setSaveDesc(e.target.value)} multiline rows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={!saveName.trim()}>Save</Button>
        </DialogActions>
      </Dialog>

      {/* Toast */}
      <Snackbar open={!!toast} autoHideDuration={4000} onClose={() => setToast(null)}>
        {toast ? <Alert severity={toast.severity} onClose={() => setToast(null)}>{toast.message}</Alert> : undefined}
      </Snackbar>
    </Box>
  );
}
