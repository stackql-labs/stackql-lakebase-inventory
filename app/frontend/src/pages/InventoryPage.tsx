import React, { useEffect, useState } from 'react';
import { Box, Typography, Chip, Button, CircularProgress, Tooltip, IconButton } from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, type ColDef, type ICellRendererParams, type RowClickedEvent } from 'ag-grid-community';
import {
  getInventoryTables, getInventoryPreview, refreshInventoryTable,
  type InventoryTable,
} from '../api/client';

ModuleRegistry.registerModules([AllCommunityModule]);

export default function InventoryPage() {
  const [tables, setTables] = useState<InventoryTable[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ columns: string[]; rows: Record<string, unknown>[] } | null>(null);
  const [loading, setLoading] = useState(false);

  const loadTables = async () => {
    try {
      setTables(await getInventoryTables());
    } catch { /* non-critical */ }
  };

  useEffect(() => { loadTables(); }, []);

  const handleRowClick = async (event: RowClickedEvent) => {
    const name = (event.data as InventoryTable).table_name;
    setSelectedTable(name);
    setLoading(true);
    try {
      const result = await getInventoryPreview(name);
      setPreview(result);
    } catch { setPreview(null); }
    finally { setLoading(false); }
  };

  const handleRefresh = async (tableName: string) => {
    try {
      await refreshInventoryTable(tableName);
      loadTables();
    } catch { /* non-critical */ }
  };

  const totalRows = tables.reduce((sum, t) => sum + t.row_count, 0);

  const tableColumnDefs: ColDef[] = [
    { field: 'table_name', headerName: 'Table', flex: 2 },
    { field: 'row_count', headerName: 'Rows', flex: 1 },
    {
      field: 'has_materialised_view', headerName: 'MV', flex: 1,
      cellRenderer: (params: ICellRendererParams) =>
        params.value ? <Chip label="Yes" size="small" color="success" variant="outlined" />
                     : <Chip label="No" size="small" variant="outlined" />,
    },
    {
      headerName: '', flex: 0.5, sortable: false, filter: false,
      cellRenderer: (params: ICellRendererParams) => (
        <Tooltip title="Refresh MV">
          <IconButton size="small" onClick={(e) => {
            e.stopPropagation();
            handleRefresh((params.data as InventoryTable).table_name);
          }}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ];

  const previewColumnDefs: ColDef[] = preview?.columns.map((col) => ({
    field: col, headerName: col, sortable: true, filter: true, resizable: true,
  })) ?? [];

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>Inventory Browser</Typography>

      {/* Metrics */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <Chip label={`${tables.length} tables`} variant="outlined" />
        <Chip label={`${totalRows.toLocaleString()} total rows`} variant="outlined" />
      </Box>

      {/* Table list */}
      <Box sx={{ mb: 3 }}>
        <AgGridReact
          rowData={tables}
          columnDefs={tableColumnDefs}
          domLayout="autoHeight"
          onRowClicked={handleRowClick}
          rowSelection="single"
        />
      </Box>

      {/* Preview */}
      {selectedTable && (
        <Box>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            Preview: {selectedTable}
            {loading && <CircularProgress size={16} sx={{ ml: 1 }} />}
          </Typography>
          {preview && (
            <AgGridReact
              rowData={preview.rows}
              columnDefs={previewColumnDefs}
              domLayout="autoHeight"
              pagination
              paginationPageSize={50}
              defaultColDef={{ flex: 1, minWidth: 120 }}
            />
          )}
        </Box>
      )}
    </Box>
  );
}
