// frontend/src/main.jsx
// Punto de entrada. Monta el ThemeProvider una sola vez para toda la app.

import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

import theme from './theme/theme.js';
import App from './App.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      {/* CssBaseline aplica background.default (hueso) al body */}
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
