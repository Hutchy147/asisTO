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

// Una página restaurada desde la caché de Atrás/Adelante (bfcache) puede
// mostrar datos de una sesión ya cerrada: se recarga para que vuelva a pasar
// por la verificación de sesión (usabilidad, padre).
window.addEventListener('pageshow', (evento) => {
  if (evento.persisted) window.location.reload();
});

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
