import React, { useEffect, useState } from 'react';
import {
  Box, List, ListItemButton, ListItemText, IconButton, Typography,
  Tooltip, Divider,
} from '@mui/material';
import { Delete as DeleteIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import { getQueries, deleteQuery, type SavedQuery } from '../api/client';

interface QueryLibraryProps {
  onSelect: (query: SavedQuery) => void;
}

export default function QueryLibrary({ onSelect }: QueryLibraryProps) {
  const [queries, setQueries] = useState<SavedQuery[]>([]);

  const loadQueries = async () => {
    try {
      setQueries(await getQueries());
    } catch {
      // Silently handle – library is non-critical
    }
  };

  useEffect(() => { loadQueries(); }, []);

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this query?')) return;
    await deleteQuery(id);
    loadQueries();
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2" color="text.secondary">Saved Queries</Typography>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={loadQueries}><RefreshIcon fontSize="small" /></IconButton>
        </Tooltip>
      </Box>
      <Divider sx={{ mb: 1 }} />
      {queries.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ px: 1 }}>
          No saved queries yet.
        </Typography>
      )}
      <List dense disablePadding>
        {queries.map((q) => (
          <ListItemButton key={q.id} onClick={() => onSelect(q)} sx={{ borderRadius: 1, mb: 0.5 }}>
            <ListItemText
              primary={q.name}
              secondary={q.description}
              primaryTypographyProps={{ variant: 'body2', noWrap: true }}
              secondaryTypographyProps={{ variant: 'caption' }}
            />
            <IconButton size="small" onClick={(e) => handleDelete(q.id!, e)}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
}
