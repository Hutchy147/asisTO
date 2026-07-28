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

## 1. Crear la base de datos

Abrir PowerShell y entrar al cliente de MySQL:

```powershell
mysql -u root -p
```

Dentro del cliente:

```sql
CREATE DATABASE asisto CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
EXIT;
```

> **PENDIENTE — cargar el schema.** Las tablas, los procedimientos
> almacenados y los datos semilla todavía no existen. Cuando el schema esté
> escrito va a vivir en `backend/database/` y este paso pasa a ser:
> `mysql -u root -p asisto < backend/database/schema.sql`
>
> Hasta entonces la base queda vacía. El backend levanta igual: el endpoint
> `/api/health` reporta `database.conectada: false` sin tirar la API abajo.

---

## 2. Backend

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

Copiar el archivo de ejemplo y completarlo con los datos locales:

```powershell
copy .env.example .env
notepad .env
```

Como mínimo hay que completar `SECRET_KEY`, `JWT_SECRET_KEY`, `DB_USER` y
`DB_PASSWORD`. El `.env` está en `.gitignore` y no se commitea nunca.

Levantar la API:

```powershell
python run.py
```

Queda en `http://127.0.0.1:5000`. Para comprobar que responde, en **otra**
terminal:

```powershell
curl http://127.0.0.1:5000/api/health
```

---

## 3. Frontend

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

La pantalla inicial es una verificación del theme: muestra los colores por
rol, los estados de sesión, los botones y el resultado del ping a
`/api/health`. Se reemplaza por el login cuando arranque la Entrega 1.

---

## 4. Levantar todo (resumen)

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
│   │   ├── __init__.py      application factory, CORS, blueprints
│   │   ├── models/          modelos SQLAlchemy (pendiente)
│   │   ├── routes/          un blueprint por módulo
│   │   ├── services/        lógica de negocio y reglas críticas
│   │   └── utils/           JWT, decoradores de RBAC
│   ├── database/            schema MySQL (pendiente)
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
