import React, { useMemo } from 'react';
import { Box, Chip, Typography } from '@mui/material';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, type ColDef } from 'ag-grid-community';
import type { QueryResult } from '../api/client';

ModuleRegistry.registerModules([AllCommunityModule]);

interface ResultsGridProps {
  result: QueryResult | null;
  error?: string | null;
}

export default function ResultsGrid({ result, error }: ResultsGridProps) {
  const columnDefs = useMemo<ColDef[]>(() => {
    if (!result?.columns) return [];
    return result.columns.map((col) => ({
      field: col,
      headerName: col,
      sortable: true,
      filter: true,
      resizable: true,
    }));
  }, [result?.columns]);

  if (error) {
    return (
      <Box sx={{ p: 2, bgcolor: 'error.main', color: 'error.contrastText', borderRadius: 1 }}>
        <Typography variant="body2" sx={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
          {error}
        </Typography>
      </Box>
    );
  }

  if (!result) return null;

  if (result.rowCount === 0) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography color="text.secondary">Query returned no rows.</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 300 }}>
      <Box sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'center' }}>
        <Chip label={`${result.rowCount} rows`} size="small" variant="outlined" />
        <Chip label={`${result.executionTime}s`} size="small" variant="outlined" />
      </Box>
      <Box sx={{ flexGrow: 1 }}>
        <AgGridReact
          rowData={result.rows}
          columnDefs={columnDefs}
          pagination={true}
          paginationPageSize={50}
          paginationPageSizeSelector={[25, 50, 100]}
          domLayout="autoHeight"
          defaultColDef={{
            flex: 1,
            minWidth: 120,
          }}
        />
      </Box>
    </Box>
  );
}
