// frontend/src/main.jsx
// Punto de entrada. Monta el ThemeProvider una sola vez para toda la app.

import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { BrowserRouter } from 'react-router-dom';

import theme from './theme/theme.js';
import { AuthProvider } from './context/AuthContext.jsx';
import App from './App.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      {/* CssBaseline aplica background.default (hueso) al body */}
      <CssBaseline />
      <BrowserRouter>
        {/* AuthProvider adentro del router: usa navegacion y estado de ruta */}
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
);
