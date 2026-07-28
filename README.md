# AsisTO

Sistema de Gestión de Asistencias y Seguimiento Terapéutico para terapia
ocupacional. Práctica Profesionalizante III — IES 9-023, Mendoza.

- **Frontend:** React + Vite + Material UI (pnpm)
- **Backend:** Python + Flask + SQLAlchemy
- **Base de datos:** MySQL 8.0+ (una instancia local por integrante)

---

## Requisitos previos

Instalar una sola vez, en Windows 10/11:

| Herramienta | Versión mínima | Verificar con |
|---|---|---|
| Python | 3.11 | `python --version` |
| Node.js | 18 | `node --version` |
| pnpm | 9 | `pnpm --version` |
| MySQL Server | 8.0 | `mysql --version` |
| Git | 2.40 | `git --version` |

Si `pnpm` no está instalado: `npm install -g pnpm`

Si `mysql` no se reconoce como comando, agregar a la variable de entorno
`Path` la carpeta `C:\Program Files\MySQL\MySQL Server 8.0\bin` y abrir una
terminal nueva.

---

## 1. Configurar el acceso a MySQL (una sola vez)

Para no escribir la contraseña en cada comando ni dejarla en el historial
de la terminal, se usa un **login-path** de MySQL. Queda guardado cifrado
en `%APPDATA%\MySQL\.mylogin.cnf`, fuera del repositorio.

Cada integrante lo crea una vez en su máquina:

```powershell
mysql_config_editor set --login-path=asisto --host=localhost --user=root --password
```

Pide la contraseña de MySQL y no la vuelve a pedir. Verificar que quedó
bien:

```powershell
mysql --login-path=asisto -e "SELECT VERSION();"
```

Si tira `mysql_config_editor no se reconoce`, falta agregar al `Path` la
carpeta `C:\Program Files\MySQL\MySQL Server 8.0\bin`. Para la sesión
actual alcanza con:

```powershell
$env:Path += ";C:\Program Files\MySQL\MySQL Server 8.0\bin"
```

> El login-path es por máquina y no se versiona. Los cuatro integrantes
> tienen que crearlo con el mismo nombre (`asisto`) para que los comandos
> del proyecto sean idénticos para todos.

---

## 2. Crear la base de datos

`schema.sql` crea la base entero: **arranca con `DROP DATABASE IF EXISTS
asisto`**, así que se puede correr las veces que haga falta, pero borra
todo lo que haya cargado.

```powershell
cd C:\dev\asisTO
mysql --login-path=asisto -e "source backend/database/schema.sql"
mysql --login-path=asisto -e "source backend/database/seed.sql"
```

El primero deja 18 tablas, 2 vistas, 3 triggers y 5 procedimientos
almacenados. El segundo carga datos de prueba con id fijos, para que las
cuatro instancias locales arranquen idénticas.

Verificar:

```powershell
mysql --login-path=asisto asisto -e "SELECT * FROM v_resumen_sesiones;"
```

> Las contraseñas del seed son **placeholders**, no hashes bcrypt válidos:
> ningún login va a funcionar con esos datos. Se reemplazan cuando exista
> el módulo de autenticación.

---

## 3. Backend

Desde la raíz del repositorio:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell bloquea la activación del entorno virtual:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Copiar el archivo de ejemplo:

```powershell
copy .env.example .env
```

**Generar los dos secretos.** `SECRET_KEY` y `JWT_SECRET_KEY` son
obligatorios y **no tienen valor por defecto**: si falta cualquiera de los
dos, la aplicación no arranca y explica qué falta. Un default commiteado
sería un secreto público firmando los JWT de todos.

Generar un valor **distinto** para cada uno:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Después completar el `.env` con esos dos valores, más `DB_USER` y
`DB_PASSWORD`:

```powershell
notepad .env
```

El `.env` está en `.gitignore` y no se commitea nunca.

Levantar la API:

```powershell
python run.py
```

Queda en `http://127.0.0.1:5000`. Para comprobar que responde, en **otra**
terminal:

```powershell
curl http://127.0.0.1:5000/api/health
```

Si `database.conectada` es `false`, revisar `DB_USER` y `DB_PASSWORD`.

---

## 4. Generar las contraseñas de prueba

**Obligatorio para poder loguear.** Los `contrasena_hash` de `seed.sql` son
placeholders, no hashes bcrypt válidos: recién cargado el seed, ningún
login funciona.

No están escritos a mano en `seed.sql` a propósito — bcrypt genera un salt
distinto en cada corrida, así que hardcodearlos dejaría una contraseña fija
commiteada en el repositorio.

Desde `backend/`, con el venv activo:

```powershell
python scripts/generar_hashes.py --aplicar
```

Sin `--aplicar` solo imprime los `UPDATE` sin tocar la base.

**Hay que volver a correrlo cada vez que se recargue `seed.sql`.**

### Usuarios de prueba

Todos con la contraseña **`asisto2026`**. Son de desarrollo: no usar en
ningún entorno real.

| Email | Rol |
|---|---|
| `laura.fernandez@asisto.local` | terapeuta |
| `diego.moyano@asisto.local` | terapeuta |
| `silvia.quiroga@asisto.local` | rrhh |
| `marta.ledesma@asisto.local` | familiar |
| `jorge.bustos@asisto.local` | familiar |
| `camila.rios@asisto.local` | paciente |

Los otros dos pacientes del seed (Tomás y Valentina) **no tienen login**, y
eso es correcto: son menores y su `pacientes.id_usuario` es `NULL`. Existen
como registro clínico completo sin credenciales (regla 5).

---

## 5. Frontend

Desde la raíz del repositorio, en **otra** terminal (el backend queda
corriendo en la primera):

```powershell
cd frontend
pnpm install
pnpm dev
```

Queda en `http://localhost:5173`. Vite proxea `/api` hacia Flask en el
puerto 5000, así que no hace falta configurar URLs absolutas ni pelear con
CORS en desarrollo.

La pantalla inicial es el login. Cada rol entra a su propio dashboard:
`/terapeuta`, `/rrhh`, `/familiar` y `/paciente`. Entrar a la ruta de otro
rol muestra un 403 propio; sin sesión, cualquier ruta protegida redirige al
login.

---

## 6. Levantar todo (resumen)

Dos terminales, desde la raíz del repositorio:

```powershell
# Terminal 1 — backend
cd backend; .\venv\Scripts\Activate.ps1; python run.py

# Terminal 2 — frontend
cd frontend; pnpm dev
```

Abrir `http://localhost:5173`.

---

## Estructura

```
asisTO/
├── backend/
│   ├── app/
│   │   ├── __init__.py      factory, CORS, blueprints, manejo de errores
│   │   ├── models/          modelos SQLAlchemy (mapean schema.sql)
│   │   ├── routes/          un blueprint por módulo
│   │   ├── services/        lógica de negocio y reglas críticas
│   │   └── utils/           security.py (JWT/RBAC), errors.py, db.py
│   ├── scripts/
│   │   └── generar_hashes.py  hashes bcrypt para el seed
│   ├── database/
│   │   ├── schema.sql       tablas, triggers, procedimientos, vistas
│   │   └── seed.sql         datos de prueba
│   ├── config.py            configuración, lee de .env
│   ├── requirements.txt
│   ├── run.py               entrypoint de desarrollo
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/      componentes reutilizables
│   │   ├── pages/           pantallas
│   │   ├── services/        cliente HTTP
│   │   ├── theme/theme.js   fuente de verdad de la identidad visual
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## Convenciones

Las convenciones de código, las reglas de negocio, el modelo de roles y el
formato de commits están documentados aparte y son de cumplimiento
obligatorio. Puntos que conviene tener presentes desde el día uno:

- Los colores salen **siempre** de `frontend/src/theme/theme.js`. Nunca un
  hex suelto en un componente.
- Variables y funciones en inglés, comentarios en español.
- Tablas y columnas de la base en español, plural, `snake_case`.
- Credenciales solo en `.env`. Nunca en el repositorio.

---

## Entregas

Una sola rama de desarrollo continuo. En cada fecha se corta un tag
(`entrega-1` a `entrega-4`) y las correcciones se aplican hacia adelante.

| Tag | Módulo | Alcance |
|---|---|---|
| `entrega-1` | Clínico | Auth + roles, pacientes, objetivos, calendario, evolución básica |
| `entrega-2` | Gestión | Edición y baja de pacientes, historial, gráficos, RRHH con export |
| `entrega-3` | Portal Familiar | Recuperación de contraseña, vínculo familiar, notas de campo, notificaciones |
| `entrega-4` | IA y PDF | Informes trimestrales con IA, export PDF, auditoría, duplas, plantillas |
