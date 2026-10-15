# API de asignaciones (HDU 11)

Un paciente tiene un terapeuta responsable. **Solo quien lo tiene asignado en la fecha de la sesión puede registrarle sesiones y evoluciones nuevas** (regla 8, en la base). La lectura sigue abierta entre terapeutas. Todos los endpoints requieren rol `terapeuta`.

La regla vive en los procedimientos `p_abrir_asignacion` / `p_cerrar_asignacion` y en los triggers `trg_sesiones_solape_insert` y `trg_evoluciones_validar_insert`. La API solo traduce.

| Método y ruta | Qué hace |
|---|---|
| `GET /api/terapeutas` | Terapeutas con usuario activo: `{terapeutas: [{id, nombre_completo, especialidad}], total}` |
| `GET /api/pacientes/<id>/asignaciones` | Historial (vigentes primero): `{id_paciente, asignaciones: [{id, id_terapeuta, terapeuta, fecha_desde, fecha_hasta, vigente}], vigentes}`. Incluye pacientes de baja. 404 si no existe |
| `POST /api/pacientes/<id>/asignaciones` | Abre. Cuerpo `{id_terapeuta, fecha_desde?}` (AAAA-MM-DD, no futura; por omisión hoy). 201 `{asignacion, mensaje}` |
| `POST /api/asignaciones/<id>/cierre` | Cierra. Cuerpo `{fecha_hasta?}` (por omisión hoy; no anterior al inicio). 200 `{asignacion, mensaje}` |
| `GET /api/pacientes` | Suma `asignado_a_mi` (bool) y `responsables` (lista de nombres vigentes) |
| `POST /api/pacientes` | Acepta `id_terapeuta` opcional: abre la asignación en el alta. Por omisión, el terapeuta que da el alta. Si la asignación falla, el paciente queda creado y el `mensaje` lo avisa |

## Errores (con `campo`)

| Situación | Status | `campo` |
|---|---|---|
| Ya hay una asignación vigente del par | 400 | `id_terapeuta` |
| Terapeuta inexistente o faltante | 400 | `id_terapeuta` |
| Paciente de baja | 400 | `id_paciente` |
| `fecha_desde` futura o mal escrita | 400 | `fecha_desde` |
| `fecha_hasta` anterior al inicio o mal escrita | 400 | `fecha_hasta` |
| Asignación inexistente al cerrar | 404 | — |
| Asignación ya cerrada | 409 | — |
| Registrar sesión de un paciente no asignado | 400 | `id_paciente` (`... no tiene asignado a este paciente`) |

## Pruebas

`tests/nube/run.sh` (arma una base descartable y corre `test_asignaciones_api.py`, 10 casos con control positivo junto a cada rechazo). UI: `tests/nube/ui_asignaciones.py` con backend en 5000 y Vite en 5173 (`VITE_ENTREGA=3`).
