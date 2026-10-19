// frontend/src/context/AuthContext.jsx
// Estado de sesion de la app: usuario, rol, perfil y token.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import {
  getMe,
  getToken,
  login as loginRequest,
  logout as logoutRequest,
  registrarManejadorDeSesion,
  setToken,
} from '../services/api.js';

const AuthContext = createContext(null);

// Ruta inicial de cada rol. Es la unica fuente de verdad del mapeo:
// la usan el login, la redireccion de "/" y el 403.
export const RUTA_POR_ROL = {
  terapeuta: '/panel',
  rrhh: '/rrhh',
  familiar: '/familiar',
  paciente: '/paciente',
  admin: '/admin',
};

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [perfil, setPerfil] = useState(null);
  // cargando arranca en true: mientras se revalida el token guardado no se
  // puede decidir si mostrar el login o el dashboard. Sin esto, al recargar
  // se ve un parpadeo del login antes de entrar.
  const [cargando, setCargando] = useState(true);
  const [avisoSesion, setAvisoSesion] = useState('');

  const limpiarSesion = useCallback(() => {
    setToken(null);
    setUsuario(null);
    setPerfil(null);
  }, []);

  // El cliente HTTP avisa cuando el backend rechaza el token. Se limpia el
  // estado y listo: la redireccion la hace RutaProtegida al no ver usuario.
  // Nadie navega desde aca, y por eso no hay forma de entrar en loop.
  useEffect(() => {
    registrarManejadorDeSesion((codigo) => {
      limpiarSesion();
      setAvisoSesion(
        codigo === 'token_expirado'
          ? 'Su sesión expiró. Vuelva a iniciar sesión.'
          : 'Su sesión ya no es válida. Vuelva a iniciar sesión.'
      );
    });
  }, [limpiarSesion]);

  // Al montar: si hay token guardado se revalida contra el backend. Un
  // token puede estar vencido o pertenecer a un usuario dado de baja, asi
  // que no alcanza con que exista en localStorage.
  useEffect(() => {
    let cancelado = false;

    async function restaurarSesion() {
      if (!getToken()) {
        setCargando(false);
        return;
      }
      try {
        const datos = await getMe();
        if (!cancelado) {
          setUsuario(datos.usuario);
          setPerfil(datos.perfil);
        }
      } catch {
        // getMe ya limpio el token si el 401 fue de sesion. No se
        // reintenta: reintentar con un token invalido es el loop.
        if (!cancelado) limpiarSesion();
      } finally {
        if (!cancelado) setCargando(false);
      }
    }

    restaurarSesion();
    return () => {
      cancelado = true;
    };
  }, [limpiarSesion]);

  const login = useCallback(async (email, contrasena) => {
    const datos = await loginRequest(email, contrasena);
    setToken(datos.token);
    setUsuario(datos.usuario);
    setPerfil(datos.perfil);
    setAvisoSesion('');
    return datos.usuario;
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // Si el backend no responde o el token ya vencio, el cierre local
      // se hace igual: quedarse con la sesion abierta seria peor.
    }
    limpiarSesion();
    setAvisoSesion('');
  }, [limpiarSesion]);

  // useCallback y no una arrow suelta dentro del useMemo: si cambiara de
  // identidad en cada render, cualquier efecto que la tenga como
  // dependencia se reejecutaria en bucle.
  const limpiarAviso = useCallback(() => setAvisoSesion(''), []);

  const valor = useMemo(
    () => ({
      usuario,
      perfil,
      cargando,
      avisoSesion,
      autenticado: Boolean(usuario),
      rol: usuario?.rol ?? null,
      login,
      logout,
      limpiarAviso,
    }),
    [usuario, perfil, cargando, avisoSesion, login, logout, limpiarAviso]
  );

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const contexto = useContext(AuthContext);
  if (!contexto) {
    throw new Error('useAuth debe usarse dentro de un AuthProvider');
  }
  return contexto;
}
