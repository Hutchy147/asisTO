# Seguridad de acceso (Entrega 3): bloqueo y recuperación de contraseña

## Bloqueo por intentos fallidos

- 5 contraseñas incorrectas seguidas bloquean **esa cuenta** 15 minutos (`MAX_INTENTOS`, `BLOQUEO_MINUTOS` en `auth_service.py`). Responde **429** con `Demasiados intentos fallidos. Proba de nuevo en N minutos o restablece tu contrasena.`
- Con la cuenta bloqueada se rechaza **aunque la contraseña sea correcta**. Un intento durante el bloqueo no lo extiende. Pasado el plazo, la cuenta arranca de cero.
- Un login correcto reinicia el contador. Restablecer la contraseña levanta el bloqueo.
- Un email que no existe nunca se bloquea y responde siempre el mismo 401 genérico (no se puede enumerar cuentas). Se verifica bcrypt igual en todas las ramas para no abrir un canal de tiempos.
- La regla vive en la base: `p_registrar_login_fallido` (lock `FOR UPDATE` de la fila del usuario: los intentos en paralelo no pierden cuentas) y `p_registrar_login_ok`.

## Recuperación de contraseña

| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `POST /api/auth/recuperar` | `{email}` | 200 con el **mismo mensaje exista o no la cuenta**. Con `RECUPERACION_MOSTRAR_TOKEN=1` (desarrollo) suma `token_desarrollo` solo si la cuenta existe y está activa |
| `POST /api/auth/restablecer` | `{token, contrasena_nueva}` | 200, o 400 con `campo`: `contrasena_nueva` (mínimo 8, letras y números, máx. 72 bytes) o `token` (inválido, vencido o ya usado) |

- El token (`secrets.token_urlsafe(32)`) **no se guarda**: en `usuarios.token_recuperacion` queda su SHA-256. Vale 60 minutos y es de un solo uso; un pedido nuevo invalida el anterior.
- **Sin servidor de mail**: en desarrollo la API devuelve el token y se loguea. `RECUPERACION_MOSTRAR_TOKEN` sigue a `FLASK_DEBUG`; **en producción tiene que ser 0**, y el envío por mail queda pendiente de definir.
- Procedimientos: `p_solicitar_recuperacion`, `p_restablecer_contrasena`.

## Pantallas

`/recuperar` y `/restablecer/:token` (públicas), link "¿Olvidaste tu contraseña?" en el login. Capacidad `auth.recuperar` (entrega 3): en entregas 1–2 no aparecen. El bloqueo, en cambio, es del backend y vale en todas las entregas.

## Pruebas

`tests/nube/test_seguridad_api.py` (9 casos) y `tests/nube/ui_seguridad.py` (Chromium; **cambia la clave de paula.cabrera en la base demo**: volver a correr `generar_hashes.py --aplicar --todos`).
