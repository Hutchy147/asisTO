# Seguridad de AsisTO

Auditoría y endurecimiento del 23/10/2026, sobre la V6. AsisTO guarda datos de
salud de menores: lo que más importa proteger es que nadie lea la historia
clínica de un paciente sin permiso y que nadie entre con la cuenta de otra
persona. Este documento resume qué ataques se consideraron, qué los frena y qué
hay que configurar al instalarlo en el centro.

## 1. Ataques considerados y defensas

| Ataque | Cómo se frena | Dónde |
|---|---|---|
| **Fuerza bruta contra una cuenta** | 5 claves incorrectas bloquean esa cuenta 15 minutos (también un email que no existe, para no delatar cuáles existen). Con la cuenta bloqueada se rechaza aunque la clave sea correcta. | `auth_service.py`, `p_registrar_login_fallido` |
| **Password spraying** (una clave común contra muchos emails) | Límite por IP: 30 logins fallidos cada 15 minutos. Los logins correctos no cuentan. | `app/utils/limites.py` |
| **Abuso de la recuperación** (pedir enlaces en masa, adivinar enlaces) | 10 pedidos y 20 intentos de restablecer por IP cada 15 minutos. El enlace es aleatorio de 256 bits, vale una hora y sirve una vez; en la base solo vive su SHA-256. | `limites.py`, `auth_service.py` |
| **Enumerar cuentas** | Mismo mensaje, mismo código, mismas cabeceras y mismo tiempo de respuesta exista o no el email (bcrypt corre siempre; la recuperación tarda lo mismo). | `auth_service.py`, `tests/backend/test_canal_lateral_login.py` |
| **Claves débiles** | Mínimo 8 caracteres con letras y números, máximo 72 bytes, rechaza una lista de claves comunes y las que contienen el email. Las claves temporales de familiares no usan I, l, O, 0 ni 1. | `_validar_contrasena_nueva`, `generar_contrasena_temporal` |
| **Robo de la sesión por XSS** | La sesión viaja en una cookie **HttpOnly**: el JavaScript de la página no la puede leer. Antes el JWT vivía en `localStorage`. | `routes/auth.py`, `services/api.js` |
| **XSS** (que un texto cargado ejecute código) | React escapa todo lo que muestra; no hay `dangerouslySetInnerHTML`. El build lleva una **política de contenido (CSP)** que solo permite scripts propios. El PDF escapa el texto antes de armarlo. | `vite.config.js`, `informes_pdf.py`, `tests/nube/ui_seguridad_web.py` |
| **CSRF** (que otra página haga pedidos con la sesión del usuario) | Cookie `SameSite=Strict` + cabecera propia `X-AsisTO` obligatoria en todo pedido que modifica datos con la cookie (otro sitio no puede ponerla sin pasar el CORS, que solo admite el origen del sistema). | `utils/security.py` |
| **Phishing / sesión robada que sigue activa** | Cerrar sesión **revoca** todos los tokens emitidos hasta ese momento (en todos los equipos). Restablecer la contraseña también. Un enlace copiado o un token robado dejan de servir en el acto. | `usuarios.sesiones_validas_desde`, `requiere_rol` |
| **Phishing por el enlace de recuperación** | La página y la API mandan `Referrer-Policy: no-referrer`: la URL con el enlace no viaja a ningún tercero. El enlace se verifica al abrirse. | `index.html`, `__init__.py` |
| **Clickjacking** (embeber el sistema en un iframe engañoso) | `X-Frame-Options: DENY` y `frame-ancestors 'none'` en la API, el servidor de desarrollo y la vista previa del build. | `__init__.py`, `vite.config.js` |
| **Redirección abierta** | El login solo vuelve a rutas internas declaradas (nada de `//otro-sitio` ni barras invertidas). | `pages/Login.jsx` |
| **Ver datos de otro paciente (IDOR)** | Cada endpoint valida rol y vínculo en el servidor: el familiar solo ve lo vinculado, el paciente solo lo suyo, RRHH nada clínico, escribir solo el terapeuta asignado. Barrido de todas las rutas GET × 8 identidades sin respuestas indebidas. | servicios, procedimientos, `tests/backend/test_rbac_mecanismo.py` |
| **Inyección SQL** | Consultas parametrizadas en todo el backend; los únicos textos armados son nombres de procedimientos internos. | servicios |
| **Datos clínicos en caché** (computadora compartida) | La API responde con `Cache-Control: no-store`. Cerrar sesión borra la cookie. En las pantallas «fuera de entrega» siempre hay «Cerrar sesión». | `__init__.py`, `FueraDeEntrega.jsx` |
| **Tokens falsificados** | JWT firmado con HS256 (algoritmo fijo), secreto de al menos 32 caracteres, distinto de `SECRET_KEY`; el usuario se revalida contra la base en cada pedido (activo, rol, revocación). | `config.py`, `security.py`, `test_jwt_manipulacion.py` |
| **Configuración peligrosa en producción** | La app no arranca con secretos cortos o iguales, ni con `RECUPERACION_MOSTRAR_TOKEN=1` fuera de desarrollo. El depurador de Werkzeug se apaga si falta `FLASK_DEBUG`. | `Config.validar()` |
| **Cuerpos enormes** | Tope de 1 MB por solicitud (413). | `MAX_CONTENT_LENGTH` |
| **Dependencias con fallas conocidas** | Backend: `pip-audit` sin hallazgos (Flask 3.1.3, Flask-Cors 6.0.5, PyJWT 2.15.1, cryptography 50.0.2, python-dotenv 1.2.4). Frontend: Vite 6.4.5, React Router 6.30.6 y parches de `nanoid` y `source-map-js`. | `requirements.txt`, `package.json`, `pnpm-workspace.yaml` |

Todo queda registrado en la **auditoría de accesos** (pantalla de RRHH): logins
exitosos, fallidos, bloqueados, con la cuenta deshabilitada, pedidos de
recuperación y cambios de contraseña, con fecha, email e IP.

## 2. Instalación en el centro (checklist)

1. **HTTPS obligatorio.** Sin HTTPS la cookie de sesión y las claves viajan en texto plano por la red del centro. Con `FLASK_DEBUG=0` la cookie es `Secure` y la API manda HSTS.
2. `backend/.env`: `FLASK_DEBUG=0`, `RECUPERACION_MOSTRAR_TOKEN=0`, `SECRET_KEY` y `JWT_SECRET_KEY` distintos generados con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. Servir la API con un servidor WSGI (por ejemplo `waitress-serve --listen=127.0.0.1:5000 run:app`), nunca con `python run.py`.
4. Si hay un proxy inverso (nginx, IIS) delante: `PROXIES_CONFIABLES=1` (o la cantidad de saltos), para que la auditoría y los límites vean la IP real.
5. El servidor web que entrega el frontend (`pnpm build` → `dist/`) tiene que mandar estas cabeceras (ejemplo nginx):

   ```nginx
   add_header X-Frame-Options "DENY" always;
   add_header X-Content-Type-Options "nosniff" always;
   add_header Referrer-Policy "no-referrer" always;
   add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
   add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
   ```

   El build ya incluye la CSP como `<meta>` por si el servidor no la pone, pero `frame-ancestors` solo funciona como cabecera.
6. Servir frontend y API **en el mismo dominio** (`/` y `/api`): así la cookie `SameSite=Strict` funciona sin configurar CORS. Si la API va en otro dominio, definir `VITE_API_URL` y agregarlo a `CORS_ORIGINS`.
7. Usuario de MySQL de la aplicación con permisos solo sobre la base `asisto` (nunca `root`), y MySQL escuchando solo en `127.0.0.1`.
8. Respaldos cifrados de la base y del `.env`, fuera del servidor.
9. Revisar dependencias cada mes: `pip-audit -r backend/requirements.txt` y `pnpm audit` en `frontend/`.

## 3. Riesgos que quedan (aceptados o fuera de alcance)

- **Bloqueo como molestia:** cualquiera que conozca un email puede bloquear esa cuenta 15 minutos equivocando la clave 5 veces. Es el costo de frenar la fuerza bruta; la salida es esperar o restablecer la contraseña. No se avisa cuántos intentos quedan: el contador de una cuenta real y el de un email inexistente no coinciden siempre, y el número permitiría distinguirlos.
- **Límite por IP en memoria:** con un solo proceso (waitress con hilos) es exacto; con varios procesos cada uno cuenta por su lado. Se reinicia al reiniciar el servidor.
- **Sin envío de correo:** la recuperación genera el enlace pero el centro todavía no definió el servidor de mail. Hasta entonces, en producción lo restablece el administrador.
- **Sin segundo factor (MFA).** Recomendable si el sistema se publica fuera de la red del centro.
- **React Router 6:** dos avisos que solo corrige la v7. Uno es de renderizado en servidor (AsisTO no lo usa); el otro es una redirección abierta con barra invertida, mitigada en el único `navigate` con destino variable (el login).
- **IA de informes:** si se activa, los datos del período (sin el nombre del paciente) salen hacia el proveedor. La coordinación tiene que aprobarlo antes.
- **Lectura clínica abierta entre terapeutas:** decisión de diseño (HDU 11): cualquier terapeuta lee la historia de cualquier paciente; solo el asignado escribe.

## 4. Pruebas

- `tests/nube/test_seguridad_web.py`: cookie HttpOnly/Strict, CSRF, revocación por logout y por cambio de clave, cabeceras, 413, límites por IP, claves comunes, configuración insegura, claves temporales.
- `tests/nube/ui_seguridad_web.py`: en el navegador, nada en `localStorage`, la cookie no es visible para el JavaScript, F5 conserva la sesión, un nombre con HTML no se ejecuta, el token de una sesión cerrada no sirve, la página no se deja embeber.
- `tests/backend/`: manipulación de JWT, RBAC, canal lateral de tiempos, revalidación del usuario.
