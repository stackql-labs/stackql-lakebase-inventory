/** Resource Browser – tree view of providers → services → resources → fields.
 *  Right-click on a resource to copy its fully qualified name to the query editor.
 */

import React, { useState, useCallback } from 'react';
import {
  Box, Typography, CircularProgress, Menu, MenuItem, Collapse, IconButton,
} from '@mui/material';
import {
  ExpandMore, ChevronRight, AccountTree as BrowseIcon,
  Cloud, Storage, ViewModule, TextFields,
} from '@mui/icons-material';
import { executeQuery } from '../api/client';

// Node types in the hierarchy
type NodeType = 'provider' | 'service' | 'resource' | 'field';

interface TreeNode {
  id: string;
  label: string;
  type: NodeType;
  fqn: string; // fully qualified name (provider.service.resource)
  children?: TreeNode[];
  loaded: boolean;
}

interface ResourceBrowserProps {
  onInsertResource: (fqn: string) => void;
}

const NODE_ICONS: Record<NodeType, React.ReactNode> = {
  provider: <Cloud sx={{ fontSize: 16, mr: 0.5 }} />,
  service: <Storage sx={{ fontSize: 16, mr: 0.5 }} />,
  resource: <ViewModule sx={{ fontSize: 16, mr: 0.5 }} />,
  field: <TextFields sx={{ fontSize: 16, mr: 0.5 }} />,
};

export default function ResourceBrowser({ onInsertResource }: ResourceBrowserProps) {
  const [expanded, setExpanded] = useState(false);
  const [nodes, setNodes] = useState<TreeNode[]>([]);
  const [openNodes, setOpenNodes] = useState<Set<string>>(new Set());
  const [loadingNodes, setLoadingNodes] = useState<Set<string>>(new Set());

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{ mouseX: number; mouseY: number; node: TreeNode } | null>(null);

  const loadProviders = useCallback(async () => {
    if (nodes.length > 0) return;
    setLoadingNodes(new Set(['root']));
    try {
      const result = await executeQuery('SHOW PROVIDERS');
      const providerNodes: TreeNode[] = result.rows.map((row) => ({
        id: String(row.name ?? row.provider),
        label: String(row.name ?? row.provider),
        type: 'provider' as const,
        fqn: String(row.name ?? row.provider),
        loaded: false,
      }));
      setNodes(providerNodes);
    } catch {
      // silently fail — user may not have providers pulled yet
    }
    setLoadingNodes(new Set());
  }, [nodes.length]);

  const loadChildren = useCallback(async (node: TreeNode) => {
    if (node.loaded) return;

    setLoadingNodes((prev) => new Set(prev).add(node.id));

    try {
      let query = '';
      let childType: NodeType = 'service';

      if (node.type === 'provider') {
        query = `SHOW SERVICES IN ${node.fqn}`;
        childType = 'service';
      } else if (node.type === 'service') {
        query = `SHOW RESOURCES IN ${node.fqn}`;
        childType = 'resource';
      } else if (node.type === 'resource') {
        query = `DESCRIBE ${node.fqn}`;
        childType = 'field';
      }

      if (!query) return;

      const result = await executeQuery(query);
      const children: TreeNode[] = result.rows.map((row) => {
        const name = String(row.name ?? row.resource ?? row.service ?? row.field ?? '');
        const fqn = childType === 'field' ? name : `${node.fqn}.${name}`;
        return {
          id: `${node.id}.${name}`,
          label: name,
          type: childType,
          fqn,
          loaded: false,
        };
      });

      // Update tree immutably
      const updateNode = (treeNodes: TreeNode[]): TreeNode[] =>
        treeNodes.map((n) => {
          if (n.id === node.id) return { ...n, children, loaded: true };
          if (n.children) return { ...n, children: updateNode(n.children) };
          return n;
        });

      setNodes((prev) => updateNode(prev));
    } catch {
      // Mark as loaded even on error to prevent retry loops
      const markLoaded = (treeNodes: TreeNode[]): TreeNode[] =>
        treeNodes.map((n) => {
          if (n.id === node.id) return { ...n, loaded: true, children: [] };
          if (n.children) return { ...n, children: markLoaded(n.children) };
          return n;
        });
      setNodes((prev) => markLoaded(prev));
    }

    setLoadingNodes((prev) => {
      const next = new Set(prev);
      next.delete(node.id);
      return next;
    });
  }, []);

  const handleToggle = async (node: TreeNode) => {
    const isOpen = openNodes.has(node.id);
    if (isOpen) {
      setOpenNodes((prev) => { const n = new Set(prev); n.delete(node.id); return n; });
    } else {
      setOpenNodes((prev) => new Set(prev).add(node.id));
      if (!node.loaded && node.type !== 'field') {
        await loadChildren(node);
      }
    }
  };

  const handleContextMenu = (e: React.MouseEvent, node: TreeNode) => {
    if (node.type !== 'resource') return;
    e.preventDefault();
    setContextMenu({ mouseX: e.clientX, mouseY: e.clientY, node });
  };

  const handleInsert = () => {
    if (contextMenu) {
      onInsertResource(contextMenu.node.fqn);
      setContextMenu(null);
    }
  };

  const handleExpand = () => {
    setExpanded(!expanded);
    if (!expanded) loadProviders();
  };

  const renderNode = (node: TreeNode, depth = 0) => {
    const isOpen = openNodes.has(node.id);
    const isLoading = loadingNodes.has(node.id);
    const hasChildren = node.type !== 'field';

    return (
      <Box key={node.id}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            pl: depth * 2,
            py: 0.25,
            cursor: hasChildren ? 'pointer' : 'default',
            '&:hover': { bgcolor: 'action.hover' },
            borderRadius: 0.5,
            userSelect: 'none',
          }}
          onClick={() => hasChildren && handleToggle(node)}
          onContextMenu={(e) => handleContextMenu(e, node)}
        >
          {hasChildren ? (
            isLoading ? (
              <CircularProgress size={14} sx={{ mr: 0.5 }} />
            ) : isOpen ? (
              <ExpandMore sx={{ fontSize: 16, mr: 0.5 }} />
            ) : (
              <ChevronRight sx={{ fontSize: 16, mr: 0.5 }} />
            )
          ) : (
            <Box sx={{ width: 20 }} />
          )}
          {NODE_ICONS[node.type]}
          <Typography
            variant="body2"
            sx={{
              fontSize: '0.8rem',
              fontFamily: node.type === 'field' ? 'monospace' : 'inherit',
            }}
            noWrap
          >
            {node.label}
          </Typography>
        </Box>
        {hasChildren && isOpen && node.children && (
          <Collapse in={isOpen}>
            {node.children.map((child) => renderNode(child, depth + 1))}
          </Collapse>
        )}
      </Box>
    );
  };

  return (
    <Box>
      <Box
        sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer', mb: 0.5 }}
        onClick={handleExpand}
      >
        <IconButton size="small">
          {expanded ? <ExpandMore fontSize="small" /> : <ChevronRight fontSize="small" />}
        </IconButton>
        <BrowseIcon sx={{ fontSize: 18 }} />
        <Typography variant="subtitle2">Resource Browser</Typography>
        {loadingNodes.has('root') && <CircularProgress size={14} sx={{ ml: 1 }} />}
      </Box>
      {expanded && (
        <Box sx={{ maxHeight: 300, overflow: 'auto', pl: 1 }}>
          {nodes.length === 0 && !loadingNodes.has('root') && (
            <Typography variant="caption" color="text.secondary" sx={{ pl: 2 }}>
              No providers found. Pull providers first with REGISTRY PULL.
            </Typography>
          )}
          {nodes.map((node) => renderNode(node))}
        </Box>
      )}

      {/* Right-click context menu for resources */}
      <Menu
        open={contextMenu !== null}
        onClose={() => setContextMenu(null)}
        anchorReference="anchorPosition"
        anchorPosition={contextMenu ? { top: contextMenu.mouseY, left: contextMenu.mouseX } : undefined}
      >
        <MenuItem onClick={handleInsert}>
          Copy to Query Editor
        </MenuItem>
      </Menu>
    </Box>
  );
}
