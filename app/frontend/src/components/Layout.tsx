import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar, Box, Drawer, IconButton, List, ListItemButton, ListItemIcon,
  ListItemText, Toolbar, Typography, useTheme,
} from '@mui/material';
import {
  Code as CodeIcon,
  Schedule as ScheduleIcon,
  Inventory2 as InventoryIcon,
  DarkMode as DarkModeIcon,
  LightMode as LightModeIcon,
  Menu as MenuIcon,
} from '@mui/icons-material';
import logo from '../assets/logo.png';
import logoWhite from '../assets/logo-white.png';

const DRAWER_WIDTH = 220;

const NAV_ITEMS = [
  { label: 'Query Editor', path: '/', icon: <CodeIcon /> },
  { label: 'Schedules', path: '/schedules', icon: <ScheduleIcon /> },
  { label: 'Inventory', path: '/inventory', icon: <InventoryIcon /> },
];

interface LayoutProps {
  onToggleTheme: () => void;
}

export default function Layout({ onToggleTheme }: LayoutProps) {
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const isDark = theme.palette.mode === 'dark';
  const [mobileOpen, setMobileOpen] = useState(false);

  const drawer = (
    <Box sx={{ mt: 1 }}>
      <List>
        {NAV_ITEMS.map((item) => (
          <ListItemButton
            key={item.path}
            selected={location.pathname === item.path}
            onClick={() => { navigate(item.path); setMobileOpen(false); }}
            sx={{ borderRadius: 1, mx: 1, mb: 0.5 }}
          >
            <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* App bar */}
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          zIndex: theme.zIndex.drawer + 1,
          borderBottom: `1px solid ${theme.palette.divider}`,
          bgcolor: 'background.paper',
          color: 'text.primary',
        }}
      >
        <Toolbar variant="dense" sx={{ gap: 1.5 }}>
          <IconButton
            edge="start"
            onClick={() => setMobileOpen(!mobileOpen)}
            sx={{ display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <img src={isDark ? logoWhite : logo} alt="StackQL" style={{ height: 26 }} />
          <Typography variant="h6" sx={{ fontSize: '1.05rem', flexGrow: 1 }}>
            Cloud Inventory
          </Typography>
          <IconButton size="small" onClick={onToggleTheme}>
            {isDark ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />}
          </IconButton>
        </Toolbar>
      </AppBar>

      {/* Sidebar – permanent on desktop, temporary on mobile */}
      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          sx={{ display: { xs: 'block', md: 'none' }, '& .MuiDrawer-paper': { width: DRAWER_WIDTH } }}
        >
          <Toolbar variant="dense" />
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
          }}
          open
        >
          <Toolbar variant="dense" />
          {drawer}
        </Drawer>
      </Box>

      {/* Main content */}
      <Box
        component="main"
        sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
      >
        <Toolbar variant="dense" />
        <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
