# Seguridad de acceso (Entrega 3): bloqueo y recuperación de contraseña

## Bloqueo por intentos fallidos

- 5 contraseñas incorrectas seguidas bloquean **esa cuenta** 15 minutos (`MAX_INTENTOS`, `BLOQUEO_MINUTOS` en `auth_service.py`). Responde **429** con `Demasiados intentos fallidos. Intente nuevamente en N minutos o restablezca su contraseña.`
- Con la cuenta bloqueada se rechaza **aunque la contraseña sea correcta**. Un intento durante el bloqueo no lo extiende. Pasado el plazo, la cuenta arranca de cero.
- Un login correcto reinicia el contador. Restablecer la contraseña levanta el bloqueo.
- Un email que no existe se bloquea con la misma regla (5 fallos en 15 minutos, contados en `auditoria_accesos`): si solo se bloquearan los reales, el 429 diría cuáles existen. Se verifica bcrypt igual en todas las ramas para no abrir un canal de tiempos.
- Además, **límite por IP** (`app/utils/limites.py`): 30 logins fallidos, 10 pedidos de recuperación y 20 intentos de restablecer por IP cada 15 minutos (configurables en el `.env`). Frena a quien prueba una clave común contra muchos emails. Ver `docs/seguridad.md`.
- La regla vive en la base: `p_registrar_login_fallido` (lock `FOR UPDATE` de la fila del usuario: los intentos en paralelo no pierden cuentas) y `p_registrar_login_ok`.

## Recuperación de contraseña

| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `POST /api/auth/recuperar` | `{email}` | 200 con el **mismo mensaje exista o no la cuenta**. Con `RECUPERACION_MOSTRAR_TOKEN=1` (desarrollo) suma `token_desarrollo` solo si la cuenta existe y está activa |
| `POST /api/auth/restablecer/verificar` | `{token}` | 200 `{vigente: bool}`. La pantalla lo consulta al abrirse: un enlace usado o vencido se avisa antes de pedir la clave |
| `POST /api/auth/restablecer` | `{token, contrasena_nueva}` | 200, o 400 con `campo`: `contrasena_nueva` (mínimo 8, letras y números, máx. 72 bytes, no una clave común ni que contenga el email) o `token` (inválido, vencido o ya usado). Restablecer **cierra todas las sesiones abiertas** de la cuenta |

- El token (`secrets.token_urlsafe(32)`) **no se guarda**: en `usuarios.token_recuperacion` queda su SHA-256. Vale 60 minutos y es de un solo uso; un pedido nuevo invalida el anterior.
- **Sin servidor de mail**: en desarrollo la API devuelve el token y se loguea. `RECUPERACION_MOSTRAR_TOKEN` sigue a `FLASK_DEBUG` (que, si falta en el `.env`, vale 0); **en producción tiene que ser 0**, y el envío por mail queda pendiente de definir.
- Procedimientos: `p_solicitar_recuperacion`, `p_restablecer_contrasena`.

## Pantallas

`/recuperar` y `/restablecer/:token` (públicas), link "¿Olvidaste tu contraseña?" en el login. Capacidad `auth.recuperar` (entrega 3): en entregas 1–2 no aparecen. El bloqueo, en cambio, es del backend y vale en todas las entregas.

## Pruebas

`tests/nube/test_seguridad_api.py` (9 casos) y `tests/nube/ui_seguridad.py` (Chromium; **cambia la clave de paula.cabrera en la base demo**: volver a correr `generar_hashes.py --aplicar --todos`).

## Auditoría de accesos

Cada intento de login deja una fila en `auditoria_accesos` (`p_registrar_acceso`): `exitoso`; `fallido` (contraseña mala o email inexistente); `inactiva` (clave correcta con la cuenta deshabilitada: para quien intenta es el mismo rechazo); `bloqueado` (el intento que dispara el bloqueo y los que llegan con la cuenta bloqueada). También `recuperacion` (se pidió un enlace) y `restablecida` (se cambió la clave con el enlace). Guarda email, IP y `id_usuario` (NULL si el email no existe). **Nunca la contraseña.** Si la auditoría falla, el login sigue: se loguea el error.

`GET /api/rrhh/auditoria-accesos` (solo rol `rrhh`): `desde`, `hasta` (por omisión los últimos 7 días), `resultado`, `email` (contiene), `limite` (100 por omisión, máx. 500). Devuelve `{resumen: {exitoso, fallido, bloqueado, total}, accesos}`; el resumen cuenta **todo el filtro**, no solo las filas devueltas. Pantalla `/rrhh/auditoria` (capacidad `auditoria.accesos`) con botón en el panel de RRHH.

Límites conocidos: detrás de un proxy inverso hay que configurar `PROXIES_CONFIABLES` para que la IP sea la del cliente; la tabla no se purga sola; el límite por IP acota cuánto se la puede llenar con emails inventados.
