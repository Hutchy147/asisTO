# API de familiares (Entrega 4)

Vincula cuentas de familiar con pacientes. **El vínculo es lo que da acceso al portal familiar**: sin fila en `familiares_pacientes`, el familiar no ve nada de ese paciente. Lo gestionan el `admin` y el terapeuta con asignación vigente sobre el paciente; cualquier otro rol (o un terapeuta sin asignación) recibe 403.

La regla vive en `p_vincular_familiar`, `p_desvincular_familiar` y `p_crear_familiar_y_vincular`. La API solo traduce.

| Método y ruta | Qué hace |
|---|---|
| `GET /api/pacientes/<id>/familiares` | Vinculados: `{id_paciente, familiares: [{id, nombre, apellido, nombre_completo, email, parentesco, telefono, cuenta_activa, fecha_vinculo}], total}` |
| `GET /api/pacientes/<id>/familiares/candidatos?q=` | Cuentas de familiar activas todavía no vinculadas a este paciente (máx. 50; `q` filtra por nombre, apellido o correo) |
| `POST /api/pacientes/<id>/familiares` | Con `{id_familiar}` vincula una cuenta existente. Sin él, crea la cuenta: `{nombre, apellido, email, parentesco?, telefono?}`. 201 `{familiar, mensaje}`; al crear suma `contrasena_temporal` (se devuelve **una sola vez**; la base solo guarda el hash) |
| `POST /api/pacientes/<id>/familiares/<id_familiar>/desvinculacion` | Quita el acceso. La cuenta se conserva. 200 `{mensaje}` |

## Errores

| Situación | Status | `campo` |
|---|---|---|
| Paciente o familiar inexistente | 404 | — |
| Familiar ya vinculado | 409 | — |
| Desvincular un vínculo que no existe | 409 | — |
| Correo ya registrado | 409 | `email` |
| Correo con formato inválido, nombre o apellido faltantes | 400 | el campo |
| Paciente de baja (no admite vínculos nuevos) | 400 | — |
| Cuenta del familiar deshabilitada | 400 | — |
| Terapeuta sin asignación vigente / otro rol | 403 | — |

## Decisiones

- La contraseña temporal es de 10 caracteres con letras y números; no hay marca de "cambiar al primer ingreso" porque el schema no la tiene. La persona puede cambiarla desde la recuperación de contraseña.
- Desvincular sigue permitido con el paciente de baja, para poder limpiar accesos.

## Pruebas

`tests/nube/test_familiares_api.py` (API) y `tests/nube/ui_familiares.py` (pantalla, modo `VITE_ENTREGA=4`).
