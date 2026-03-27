import React, { useState, useMemo } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { lightTheme, darkTheme } from './theme';
import Layout from './components/Layout';
import IdePage from './pages/IdePage';
import SchedulesPage from './pages/SchedulesPage';
import InventoryPage from './pages/InventoryPage';
import ProvidersPage from './pages/ProvidersPage';

export default function App() {
  const [mode, setMode] = useState<'light' | 'dark'>('dark');
  const theme = useMemo(() => (mode === 'dark' ? darkTheme : lightTheme), [mode]);

  const toggleTheme = () => setMode((m) => (m === 'dark' ? 'light' : 'dark'));

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route element={<Layout onToggleTheme={toggleTheme} />}>
            <Route path="/" element={<IdePage />} />
            <Route path="/schedules" element={<SchedulesPage />} />
            <Route path="/inventory" element={<InventoryPage />} />
            <Route path="/providers" element={<ProvidersPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
