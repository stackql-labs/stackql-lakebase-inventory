import React, { useEffect, useState } from 'react';
import {
  Box, Button, Typography, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Select, MenuItem, FormControl, InputLabel, IconButton, Tooltip,
  Chip, Snackbar, Alert,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, CheckCircle as TestIcon } from '@mui/icons-material';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, type ColDef, type ICellRendererParams } from 'ag-grid-community';
import {
  getProviders, saveProvider, deleteProvider, testProvider, type ProviderConfig,
} from '../api/client';

ModuleRegistry.registerModules([AllCommunityModule]);

const KNOWN_PROVIDERS = ['aws', 'azure', 'google', 'databricks', 'github', 'cloudflare', 'okta'];

export default function ProvidersPage() {
  const [configs, setConfigs] = useState<ProviderConfig[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ provider: '', env_var_name: '', secret_scope: '', secret_key: '' });
  const [toast, setToast] = useState<{ message: string; severity: 'success' | 'error' } | null>(null);

  const load = async () => {
    try { setConfigs(await getProviders()); } catch { /* non-critical */ }
  };

  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    const { provider, env_var_name, secret_scope, secret_key } = form;
    if (!provider || !env_var_name || !secret_scope || !secret_key) return;
    try {
      await saveProvider(form);
      setDialogOpen(false);
      setForm({ provider: '', env_var_name: '', secret_scope: '', secret_key: '' });
      setToast({ message: 'Provider config saved!', severity: 'success' });
      load();
    } catch (err) {
      setToast({ message: (err as Error).message, severity: 'error' });
    }
  };

  const handleTest = async (id: number) => {
    try {
      const result = await testProvider(id);
      setToast({ message: result.message, severity: result.success ? 'success' : 'error' });
    } catch (err) {
      setToast({ message: (err as Error).message, severity: 'error' });
    }
  };

  const ActionsRenderer = (params: ICellRendererParams) => {
    const c = params.data as ProviderConfig;
    return (
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <Tooltip title="Test connection">
          <IconButton size="small" onClick={() => handleTest(c.id!)}>
            <TestIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Delete">
          <IconButton size="small" onClick={async () => {
            if (!confirm('Delete this provider config?')) return;
            await deleteProvider(c.id!);
            load();
          }}>
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    );
  };

  const columnDefs: ColDef[] = [
    { field: 'provider', headerName: 'Provider', flex: 1 },
    { field: 'env_var_name', headerName: 'Env Var', flex: 1.5 },
    { field: 'secret_scope', headerName: 'Secret Scope', flex: 1.5 },
    {
      field: 'secret_key', headerName: 'Secret Key', flex: 1.5,
      cellRenderer: () => <Chip label="***" size="small" variant="outlined" />,
    },
    { headerName: 'Actions', flex: 1, cellRenderer: ActionsRenderer, sortable: false, filter: false },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Provider Configuration</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
          Add Mapping
        </Button>
      </Box>

      <AgGridReact rowData={configs} columnDefs={columnDefs} domLayout="autoHeight" />

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Provider Mapping</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 1, mb: 2 }}>
            <InputLabel>Provider</InputLabel>
            <Select value={form.provider} label="Provider" onChange={(e) => setForm({ ...form, provider: e.target.value })}>
              {KNOWN_PROVIDERS.map((p) => <MenuItem key={p} value={p}>{p}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField
            fullWidth label="Environment Variable Name" placeholder="AWS_ACCESS_KEY_ID"
            value={form.env_var_name} onChange={(e) => setForm({ ...form, env_var_name: e.target.value })}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth label="Secret Scope"
            value={form.secret_scope} onChange={(e) => setForm({ ...form, secret_scope: e.target.value })}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth label="Secret Key"
            value={form.secret_key} onChange={(e) => setForm({ ...form, secret_key: e.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave}>Save</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={4000} onClose={() => setToast(null)}>
        {toast ? <Alert severity={toast.severity} onClose={() => setToast(null)}>{toast.message}</Alert> : undefined}
      </Snackbar>
    </Box>
  );
}
