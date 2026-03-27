import React, { useEffect, useState } from 'react';
import {
  Box, Button, Chip, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Select, MenuItem, FormControl, InputLabel, IconButton, Tooltip,
  Typography, Snackbar, Alert,
} from '@mui/material';
import { Add as AddIcon, Pause as PauseIcon, PlayArrow as PlayIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, type ColDef, type ICellRendererParams } from 'ag-grid-community';
import {
  getSchedules, createSchedule, pauseSchedule, resumeSchedule, deleteSchedule,
  getQueries, type Schedule, type SavedQuery,
} from '../api/client';

ModuleRegistry.registerModules([AllCommunityModule]);

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [queries, setQueries] = useState<SavedQuery[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ query_id: 0, cron_expression: '', target_table: '' });
  const [toast, setToast] = useState<{ message: string; severity: 'success' | 'error' } | null>(null);

  const load = async () => {
    const [s, q] = await Promise.all([getSchedules(), getQueries()]);
    setSchedules(s);
    setQueries(q);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!form.query_id || !form.cron_expression || !form.target_table) return;
    try {
      await createSchedule(form);
      setDialogOpen(false);
      setForm({ query_id: 0, cron_expression: '', target_table: '' });
      setToast({ message: 'Schedule created!', severity: 'success' });
      load();
    } catch (err) {
      setToast({ message: (err as Error).message, severity: 'error' });
    }
  };

  const StatusRenderer = (params: ICellRendererParams) => {
    const status = params.value as string | null;
    if (!status) return <Chip label="No runs" size="small" variant="outlined" />;
    const color = status === 'SUCCESS' ? 'success' : status === 'FAILED' ? 'error' : 'default';
    return <Chip label={status} size="small" color={color} variant="outlined" />;
  };

  const ActiveRenderer = (params: ICellRendererParams) => {
    return params.value ? <Chip label="Active" size="small" color="success" /> : <Chip label="Paused" size="small" />;
  };

  const ActionsRenderer = (params: ICellRendererParams) => {
    const s = params.data as Schedule;
    return (
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <Tooltip title={s.is_active ? 'Pause' : 'Resume'}>
          <IconButton size="small" onClick={async () => {
            s.is_active ? await pauseSchedule(s.id!) : await resumeSchedule(s.id!);
            load();
          }}>
            {s.is_active ? <PauseIcon fontSize="small" /> : <PlayIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
        <Tooltip title="Delete">
          <IconButton size="small" onClick={async () => {
            if (!confirm('Delete this schedule?')) return;
            await deleteSchedule(s.id!);
            load();
          }}>
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    );
  };

  const columnDefs: ColDef[] = [
    { field: 'query_name', headerName: 'Query', flex: 2 },
    { field: 'cron_expression', headerName: 'Cron', flex: 1 },
    { field: 'target_table', headerName: 'Target Table', flex: 1.5 },
    { field: 'is_active', headerName: 'Status', flex: 1, cellRenderer: ActiveRenderer },
    { field: 'last_run_status', headerName: 'Last Run', flex: 1, cellRenderer: StatusRenderer },
    { headerName: 'Actions', flex: 1, cellRenderer: ActionsRenderer, sortable: false, filter: false },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Schedules</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
          New Schedule
        </Button>
      </Box>

      <Box sx={{ height: 500 }}>
        <AgGridReact rowData={schedules} columnDefs={columnDefs} domLayout="autoHeight" />
      </Box>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New Schedule</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 1, mb: 2 }}>
            <InputLabel>Query</InputLabel>
            <Select value={form.query_id} label="Query" onChange={(e) => setForm({ ...form, query_id: Number(e.target.value) })}>
              {queries.map((q) => <MenuItem key={q.id} value={q.id!}>{q.name}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField
            fullWidth label="Cron Expression" placeholder="0 */6 * * *"
            value={form.cron_expression} onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth label="Target Table"
            value={form.target_table} onChange={(e) => setForm({ ...form, target_table: e.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate}>Create</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={4000} onClose={() => setToast(null)}>
        {toast ? <Alert severity={toast.severity} onClose={() => setToast(null)}>{toast.message}</Alert> : undefined}
      </Snackbar>
    </Box>
  );
}
