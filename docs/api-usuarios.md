# API de cuentas de acceso (administrador)

Solo el rol `admin`. Cualquier otro rol recibe `403`. Pantalla: `/admin/usuarios`
(menú «Cuentas de acceso»).

Antes solo podían ingresar los correos precargados en el seed. Ahora el
administrador da de alta un correo con una contraseña que él elige (o genera) y
se la entrega a la persona.

## Qué roles se dan de alta
`terapeuta`, `rrhh`, `admin` y `familiar`. La cuenta del **paciente** no: depende
de su ficha clínica (`pacientes.id_usuario`) y se habilita desde el paciente. Un
familiar creado acá queda **sin pacientes vinculados**; el vínculo se hace
después desde la ficha del paciente o desde Asignaciones.

## `GET /api/admin/usuarios?rol=&estado=&busqueda=`
`estado`: `activas` o `deshabilitadas`. Devuelve `{ usuarios, total }` con, por
cuenta: `id, nombre, apellido, nombre_completo, email, rol, activo, bloqueado,
perfil` (matrícula, legajo o parentesco), `ultimo_ingreso`,
`pacientes_a_cargo` (terapeutas) y `es_usted`. Nunca incluye hashes ni tokens.

## `GET /api/admin/usuarios/contrasena-sugerida`
`{ contrasena }`: 10 caracteres con letras y números, sin I, l, O, 0 ni 1.

## `POST /api/admin/usuarios`
```json
{ "rol": "terapeuta", "nombre": "Nora", "apellido": "Pérez",
  "email": "nora@centro.org", "contrasena": "Entrada2026x",
  "matricula": "MP-9001", "especialidad": "opcional" }
```
Datos propios del rol: terapeuta `matricula` (obligatoria) y `especialidad`;
rrhh `nro_legajo` (obligatorio) y `sector`; familiar `parentesco` y `telefono`.
La contraseña cumple la misma política que el resto (mínimo 8, letras y números,
no común, sin el correo adentro).

| Caso | Status | `campo` |
|---|---|---|
| Creada | `201` | |
| Rol no válido (incluye `paciente`) | `400` | `rol` |
| Falta nombre, apellido o dato del rol | `400` | el que falta |
| Correo con formato inválido | `400` | `email` |
| Contraseña que no cumple la política | `400` | `contrasena` |
| Correo ya existente (sin distinguir mayúsculas) | `409` | `email` |
| Matrícula o legajo repetido | `409` | `matricula` / `nro_legajo` |

La cuenta se crea en una sola transacción: si falla el perfil, no queda un
usuario a medias.

## `PUT /api/admin/usuarios/<id>/estado`
`{ "activo": true | false }`. Deshabilitar impide ingresar y **revoca las sesiones
abiertas** de esa cuenta (`sesiones_validas_desde`); no borra nada de lo que la
persona cargó. Rechaza (`409`) deshabilitar la propia cuenta y deshabilitar al
último administrador activo.

## `PUT /api/admin/usuarios/<id>/contrasena`
`{ "contrasena": "..." }`. Fija la clave nueva, **desbloquea** la cuenta, anula
un enlace de recuperación pendiente y cierra sus sesiones abiertas.

## Seguridad
- La contraseña que elige el administrador **la conoce el administrador**. La
  pantalla recomienda a la persona cambiarla al entrar, con «¿Olvidó su
  contraseña?». La clave se muestra una sola vez, al crear o restablecer.
- Cada alta, habilitación, deshabilitación y restablecimiento queda en el log
  del servidor con el id del administrador que lo hizo.
- Pruebas: `tests/nube/test_admin_usuarios.py` y `tests/nube/ui_admin_usuarios.py`.
