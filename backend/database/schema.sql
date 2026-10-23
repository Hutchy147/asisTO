-- =====================================================================
-- AsisTO — Schema de base de datos
-- MySQL 8.0+ / utf8mb4_unicode_ci
--
-- Script idempotente: se puede correr las veces que haga falta.
-- ATENCION: arranca con DROP DATABASE. Borra todo lo que haya.
--
--   mysql -u root -p < backend/database/schema.sql
-- =====================================================================

-- =====================================================================
-- CUIDADO: ESTE ARCHIVO NOMBRA LA BASE Y EMPIEZA BORRANDOLA.
--
-- Las tres lineas de abajo dicen `asisto` y la primera es un DROP DATABASE.
-- `mysql --login-path=asisto otra_base < schema.sql` **NO** arma otra_base:
-- BORRA `asisto` y la rehace vacia. El argumento de linea de comandos no
-- protege de nada, porque estas lineas lo pisan.
--
-- POR QUE SIGUE ASI, cuando `seed.sql` y `seed_demo.sql` ya no nombran
-- ninguna base (2026-09-13): este archivo CREA la base, no escribe en una
-- que ya existe. Sacarle el nombre lo dejaria sin `CREATE DATABASE` y sin
-- contexto para los `CREATE TABLE`, y quien tendria que crearla pasa a ser
-- el invocador — hoy `tests/db/setup/build_test_db.ps1`, que vive en
-- `tests/` y no lo escribe esta terminal. Es un cambio coordinado, no una
-- linea. Queda propuesto y sin hacer.
--
-- MIENTRAS TANTO, la unica forma seria de correrlo contra otra base es la
-- que ya usa el script: reescribir estas tres lineas sobre una COPIA del
-- archivo. A mano, nunca.
-- =====================================================================
DROP DATABASE IF EXISTS asisto;
CREATE DATABASE asisto
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE asisto;

-- La conexion que carga este archivo fija el collation con el que se
-- crean los procedimientos. Sin esta linea, un cliente `mysql` que conecte
-- en utf8mb4 (el de MySQL 8 en Windows) los crea con utf8mb4_0900_ai_ci y las
-- columnas de JSON_TABLE chocan con las de las tablas (ERROR 1267).
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;


-- =====================================================================
-- 1. USUARIOS Y PERFILES
-- =====================================================================

-- Credenciales y datos de acceso. OJO: esta tabla NO es la fuente de
-- verdad de la identidad clinica del paciente (ver tabla pacientes).
CREATE TABLE usuarios (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre              VARCHAR(100) NOT NULL,
  apellido            VARCHAR(100) NOT NULL,
  email               VARCHAR(180) NOT NULL,
  contrasena_hash     VARCHAR(255) NOT NULL,
  activo              BOOLEAN      NOT NULL DEFAULT TRUE,
  rol                 ENUM('terapeuta','rrhh','familiar','paciente','admin') NOT NULL,

  -- Campos de seguridad: se usan recien en la Entrega 3 (bloqueo por
  -- intentos fallidos y recuperacion de contrasena). Se crean ahora para
  -- no migrar la tabla despues.
  intentos_fallidos   TINYINT UNSIGNED NOT NULL DEFAULT 0,
  bloqueado_hasta     DATETIME     NULL DEFAULT NULL,
  token_recuperacion  VARCHAR(255) NULL DEFAULT NULL,
  token_expira        DATETIME     NULL DEFAULT NULL,

  -- Los JWT emitidos ANTES de este momento dejan de valer: se fija al
  -- cerrar sesion y al restablecer la contrasena. Sin esto, un token robado
  -- seguia sirviendo hasta vencer aunque la persona cambiara la clave.
  -- Con microsegundos: un token emitido en el mismo segundo que el cierre
  -- de sesion tiene que quedar revocado igual.
  sesiones_validas_desde DATETIME(6) NULL DEFAULT NULL,

  fecha_creacion      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE KEY uq_usuarios_email (email),
  KEY idx_usuarios_token_recuperacion (token_recuperacion),
  KEY idx_usuarios_rol (rol)
) ENGINE=InnoDB;


CREATE TABLE terapeutas (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_usuario     INT UNSIGNED NOT NULL,
  matricula      VARCHAR(50)  NOT NULL,
  especialidad   VARCHAR(120) NULL DEFAULT NULL,
  nro_licencia   VARCHAR(50)  NULL DEFAULT NULL,

  PRIMARY KEY (id),
  UNIQUE KEY uq_terapeutas_usuario (id_usuario),
  UNIQUE KEY uq_terapeutas_matricula (matricula),
  CONSTRAINT fk_terapeutas_usuario
    FOREIGN KEY (id_usuario) REFERENCES usuarios (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


CREATE TABLE rrhh (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_usuario   INT UNSIGNED NOT NULL,
  sector       VARCHAR(120) NULL DEFAULT NULL,
  nro_legajo   VARCHAR(50)  NOT NULL,

  PRIMARY KEY (id),
  UNIQUE KEY uq_rrhh_usuario (id_usuario),
  UNIQUE KEY uq_rrhh_legajo (nro_legajo),
  CONSTRAINT fk_rrhh_usuario
    FOREIGN KEY (id_usuario) REFERENCES usuarios (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


CREATE TABLE familiares (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_usuario   INT UNSIGNED NOT NULL,
  parentesco   VARCHAR(60)  NULL DEFAULT NULL,
  telefono     VARCHAR(40)  NULL DEFAULT NULL,

  PRIMARY KEY (id),
  UNIQUE KEY uq_familiares_usuario (id_usuario),
  CONSTRAINT fk_familiares_usuario
    FOREIGN KEY (id_usuario) REFERENCES usuarios (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- PACIENTES — regla 5 del CLAUDE.md
--
-- id_usuario es NULLABLE A PROPOSITO. El login del paciente es opcional:
-- solo se le ofrece a mayores de edad con capacidad de usarlo. Un menor
-- existe como registro clinico completo, sin credenciales.
--
-- Por eso nombre, apellido y fecha_nacimiento viven ACA y no en usuarios:
-- esta tabla es la fuente de verdad de la identidad clinica, tenga login
-- o no. NO mover esos campos a usuarios.
--
-- La UNIQUE sobre id_usuario permite varios NULL (asi funciona UNIQUE en
-- MySQL), que es justo lo que se necesita: N pacientes sin login, pero un
-- usuario no puede estar vinculado a dos pacientes.
--
-- ON DELETE SET NULL: si se borra el usuario, el paciente sobrevive y
-- pierde solo el acceso. Nunca se pierde la historia clinica.
-- ---------------------------------------------------------------------
CREATE TABLE pacientes (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_usuario        INT UNSIGNED NULL DEFAULT NULL,
  nombre            VARCHAR(100) NOT NULL,
  apellido          VARCHAR(100) NOT NULL,
  fecha_nacimiento  DATE         NOT NULL,
  diagnostico       TEXT         NULL DEFAULT NULL,
  -- Nullable a proposito: un paciente particular no tiene obra social, y no
  -- siempre se conoce al dar el alta. NO es contenido clinico — es dato
  -- administrativo, asi que puede viajar en to_dict() cuando se exponga.
  obra_social       VARCHAR(120) NULL DEFAULT NULL,
  nro_historia      VARCHAR(30)  NOT NULL,
  activo            BOOLEAN      NOT NULL DEFAULT TRUE,
  fecha_alta        DATE         NOT NULL DEFAULT (CURRENT_DATE),
  fecha_baja        DATE         NULL DEFAULT NULL,
  -- COMO SE CERRO (Entrega 3, semantica del rubro). fecha_baja es la fecha
  -- del cierre en los dos casos; este campo dice de que cierre se trata:
  --   'pausa' = la baja: el tratamiento se interrumpe y se puede retomar.
  --             Lleva MOTIVO obligatorio y no toca objetivos ni asignacion.
  --   'alta'  = el cierre del tratamiento (el egreso): archiva los objetivos
  --             y cierra la asignacion. Es lo que hacia p_baja_paciente.
  -- NULL con activo = FALSE son bajas anteriores a la Entrega 3: se leen
  -- como 'alta', que es lo que hacian. Siempre NULL mientras esta activo.
  tipo_cierre       ENUM('pausa','alta') NULL DEFAULT NULL,
  motivo_baja       VARCHAR(200) NULL DEFAULT NULL,

  PRIMARY KEY (id),
  UNIQUE KEY uq_pacientes_usuario (id_usuario),
  UNIQUE KEY uq_pacientes_nro_historia (nro_historia),
  KEY idx_pacientes_activo (activo),
  KEY idx_pacientes_apellido (apellido, nombre),
  CONSTRAINT fk_pacientes_usuario
    FOREIGN KEY (id_usuario) REFERENCES usuarios (id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT chk_pacientes_cierre_inactivo
    CHECK (activo = FALSE OR (tipo_cierre IS NULL AND motivo_baja IS NULL)),
  CONSTRAINT chk_pacientes_pausa_con_motivo
    CHECK (tipo_cierre IS NULL OR tipo_cierre <> 'pausa'
           OR (motivo_baja IS NOT NULL AND CHAR_LENGTH(TRIM(motivo_baja)) > 0))
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- ASIGNACIONES — que terapeuta atiende a que paciente, y desde cuando
--
-- Es el insumo de la decision abierta de la Entrega 2: la HDU 1 pide
-- "listado de pacientes asignados" y hoy todos los terapeutas ven todos los
-- pacientes. Esta tabla es el vinculo explicito; el filtro en si todavia no
-- esta construido.
--
-- fecha_hasta NULL significa VIGENTE. Un terapeuta no puede tener dos
-- asignaciones vigentes con el mismo paciente: lo rechazan los triggers de
-- mas abajo, en las dos rutas de escritura.
--
-- LO QUE ESTA TABLA NO DECIDE, A PROPOSITO: si un paciente puede tener
-- varios terapeutas a la vez. No hay ninguna restriccion sobre eso porque
-- todavia no esta decidido, y una constraint puesta "por las dudas" es mas
-- cara de sacar que de agregar. Si se decide que no puede, el lugar es un
-- trigger nuevo, no tocar los de abajo.
--
-- id_terapeuta apunta a terapeutas(id), igual que sesiones e informes. Es
-- contra eso que se van a escribir los JOIN, y ademas la asignacion es una
-- relacion CLINICA: un usuario que no sea terapeuta no tiene por que poder
-- quedar asignado a un paciente, y la FK contra terapeutas lo impide sola.
-- (Durante la migracion del 2026-08-07 apunto un rato a usuarios(id); se
-- corrigio el mismo dia, antes de que existiera ningun dato real.)
-- ---------------------------------------------------------------------
CREATE TABLE asignaciones (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_terapeuta  INT UNSIGNED NOT NULL,
  id_paciente   INT UNSIGNED NOT NULL,
  fecha_desde   DATE         NOT NULL,
  fecha_hasta   DATE         NULL DEFAULT NULL,

  PRIMARY KEY (id),
  KEY idx_asignaciones_terapeuta (id_terapeuta, fecha_hasta),
  KEY idx_asignaciones_paciente (id_paciente, fecha_hasta),
  CONSTRAINT fk_asignaciones_terapeuta
    FOREIGN KEY (id_terapeuta) REFERENCES terapeutas (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_asignaciones_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


-- =====================================================================
-- 2. NUCLEO CLINICO
-- =====================================================================

-- ---------------------------------------------------------------------
-- OBJETIVOS TERAPEUTICOS — reglas 1 y 4 del CLAUDE.md
--
-- El limite de 4 aplica a objetivos ACTIVOS, no al total historico. Un
-- objetivo archivado no consume cupo y se puede recrear con la misma
-- descripcion (escenario clinico normal: se retoma un objetivo viejo).
--
-- descripcion_activa es una columna generada STORED que replica la
-- descripcion SOLO si el objetivo esta activo, y NULL si esta archivado.
-- La UNIQUE va sobre (id_paciente, descripcion_activa).
--
-- Por que asi: en MySQL los NULL no participan de una UNIQUE, entonces
-- las filas archivadas quedan exentas automaticamente. Si la UNIQUE
-- fuera sobre descripcion a secas, archivar y recrear con el mismo texto
-- fallaria.
--
-- El limite de 4 NO se puede expresar con una constraint declarativa:
-- se aplica por trigger, mas abajo.
--
-- TAMANO DE descripcion: 700, y el numero no es arbitrario.
--
-- Se valido la Entrega 1 con terapeutas ocupacionales y el formato real de
-- un objetivo es "Que [paciente] [verbo] [conducta observable], [nivel de
-- apoyo], [criterio de medicion], [contexto], [plazo]". Uno de los ejemplos
-- que dieron mide 398 caracteres. El schema estaba en 500, que entraba por
-- poco, y el formulario cortaba en 180: no se podia cargar un objetivo real.
--
-- El techo duro es 767 y esta MEDIDO, no deducido: la UNIQUE de abajo es
-- (id_paciente, descripcion_activa), o sea INT UNSIGNED + VARCHAR(N) en
-- utf8mb4, y 767*4 + 4 = 3072 bytes, que es exactamente el limite de clave
-- de InnoDB. Con VARCHAR(768) el CREATE TABLE falla con ERROR 1071
-- ("Specified key was too long"). 700 deja margen para que un cambio futuro
-- en ese indice no reviente el ALTER.
--
-- Y por eso NO es TEXT: una columna TEXT no se puede indexar sin prefijo, y
-- una UNIQUE por prefijo cambiaria el significado de la regla — dos
-- objetivos que compartan el arranque y difieran solo en el plazo o en el
-- criterio (la forma exacta del formato real) chocarian entre si.
-- ---------------------------------------------------------------------
CREATE TABLE objetivos_terapeuticos (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_paciente         INT UNSIGNED NOT NULL,
  descripcion         VARCHAR(700) NOT NULL,
  activo              BOOLEAN      NOT NULL DEFAULT TRUE,
  fecha_creacion      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_archivado     DATETIME     NULL DEFAULT NULL,

  -- Se redefine junto con descripcion, no solo se ensancha: es una columna
  -- generada y su tipo tiene que seguir al de la columna de origen.
  descripcion_activa  VARCHAR(700)
    GENERATED ALWAYS AS (IF(activo, descripcion, NULL)) STORED,

  PRIMARY KEY (id),
  UNIQUE KEY uq_objetivos_paciente_descripcion_activa
    (id_paciente, descripcion_activa),
  KEY idx_objetivos_paciente_activo (id_paciente, activo),
  CONSTRAINT fk_objetivos_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- SESIONES — regla 6 del CLAUDE.md
--
-- La UNIQUE evita duplicar la misma sesion del paciente. El solapamiento
-- del TERAPEUTA no se puede expresar declarativamente (es un rango, no
-- una igualdad): se valida en p_registrar_sesion.
--
-- notas es contenido clinico. RRHH NO puede verlo: ningun procedimiento
-- ni vista destinada a RRHH devuelve esta columna.
-- ---------------------------------------------------------------------
CREATE TABLE sesiones (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_terapeuta    INT UNSIGNED NOT NULL,
  id_paciente     INT UNSIGNED NOT NULL,
  fecha           DATE         NOT NULL,
  hora_inicio     TIME         NOT NULL,
  hora_fin        TIME         NULL DEFAULT NULL,
  estado          ENUM('completa','incompleta','ausencia')
                    NOT NULL DEFAULT 'incompleta',
  -- QUIEN FALTO, solo cuando estado='ausencia'. Es un eje distinto del
  -- estado: `estado` describe QUE paso con la sesion (se hizo, se corto,
  -- no hubo sesion); esta columna describe QUIEN de los dos no estuvo.
  -- Va en columna propia y no ampliando el ENUM de estado porque son dos
  -- preguntas distintas, no dos valores del mismo eje.
  --
  -- Tiene que ser NULL siempre que estado no sea 'ausencia', y no-NULL
  -- siempre que SI lo sea: los dos triggers de mas abajo rechazan las dos
  -- combinaciones inconsistentes. La validacion esta guardada para correr
  -- SOLO cuando `estado` o esta columna cambian (ver trg_sesiones_solape_
  -- update): las filas de ausencia sembradas antes de que esta columna
  -- existiera quedan con ausencia_de NULL, sin dato que nadie puede
  -- reponer, y no se fuerza su reescritura por editar otra cosa.
  ausencia_de     ENUM('paciente','terapeuta') NULL DEFAULT NULL,
  notas           TEXT         NULL DEFAULT NULL,
  -- DUPLA TERAPEUTICA — preparacion de la Entrega 4, hoy sin uso.
  --
  -- Una dupla es UNA terapeuta atendiendo a DOS NINIOS en el mismo horario,
  -- cada uno con sus propios objetivos y su propia evolucion. NO son dos
  -- terapeutas sobre un paciente: eso es trabajo INTERDISCIPLINARIO y queda
  -- fuera del alcance de AsisTO por decision de producto.
  --
  -- Dos sesiones que comparten id_dupla SON una dupla. No hay tabla de
  -- parejas de pacientes a proposito: la dupla se arma al agendar, buscando
  -- edades o diagnosticos parecidos, y no es un vinculo permanente entre dos
  -- ninios. Ademas asi el trigger de solape compara un campo de la fila que
  -- YA lee, sin sumar una tabla al orden de locks.
  --
  -- QUE FALTA (Entrega 4): hoy la columna no tiene trigger ni validacion, y
  -- NADA la escribe. La regla 6 sigue rechazando dos sesiones
  -- solapadas del mismo terapeuta aunque compartan id_dupla — que es
  -- justamente el caso que la Entrega 4 tiene que abrir, en los dos triggers
  -- de solape Y en el conteo propio de p_registrar_sesion. Sin sentido
  -- todavia: mientras nadie la escriba, id_dupla es NULL en todas las filas.
  --
  -- Lo que NO cambia por este motivo: la AUTORIA de la evolucion. Hay una
  -- sola terapeuta y carga las dos evoluciones a su nombre.
  id_dupla        INT UNSIGNED NULL DEFAULT NULL,
  fecha_registro  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE KEY uq_sesiones_paciente_fecha_hora (id_paciente, fecha, hora_inicio),
  KEY idx_sesiones_terapeuta_fecha (id_terapeuta, fecha),
  KEY idx_sesiones_paciente_fecha (id_paciente, fecha),
  -- COMUN, no UNIQUE: una dupla son DOS filas con el mismo valor, asi que
  -- una UNIQUE haria imposible justamente el caso que la columna modela.
  -- Lo usa la Entrega 4 para encontrar la sesion hermana con
  -- WHERE id_dupla = ?. Se crea ahora porque esta es la ultima apertura
  -- planificada del schema, aunque todavia nada lo consulte.
  KEY idx_sesiones_dupla (id_dupla),
  CONSTRAINT fk_sesiones_terapeuta
    FOREIGN KEY (id_terapeuta) REFERENCES terapeutas (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_sesiones_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- EVOLUCIONES — reglas 2, 3 y 4 del CLAUDE.md
--
-- Normalmente se trabaja un objetivo por sesion, pero la estructura no lo
-- impide: la UNIQUE es (id_sesion, id_objetivo), asi que una sesion puede
-- evaluar varios objetivos distintos, pero nunca el mismo dos veces.
--
-- Las tres reglas de negocio se validan en un unico trigger, mas abajo.
-- ---------------------------------------------------------------------
CREATE TABLE evoluciones (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_sesion       INT UNSIGNED NOT NULL,
  id_objetivo     INT UNSIGNED NOT NULL,
  valor           TINYINT UNSIGNED NOT NULL,
  observaciones   TEXT         NULL DEFAULT NULL,
  fecha_registro  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE KEY uq_evoluciones_sesion_objetivo (id_sesion, id_objetivo),
  KEY idx_evoluciones_objetivo (id_objetivo),
  CONSTRAINT chk_evoluciones_valor CHECK (valor BETWEEN 1 AND 5),
  CONSTRAINT fk_evoluciones_sesion
    FOREIGN KEY (id_sesion) REFERENCES sesiones (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_evoluciones_objetivo
    FOREIGN KEY (id_objetivo) REFERENCES objetivos_terapeuticos (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


-- =====================================================================
-- 3. RRHH
-- =====================================================================

-- Observaciones TECNICAS de RRHH sobre una sesion (llego tarde, faltaba
-- material, etc). No es contenido clinico y no lo ve el terapeuta como
-- parte de la evolucion.
CREATE TABLE observaciones_rrhh (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_sesion       INT UNSIGNED NOT NULL,
  id_rrhh         INT UNSIGNED NOT NULL,
  texto           TEXT         NOT NULL,
  fecha_registro  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  KEY idx_observaciones_rrhh_sesion (id_sesion),
  CONSTRAINT fk_observaciones_rrhh_sesion
    FOREIGN KEY (id_sesion) REFERENCES sesiones (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_observaciones_rrhh_rrhh
    FOREIGN KEY (id_rrhh) REFERENCES rrhh (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


-- =====================================================================
-- 4. PORTAL FAMILIAR
-- =====================================================================

CREATE TABLE familiares_pacientes (
  id_familiar    INT UNSIGNED NOT NULL,
  id_paciente    INT UNSIGNED NOT NULL,
  fecha_vinculo  DATE         NOT NULL DEFAULT (CURRENT_DATE),

  PRIMARY KEY (id_familiar, id_paciente),
  KEY idx_familiares_pacientes_paciente (id_paciente),
  CONSTRAINT fk_familiares_pacientes_familiar
    FOREIGN KEY (id_familiar) REFERENCES familiares (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_familiares_pacientes_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;


CREATE TABLE notificaciones (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_familiar  INT UNSIGNED NOT NULL,
  id_paciente  INT UNSIGNED NOT NULL,
  tipo         ENUM('nueva_sesion','informe_generado','cambio_objetivo') NOT NULL,
  mensaje      VARCHAR(500) NOT NULL,
  leida        BOOLEAN      NOT NULL DEFAULT FALSE,
  fecha        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  KEY idx_notificaciones_familiar_leida (id_familiar, leida),
  CONSTRAINT fk_notificaciones_familiar
    FOREIGN KEY (id_familiar) REFERENCES familiares (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_notificaciones_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;


CREATE TABLE preferencias_notificacion (
  id_familiar  INT UNSIGNED NOT NULL,
  tipo         ENUM('nueva_sesion','informe_generado','cambio_objetivo') NOT NULL,
  habilitada   BOOLEAN      NOT NULL DEFAULT TRUE,

  PRIMARY KEY (id_familiar, tipo),
  CONSTRAINT fk_preferencias_notificacion_familiar
    FOREIGN KEY (id_familiar) REFERENCES familiares (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;


-- =====================================================================
-- 5. ETIQUETAS
-- =====================================================================

CREATE TABLE etiquetas (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre     VARCHAR(80)  NOT NULL,
  color_hex  CHAR(7)      NOT NULL,

  PRIMARY KEY (id),
  UNIQUE KEY uq_etiquetas_nombre (nombre)
) ENGINE=InnoDB;


CREATE TABLE sesiones_etiquetas (
  id_sesion    INT UNSIGNED NOT NULL,
  id_etiqueta  INT UNSIGNED NOT NULL,

  PRIMARY KEY (id_sesion, id_etiqueta),
  KEY idx_sesiones_etiquetas_etiqueta (id_etiqueta),
  CONSTRAINT fk_sesiones_etiquetas_sesion
    FOREIGN KEY (id_sesion) REFERENCES sesiones (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_sesiones_etiquetas_etiqueta
    FOREIGN KEY (id_etiqueta) REFERENCES etiquetas (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- RENGLONES DE LA SESION — notas de campo (Entrega 3)
--
-- La unidad de escritura clinica de la terapeuta es el RENGLON: fragmentos
-- de tres a ocho palabras, no parrafos (relevamiento con la TO, cuaderno en
-- fotos). Cada renglon es una fila propia, y eso no es estilo sino modelo:
-- sin filas no se puede arrastrar lo pendiente ni destacar un fragmento.
--
-- `momento` separa los dos tiempos de UN mismo objeto, la sesion:
--   'plan'     lo que se piensa hacer. Se puede escribir antes, y despues.
--   'registro' lo que paso. Solo cuando la sesion ya ocurrio y no fue ausencia.
-- `cierre` solo existe para el plan: NULL = pendiente (se ARRASTRA a la
-- proxima sesion del mismo paciente), 'hecho' o 'descartado' = resuelto.
-- `destacado` es la marca del resaltador del cuaderno: un booleano, no
-- colores libres (decision de producto).
--
-- Se escribe SOLO por p_agregar_renglon / p_editar_renglon / p_cerrar_renglon
-- / p_borrar_renglon. Contenido clinico: RRHH no lo ve.
-- ---------------------------------------------------------------------
CREATE TABLE sesion_renglones (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_sesion       INT UNSIGNED NOT NULL,
  momento         ENUM('plan','registro') NOT NULL,
  texto           VARCHAR(160) NOT NULL,
  destacado       BOOLEAN      NOT NULL DEFAULT FALSE,
  cierre          ENUM('hecho','descartado') NULL DEFAULT NULL,
  orden           SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  fecha_creacion  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  KEY idx_renglones_sesion (id_sesion, momento, orden),
  KEY idx_renglones_pendientes (momento, cierre),
  CONSTRAINT fk_renglones_sesion
    FOREIGN KEY (id_sesion) REFERENCES sesiones (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT chk_renglones_cierre_solo_plan
    CHECK (cierre IS NULL OR momento = 'plan'),
  CONSTRAINT chk_renglones_texto
    CHECK (CHAR_LENGTH(TRIM(texto)) > 0)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- SESION_OBJETIVOS — objetivos que se planea trabajar en una sesion (Entrega 3)
--
-- El PLAN de la sesion se arma eligiendo, de los objetivos del paciente, el o
-- los que se van a trabajar (la TO no quiere reescribir un objetivo que ya
-- existe). Es una relacion sesion-objetivo y no un renglon: la descripcion de
-- un objetivo llega a 700 caracteres y el renglon a 160, y copiarla duplicaria
-- el dato. Los renglones de plan siguen para lo que no es un objetivo.
--
-- Se escribe SOLO por p_marcar_objetivo_sesion. Si el objetivo se archiva
-- despues, la fila queda: es historia de lo que se planeo ese dia.
-- ---------------------------------------------------------------------
CREATE TABLE sesion_objetivos (
  id_sesion       INT UNSIGNED NOT NULL,
  id_objetivo     INT UNSIGNED NOT NULL,
  fecha_creacion  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id_sesion, id_objetivo),
  KEY idx_sesion_objetivos_objetivo (id_objetivo),
  CONSTRAINT fk_sesion_objetivos_sesion
    FOREIGN KEY (id_sesion) REFERENCES sesiones (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_sesion_objetivos_objetivo
    FOREIGN KEY (id_objetivo) REFERENCES objetivos_terapeuticos (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- AGENDA_RECURRENTE — agenda semanal recurrente (Entrega 3)
--
-- La plantilla de la semana de una terapeuta: "los lunes a las 9 viene
-- este paciente". NO es una sesion: no cuenta como asistencia ni aparece en
-- los listados de sesiones. Sirve para GENERAR sesiones futuras (de lunes a
-- viernes) con el servicio, que las agenda una por una a traves de
-- p_registrar_sesion, asi que superposicion, paciente de baja y asignacion
-- siguen aplicandolas el procedimiento y los triggers.
--
-- dia_semana: 1 = lunes ... 5 = viernes. Sabado y domingo no se agendan.
-- Borrar una plantilla la desactiva (activo = FALSE): las sesiones ya
-- generadas no se tocan.
-- ---------------------------------------------------------------------
CREATE TABLE agenda_recurrente (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_terapeuta    INT UNSIGNED NOT NULL,
  id_paciente     INT UNSIGNED NOT NULL,
  dia_semana      TINYINT UNSIGNED NOT NULL,
  hora_inicio     TIME         NOT NULL,
  hora_fin        TIME         NOT NULL,
  activo          BOOLEAN      NOT NULL DEFAULT TRUE,
  fecha_creacion  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- DUPLA (Entrega 5): dos turnos activos con el mismo id_dupla son UN turno
  -- en dupla (una terapeuta, dos ninios, mismo dia y horario). Mismo criterio
  -- que sesiones.id_dupla: sin tabla de parejas; el valor es el id del primer
  -- turno de la dupla. Un turno cuya hermana se quito queda con id_dupla pero
  -- solo, y se lee como individual. Las sesiones que genera heredan la dupla.
  id_dupla        INT UNSIGNED NULL DEFAULT NULL,

  PRIMARY KEY (id),
  KEY idx_agenda_rec_terapeuta (id_terapeuta, activo, dia_semana),
  KEY idx_agenda_rec_dupla (id_dupla),
  KEY idx_agenda_rec_paciente (id_paciente),
  CONSTRAINT fk_agenda_rec_terapeuta
    FOREIGN KEY (id_terapeuta) REFERENCES terapeutas (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_agenda_rec_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_agenda_rec_dia CHECK (dia_semana BETWEEN 1 AND 5),
  CONSTRAINT chk_agenda_rec_horas CHECK (hora_fin > hora_inicio)
) ENGINE=InnoDB;


-- =====================================================================
-- 5 bis. FLUJO DE INGRESO (Entrega 4)
--
-- Paciente nuevo: revision de la carpeta -> evaluacion inicial -> entrevista
-- a la familia -> PTI (plan terapeutico integral). Al cerrar las cuatro
-- etapas y con los objetivos fijados (minimo 3 activos), el ingreso se
-- COMPLETA y queda la historia clinica del centro.
--
-- El formulario de cada etapa es CONFIGURABLE (ingreso_campos): el centro
-- todavia no definio su formulario estandar, asi que se parte de uno
-- generico de terapia ocupacional que el administrador puede ajustar sin
-- tocar codigo. Los campos no se borran, se desactivan: las respuestas ya
-- cargadas siguen apuntando a ellos.
--
-- Al completar se guarda una COPIA (ingresos.historia_clinica, JSON) con las
-- etiquetas y respuestas de ese momento: cambiar el formulario despues no
-- reescribe historias ya hechas.
--
-- Lock: pacientes primero (igual que el resto), despues terapeutas,
-- asignaciones, ingresos y sus etapas, objetivos y respuestas al final.
-- =====================================================================

CREATE TABLE ingresos (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_paciente       INT UNSIGNED NOT NULL,
  id_terapeuta      INT UNSIGNED NOT NULL,
  estado            ENUM('en_curso','completado') NOT NULL DEFAULT 'en_curso',
  fecha_inicio      DATE         NOT NULL DEFAULT (CURRENT_DATE),
  fecha_completado  DATETIME     NULL DEFAULT NULL,
  historia_clinica  JSON         NULL DEFAULT NULL,

  PRIMARY KEY (id),
  UNIQUE KEY uq_ingresos_paciente (id_paciente),
  CONSTRAINT fk_ingresos_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_ingresos_terapeuta
    FOREIGN KEY (id_terapeuta) REFERENCES terapeutas (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


CREATE TABLE ingreso_campos (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  etapa        ENUM('carpeta','evaluacion','entrevista','pti') NOT NULL,
  clave        VARCHAR(40)  NOT NULL,
  etiqueta     VARCHAR(150) NOT NULL,
  ayuda        VARCHAR(300) NULL DEFAULT NULL,
  tipo         ENUM('texto','texto_largo','fecha','opcion') NOT NULL DEFAULT 'texto_largo',
  -- Solo para tipo 'opcion': alternativas separadas por barra vertical
  opciones     VARCHAR(500) NULL DEFAULT NULL,
  obligatorio  BOOLEAN      NOT NULL DEFAULT FALSE,
  orden        SMALLINT UNSIGNED NOT NULL DEFAULT 100,
  activo       BOOLEAN      NOT NULL DEFAULT TRUE,

  PRIMARY KEY (id),
  UNIQUE KEY uq_ingreso_campos_clave (etapa, clave)
) ENGINE=InnoDB;


CREATE TABLE ingreso_etapas (
  id_ingreso   INT UNSIGNED NOT NULL,
  etapa        ENUM('carpeta','evaluacion','entrevista','pti') NOT NULL,
  estado       ENUM('pendiente','en_curso','cerrada') NOT NULL DEFAULT 'pendiente',
  fecha_cierre DATETIME     NULL DEFAULT NULL,

  PRIMARY KEY (id_ingreso, etapa),
  CONSTRAINT fk_ingreso_etapas_ingreso
    FOREIGN KEY (id_ingreso) REFERENCES ingresos (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;


CREATE TABLE ingreso_respuestas (
  id_ingreso          INT UNSIGNED NOT NULL,
  id_campo            INT UNSIGNED NOT NULL,
  valor               TEXT         NOT NULL,
  fecha_modificacion  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id_ingreso, id_campo),
  CONSTRAINT fk_ingreso_respuestas_ingreso
    FOREIGN KEY (id_ingreso) REFERENCES ingresos (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_ingreso_respuestas_campo
    FOREIGN KEY (id_campo) REFERENCES ingreso_campos (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


-- Formulario generico de terapia ocupacional (punto de partida; el centro lo
-- ajusta desde la pantalla de administracion). Los textos con tilde van como
-- bytes UTF-8 en hexadecimal: este archivo se carga en Windows sin depender
-- de la codificacion de la consola.
INSERT INTO ingreso_campos (etapa, clave, etiqueta, ayuda, tipo, opciones, obligatorio, orden) VALUES
  ('carpeta', 'fuente', CONVERT(0x4F726967656E206465206C612063617270657461 USING utf8mb4), CONVERT(0x496E73746974756369C3B36E2C2070726F666573696F6E616C206F2066616D696C696120717565206C612061706F7274C3B32E USING utf8mb4), 'texto', NULL, 0, 10),
  ('carpeta', 'antecedentes', CONVERT(0x416E7465636564656E7465732072656C6576616E746573 USING utf8mb4), CONVERT(0x456D626172617A6F2C20706172746F2C206465736172726F6C6C6F207920656E6665726D65646164657320707265766961732E USING utf8mb4), 'texto_largo', NULL, 1, 20),
  ('carpeta', 'diagnosticos_previos', CONVERT(0x446961676EC3B3737469636F732079206573747564696F732070726576696F73 USING utf8mb4), CONVERT(0x446961676EC3B3737469636F732C20696E666F726D65732079206573747564696F7320717565206669677572616E20656E206C6120636172706574612E USING utf8mb4), 'texto_largo', NULL, 1, 30),
  ('carpeta', 'tratamientos_previos', CONVERT(0x54726174616D69656E746F73207920746572617069617320616E746572696F726573 USING utf8mb4), CONVERT(0x5175C3A920746572617069617320726563696269C3B32C2064C3B36E6465207920706F72206375C3A16E746F207469656D706F2E USING utf8mb4), 'texto_largo', NULL, 0, 40),
  ('carpeta', 'medicacion', CONVERT(0x4D65646963616369C3B36E2061637475616C USING utf8mb4), CONVERT(0x496E6469636172207369206E6F20746F6D61206D65646963616369C3B36E2E USING utf8mb4), 'texto', NULL, 0, 50),
  ('evaluacion', 'fecha_evaluacion', CONVERT(0x4665636861206465206C61206576616C75616369C3B36E USING utf8mb4), NULL, 'fecha', NULL, 1, 10),
  ('evaluacion', 'motivo_consulta', CONVERT(0x4D6F7469766F20646520636F6E73756C7461 USING utf8mb4), CONVERT(0x506F72207175C3A9206C6C65676120616C2063656E74726F2C20736567C3BA6E206C6F206F627365727661646F2E USING utf8mb4), 'texto_largo', NULL, 1, 20),
  ('evaluacion', 'vida_diaria', CONVERT(0x446573656D7065C3B16F20656E206163746976696461646573206465206C61207669646120646961726961 USING utf8mb4), CONVERT(0x416C696D656E74616369C3B36E2C207665737469646F2C2068696769656E652079206A7565676F2E USING utf8mb4), 'texto_largo', NULL, 1, 30),
  ('evaluacion', 'motricidad', CONVERT(0x4D6F74726963696461642066696E61207920677275657361 USING utf8mb4), NULL, 'texto_largo', NULL, 0, 40),
  ('evaluacion', 'procesamiento_sensorial', CONVERT(0x50726F636573616D69656E746F2073656E736F7269616C USING utf8mb4), NULL, 'texto_largo', NULL, 0, 50),
  ('evaluacion', 'atencion_conducta', CONVERT(0x4174656E6369C3B36E2C20636F6E6475637461207920726567756C616369C3B36E USING utf8mb4), NULL, 'texto_largo', NULL, 0, 60),
  ('evaluacion', 'comunicacion_juego', CONVERT(0x436F6D756E6963616369C3B36E2079206A7565676F USING utf8mb4), NULL, 'texto_largo', NULL, 0, 70),
  ('evaluacion', 'escolaridad', CONVERT(0x4573636F6C617269646164 USING utf8mb4), CONVERT(0x4E6976656C2C2061646170746163696F6E657320792072656C616369C3B36E20636F6E2070617265732E USING utf8mb4), 'texto_largo', NULL, 0, 80),
  ('evaluacion', 'fortalezas', CONVERT(0x466F7274616C657A6173206520696E74657265736573 USING utf8mb4), NULL, 'texto_largo', NULL, 0, 90),
  ('evaluacion', 'impresion', CONVERT(0x496D7072657369C3B36E2070726F666573696F6E616C USING utf8mb4), CONVERT(0x53C3AD6E7465736973206465206C61206576616C75616369C3B36E20696E696369616C2E USING utf8mb4), 'texto_largo', NULL, 1, 100),
  ('entrevista', 'fecha_entrevista', CONVERT(0x4665636861206465206C6120656E7472657669737461 USING utf8mb4), NULL, 'fecha', NULL, 1, 10),
  ('entrevista', 'asistentes', CONVERT(0x517569C3A96E657320706172746963697061726F6E USING utf8mb4), CONVERT(0x46616D696C69617265732070726573656E746573207920737520706172656E746573636F2E USING utf8mb4), 'texto', NULL, 1, 20),
  ('entrevista', 'preocupaciones', CONVERT(0x5175C3A9207072656F637570612061206C612066616D696C6961 USING utf8mb4), CONVERT(0x436F6E207375732070616C61627261732C20656E206C6F20706F7369626C652E USING utf8mb4), 'texto_largo', NULL, 1, 30),
  ('entrevista', 'rutina', CONVERT(0x527574696E6120646961726961 USING utf8mb4), NULL, 'texto_largo', NULL, 0, 40),
  ('entrevista', 'desarrollo', CONVERT(0x416E7465636564656E7465732064656C206465736172726F6C6C6F20736567C3BA6E206C612066616D696C6961 USING utf8mb4), NULL, 'texto_largo', NULL, 0, 50),
  ('entrevista', 'expectativas', CONVERT(0x457870656374617469766173206465206C612066616D696C6961 USING utf8mb4), CONVERT(0x5175C3A9206573706572616E206C6F6772617220636F6E20656C2074726174616D69656E746F2E USING utf8mb4), 'texto_largo', NULL, 1, 60),
  ('entrevista', 'otras_observaciones', CONVERT(0x4F74726173206F62736572766163696F6E6573 USING utf8mb4), NULL, 'texto_largo', NULL, 0, 70),
  ('pti', 'frecuencia', CONVERT(0x4672656375656E636961206465206C617320736573696F6E6573 USING utf8mb4), NULL, 'opcion', '1 vez por semana|2 veces por semana|3 veces por semana|Otra', 1, 10),
  ('pti', 'areas', CONVERT(0xC3817265617320612074726162616A6172 USING utf8mb4), CONVERT(0x4C6F73206F626A657469766F7320636F6E637265746F732073652063617267616E20656E206C61207065737461C3B161204F626A657469766F732E USING utf8mb4), 'texto_largo', NULL, 1, 20),
  ('pti', 'estrategias', CONVERT(0x4573747261746567696173207920656E666F717565 USING utf8mb4), NULL, 'texto_largo', NULL, 1, 30),
  ('pti', 'coordinacion', CONVERT(0x436F6F7264696E616369C3B36E20636F6E206C612065736375656C612079206F74726F732070726F666573696F6E616C6573 USING utf8mb4), NULL, 'texto_largo', NULL, 0, 40),
  ('pti', 'criterios_revision', CONVERT(0x437269746572696F7320646520726576697369C3B36E207920646520616C7461 USING utf8mb4), NULL, 'texto_largo', NULL, 0, 50),
  ('pti', 'fecha_revision', CONVERT(0x4665636861206465206C61207072696D65726120726576697369C3B36E USING utf8mb4), CONVERT(0x4C6F73206F626A657469766F73207365206576616CC3BA616E20636164612073656973206D657365732E USING utf8mb4), 'fecha', NULL, 0, 60);


-- =====================================================================
-- 6. INFORMES, PLANTILLAS Y AUDITORIA (Entrega 4)
-- =====================================================================

-- Informes (Entrega 6, HDU 5 y 8). Tres tipos, los del rubro: mensual,
-- semestral y PTI (plan terapeutico integral de ingreso). NO existe el
-- trimestral: fue un error de escritura del documento.
--
-- contenido_original guarda el texto tal como lo genero el generador (plantilla
-- con los datos del periodo, o IA si el centro la configuro); contenido guarda
-- la version editada por la terapeuta. Se conservan los dos para poder auditar
-- que cambio una persona sobre la salida del generador. Ningun informe se
-- publica sin revision humana.
--
-- periodo es la clave legible del informe: 'AAAA-MM' (mensual), 'AAAA-S1' o
-- 'AAAA-S2' (semestral) y 'pti'. Un periodo puede tener varias VERSIONES: un
-- informe publicado no se edita, se corrige armando una version nueva; al
-- publicarla la anterior pasa a 'reemplazado'. Solo los 'final' los ve el
-- familiar. Los valores por defecto de las columnas nuevas existen para que
-- una escritura minima (id_paciente, id_terapeuta, periodo) siga llegando a
-- la comprobacion de la FK, como la usa tests/db.
CREATE TABLE informes (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_paciente         INT UNSIGNED NOT NULL,
  id_terapeuta        INT UNSIGNED NOT NULL,
  tipo                ENUM('mensual','semestral','pti') NOT NULL DEFAULT 'mensual',
  periodo             VARCHAR(20)  NOT NULL,
  fecha_desde         DATE         NOT NULL DEFAULT (CURRENT_DATE),
  fecha_hasta         DATE         NOT NULL DEFAULT (CURRENT_DATE),
  version             SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  contenido           LONGTEXT     NULL DEFAULT NULL,
  contenido_original  LONGTEXT     NULL DEFAULT NULL,
  generado_con        ENUM('plantilla','ia') NOT NULL DEFAULT 'plantilla',
  proveedor           VARCHAR(60)  NULL DEFAULT NULL,
  estado              ENUM('borrador','final','reemplazado') NOT NULL DEFAULT 'borrador',
  fecha_generacion    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_edicion       DATETIME     NULL DEFAULT NULL,
  fecha_publicacion   DATETIME     NULL DEFAULT NULL,

  PRIMARY KEY (id),
  UNIQUE KEY uq_informes_version (id_paciente, tipo, periodo, version),
  KEY idx_informes_paciente_periodo (id_paciente, periodo),
  KEY idx_informes_estado (id_paciente, estado),
  CONSTRAINT fk_informes_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_informes_terapeuta
    FOREIGN KEY (id_terapeuta) REFERENCES terapeutas (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_informes_periodo CHECK (fecha_desde <= fecha_hasta),
  CONSTRAINT chk_informes_publicado CHECK (estado = 'borrador' OR fecha_publicacion IS NOT NULL)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- duplas_terapeuticas: ELIMINADA (2026-08-07)
--
-- Tenia dos FK a terapeutas y una a pacientes: modelaba DOS PROFESIONALES
-- SOBRE UN PACIENTE con el nombre del caso dupla. Eso es trabajo
-- INTERDISCIPLINARIO, que queda fuera del alcance de AsisTO por decision de
-- producto. La dupla real —UNA terapeuta, DOS ninios— se modela ahora con
-- sesiones.id_dupla; ver el comentario de esa columna.
--
-- No se reemplaza por nada aca: no hay tabla de duplas. Si aparece la
-- tentacion de volver a crear una tabla con dos FK a terapeutas, releer
-- esto primero.
-- ---------------------------------------------------------------------


-- descripcion acompania a objetivos_terapeuticos.descripcion: es la misma
-- clase de texto y una plantilla que no pueda contener un objetivo real no
-- sirve para nada. Si una de las dos cambia de tamano, cambian las dos.
CREATE TABLE plantillas_objetivos (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  area         VARCHAR(120) NOT NULL,
  descripcion  VARCHAR(700) NOT NULL,

  PRIMARY KEY (id),
  KEY idx_plantillas_area (area)
) ENGINE=InnoDB;


-- id_usuario es NULLABLE: un intento de login contra un email que no
-- existe igual se audita, y en ese caso no hay usuario al que apuntar.
-- ON DELETE SET NULL para no perder el rastro si se borra el usuario.
CREATE TABLE auditoria_accesos (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_usuario  INT UNSIGNED NULL DEFAULT NULL,
  email       VARCHAR(180) NOT NULL,
  -- recuperacion: se pidio un enlace; restablecida: se cambio la contrasena
  -- con el enlace; inactiva: la clave era correcta pero la cuenta esta
  -- deshabilitada (para el usuario es el mismo rechazo que un fallo).
  resultado   ENUM('exitoso','fallido','bloqueado','recuperacion','restablecida','inactiva') NOT NULL,
  ip          VARCHAR(45)  NULL DEFAULT NULL,
  fecha       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  KEY idx_auditoria_email_fecha (email, fecha),
  KEY idx_auditoria_usuario (id_usuario),
  CONSTRAINT fk_auditoria_usuario
    FOREIGN KEY (id_usuario) REFERENCES usuarios (id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;


-- =====================================================================
-- 7. TRIGGERS
-- =====================================================================

DELIMITER $$

-- =====================================================================
-- NOTA DE CONCURRENCIA — leer antes de tocar cualquier trigger de abajo
--
-- Todo trigger que valide un CONTEO o un RANGO usa dos locks, y los dos
-- hacen falta. Sacar cualquiera de los dos reabre una condicion de
-- carrera real, confirmada con dos conexiones simultaneas:
--
--   1. SELECT ... FROM <tabla_padre> WHERE id = ... FOR UPDATE
--      Serializa a los que escriben sobre el MISMO paciente o el MISMO
--      terapeuta. No bloquea la tabla entera ni a los demas pacientes.
--
--   2. El conteo sobre la propia tabla lleva FOR SHARE.
--      Sin esto el lock de arriba NO alcanza: en REPEATABLE READ (default
--      de MySQL) un SELECT comun lee del snapshot que la transaccion fijo
--      en su PRIMERA lectura, asi que el trigger no ve la fila que la otra
--      transaccion acaba de confirmar, aunque haya esperado su lock.
--      FOR SHARE es lectura con lock, y toda lectura con lock lee la
--      version actual confirmada.
--
--      Tiene que ser FOR SHARE y no FOR UPDATE: MySQL rechaza FOR UPDATE
--      sobre la tabla del propio trigger con ERROR 1442 ("Can't update
--      table ... already used by statement which invoked this trigger").
--      FOR SHARE si esta permitido y alcanza, porque el lock de la fila
--      padre ya garantiza que solo una transaccion este en la seccion
--      critica a la vez.
--
-- Hay dos formas de tomar el lock, y cual corresponde depende de si la
-- tabla que se lee es la del propio trigger:
--
--   * Se lee OTRA tabla  -> FOR SHARE (o FOR UPDATE) directo sobre la fila.
--     Es el caso de los triggers de evoluciones, que validan contra
--     sesiones y objetivos_terapeuticos.
--   * Se lee la PROPIA tabla del trigger -> FOR UPDATE esta prohibido
--     (ERROR 1442). Ahi va lock de fila padre + FOR SHARE en el conteo.
--     Es el caso de los triggers de objetivos_terapeuticos y sesiones.
--
-- ORDEN DE ADQUISICION DE LOCKS (el canonico esta en CLAUDE.md):
--
--      pacientes -> terapeutas -> asignaciones -> sesiones
--                -> objetivos_terapeuticos -> evoluciones
--
-- El criterio que fija el orden: una tabla se toma DESPUES de todas las que
-- referencia. Sirve para ubicar cualquier tabla nueva sin tener que
-- reproducir un deadlock primero. `asignaciones` cae entre `terapeutas` y
-- `sesiones` porque apunta a pacientes y a terapeutas, y nada la apunta a
-- ella.
--
-- Todo lo de este schema lo respeta:
--      pacientes   -> objetivos_terapeuticos   (triggers de objetivos)
--      pacientes   -> asignaciones             (triggers de asignaciones)
--      terapeutas  -> asignaciones             (trigger de sesiones, regla 8)
--      terapeutas  -> sesiones                 (triggers de sesiones)
--      sesiones    -> objetivos_terapeuticos   (triggers de evoluciones)
--      pacientes   -> asignaciones
--                  -> objetivos_terapeuticos   (p_baja_paciente)
--
-- Invertirlo introduce deadlocks. No es teorico: una transaccion que toma
-- objetivos_terapeuticos y despues sesiones, contra un INSERT de evolucion
-- concurrente, termina en ERROR 1213. Esta reproducido.
--
-- DOS EXCEPCIONES FORZADAS, documentadas junto al trigger que las tiene, no
-- aca: trg_sesiones_solape_update toma sesiones antes que pacientes (ver su
-- NOTA PARA LA ENTREGA 4), y trg_evoluciones_validar_insert/_update, desde
-- la regla 8, toman sesiones antes que asignaciones (ver el bloque REGLA 8
-- en el trigger de INSERT). Las dos comparten el motivo: el dato que decide
-- QUE fila pedir en la tabla de mas arriba en el orden sale de una fila que
-- ya hubo que leer de una tabla de mas abajo. Ninguna de las dos abre un
-- ciclo de dos actores porque ningun escritor de la tabla "de arriba" toma
-- nunca un lock de la tabla "de abajo" en esa transaccion.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Regla 1 — maximo 4 objetivos ACTIVOS por paciente (alta)
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_objetivos_limite_activos_insert
BEFORE INSERT ON objetivos_terapeuticos
FOR EACH ROW
BEGIN
  DECLARE v_activos INT UNSIGNED DEFAULT 0;
  DECLARE v_lock    INT UNSIGNED DEFAULT NULL;
  DECLARE v_paciente_activo BOOLEAN DEFAULT NULL;

  -- Un objetivo que nace archivado no consume cupo
  IF NEW.activo = TRUE THEN
    -- Ver NOTA DE CONCURRENCIA
    SELECT id, activo INTO v_lock, v_paciente_activo
      FROM pacientes
     WHERE id = NEW.id_paciente
     FOR UPDATE;

    -- Un paciente dado de baja no admite objetivos activos nuevos.
    --
    -- Agregado el 2026-08-12 por un hallazgo de auditoria. Hasta hoy esto lo
    -- frenaba SOLO `obtener_paciente()` en Python, o sea un unico camino: un
    -- INSERT directo, un script o cualquier endpoint futuro lo esquivaba, y
    -- el paciente quedaba inactivo pero con objetivos vivos. La baja dejaba
    -- de ser cierta sin que nada avisara.
    --
    -- Va aca adentro y no en su propio IF porque el lock sobre `pacientes` ya
    -- esta tomado en esta rama: se aprovecha la lectura que ya se hacia.
    IF v_paciente_activo = FALSE THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'El paciente no esta en tratamiento activo: no se le pueden crear objetivos';
    END IF;

    SELECT COUNT(*) INTO v_activos
      FROM objetivos_terapeuticos
     WHERE id_paciente = NEW.id_paciente
       AND activo = TRUE
     FOR SHARE;

    IF v_activos >= 4 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'El paciente ya tiene 4 objetivos activos. Archive uno antes de crear otro';
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- Regla 1 — el mismo limite, pero al REACTIVAR un objetivo archivado.
-- Sin este trigger el limite se saltea con un UPDATE en vez de un INSERT.
-- Tambien cubre el caso de mover un objetivo activo a otro paciente.
--
-- De paso mantiene fecha_archivado consistente con activo, para que no
-- queden filas archivadas sin fecha ni filas activas con fecha vieja.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_objetivos_limite_activos_update
BEFORE UPDATE ON objetivos_terapeuticos
FOR EACH ROW
BEGIN
  DECLARE v_activos     INT UNSIGNED DEFAULT 0;
  DECLARE v_evoluciones INT UNSIGNED DEFAULT 0;
  DECLARE v_lock        INT UNSIGNED DEFAULT NULL;
  DECLARE v_paciente_activo BOOLEAN DEFAULT NULL;

  -- La descripcion de un objetivo ARCHIVADO es inmutable.
  --
  -- El motivo no es tecnico. Un objetivo archivado tiene evoluciones
  -- colgando, y reescribir su texto dejaria calificaciones historicas
  -- puntuando contra algo que hoy dice otra cosa. Estos registros
  -- respaldan el tratamiento ante obras sociales e instituciones: el
  -- pasado no se reescribe.
  --
  -- Vive en la base y no solo en el endpoint a proposito. Es la misma
  -- leccion de los hallazgos C1/C3/A1: una regla que solo se aplica en un
  -- camino de escritura se elude por cualquier otro (un UPDATE directo, un
  -- script de migracion, un endpoint futuro).
  --
  -- Reactivar y reescribir en la MISMA sentencia tambien se rechaza: el
  -- objetivo todavia estaba archivado cuando se pidio el cambio. Para
  -- reescribirlo hay que reactivarlo primero y editarlo despues, ya activo.
  IF OLD.activo = FALSE AND NEW.descripcion <> OLD.descripcion THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'El objetivo esta archivado: su descripcion quedo fija y no se puede editar';
  END IF;

  -- Mover un objetivo a otro paciente deja las evoluciones ya cargadas
  -- apuntando a un objetivo cuyo paciente no coincide con el de sus
  -- sesiones: viola la regla 3 retroactivamente. Se rechaza.
  IF NEW.id_paciente <> OLD.id_paciente THEN
    SELECT COUNT(*) INTO v_evoluciones
      FROM evoluciones
     WHERE id_objetivo = OLD.id;

    IF v_evoluciones > 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'No se puede mover el objetivo a otro paciente: ya tiene evoluciones registradas';
    END IF;
  END IF;

  -- MINIMO DE 3 OBJETIVOS ACTIVOS (Entrega 3). Archivar uno no puede dejar a
  -- un paciente EN TRATAMIENTO con menos de 3: hay que crear el reemplazo
  -- antes (por eso el tope de 4 deja margen). No rige cuando el paciente ya
  -- esta de baja, y por eso el cierre (p_baja_paciente) que archiva todo no
  -- se rechaza: marca la baja primero y archiva despues. Los pacientes que ya
  -- tenian menos de 3 siguen validos; solo no pueden archivar hasta llegar a 3.
  IF OLD.activo = TRUE AND NEW.activo = FALSE AND NEW.id_paciente = OLD.id_paciente THEN
    -- Ver NOTA DE CONCURRENCIA
    SELECT id, activo INTO v_lock, v_paciente_activo
      FROM pacientes
     WHERE id = NEW.id_paciente
     FOR UPDATE;

    IF v_paciente_activo = TRUE THEN
      SELECT COUNT(*) INTO v_activos
        FROM objetivos_terapeuticos
       WHERE id_paciente = NEW.id_paciente
         AND activo = TRUE
         AND id <> OLD.id
       FOR SHARE;

      IF v_activos < 3 THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT =
            'El paciente tiene que mantener al menos 3 objetivos activos: cree el reemplazo antes de archivar este';
      END IF;
    END IF;
  END IF;

  IF NEW.activo = TRUE
     AND (OLD.activo = FALSE OR NEW.id_paciente <> OLD.id_paciente) THEN

    -- Ver NOTA DE CONCURRENCIA
    SELECT id, activo INTO v_lock, v_paciente_activo
      FROM pacientes
     WHERE id = NEW.id_paciente
     FOR UPDATE;

    -- Desarchivar un objetivo de un paciente dado de baja deja al paciente
    -- inactivo y con un objetivo vivo: la baja deja de ser cierta. Es el
    -- mismo hueco que el del INSERT, por la puerta del UPDATE — que es
    -- exactamente el par que este schema ya cuida en las otras cuatro reglas.
    IF v_paciente_activo = FALSE THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'El paciente no esta en tratamiento activo: no se le pueden activar objetivos';
    END IF;

    SELECT COUNT(*) INTO v_activos
      FROM objetivos_terapeuticos
     WHERE id_paciente = NEW.id_paciente
       AND activo = TRUE
       AND id <> OLD.id
     FOR SHARE;

    IF v_activos >= 4 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'El paciente ya tiene 4 objetivos activos. Archive uno antes de reactivar este';
    END IF;
  END IF;

  -- Sincroniza fecha_archivado con el estado real
  IF NEW.activo = FALSE AND OLD.activo = TRUE THEN
    SET NEW.fecha_archivado = NOW();
  ELSEIF NEW.activo = TRUE AND OLD.activo = FALSE THEN
    SET NEW.fecha_archivado = NULL;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- Regla 6 — sin sesiones solapadas del mismo terapeuta (alta)
--
-- Hasta la auditoria esta regla vivia SOLO en p_registrar_sesion, asi que
-- cualquier INSERT o UPDATE directo sobre sesiones la eludia. Ahora vive
-- en la tabla: el procedimiento CONSERVA su validacion (da un mensaje por
-- OUT p_mensaje en vez de un error), y el trigger es la red de seguridad
-- para cualquier otro camino de escritura.
--
-- Criterio de solape identico al del procedimiento: se usa < y >, no <=
-- y >=. Una sesion que termina 10:00 y otra que arranca 10:00 se tocan,
-- no se pisan. Si hora_fin es NULL se asume una hora de duracion.
--
-- Las sesiones en 'ausencia' TAMBIEN bloquean el horario (decision
-- tomada): el paciente falto, pero el turno estaba ocupado igual.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_sesiones_solape_insert
BEFORE INSERT ON sesiones
FOR EACH ROW
BEGIN
  DECLARE v_hora_fin     TIME         DEFAULT NULL;
  DECLARE v_superpuestas INT UNSIGNED DEFAULT 0;
  DECLARE v_lock         INT UNSIGNED DEFAULT NULL;
  DECLARE v_activo_pac   BOOLEAN      DEFAULT NULL;
  DECLARE v_fecha_baja   DATE         DEFAULT NULL;
  DECLARE v_asignacion   INT UNSIGNED DEFAULT NULL;
  DECLARE v_hermanas     INT UNSIGNED DEFAULT 0;
  DECLARE v_coinciden    INT UNSIGNED DEFAULT 0;

  -- =====================================================================
  -- AUSENCIA Y QUIEN FALTO TIENEN QUE VIAJAR JUNTOS (2026-09-10)
  --
  -- No lee ninguna tabla ni toma ningun lock: compara NEW contra si misma,
  -- asi que va primero, antes de gastar el lock de pacientes en una fila
  -- que de todos modos se va a rechazar. Mismo mensaje que en el trigger
  -- de UPDATE — son las dos puertas de la misma regla.
  -- =====================================================================
  IF NEW.estado = 'ausencia' AND NEW.ausencia_de IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'No se puede marcar la sesion como ausencia sin declarar quien falto';
  END IF;

  IF NEW.estado <> 'ausencia' AND NEW.ausencia_de IS NOT NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'Quien falto solo se declara en una sesion marcada como ausencia';
  END IF;

  -- =====================================================================
  -- SESION SOBRE UN PACIENTE DADO DE BAJA (2026-08-13)
  --
  -- Mismo criterio que p_registrar_sesion: el corte es la FECHA de la
  -- sesion contra fecha_baja, no el estado del paciente. Una sesion que
  -- ocurrio antes de la baja se puede cargar tarde; una posterior no
  -- ocurrio. Ver el bloque largo del procedimiento.
  --
  -- ESTE CHEQUEO VA PRIMERO, ANTES DEL LOCK DE TERAPEUTAS, Y NO ES
  -- COSMETICO. El orden canonico es pacientes -> terapeutas, y si se
  -- invierte aca se abre un ciclo con cualquier baja concurrente. Por lo
  -- mismo va DENTRO de este trigger y no en uno propio: MySQL corre los
  -- triggers del mismo evento en orden de creacion, asi que uno nuevo
  -- correria DESPUES de este y tomaria pacientes despues de terapeutas.
  --
  -- El texto del mensaje es identico al del trigger de UPDATE y al del
  -- procedimiento. Son las tres puertas de la misma regla.
  -- =====================================================================
  SELECT activo, fecha_baja INTO v_activo_pac, v_fecha_baja
    FROM pacientes
   WHERE id = NEW.id_paciente
   FOR SHARE;

  IF v_activo_pac = FALSE
     AND (v_fecha_baja IS NULL OR NEW.fecha > v_fecha_baja) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'El paciente no esta en tratamiento activo: solo se pueden cargar sesiones hasta el dia del cierre';
  END IF;

  -- Ver NOTA DE CONCURRENCIA
  SELECT id INTO v_lock
    FROM terapeutas
   WHERE id = NEW.id_terapeuta
   FOR UPDATE;

  IF v_lock IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El terapeuta indicado no existe';
  END IF;

  -- =====================================================================
  -- REGLA 8 — ASIGNACION VIGENTE A LA FECHA DE LA SESION (2026-09-28)
  --
  -- Un terapeuta solo puede REGISTRAR una sesion de un paciente que tiene
  -- asignado. Decision de producto, respaldada por el relevamiento: hoy
  -- cualquier terapeuta podia atender a cualquier paciente (medido el
  -- 2026-09-22, ver ESTADO.md "Medicion de la relacion paciente-terapeuta"),
  -- y en el rubro no es asi.
  --
  -- LA LECTURA NO SE TOCA. Esta regla es de ESCRITURA solamente: ver la
  -- sesion, el historial, el grafico y las observaciones clinicas de un
  -- colega sigue abierto entre terapeutas. Esa apertura ya esta decidida y
  -- escrita en `sesiones_service.obtener_detalle` y `listar_por_paciente`.
  --
  -- CONTRA LA FECHA DE LA SESION, NO CONTRA HOY. NEW.fecha, no CURDATE(): es
  -- el mismo criterio que ya usa el chequeo de paciente dado de baja, de
  -- arriba, y por el mismo motivo. La carga retroactiva SI tiene que entrar
  -- (la terapeuta que atendio el viernes y recien carga el lunes), asi que
  -- lo que se evalua es si la asignacion CUBRIA esa fecha, vigente o no hoy.
  --
  -- SOLO ALTAS NUEVAS. Por eso vive en el trigger de INSERT y
  -- trg_sesiones_solape_update NO tiene este chequeo (ver la nota puesta
  -- ahi). Hay 425 de 647 sesiones en `asisto` sin asignacion vigente ese
  -- dia (medido el 2026-09-22): exigirselo a una EDICION habria congelado
  -- gran parte del historial ya cargado, y editar sesion es entregable
  -- aprobado de la Entrega 2.
  --
  -- ORDEN DE LOCKS: se LEE aca, en el lugar canonico
  -- (pacientes -> terapeutas -> asignaciones -> sesiones), inmediatamente
  -- despues de terapeutas y antes del chequeo de solape sobre la propia
  -- tabla. Pero el SIGNAL se deja para el final del trigger, no aca: esta
  -- regla es ESTRICTAMENTE ADITIVA y no tiene que taparle el mensaje a un
  -- rechazo mas especifico (paciente de baja, terapeuta inexistente, hora
  -- invertida o solapamiento) que esta misma fila ya iba a recibir. Mismo
  -- criterio que ordena regla 4 antes que regla 3 en el trigger de
  -- evoluciones: la que se reporta es la condicion mas util para quien
  -- corrige, y una fila que ya se rechazaba por otro motivo no cambia de
  -- veredicto por esta regla.
  --
  -- FOR SHARE y no FOR UPDATE: se lee OTRA tabla (no la del propio
  -- trigger), y esto es una existencia puntual, no un conteo que necesite
  -- serializar contra otro INSERT de sesiones del mismo par. Ver NOTA DE
  -- CONCURRENCIA.
  -- =====================================================================
  SELECT id INTO v_asignacion
    FROM asignaciones
   WHERE id_terapeuta = NEW.id_terapeuta
     AND id_paciente = NEW.id_paciente
     AND fecha_desde <= NEW.fecha
     AND (fecha_hasta IS NULL OR fecha_hasta >= NEW.fecha)
   LIMIT 1
   FOR SHARE;

  SET v_hora_fin = IFNULL(NEW.hora_fin, ADDTIME(NEW.hora_inicio, '01:00:00'));

  IF v_hora_fin <= NEW.hora_inicio THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'La hora de fin debe ser posterior a la hora de inicio';
  END IF;

  -- DUPLAS (Entrega 5, 2026-10-19): las sesiones de la MISMA dupla se
  -- superponen a proposito, asi que no cuentan como choque. Solo se exime a
  -- quien comparte id_dupla con la fila nueva; una sesion suelta o de otra
  -- dupla en ese horario sigue siendo un solape.
  SELECT COUNT(*) INTO v_superpuestas
    FROM sesiones
   WHERE id_terapeuta = NEW.id_terapeuta
     AND fecha = NEW.fecha
     AND NEW.hora_inicio < IFNULL(hora_fin, ADDTIME(hora_inicio, '01:00:00'))
     AND v_hora_fin > hora_inicio
     AND (NEW.id_dupla IS NULL OR id_dupla IS NULL OR id_dupla <> NEW.id_dupla)
   FOR SHARE;

  IF v_superpuestas > 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'El terapeuta ya tiene sesiones que se superponen con ese horario';
  END IF;

  -- DUPLAS: una dupla son a lo sumo DOS sesiones de la misma terapeuta, el
  -- mismo dia y en el mismo horario exacto (el horario efectivo: sin hora de
  -- fin se asume una hora, igual que en el resto del schema). Se valida al
  -- ARMARLA, que es cuando ambas filas existen y se pueden comparar.
  IF NEW.id_dupla IS NOT NULL THEN
    SELECT COUNT(*),
           IFNULL(SUM(id_terapeuta = NEW.id_terapeuta
                      AND fecha = NEW.fecha
                      AND hora_inicio = NEW.hora_inicio
                      AND IFNULL(hora_fin, ADDTIME(hora_inicio, '01:00:00')) = v_hora_fin), 0)
      INTO v_hermanas, v_coinciden
      FROM sesiones
     WHERE id_dupla = NEW.id_dupla
     FOR SHARE;

    IF v_hermanas >= 2 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Una dupla terapeutica tiene como maximo dos sesiones';
    END IF;

    IF v_hermanas > 0 AND v_coinciden < v_hermanas THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'Las dos sesiones de una dupla tienen que ser de la misma terapeuta, el mismo dia y el mismo horario';
    END IF;
  END IF;

  -- Regla 8, recien aca: ver el bloque de arriba, es estrictamente aditiva.
  IF v_asignacion IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'El terapeuta no tiene asignado a este paciente en la fecha de la sesion';
  END IF;
END$$


-- ---------------------------------------------------------------------
-- Regla 6 en UPDATE + regla 2 al cambiar el estado a 'ausencia'
--
-- REGLA 8 (2026-09-28) NO VA ACA, A PROPOSITO: es solo de ALTAS NUEVAS.
-- Ver el bloque grande en trg_sesiones_solape_insert. Agregarla aca
-- congelaria el historial ya cargado (425 de 647 sesiones de `asisto` sin
-- asignacion vigente el dia en que ocurrieron) y le pondria una regla nueva
-- a editar sesion, que es entregable aprobado de la Entrega 2.
--
-- El chequeo de solape solo corre si cambio algo del horario: mover una
-- sesion de dia u hora. Un UPDATE que solo toca notas o estado no paga el
-- costo del lock.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_sesiones_solape_update
BEFORE UPDATE ON sesiones
FOR EACH ROW
BEGIN
  DECLARE v_hora_fin     TIME         DEFAULT NULL;
  DECLARE v_superpuestas INT UNSIGNED DEFAULT 0;
  DECLARE v_evoluciones  INT UNSIGNED DEFAULT 0;
  DECLARE v_renglones    INT UNSIGNED DEFAULT 0;
  DECLARE v_lock         INT UNSIGNED DEFAULT NULL;
  DECLARE v_activo_pac   BOOLEAN      DEFAULT NULL;
  DECLARE v_fecha_baja   DATE         DEFAULT NULL;
  DECLARE v_hermanas     INT UNSIGNED DEFAULT 0;
  DECLARE v_coinciden    INT UNSIGNED DEFAULT 0;
  DECLARE v_fin_nuevo    TIME         DEFAULT NULL;

  -- =====================================================================
  -- SESION SOBRE UN PACIENTE DADO DE BAJA (2026-08-13)
  --
  -- Par del chequeo del trigger de INSERT, con el mismo mensaje. Ver alla
  -- el porque; aca cambian dos cosas.
  --
  -- 1. CORRE SOLO SI CAMBIA `fecha` O `id_paciente`, que son los dos campos
  --    de los que depende la regla. No va suelto y tampoco va dentro del IF
  --    del horario, y las dos cosas se probaron mal antes de quedar asi:
  --
  --    - Suelto (primera version, corregida el 2026-08-13 por un hallazgo de
  --      auditoria): una sesion FUTURA agendada ANTES de la baja quedaba
  --      congelada. Su fecha ya era posterior a fecha_baja, asi que
  --      cualquier UPDATE la volvia a evaluar y la rechazaba: no se le podia
  --      cambiar ni el estado ni las notas. La regla es sobre DONDE cae la
  --      sesion, no sobre si se la puede seguir administrando.
  --
  --    - Dentro del IF del horario: reabre el agujero de mover la sesion a
  --      otro paciente, porque ese IF no mira `id_paciente`. Auditoria lo
  --      falso.
  --
  -- 2. ACA EL ORDEN DE LOCKS QUEDA INVERTIDO Y NO HAY FORMA DE EVITARLO.
  --    Un BEFORE UPDATE corre con el lock exclusivo de la fila de sesiones
  --    YA tomado por el UPDATE, asi que este SELECT sobre pacientes llega
  --    despues: sesiones -> pacientes, al reves del canonico. Medido: con
  --    una baja concurrente eso ARMA UN DEADLOCK real, y la victima que
  --    elige InnoDB es la baja.
  --
  --    Se aplica igual, y esto se decidio con el numero en la mano: la baja
  --    esta decorada con @reintentar_en_deadlock, recibe el 1213 por el
  --    RESIGNAL y ENTRA EN EL PRIMER REINTENTO. Cuatro corridas end-to-end
  --    por la aplicacion, las cuatro identicas: 1 reintento de 3, 2,49 s,
  --    baja completa y correcta.
  --
  --    Y el deadlock solo lo produce quien se saltea la convencion: un
  --    llamador que tome pacientes FOR SHARE antes que terapeutas —como
  --    hace p_registrar_sesion— llega aca con el lock ya en su propia
  --    transaccion, y este SELECT no espera a nadie. Ver la NOTA PARA LA
  --    ENTREGA 4 al pie de este bloque de triggers.
  -- =====================================================================
  IF NEW.fecha <> OLD.fecha OR NEW.id_paciente <> OLD.id_paciente THEN
    SELECT activo, fecha_baja INTO v_activo_pac, v_fecha_baja
      FROM pacientes
     WHERE id = NEW.id_paciente
     FOR SHARE;

    IF v_activo_pac = FALSE
       AND (v_fecha_baja IS NULL OR NEW.fecha > v_fecha_baja) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'El paciente no esta en tratamiento activo: solo se pueden cargar sesiones hasta el dia del cierre';
    END IF;
  END IF;

  -- Regla 2 por la puerta de atras: marcar como ausencia una sesion que
  -- ya tiene evolucion cargada deja exactamente el estado que la regla 2
  -- dice que no puede existir.
  IF NEW.estado = 'ausencia' AND OLD.estado <> 'ausencia' THEN
    SELECT COUNT(*) INTO v_evoluciones
      FROM evoluciones
     WHERE id_sesion = OLD.id;

    IF v_evoluciones > 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'No se puede marcar la sesion como ausencia: ya tiene evoluciones cargadas';
    END IF;

    -- Entrega 3: "Ausente" cierra la sesion, y una sesion que ya tiene
    -- registro escrito no puede pasar a ausencia (mismo criterio que con las
    -- evoluciones). El PLAN no cuenta: una sesion planificada a la que el
    -- paciente falto conserva su plan, que se arrastra. Ultimo en el orden
    -- de locks: sesion_renglones va despues de evoluciones.
    SELECT COUNT(*) INTO v_renglones
      FROM sesion_renglones
     WHERE id_sesion = OLD.id AND momento = 'registro'
       FOR SHARE;

    IF v_renglones > 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'No se puede marcar la sesion como ausencia: ya tiene renglones de registro';
    END IF;
  END IF;

  -- =====================================================================
  -- AUSENCIA Y QUIEN FALTO TIENEN QUE VIAJAR JUNTOS (2026-09-10)
  --
  -- Par del chequeo del trigger de INSERT, mismos dos mensajes. Aca no es
  -- incondicional: CORRE SOLO SI CAMBIA `estado` O `ausencia_de`. Sin esta
  -- guarda, cualquier UPDATE sobre una fila de ausencia sembrada ANTES de
  -- que esta columna existiera (59 en `asisto`, 59 en seed_demo.sql, 2 en
  -- seed.sql, medido el 2026-09-10 y ninguna tiene ausencia_de) quedaria
  -- congelada para siempre: NEW repite el mismo estado='ausencia' con
  -- ausencia_de NULL que la fila ya tenia, y una regla sin guarda la
  -- rechazaria por un dato que nadie puede reponer, aunque el UPDATE real
  -- solo tocara `notas`. Es el mismo defecto, con la misma solucion, que
  -- ya se encontro y se corrigio para el chequeo de fecha_baja de arriba
  -- (ver su comentario, punto 1): la regla es sobre el estado FINAL que se
  -- esta declarando, no sobre si una fila vieja se puede seguir tocando.
  -- No va dentro del IF de ausencia+evolucion de arriba porque esa guarda
  -- (`NEW.estado = 'ausencia' AND OLD.estado <> 'ausencia'`) no cubre el
  -- caso de corregir solo `ausencia_de` sobre una fila que YA es ausencia.
  -- =====================================================================
  IF NEW.estado <> OLD.estado OR NOT (NEW.ausencia_de <=> OLD.ausencia_de) THEN
    IF NEW.estado = 'ausencia' AND NEW.ausencia_de IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'No se puede marcar la sesion como ausencia sin declarar quien falto';
    END IF;

    IF NEW.estado <> 'ausencia' AND NEW.ausencia_de IS NOT NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'Quien falto solo se declara en una sesion marcada como ausencia';
    END IF;
  END IF;

  -- DUPLAS (Entrega 5): al ARMAR una dupla (id_dupla pasa de NULL o de otro
  -- valor a uno nuevo) la fila tiene que coincidir en terapeuta, dia y
  -- horario exacto con su hermana, y la dupla no puede pasar de dos. Mismos
  -- mensajes que el trigger de INSERT. Mover despues el horario de una
  -- sesion de dupla no se valida aca contra la hermana (son dos UPDATE y la
  -- primera fila vera a la otra todavia en el horario viejo): lo mueve
  -- p_editar_sesion con una sola sentencia sobre las dos filas.
  IF NEW.id_dupla IS NOT NULL AND NOT (NEW.id_dupla <=> OLD.id_dupla) THEN
    SELECT id INTO v_lock
      FROM terapeutas
     WHERE id = NEW.id_terapeuta
     FOR UPDATE;

    SET v_fin_nuevo = IFNULL(NEW.hora_fin, ADDTIME(NEW.hora_inicio, '01:00:00'));

    SELECT COUNT(*),
           IFNULL(SUM(id_terapeuta = NEW.id_terapeuta
                      AND fecha = NEW.fecha
                      AND hora_inicio = NEW.hora_inicio
                      AND IFNULL(hora_fin, ADDTIME(hora_inicio, '01:00:00')) = v_fin_nuevo), 0)
      INTO v_hermanas, v_coinciden
      FROM sesiones
     WHERE id_dupla = NEW.id_dupla
       AND id <> OLD.id
     FOR SHARE;

    IF v_hermanas >= 2 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Una dupla terapeutica tiene como maximo dos sesiones';
    END IF;

    IF v_hermanas > 0 AND v_coinciden < v_hermanas THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'Las dos sesiones de una dupla tienen que ser de la misma terapeuta, el mismo dia y el mismo horario';
    END IF;
  END IF;

  IF NEW.id_terapeuta <> OLD.id_terapeuta
     OR NEW.fecha <> OLD.fecha
     OR NEW.hora_inicio <> OLD.hora_inicio
     OR NOT (NEW.hora_fin <=> OLD.hora_fin) THEN

    -- Ver NOTA DE CONCURRENCIA
    SELECT id INTO v_lock
      FROM terapeutas
     WHERE id = NEW.id_terapeuta
     FOR UPDATE;

    IF v_lock IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'El terapeuta indicado no existe';
    END IF;

    SET v_hora_fin = IFNULL(NEW.hora_fin, ADDTIME(NEW.hora_inicio, '01:00:00'));

    IF v_hora_fin <= NEW.hora_inicio THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'La hora de fin debe ser posterior a la hora de inicio';
    END IF;

    -- Se excluye la propia fila: mover una sesion no se solapa consigo misma
    SELECT COUNT(*) INTO v_superpuestas
      FROM sesiones
     WHERE id_terapeuta = NEW.id_terapeuta
       AND fecha = NEW.fecha
       AND id <> OLD.id
       AND NEW.hora_inicio < IFNULL(hora_fin, ADDTIME(hora_inicio, '01:00:00'))
       AND v_hora_fin > hora_inicio
       -- DUPLAS (Entrega 5): la hermana de dupla no es un choque
       AND (NEW.id_dupla IS NULL OR id_dupla IS NULL OR id_dupla <> NEW.id_dupla)
     FOR SHARE;

    IF v_superpuestas > 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'El terapeuta ya tiene sesiones que se superponen con ese horario';
    END IF;
  END IF;
END$$


-- =====================================================================
-- NOTA PARA LA ENTREGA 4 EN ADELANTE — leer antes de escribir cualquier
-- camino nuevo que escriba en `sesiones`. La agenda a futuro, el modulo de
-- IA y el endpoint de EDITAR SESION entran todos por aca.
--
-- REGLA: todo camino de escritura sobre `sesiones` tiene que pasar por un
-- procedimiento que tome `pacientes FOR SHARE` ANTES que `terapeutas`,
-- como hace p_registrar_sesion. No es una preferencia de estilo.
--
-- POR QUE. Los triggers de arriba leen `pacientes` para decidir si la sesion
-- cae despues de la baja. En el INSERT eso no cuesta nada: el trigger corre
-- antes de que exista la fila, asi que el orden queda
-- pacientes -> terapeutas -> sesiones, el canonico. En el UPDATE es distinto
-- y no se puede arreglar desde el trigger: un BEFORE UPDATE corre con el lock
-- exclusivo de la fila YA tomado, o sea sesiones -> pacientes, invertido.
--
-- QUE ABRE ESA INVERSION, medido por las dos terminales y reescrito el
-- 2026-08-14 con el cuadro completo. Son DOS modos de falla distintos y el
-- que mas se va a ver NO es el deadlock.
--
-- ---------------------------------------------------------------------
-- MODO 1 — ESPERA. Dos actores. Es el caso FRECUENTE.
-- ---------------------------------------------------------------------
-- Alguien edita una sesion mientras se da una baja del mismo paciente, y no
-- hay nadie registrando una sesion en el medio. NO hay ciclo y NO hay
-- deadlock: hay espera. El que edita toma la fila de `sesiones` y pide
-- `pacientes`; la baja nunca toca `sesiones`, asi que el que edita no
-- necesita nada que la baja tenga, y la cola se resuelve sola.
--
-- Medido: la baja ESPERA 19,18 s con un retenedor de 20 s, y completa. Cero
-- deadlocks. Verificado ademas en performance_schema.data_locks.
--
-- EL RIESGO DE ESTE MODO NO ES EL 1213, ES EL 1205: si la espera supera
-- `innodb_lock_wait_timeout`, la baja recibe lock wait timeout. El decorador
-- tambien lo reintenta, pero si el que retiene sigue ahi los tres intentos se
-- agotan y LA BAJA FALLA. Una transaccion larga sobre `sesiones` es, por si
-- sola, suficiente para voltear una baja.
--
-- ---------------------------------------------------------------------
-- MODO 2 — DEADLOCK. Tres actores en el ciclo, y un cuarto para montarlo.
-- ---------------------------------------------------------------------
--   A  UPDATE directo        tiene X(sesion)     y quiere S(pacientes)
--   B  la baja                                     quiere X(pacientes)
--   C  p_registrar_sesion    tiene S(pacientes)  y quiere S(sesion), por el
--                                                 chequeo de solape
--
-- A queda detras de la X ENCOLADA de B —InnoDB no deja que una S nueva se
-- adelante a una X que ya espera—, B detras de la S de C, y C detras de la X
-- de A. `delta lock_deadlocks = 1`, ERROR 1213, y la victima que elige InnoDB
-- es LA BAJA.
--
-- HACE FALTA UN CUARTO ACTOR PARA ARMARLO, y por eso no aparece solo: C tiene
-- que quedarse detenido DESPUES de tomar `pacientes` y ANTES de leer el
-- solape, y el unico punto entre esas dos cosas es el `terapeutas FOR
-- UPDATE`. Alguien reteniendo esa fila abre la ventana. Sin el, C pasa de
-- largo y la cola no se forma.
--
-- Y SOLO LO ABRE UN UPDATE QUE MUEVA `fecha` O `id_paciente`, porque el
-- chequeo de arriba corre solo en ese caso: un UPDATE de notas, estado u
-- hora no lee `pacientes` y no participa del ciclo. Medido de los dos lados:
-- SET notas -> sin deadlock; SET fecha -> 1213 con la baja como victima.
--
-- Por que se aplico igual: la baja lleva @reintentar_en_deadlock, recibe el
-- 1213 gracias al RESIGNAL y entra en el PRIMER reintento. Cuatro corridas
-- end-to-end por la aplicacion, las cuatro iguales: 1 de 3 intentos. El
-- deadlock es el modo BENIGNO de los dos: se reintenta y entra.
--
-- ---------------------------------------------------------------------
-- LO QUE LE TOCA A QUIEN ESCRIBA EL CODIGO NUEVO
-- ---------------------------------------------------------------------
-- Los dos modos los produce lo mismo: entrar por un UPDATE directo. Un
-- llamador que tome `pacientes FOR SHARE` PRIMERO llega al trigger con el
-- lock ya en su propia transaccion, el SELECT de adentro no espera a nadie,
-- y evita el ciclo de tres Y la espera del modo 1.
--
-- Si el endpoint de editar sesion se escribe con un UPDATE del ORM y sin
-- procedimiento, va a funcionar en las pruebas de a uno y va a empezar a
-- frenar bajas —y a voltear alguna por 1205— en cuanto haya dos personas
-- trabajando a la vez.
--
-- Un error de metodo que quedo a la vista y conviene no repetir: las dos
-- terminales probaron las combinaciones de DOS actores, no encontraron ciclo
-- y generalizaron a "no hay ciclo". El tercero lo cierra. Con locks, no
-- haberlo encontrado con N actores no dice nada sobre N+1.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Reglas 2, 3 y 4 — validacion unificada de evoluciones, mas la regla del
-- objetivo posterior a la sesion (2026-08-19).
--
-- Un solo trigger a proposito, no tres. Motivo: las tres validaciones
-- necesitan los mismos dos SELECT (la sesion y el objetivo). Separarlas
-- multiplicaria las consultas por tres para el mismo INSERT, y el orden
-- de disparo entre triggers del mismo evento no seria explicito.
-- Cada regla conserva su propio mensaje de error.
--
-- =====================================================================
-- LA REGLA DEL OBJETIVO POSTERIOR A LA SESION (2026-08-19)
--
-- No se puede calificar una sesion contra un objetivo que todavia no
-- existia cuando esa sesion ocurrio.
--
-- POR QUE ES UNA REGLA Y NO UNA MOLESTIA: `p_evolucion_paciente` arma las
-- series con los objetivos VIVOS al momento de cada sesion
-- (`o.fecha_creacion <= TIMESTAMP(s.fecha, s.hora_inicio)`), asi que una
-- evolucion sobre un objetivo creado despues NO ENTRA EN NINGUNA SERIE,
-- con cualquier rango de fechas que se pida. Es una escritura que la
-- lectura no puede devolver nunca: el sistema la acepta, contesta 201, y
-- despues no la muestra en ningun lado. Aceptar lo que no se puede leer es
-- perdida silenciosa, y por eso se corta en la escritura.
--
-- Medido antes de aplicarla: en la base real `asisto` habia 1 fila asi
-- sobre 460 evoluciones (la evolucion 460, contra un objetivo creado nueve
-- dias despues de su sesion). En `seed.sql` y en `seed_demo.sql` recien
-- cargados, CERO. Un trigger que afirma que algo no puede pasar mientras
-- el seed lo hace seria peor que no tenerlo.
--
-- OJO: el trigger no arregla la fila que ya esta. Solo cierra la puerta.
--
-- POR QUE VA ULTIMA Y NO ANTES. El orden regla 4 -> regla 3 es
-- load-bearing y esta justificado abajo; meterse en el medio le cambiaria
-- el mensaje a casos que hoy ya se rechazan. Puesta al final, esta regla
-- es estrictamente aditiva: no altera el veredicto de ninguna entrada que
-- los triggers ya rechazaban, y solo habla cuando el objetivo ya demostro
-- ser un objetivo legitimo de ese paciente y no archivado. Decirle a
-- alguien "ese objetivo no existia todavia" sobre un objetivo que ademas
-- es de otro paciente lo mandaria a corregir lo que no importa.
--
-- Locks: NO agrega ninguno. Las tres columnas nuevas —fecha, hora_inicio
-- y fecha_creacion— salen de los mismos dos SELECT que ya estaban, con su
-- mismo FOR SHARE y en el mismo orden
-- (sesiones antes que objetivos_terapeuticos). No entra ninguna tabla
-- nueva al orden de adquisicion.
-- =====================================================================
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_evoluciones_validar_insert
BEFORE INSERT ON evoluciones
FOR EACH ROW
BEGIN
  DECLARE v_estado_sesion     ENUM('completa','incompleta','ausencia') DEFAULT NULL;
  DECLARE v_paciente_sesion   INT UNSIGNED DEFAULT NULL;
  DECLARE v_terapeuta_sesion  INT UNSIGNED DEFAULT NULL;
  DECLARE v_paciente_objetivo INT UNSIGNED DEFAULT NULL;
  DECLARE v_objetivo_activo   BOOLEAN      DEFAULT NULL;
  DECLARE v_fecha_sesion      DATE         DEFAULT NULL;
  DECLARE v_hora_sesion       TIME         DEFAULT NULL;
  DECLARE v_objetivo_creado   DATETIME     DEFAULT NULL;
  DECLARE v_asignacion        INT UNSIGNED DEFAULT NULL;

  -- Los dos SELECT llevan FOR SHARE, y no es decorativo. Ver NOTA DE
  -- CONCURRENCIA: sin lock, estas serian lecturas consistentes de MVCC y
  -- no verian que otra transaccion, todavia sin confirmar, ya archivo el
  -- objetivo, lo movio de paciente o marco la sesion como ausencia. El
  -- INSERT pasaba las tres validaciones contra datos viejos.
  --
  -- Aca alcanza con FOR SHARE y no hace falta el rodeo del lock de fila
  -- padre que usan los triggers de objetivos y sesiones: esas dos tablas
  -- NO son la tabla del trigger (que es evoluciones), asi que el ERROR
  -- 1442 no aplica y se puede bloquear la fila leida directamente.
  --
  -- FOR SHARE y no FOR UPDATE porque alcanza: conflictua con el lock
  -- exclusivo de quien este modificando esa fila (que es de lo que hay que
  -- protegerse) y hace lectura actual, pero deja que dos evoluciones sobre
  -- el mismo objetivo entren en paralelo, que no se pisan entre si. Aca no
  -- se actualiza ninguna de las dos filas, asi que no hay ascenso de S a X
  -- ni el deadlock que eso traeria.
  --
  -- ORDEN: sesiones primero, objetivos_terapeuticos despues. Igual en los
  -- dos triggers de evoluciones. Invertirlo en uno solo crea un deadlock.
  SELECT estado, id_paciente, fecha, hora_inicio, id_terapeuta
    INTO v_estado_sesion, v_paciente_sesion, v_fecha_sesion, v_hora_sesion, v_terapeuta_sesion
    FROM sesiones
   WHERE id = NEW.id_sesion
   FOR SHARE;

  -- =====================================================================
  -- REGLA 8 — ASIGNACION VIGENTE A LA FECHA DE LA SESION (2026-09-28)
  --
  -- Ver el bloque grande en trg_sesiones_solape_insert: misma regla, mismo
  -- criterio (fecha de la sesion, no hoy), misma disciplina de "solo altas
  -- nuevas" (trg_evoluciones_validar_update NO la tiene, ver la nota ahi).
  --
  -- EL TERAPEUTA ES EL DE LA SESION, no un parametro de esta tabla:
  -- `evoluciones` no tiene columna id_terapeuta. p_registrar_evolucion ya
  -- exige que quien carga sea el terapeuta de la sesion (autoria), asi que
  -- validar contra v_terapeuta_sesion cubre tambien un INSERT directo que
  -- se salte esa capa — el mismo motivo por el que esta regla vive en el
  -- trigger y no solo en el procedimiento.
  --
  -- ORDEN DE LOCKS, Y POR QUE QUEDA INVERTIDO CONTRA sesiones. El canonico
  -- es pacientes -> terapeutas -> asignaciones -> sesiones ->
  -- objetivos_terapeuticos. Aca la consulta de abajo necesita id_paciente e
  -- id_terapeuta, y los dos salen de la fila de `sesiones` que se acaba de
  -- leer: no hay forma de pedir este lock ANTES sin adivinar esos dos
  -- valores. Es la misma clase de inversion forzada que ya tiene
  -- trg_sesiones_solape_update contra `pacientes` (ver su NOTA PARA LA
  -- ENTREGA 4), y por el mismo motivo no es peligrosa: ningun escritor de
  -- `asignaciones` (solo p_baja_paciente, que cierra vigentes por paciente)
  -- toma nunca un lock de `sesiones` ni de `terapeutas`, asi que no hay
  -- ciclo de dos actores posible entre esta lectura y una baja concurrente
  -- — como mucho, esta transaccion espera detras de la baja o la baja
  -- espera detras de esta, nunca las dos a la vez. Cualquier deadlock
  -- residual que igual apareciera queda cubierto por
  -- @reintentar_en_deadlock en el endpoint, igual que el resto del schema.
  --
  -- Se preserva el orden canonico contra `objetivos_terapeuticos`: esta
  -- lectura va ANTES que esa, no despues, porque nada la obliga a esperar.
  SELECT id INTO v_asignacion
    FROM asignaciones
   WHERE id_terapeuta = v_terapeuta_sesion
     AND id_paciente = v_paciente_sesion
     AND fecha_desde <= v_fecha_sesion
     AND (fecha_hasta IS NULL OR fecha_hasta >= v_fecha_sesion)
   LIMIT 1
   FOR SHARE;
  -- =====================================================================

  SELECT id_paciente, activo, fecha_creacion
    INTO v_paciente_objetivo, v_objetivo_activo, v_objetivo_creado
    FROM objetivos_terapeuticos
   WHERE id = NEW.id_objetivo
   FOR SHARE;

  -- Guardas de existencia: la FK tambien lo cubre, pero asi el mensaje
  -- es legible en vez de un error de constraint.
  IF v_paciente_sesion IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'La sesion indicada no existe';
  END IF;

  IF v_paciente_objetivo IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El objetivo indicado no existe';
  END IF;

  -- Regla 2
  IF v_estado_sesion = 'ausencia' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'No se puede cargar evolucion: la sesion esta marcada como ausencia';
  END IF;

  -- Regla 4 ANTES que la regla 3, y el orden importa: un solo UPDATE puede
  -- violar las dos a la vez (mover la evolucion a un objetivo que esta
  -- archivado Y ademas es de otro paciente). Cuando pasan las dos, la que
  -- hay que reportar es el objetivo archivado: es la condicion que el
  -- terapeuta puede corregir por si mismo, desarchivando o eligiendo otro.
  -- Este orden es identico en los dos triggers y tiene que seguir siendolo.
  IF v_objetivo_activo = FALSE THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'No se puede cargar evolucion sobre un objetivo archivado';
  END IF;

  -- Regla 3
  IF v_paciente_objetivo <> v_paciente_sesion THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'El objetivo evaluado no pertenece al paciente de esta sesion';
  END IF;

  -- Objetivo posterior a la sesion. VA ULTIMA de las tres primeras a
  -- proposito: ver el bloque del encabezado. No cambia el veredicto de
  -- ninguna entrada que las otras tres ya rechazaban.
  IF v_objetivo_creado > TIMESTAMP(v_fecha_sesion, v_hora_sesion) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'No se puede cargar evolucion: el objetivo se creo despues de esa sesion';
  END IF;

  -- Regla 8, recien aca: estrictamente aditiva, igual que la de arriba. No
  -- le cambia el mensaje a ninguna fila que ya se rechazaba por otro motivo.
  IF v_asignacion IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'No se puede cargar evolucion: el terapeuta de la sesion no tenia asignado a este paciente en esa fecha';
  END IF;
END$$


-- ---------------------------------------------------------------------
-- Reglas 2, 3 y 4 en UPDATE — espejo exacto del trigger de INSERT.
--
-- Duplicacion deliberada. En MySQL no hay forma limpia de compartir el
-- cuerpo entre dos triggers (un procedimiento auxiliar no puede leer NEW
-- y agrega una capa que oscurece que se valida), y tener los dos cuerpos
-- a la vista hace evidente en la auditoria si uno queda desactualizado
-- respecto del otro. Si se cambia una regla aca, hay que cambiarla en el
-- trigger de INSERT tambien.
--
-- Sin esto, un solo UPDATE de id_objetivo puede violar la regla 3 y la
-- regla 4 al mismo tiempo.
--
-- REGLA 8 (2026-09-28) NO VA ACA, A PROPOSITO: es solo de ALTAS NUEVAS. Ver
-- el bloque grande en trg_evoluciones_validar_insert. Este trigger sigue
-- siendo espejo de las reglas 2, 3, 4 y 7 unicamente.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_evoluciones_validar_update
BEFORE UPDATE ON evoluciones
FOR EACH ROW
BEGIN
  DECLARE v_estado_sesion     ENUM('completa','incompleta','ausencia') DEFAULT NULL;
  DECLARE v_paciente_sesion   INT UNSIGNED DEFAULT NULL;
  DECLARE v_paciente_objetivo INT UNSIGNED DEFAULT NULL;
  DECLARE v_objetivo_activo   BOOLEAN      DEFAULT NULL;
  DECLARE v_fecha_sesion      DATE         DEFAULT NULL;
  DECLARE v_hora_sesion       TIME         DEFAULT NULL;
  DECLARE v_objetivo_creado   DATETIME     DEFAULT NULL;

  -- Los dos SELECT llevan FOR SHARE, y no es decorativo. Ver NOTA DE
  -- CONCURRENCIA: sin lock, estas serian lecturas consistentes de MVCC y
  -- no verian que otra transaccion, todavia sin confirmar, ya archivo el
  -- objetivo, lo movio de paciente o marco la sesion como ausencia. El
  -- INSERT pasaba las tres validaciones contra datos viejos.
  --
  -- Aca alcanza con FOR SHARE y no hace falta el rodeo del lock de fila
  -- padre que usan los triggers de objetivos y sesiones: esas dos tablas
  -- NO son la tabla del trigger (que es evoluciones), asi que el ERROR
  -- 1442 no aplica y se puede bloquear la fila leida directamente.
  --
  -- FOR SHARE y no FOR UPDATE porque alcanza: conflictua con el lock
  -- exclusivo de quien este modificando esa fila (que es de lo que hay que
  -- protegerse) y hace lectura actual, pero deja que dos evoluciones sobre
  -- el mismo objetivo entren en paralelo, que no se pisan entre si. Aca no
  -- se actualiza ninguna de las dos filas, asi que no hay ascenso de S a X
  -- ni el deadlock que eso traeria.
  --
  -- ORDEN: sesiones primero, objetivos_terapeuticos despues. Igual en los
  -- dos triggers de evoluciones. Invertirlo en uno solo crea un deadlock.
  SELECT estado, id_paciente, fecha, hora_inicio
    INTO v_estado_sesion, v_paciente_sesion, v_fecha_sesion, v_hora_sesion
    FROM sesiones
   WHERE id = NEW.id_sesion
   FOR SHARE;

  SELECT id_paciente, activo, fecha_creacion
    INTO v_paciente_objetivo, v_objetivo_activo, v_objetivo_creado
    FROM objetivos_terapeuticos
   WHERE id = NEW.id_objetivo
   FOR SHARE;

  IF v_paciente_sesion IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'La sesion indicada no existe';
  END IF;

  IF v_paciente_objetivo IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El objetivo indicado no existe';
  END IF;

  -- Regla 2
  IF v_estado_sesion = 'ausencia' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'No se puede cargar evolucion: la sesion esta marcada como ausencia';
  END IF;

  -- Regla 4 ANTES que la regla 3, y el orden importa: un solo UPDATE puede
  -- violar las dos a la vez (mover la evolucion a un objetivo que esta
  -- archivado Y ademas es de otro paciente). Cuando pasan las dos, la que
  -- hay que reportar es el objetivo archivado: es la condicion que el
  -- terapeuta puede corregir por si mismo, desarchivando o eligiendo otro.
  -- Este orden es identico en los dos triggers y tiene que seguir siendolo.
  IF v_objetivo_activo = FALSE THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'No se puede cargar evolucion sobre un objetivo archivado';
  END IF;

  -- Regla 3
  IF v_paciente_objetivo <> v_paciente_sesion THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'El objetivo evaluado no pertenece al paciente de esta sesion';
  END IF;

  -- Objetivo posterior a la sesion. VA ULTIMA a proposito: ver el bloque
  -- del encabezado. Es la unica de las cuatro que no cambia el veredicto
  -- de ninguna entrada que las otras tres ya rechazaban.
  IF v_objetivo_creado > TIMESTAMP(v_fecha_sesion, v_hora_sesion) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'No se puede cargar evolucion: el objetivo se creo despues de esa sesion';
  END IF;
END$$


-- ---------------------------------------------------------------------
-- ASIGNACIONES — una sola asignacion vigente por terapeuta y paciente
--
-- Los dos triggers son deliberadamente iguales y sus dos mensajes son
-- IDENTICOS palabra por palabra. El par INSERT/UPDATE es duplicacion
-- explicita, igual que los otros tres pares del schema: el riesgo conocido
-- es que uno quede desactualizado respecto del otro. Si se toca uno, se
-- toca el otro en el mismo commit.
--
-- Vigente = fecha_hasta IS NULL. NO se valida solapamiento entre rangos
-- cerrados: dos asignaciones terminadas que se pisan en el tiempo se
-- aceptan. Es a proposito y es el limite conocido de esta version.
--
-- Locks: mismo patron que los triggers de objetivos. Lock de la fila padre
-- en pacientes con FOR UPDATE —primero en el orden canonico— y el conteo
-- sobre la PROPIA tabla con FOR SHARE, porque FOR UPDATE sobre la tabla del
-- trigger da ERROR 1442. Ver NOTA DE CONCURRENCIA arriba.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_asignaciones_vigente_insert
BEFORE INSERT ON asignaciones
FOR EACH ROW
BEGIN
  DECLARE v_vigentes INT UNSIGNED DEFAULT 0;
  DECLARE v_lock     INT UNSIGNED DEFAULT NULL;
  DECLARE v_paciente_activo BOOLEAN DEFAULT NULL;

  IF NEW.fecha_hasta IS NOT NULL AND NEW.fecha_hasta < NEW.fecha_desde THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'La fecha de fin de la asignacion no puede ser anterior a la de inicio';
  END IF;

  -- Una asignacion que nace cerrada no compite por la vigencia
  IF NEW.fecha_hasta IS NULL THEN
    -- Ver NOTA DE CONCURRENCIA
    SELECT id, activo INTO v_lock, v_paciente_activo
      FROM pacientes
     WHERE id = NEW.id_paciente
     FOR UPDATE;

    -- Una asignacion VIGENTE afirma que esa terapeuta atiende hoy a ese
    -- paciente. Sobre un paciente dado de baja eso es falso por definicion, y
    -- ademas ensucia el filtro de "pacientes asignados" que viene en la
    -- Entrega 2. Hallazgo de auditoria del 2026-08-12: todavia no hay
    -- endpoint de asignaciones, asi que esto se cierra ANTES de que exista un
    -- camino que lo explote, que es la unica vez que sale barato.
    IF v_paciente_activo = FALSE THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'El paciente no esta en tratamiento activo: no se le pueden abrir asignaciones';
    END IF;

    SELECT COUNT(*) INTO v_vigentes
      FROM asignaciones
     WHERE id_terapeuta = NEW.id_terapeuta
       AND id_paciente = NEW.id_paciente
       AND fecha_hasta IS NULL
     FOR SHARE;

    IF v_vigentes > 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'Ese terapeuta ya tiene una asignacion vigente con ese paciente';
    END IF;
  END IF;
END$$


-- Sin este trigger la regla se saltea con un UPDATE: reabrir una asignacion
-- cerrada (fecha_hasta a NULL) o mover una vigente a otro paciente o a otro
-- terapeuta llega al mismo estado que el INSERT rechaza.
CREATE TRIGGER trg_asignaciones_vigente_update
BEFORE UPDATE ON asignaciones
FOR EACH ROW
BEGIN
  DECLARE v_vigentes INT UNSIGNED DEFAULT 0;
  DECLARE v_lock     INT UNSIGNED DEFAULT NULL;
  DECLARE v_paciente_activo BOOLEAN DEFAULT NULL;

  IF NEW.fecha_hasta IS NOT NULL AND NEW.fecha_hasta < NEW.fecha_desde THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'La fecha de fin de la asignacion no puede ser anterior a la de inicio';
  END IF;

  IF NEW.fecha_hasta IS NULL THEN
    -- Ver NOTA DE CONCURRENCIA
    SELECT id, activo INTO v_lock, v_paciente_activo
      FROM pacientes
     WHERE id = NEW.id_paciente
     FOR UPDATE;

    -- Mismo chequeo que el trigger de INSERT, con el mismo mensaje. Ver alla
    -- el porque; aca solo cambia la puerta por la que se entra.
    IF v_paciente_activo = FALSE THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'El paciente no esta en tratamiento activo: no se le pueden abrir asignaciones';
    END IF;

    -- id <> OLD.id: la propia fila no cuenta como conflicto consigo misma.
    -- Sin esto, guardar una asignacion vigente sin cambiarle nada fallaria.
    SELECT COUNT(*) INTO v_vigentes
      FROM asignaciones
     WHERE id_terapeuta = NEW.id_terapeuta
       AND id_paciente = NEW.id_paciente
       AND fecha_hasta IS NULL
       AND id <> OLD.id
     FOR SHARE;

    IF v_vigentes > 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'Ese terapeuta ya tiene una asignacion vigente con ese paciente';
    END IF;
  END IF;
END$$


-- =====================================================================
-- 8. PROCEDIMIENTOS ALMACENADOS
-- =====================================================================

-- =====================================================================
-- CRITERIO GENERAL DE ERRORES — aplica a TODO procedimiento nuevo
--
-- p_mensaje NUNCA lleva texto crudo de MySQL concatenado adentro. Dos
-- razones, las dos comprobadas:
--
--   1. El error nativo incluye nombre de base, tabla y constraint. Eso es
--      estructura interna filtrada al llamador y, via API, al navegador.
--   2. Ese texto puede pasarse de los 255 caracteres de p_mensaje. Cuando
--      pasa, el propio SET dentro del EXIT HANDLER dispara un segundo
--      error que nadie captura (ERROR 1406) y el CALL entero termina en
--      un error crudo: el contrato OUT p_mensaje se rompe y el llamador
--      no recibe nada. El margen dependia del largo del nombre de la
--      base, asi que cambiar 'asisto' por otro nombre lo rompia.
--
-- El patron es siempre el mismo:
--
--   a) Validar ANTES del INSERT que exista todo lo que referencia una FK,
--      y devolver mensaje propio en castellano. Asi la FK nunca llega a
--      fallar por el camino normal.
--   b) EXIT HANDLER FOR SQLSTATE '45000' -> propaga MESSAGE_TEXT tal cual.
--      Ese SQLSTATE solo lo emiten nuestros propios SIGNAL, que ya estan
--      en castellano y MySQL limita a 128 caracteres: no puede desbordar.
--   c) EXIT HANDLER FOR SQLEXCEPTION -> mensaje fijo, sin concatenar nada.
--      Es la red para lo imprevisto.
--   d) EXIT HANDLER FOR SQLSTATE '23000' donde haya una UNIQUE que pueda
--      ganar una carrera -> mensaje fijo propio.
-- =====================================================================

-- ---------------------------------------------------------------------
-- p_alta_paciente
-- Valida nro_historia duplicado y existencia del usuario antes de insertar.
-- p_id_usuario puede venir NULL: paciente sin login (regla 5).
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_alta_paciente (
  IN  p_nombre            VARCHAR(100),
  IN  p_apellido          VARCHAR(100),
  IN  p_fecha_nacimiento  DATE,
  IN  p_diagnostico       TEXT,
  IN  p_nro_historia      VARCHAR(30),
  IN  p_id_usuario        INT UNSIGNED,
  OUT p_id_paciente       INT UNSIGNED,
  OUT p_mensaje           VARCHAR(255)
)
BEGIN
  DECLARE v_existe        INT UNSIGNED DEFAULT 0;
  DECLARE v_existe_usuario INT UNSIGNED DEFAULT 0;
  DECLARE v_error         VARCHAR(255) DEFAULT '';

  -- Nuestros propios SIGNAL: texto ya en castellano y acotado a 128
  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_paciente = NULL;
    SET p_mensaje = v_error;
  END;

  -- La UNIQUE de nro_historia gana la carrera si dos altas simultaneas
  -- pasan el chequeo amigable de abajo
  DECLARE EXIT HANDLER FOR SQLSTATE '23000'
  BEGIN
    ROLLBACK;
    SET p_id_paciente = NULL;
    SET p_mensaje = 'Ya existe un paciente con ese numero de historia';
  END;

  -- =====================================================================
  -- DEADLOCK: SE PROPAGA, NO SE TRADUCE. Va ANTES del generico.
  --
  -- Sin este handler el deadlock (SQLSTATE '40001', errno 1213) entraba por
  -- el SQLEXCEPTION de abajo como cualquier otro error: el procedimiento
  -- hacia ROLLBACK, devolvia "error interno" y el CALL terminaba EN EXITO.
  -- Python nunca veia un OperationalError 1213, asi que
  -- @reintentar_en_deadlock no podia dispararse. El decorador estaba puesto
  -- en tres de los seis caminos de escritura donde no podia funcionar.
  --
  -- Medido por auditoria antes y despues, no deducido: con el ataque que
  -- provoca el deadlock, el contador lock_deadlocks de InnoDB subia igual
  -- —el deadlock ocurria— pero el CALL salia con exit 0.
  --
  -- RESIGNAL y no SIGNAL: reemite la condicion ORIGINAL con su SQLSTATE y su
  -- errno intactos, que es lo unico que el decorador puede reconocer.
  --
  -- El ROLLBACK va igual porque el procedimiento abre su propia transaccion:
  -- InnoDB revierte la sentencia que eligio como victima, no necesariamente
  -- la transaccion entera.
  --
  -- ESTA ES LA UNICA EXCEPCION al criterio de errores de mas arriba. Un
  -- deadlock no es un error para mostrarle a nadie: es una condicion
  -- transitoria que se resuelve reintentando, y traducirla a texto es
  -- convertir algo recuperable en un fracaso.
  --
  -- SON DOS ERRORES, NO UNO. @reintentar_en_deadlock reintenta 1213 Y 1205
  -- (lock wait timeout), asi que con solo el 40001 la mitad de la proteccion
  -- seguia sin poder dispararse. El 1205 no se puede atajar por SQLSTATE
  -- porque el suyo es 'HY000', el generico de casi todos los errores del
  -- servidor: filtrarlo asi se tragaria todo lo demas. Se ataja POR NUMERO,
  -- que MySQL admite, y el handler por numero es mas especifico que el de
  -- SQLSTATE y que el de SQLEXCEPTION.
  --
  -- Los dos handlers van en los TRES procedimientos de escritura o en
  -- ninguno: media proteccion es peor que ninguna, porque parece que esta.
  -- =====================================================================
  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_paciente = NULL;
    SET p_mensaje = 'No se pudo dar de alta el paciente por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_paciente = NULL;

  -- Validaciones FUERA de la transaccion: son lecturas y asi la primera
  -- lectura consistente de la transaccion queda despues de los locks
  SELECT COUNT(*) INTO v_existe
    FROM pacientes
   WHERE nro_historia = p_nro_historia;

  IF p_id_usuario IS NOT NULL THEN
    SELECT COUNT(*) INTO v_existe_usuario
      FROM usuarios
     WHERE id = p_id_usuario;
  END IF;

  IF v_existe > 0 THEN
    SET p_mensaje = CONCAT(
      'Ya existe un paciente con el numero de historia ', p_nro_historia);
  ELSEIF p_id_usuario IS NOT NULL AND v_existe_usuario = 0 THEN
    SET p_mensaje = 'El usuario indicado no existe';
  ELSE
    START TRANSACTION;

    INSERT INTO pacientes (
      id_usuario, nombre, apellido, fecha_nacimiento, diagnostico,
      nro_historia, activo, fecha_alta
    ) VALUES (
      p_id_usuario, p_nombre, p_apellido, p_fecha_nacimiento, p_diagnostico,
      p_nro_historia, TRUE, CURRENT_DATE
    );

    SET p_id_paciente = LAST_INSERT_ID();
    COMMIT;
    SET p_mensaje = 'Paciente registrado correctamente';
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_editar_paciente
--
-- Edita los datos del paciente. NO toca id_usuario: vincular o desvincular
-- un login es otra operacion, con su propia UNIQUE y sus propias reglas, y
-- meterla aca la escondería adentro de un formulario de datos personales.
--
-- fecha_nacimiento y nro_historia SI son editables, por indicacion de
-- planeamiento: los dos se cargan a mano en el alta y los dos se tipean mal.
-- Bloquearlos obligaria a dar de baja y volver a crear al paciente para
-- corregir un digito, y eso parte la historia clinica en dos.
--
-- Rechaza editar un paciente dado de baja. Es la misma linea que ya rige el
-- resto del modulo: su ficha se LEE, no se escribe. Para editarlo hay que
-- reactivarlo primero, que es una decision explicita y no un efecto lateral
-- de guardar un formulario.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_editar_paciente (
  IN  p_id_paciente       INT UNSIGNED,
  IN  p_nombre            VARCHAR(100),
  IN  p_apellido          VARCHAR(100),
  IN  p_fecha_nacimiento  DATE,
  IN  p_diagnostico       TEXT,
  IN  p_obra_social       VARCHAR(120),
  IN  p_nro_historia      VARCHAR(30),
  OUT p_editado           TINYINT UNSIGNED,
  OUT p_mensaje           VARCHAR(255)
)
BEGIN
  DECLARE v_existe    INT UNSIGNED DEFAULT 0;
  DECLARE v_activo    BOOLEAN      DEFAULT NULL;
  DECLARE v_duplicado INT UNSIGNED DEFAULT 0;
  DECLARE v_lock      INT UNSIGNED DEFAULT NULL;
  DECLARE v_error     VARCHAR(255) DEFAULT '';

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_editado = NULL;
    SET p_mensaje = v_error;
  END;

  -- La UNIQUE de nro_historia gana la carrera si dos ediciones simultaneas
  -- pasan el chequeo amigable de abajo. Mismo criterio que p_alta_paciente.
  DECLARE EXIT HANDLER FOR SQLSTATE '23000'
  BEGIN
    ROLLBACK;
    SET p_editado = NULL;
    SET p_mensaje = 'Ya existe un paciente con ese numero de historia';
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_editado = NULL;
    SET p_mensaje = 'No se pudo editar el paciente por un problema inesperado. Intente nuevamente.';
  END;

  SET p_editado = NULL;

  SELECT COUNT(*), MAX(activo) INTO v_existe, v_activo
    FROM pacientes
   WHERE id = p_id_paciente;

  -- El duplicado se busca en los OTROS pacientes: la propia fila no cuenta
  -- como conflicto consigo misma. Sin el id <> p_id_paciente, guardar sin
  -- cambiarle el numero de historia fallaria siempre.
  SELECT COUNT(*) INTO v_duplicado
    FROM pacientes
   WHERE nro_historia = p_nro_historia
     AND id <> p_id_paciente;

  IF v_existe = 0 THEN
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_activo = FALSE THEN
    SET p_mensaje = 'El paciente no esta en tratamiento activo: reactivelo antes de editarlo';
  ELSEIF v_duplicado > 0 THEN
    SET p_mensaje = CONCAT(
      'Ya existe un paciente con el numero de historia ', p_nro_historia);
  ELSE
    START TRANSACTION;

    SELECT id, activo INTO v_lock, v_activo
      FROM pacientes
     WHERE id = p_id_paciente
     FOR UPDATE;

    -- Relectura dentro del lock: una baja concurrente puede haber entrado
    -- entre el chequeo de arriba y este lock, y editar a un paciente recien
    -- dado de baja lo dejaria con datos nuevos y la baja puesta.
    IF v_activo = FALSE THEN
      ROLLBACK;
      SET p_editado = NULL;
      SET p_mensaje = 'El paciente no esta en tratamiento activo: reactivelo antes de editarlo';
    ELSE

    UPDATE pacientes
       SET nombre           = p_nombre,
           apellido         = p_apellido,
           fecha_nacimiento = p_fecha_nacimiento,
           diagnostico      = p_diagnostico,
           obra_social      = p_obra_social,
           nro_historia     = p_nro_historia
     WHERE id = p_id_paciente;

    COMMIT;
    SET p_editado = 1;
    SET p_mensaje = 'Paciente actualizado correctamente';
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_baja_paciente — baja LOGICA del paciente
--
-- Nunca borra: la historia clinica no se borra. Marca activo = FALSE, deja
-- fecha_baja, cierra las asignaciones vigentes y archiva los objetivos
-- activos. Las sesiones y las evoluciones NO se tocan: son hechos que
-- ocurrieron y una baja administrativa posterior no los cambia.
--
-- ORDEN DE LOCKS: pacientes -> asignaciones -> objetivos_terapeuticos.
--
-- `asignaciones` va entre `terapeutas` y `sesiones` en el orden canonico del
-- CLAUDE.md, que es donde cae por dependencia: referencia a pacientes y a
-- terapeutas, y nada la referencia a ella. Este procedimiento fue el primero
-- en tocarla junto con otras tablas; la ubicacion quedo PROPUESTA aca y
-- ADOPTADA en el orden canonico el 2026-08-12.
--
-- Las tres escrituras van en UNA transaccion. Una baja a medias —el paciente
-- inactivo pero con objetivos activos, o con asignaciones abiertas— es peor
-- que una baja que falla entera, porque el filtro de "pacientes asignados"
-- que viene en la Entrega 2 leeria una asignacion que ya no es cierta.
--
-- Sobre el GREATEST de la fecha: una asignacion puede tener fecha_desde en el
-- futuro. Cerrarla con CURRENT_DATE a secas dejaria fecha_hasta < fecha_desde
-- y trg_asignaciones_vigente_update la rechaza con 1644, o sea que UNA
-- asignacion futura haria fallar la baja entera. Se cierra en el maximo entre
-- hoy y su propio inicio: una asignacion que nunca llego a empezar queda
-- cerrada el dia en que iba a empezar, que es lo unico coherente.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_baja_paciente (
  IN  p_id_paciente           INT UNSIGNED,
  OUT p_objetivos_archivados  INT UNSIGNED,
  OUT p_asignaciones_cerradas INT UNSIGNED,
  OUT p_mensaje               VARCHAR(255)
)
BEGIN
  DECLARE v_existe  INT UNSIGNED DEFAULT 0;
  DECLARE v_activo  BOOLEAN      DEFAULT NULL;
  DECLARE v_lock    INT UNSIGNED DEFAULT NULL;
  DECLARE v_error   VARCHAR(255) DEFAULT '';

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_objetivos_archivados = NULL;
    SET p_asignaciones_cerradas = NULL;
    SET p_mensaje = v_error;
  END;

  -- Ver el bloque DEADLOCK de p_alta_paciente. Los dos handlers van en TODO
  -- procedimiento de escritura o en ninguno: media proteccion es peor que
  -- ninguna, porque parece que esta.
  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_objetivos_archivados = NULL;
    SET p_asignaciones_cerradas = NULL;
    SET p_mensaje = 'No se pudo dar de baja el paciente por un problema inesperado. Intente nuevamente.';
  END;

  SET p_objetivos_archivados = NULL;
  SET p_asignaciones_cerradas = NULL;

  SELECT COUNT(*), MAX(activo) INTO v_existe, v_activo
    FROM pacientes
   WHERE id = p_id_paciente;

  IF v_existe = 0 THEN
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_activo = FALSE THEN
    SET p_mensaje = 'El tratamiento del paciente ya estaba cerrado';
  ELSE
    START TRANSACTION;

    -- 1) pacientes. Primero por el orden canonico, y ademas porque es el lock
    --    que los triggers de las otras dos tablas toman sobre esta misma fila.
    SELECT id, activo INTO v_lock, v_activo
      FROM pacientes
     WHERE id = p_id_paciente
     FOR UPDATE;

    -- RELECTURA DENTRO DEL LOCK, y no es redundante.
    --
    -- El chequeo de mas arriba corre FUERA de la transaccion. Entre esa
    -- lectura y este lock hay una ventana real: dos bajas simultaneas leian
    -- las dos `activo = TRUE`, hacian cola en el lock, y la segunda escribia
    -- encima informando "Paciente dado de baja correctamente" con los
    -- contadores en cero. Lo demostro un test de auditoria con las dos
    -- conexiones detenidas a proposito.
    --
    -- No alcanza con bloquear: hay que VOLVER A LEER despues de bloquear. Es
    -- la misma leccion de la regla 1, donde el FOR UPDATE del padre sin
    -- relectura dejaba pasar el quinto objetivo.
    IF v_activo = FALSE THEN
      ROLLBACK;
      SET p_objetivos_archivados = NULL;
      SET p_asignaciones_cerradas = NULL;
      SET p_mensaje = 'El tratamiento del paciente ya estaba cerrado';
    ELSE

    -- Este procedimiento es el CIERRE del tratamiento (el alta del rubro).
    -- La pausa tiene el suyo: p_pausar_paciente.
    UPDATE pacientes
       SET activo = FALSE,
           fecha_baja = CURRENT_DATE,
           tipo_cierre = 'alta',
           motivo_baja = NULL
     WHERE id = p_id_paciente;

    -- 2) asignaciones: vigente es fecha_hasta IS NULL y nada mas
    UPDATE asignaciones
       SET fecha_hasta = GREATEST(fecha_desde, CURRENT_DATE)
     WHERE id_paciente = p_id_paciente
       AND fecha_hasta IS NULL;

    SET p_asignaciones_cerradas = ROW_COUNT();

    -- 3) objetivos_terapeuticos. fecha_archivado la pone
    --    trg_objetivos_limite_activos_update, no se escribe aca.
    UPDATE objetivos_terapeuticos
       SET activo = FALSE
     WHERE id_paciente = p_id_paciente
       AND activo = TRUE;

    SET p_objetivos_archivados = ROW_COUNT();

    COMMIT;
    SET p_mensaje = 'Alta del tratamiento registrada correctamente';
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_reactivar_paciente — deshace la baja, y NADA MAS
--
-- Un tratamiento que se retoma es un escenario clinico normal, asi que la
-- baja no es definitiva. Pero reactivar NO desarchiva los objetivos ni
-- reabre las asignaciones, y eso es deliberado:
--
--   - Los objetivos los elige la terapeuta al retomar. Desarchivarlos todos
--     podria ademas pasarse del limite de 4 activos si mientras tanto se
--     cargaron otros, y el trigger rechazaria la reactivacion entera por una
--     razon que no tiene nada que ver con lo que se pidio.
--   - Una asignacion cerrada dice quien lo atendia ANTES. Reabrirla afirmaria
--     que esa terapeuta lo sigue atendiendo, que es justo lo que no se sabe.
--
-- Toca una sola tabla, pero lleva los mismos handlers: es un camino de
-- escritura y el decorador de Python necesita ver el 1213 y el 1205.
-- ---------------------------------------------------------------------
-- p_reactivado sale en 1 si la reactivacion ocurrio y en NULL si se rechazo,
-- igual que p_id_paciente en p_alta_paciente. El llamador NO tiene que
-- deducir el resultado del texto de p_mensaje: comparar mensajes es la misma
-- trampa que duplicar una regla de negocio en el backend, porque cambiar una
-- palabra del mensaje rompe silenciosamente al que lo estaba comparando.
CREATE PROCEDURE p_reactivar_paciente (
  IN  p_id_paciente  INT UNSIGNED,
  OUT p_reactivado   TINYINT UNSIGNED,
  OUT p_mensaje      VARCHAR(255)
)
BEGIN
  DECLARE v_existe  INT UNSIGNED DEFAULT 0;
  DECLARE v_activo  BOOLEAN      DEFAULT NULL;
  DECLARE v_lock    INT UNSIGNED DEFAULT NULL;
  DECLARE v_error   VARCHAR(255) DEFAULT '';

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_reactivado = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_reactivado = NULL;
    SET p_mensaje = 'No se pudo reactivar el paciente por un problema inesperado. Intente nuevamente.';
  END;

  SET p_reactivado = NULL;

  SELECT COUNT(*), MAX(activo) INTO v_existe, v_activo
    FROM pacientes
   WHERE id = p_id_paciente;

  IF v_existe = 0 THEN
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_activo = TRUE THEN
    SET p_mensaje = 'El paciente ya estaba activo';
  ELSE
    START TRANSACTION;

    SELECT id, activo INTO v_lock, v_activo
      FROM pacientes
     WHERE id = p_id_paciente
     FOR UPDATE;

    -- Relectura dentro del lock. Ver el comentario largo de p_baja_paciente:
    -- dos reactivaciones simultaneas tenian la misma ventana.
    IF v_activo = TRUE THEN
      ROLLBACK;
      SET p_reactivado = NULL;
      SET p_mensaje = 'El paciente ya estaba activo';
    ELSE
      UPDATE pacientes
         SET activo = TRUE,
             fecha_baja = NULL,
             tipo_cierre = NULL,
             motivo_baja = NULL
       WHERE id = p_id_paciente;

      COMMIT;
      SET p_reactivado = 1;
      SET p_mensaje = 'Paciente reactivado correctamente';
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_pausar_paciente — la BAJA del rubro: el tratamiento se interrumpe
--
-- Distinta del cierre (p_baja_paciente, el alta): pausar es reversible y no
-- desarma nada. El paciente deja de figurar en los listados operativos y no
-- admite sesiones nuevas, pero conserva sus objetivos activos y su
-- asignacion, para retomar donde quedo con p_reactivar_paciente. Por eso el
-- MOTIVO es obligatorio: es lo que explica la interrupcion cuando se vuelve
-- a mirar la ficha.
--
-- Mismos handlers y mismo orden de locks que p_baja_paciente. Con
-- p_pausado en NULL se rechazo; no se deduce del texto de p_mensaje.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_pausar_paciente (
  IN  p_id_paciente  INT UNSIGNED,
  IN  p_motivo       VARCHAR(255),
  OUT p_pausado      TINYINT UNSIGNED,
  OUT p_mensaje      VARCHAR(255)
)
BEGIN
  DECLARE v_existe  INT UNSIGNED DEFAULT 0;
  DECLARE v_activo  BOOLEAN      DEFAULT NULL;
  DECLARE v_lock    INT UNSIGNED DEFAULT NULL;
  DECLARE v_error   VARCHAR(255) DEFAULT '';
  DECLARE v_motivo  VARCHAR(255) DEFAULT TRIM(COALESCE(p_motivo, ''));

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_pausado = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_pausado = NULL;
    SET p_mensaje = 'No se pudo pausar el tratamiento por un problema inesperado. Intente nuevamente.';
  END;

  SET p_pausado = NULL;

  SELECT COUNT(*), MAX(activo) INTO v_existe, v_activo
    FROM pacientes
   WHERE id = p_id_paciente;

  IF v_existe = 0 THEN
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF CHAR_LENGTH(v_motivo) = 0 THEN
    SET p_mensaje = 'La pausa necesita un motivo';
  ELSEIF CHAR_LENGTH(v_motivo) > 200 THEN
    SET p_mensaje = 'El motivo de la pausa no puede superar los 200 caracteres';
  ELSEIF v_activo = FALSE THEN
    SET p_mensaje = 'El tratamiento del paciente ya estaba cerrado';
  ELSE
    START TRANSACTION;

    SELECT id, activo INTO v_lock, v_activo
      FROM pacientes
     WHERE id = p_id_paciente
     FOR UPDATE;

    -- Relectura dentro del lock: ver p_baja_paciente.
    IF v_activo = FALSE THEN
      ROLLBACK;
      SET p_mensaje = 'El tratamiento del paciente ya estaba cerrado';
    ELSE
      UPDATE pacientes
         SET activo = FALSE,
             fecha_baja = CURRENT_DATE,
             tipo_cierre = 'pausa',
             motivo_baja = v_motivo
       WHERE id = p_id_paciente;

      COMMIT;
      SET p_pausado = 1;
      SET p_mensaje = 'Tratamiento pausado correctamente';
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_registrar_sesion — regla 6
--
-- Detecta superposicion horaria del TERAPEUTA. Si hora_fin es NULL se
-- asume una hora de duracion, tanto para la sesion nueva como para las
-- que ya estan cargadas.
--
-- Dos rangos se solapan si: inicio_nuevo < fin_viejo Y fin_nuevo > inicio_viejo.
-- Se usa < y > (no <=) a proposito: una sesion que termina 10:00 y otra
-- que arranca 10:00 no se solapan, se tocan.
--
-- Las sesiones marcadas como 'ausencia' TAMBIEN bloquean el horario: el
-- paciente falto, pero el terapeuta tenia el turno ocupado igual.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_registrar_sesion (
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_id_paciente   INT UNSIGNED,
  IN  p_fecha         DATE,
  IN  p_hora_inicio   TIME,
  IN  p_hora_fin      TIME,
  IN  p_estado        VARCHAR(20),
  -- Quien falto, solo cuando p_estado='ausencia'. NULL en cualquier otro
  -- caso. La consistencia entre los dos la valida el trigger de INSERT,
  -- no este procedimiento — ver AUSENCIA Y QUIEN FALTO TIENEN QUE VIAJAR
  -- JUNTOS en trg_sesiones_solape_insert.
  --
  -- PARAMETRO NUEVO (2026-09-10): agregarlo cambio la aridad del
  -- procedimiento, asi que todo CALL existente con 7 argumentos posicionales
  -- deja de compilar. El unico llamador que este cambio pudo corregir es
  -- `sesiones_service.py` (backend, no es tests/). Los CALL directos de
  -- `tests/db` y `tests/backend` quedan rotos a proposito: tests/ es de
  -- auditoria, no se toca desde aca. Ver la nota para la otra terminal en
  -- ESTADO.md.
  IN  p_ausencia_de   VARCHAR(20),
  IN  p_notas         TEXT,
  OUT p_id_sesion     INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_hora_fin      TIME         DEFAULT NULL;
  DECLARE v_superpuestas  INT UNSIGNED DEFAULT 0;
  DECLARE v_existe_ter    INT UNSIGNED DEFAULT 0;
  DECLARE v_existe_pac    INT UNSIGNED DEFAULT 0;
  DECLARE v_activo_pac    BOOLEAN      DEFAULT NULL;
  DECLARE v_fecha_baja    DATE         DEFAULT NULL;
  DECLARE v_lock          INT UNSIGNED DEFAULT NULL;
  DECLARE v_error         VARCHAR(255) DEFAULT '';

  -- Ver CRITERIO GENERAL DE ERRORES
  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_sesion = NULL;
    SET p_mensaje = v_error;
  END;

  -- Deadlock (40001) y lock wait timeout (1205) se propagan tal cual, ANTES
  -- del generico. El desarrollo completo del porque esta en p_alta_paciente;
  -- los tres procedimientos de escritura llevan los mismos dos handlers y se
  -- tocan juntos o no se toca ninguno.
  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_sesion = NULL;
    SET p_mensaje = 'No se pudo registrar la sesion por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_sesion = NULL;

  -- Si no se informa hora de fin, se asume una hora de duracion
  SET v_hora_fin = IFNULL(p_hora_fin, ADDTIME(p_hora_inicio, '01:00:00'));

  -- Validacion de FK antes de tocar nada, para no depender del error nativo
  SELECT COUNT(*) INTO v_existe_ter FROM terapeutas WHERE id = p_id_terapeuta;
  SELECT COUNT(*), MAX(activo), MAX(fecha_baja)
    INTO v_existe_pac, v_activo_pac, v_fecha_baja
    FROM pacientes WHERE id = p_id_paciente;

  IF v_existe_ter = 0 THEN
    SET p_mensaje = 'El terapeuta indicado no existe';
  ELSEIF v_existe_pac = 0 THEN
    SET p_mensaje = 'El paciente indicado no existe';
  -- CERRADO 2026-09-10 (hallazgo C1): hasta hoy esta rama no existia y el
  -- INSERT de mas abajo hacia IFNULL(p_estado, 'incompleta'). Un CALL
  -- directo sin estado entraba igual, declarado como si alguien hubiera
  -- dicho "incompleta" sin haberlo dicho — el mismo hallazgo que ya se
  -- habia cerrado del lado de Python (`registrar_sesion`), eludido por
  -- este otro camino de escritura. Medido antes de aplicar: los 14
  -- llamadores de este procedimiento en todo el repo (`grep -rn "CALL
  -- p_registrar_sesion("`) mandan un estado explicito, ninguno dependia
  -- del default.
  ELSEIF p_estado IS NULL OR p_estado = '' THEN
    SET p_mensaje = 'El estado es obligatorio';
  -- Agregado el 2026-08-12, con el modulo de baja. Hasta ese dia el
  -- procedimiento validaba que el paciente EXISTIERA y nada mas, y lo unico
  -- que impedia agendarle una sesion a alguien dado de baja era que no
  -- apareciera en el desplegable: una proteccion de interfaz, que un CALL
  -- directo, un script o un cliente cualquiera esquiva sin enterarse.
  --
  -- LA CARGA RETROACTIVA SI SE PERMITE: el corte es la FECHA de la sesion
  -- contra fecha_baja, no el estado del paciente. El caso real es la terapeuta
  -- que atendio el viernes y recien carga el lunes; si entre medio el paciente
  -- se dio de baja, esa sesion ocurrio igual y tiene que poder registrarse.
  -- Lo que se rechaza es una sesion POSTERIOR a la baja, que no ocurrio.
  --
  -- Sin esto la unica salida era reactivar, cargar y volver a dar de baja, que
  -- ademas pisa fecha_baja: la correccion de un olvido administrativo
  -- terminaba falseando la fecha del alta medica.
  --
  -- fecha_baja NULL con el paciente inactivo no deberia existir —la pone la
  -- misma sentencia que apaga `activo`— pero si apareciera no hay con que
  -- comparar, y ante un estado incoherente se rechaza en vez de adivinar.
  ELSEIF v_activo_pac = FALSE
     AND (v_fecha_baja IS NULL OR p_fecha > v_fecha_baja) THEN
    SET p_mensaje = 'El paciente no esta en tratamiento activo: solo se pueden cargar sesiones hasta el dia del cierre';
  ELSEIF v_hora_fin <= p_hora_inicio THEN
    SET p_mensaje = 'La hora de fin debe ser posterior a la hora de inicio';
  ELSE
    START TRANSACTION;

    -- PACIENTES PRIMERO, y el chequeo de activo se REHACE aca adentro.
    --
    -- El chequeo de arriba corre fuera de la transaccion y por si solo no
    -- sirve: auditoria demostro la ventana con las dos conexiones detenidas
    -- —la victima pasaba el chequeo, quedaba esperando el lock de terapeutas,
    -- la baja entraba, y la sesion terminaba insertada sobre un paciente ya
    -- dado de baja—. Se toma FOR SHARE, no FOR UPDATE: alcanza con impedir
    -- que una baja escriba esa fila mientras dura esta transaccion, y dos
    -- sesiones de pacientes distintos no tienen por que serializarse.
    --
    -- Va ANTES de terapeutas por el orden canonico de locks del CLAUDE.md
    -- (pacientes -> terapeutas -> ...). Invertirlo es la decision 12 otra vez.
    --
    -- fecha_baja se lee EN ESTE MISMO SELECT y no antes. Leerla afuera y
    -- comparar aca adentro seria el mismo TOCTOU que el chequeo de `activo`
    -- que se corrigio hoy: entre las dos operaciones la baja puede entrar y
    -- cambiar justamente el valor contra el que se compara. El dato con el que
    -- se decide tiene que venir de la lectura que sostiene el lock.
    SELECT activo, fecha_baja INTO v_activo_pac, v_fecha_baja
      FROM pacientes
     WHERE id = p_id_paciente
     FOR SHARE;

    IF v_activo_pac = FALSE
       AND (v_fecha_baja IS NULL OR p_fecha > v_fecha_baja) THEN
      ROLLBACK;
      SET p_id_sesion = NULL;
      SET p_mensaje = 'El paciente no esta en tratamiento activo: solo se pueden cargar sesiones hasta el dia del cierre';
    ELSE

    -- Ver NOTA DE CONCURRENCIA. Mismo orden que el trigger de sesiones:
    -- terapeutas primero, sesiones despues. El trigger vuelve a pedir este
    -- mismo lock durante el INSERT: como ya lo tiene esta transaccion, no
    -- espera. Invertir el orden entre ambos introduciria un deadlock.
    SELECT id INTO v_lock
      FROM terapeutas
     WHERE id = p_id_terapeuta
     FOR UPDATE;

    SELECT COUNT(*) INTO v_superpuestas
      FROM sesiones
     WHERE id_terapeuta = p_id_terapeuta
       AND fecha = p_fecha
       AND p_hora_inicio < IFNULL(hora_fin, ADDTIME(hora_inicio, '01:00:00'))
       AND v_hora_fin > hora_inicio
     FOR SHARE;

    IF v_superpuestas > 0 THEN
      ROLLBACK;
      -- Sin la cantidad: "1 sesion(es)" no concordaba y el numero no ayuda.
      SET p_mensaje = 'El terapeuta ya tiene sesiones que se superponen con ese horario';
    ELSE
      INSERT INTO sesiones (
        id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado,
        ausencia_de, notas
      ) VALUES (
        p_id_terapeuta, p_id_paciente, p_fecha, p_hora_inicio, p_hora_fin,
        p_estado, p_ausencia_de, p_notas
      );

      SET p_id_sesion = LAST_INSERT_ID();
      COMMIT;
      SET p_mensaje = 'Sesion registrada correctamente';
    END IF;
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_editar_sesion
--
-- Edita estado, notas, fecha, hora_inicio y hora_fin de una sesion ya
-- registrada. id_terapeuta e id_paciente NO se editan por esta puerta: el
-- terapeuta lo fija el login (igual que en p_registrar_sesion) y el
-- paciente es un hecho de la sesion, no un dato que se corrija aca.
--
-- AUTORIA — mismo criterio que p_registrar_evolucion (decision 20).
-- p_id_terapeuta es quien esta editando, no el dueno de la sesion. El 403
-- de Python es la primera linea; esta revalidacion es la segunda, para que
-- un CALL directo sin pasar por Flask de el mismo veredicto que la API.
-- p_id_terapeuta NULL se rechaza igual que un id que no coincide.
--
-- ORDEN DE LOCKS — pacientes FOR SHARE SIEMPRE, no solo cuando cambia la
-- fecha. Es la misma convencion que p_registrar_sesion (ver la NOTA DE
-- CONCURRENCIA al pie de los triggers de sesiones, mas arriba en este
-- archivo): si el UPDATE dispara el chequeo de fecha_baja de
-- trg_sesiones_solape_update -que solo corre cuando cambia fecha o
-- id_paciente-, ese trigger vuelve a pedir el mismo lock que esta
-- transaccion ya tiene, y no espera. Sostener la propiedad para CUALQUIER
-- edicion -no solo las que tocan la fecha- evita tener que razonar caso
-- por caso cual UPDATE la necesita, que es justo lo que ya fallo tres
-- veces en este repo (hallazgo C1/A1).
--
-- LO QUE ESTE PROCEDIMIENTO NO REVALIDA, A PROPOSITO: superposicion de
-- horario, sesion posterior a la baja del paciente, y ausencia con
-- evoluciones ya cargadas. Las tres las aplica trg_sesiones_solape_update,
-- que las revalida exactamente cuando el campo del que dependen cambia.
-- Repetirlas aca duplicaria una regla que ya vive en un solo lugar.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_editar_sesion (
  IN  p_id_sesion     INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_estado        VARCHAR(20),
  -- Quien falto, mismo criterio que p_registrar_sesion (ver ahi el porque
  -- de la consistencia y el mensaje). NUEVO 2026-09-11, cambia la aridad:
  -- el unico llamador de este procedimiento en todo el repo es
  -- `sesiones_service.py` (`grep -rn "p_editar_sesion" tests/db
  -- tests/backend` no da nada fuera de _respaldos), asi que no hay ningun
  -- CALL en tests/ que se rompa por este parametro.
  IN  p_ausencia_de   VARCHAR(20),
  IN  p_notas         TEXT,
  IN  p_fecha         DATE,
  IN  p_hora_inicio   TIME,
  IN  p_hora_fin      TIME,
  OUT p_editado       TINYINT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error        VARCHAR(255) DEFAULT '';
  DECLARE v_ter_sesion   INT UNSIGNED DEFAULT NULL;
  DECLARE v_id_paciente  INT UNSIGNED DEFAULT NULL;
  DECLARE v_lock         INT UNSIGNED DEFAULT NULL;
  DECLARE v_dupla        INT UNSIGNED DEFAULT NULL;
  DECLARE v_fecha_ant    DATE         DEFAULT NULL;
  DECLARE v_inicio_ant   TIME         DEFAULT NULL;
  DECLARE v_fin_ant      TIME         DEFAULT NULL;
  DECLARE v_pacientes    INT UNSIGNED DEFAULT 0;

  -- Ver CRITERIO GENERAL DE ERRORES
  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_editado = NULL;
    SET p_mensaje = v_error;
  END;

  -- Deadlock (40001) y lock wait timeout (1205) se propagan tal cual, ANTES
  -- del generico. Ver p_alta_paciente para el desarrollo completo.
  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_editado = NULL;
    SET p_mensaje = 'No se pudo editar la sesion por un problema inesperado. Intente nuevamente.';
  END;

  SET p_editado = NULL;

  -- id_terapeuta e id_paciente son inmutables para una sesion (ninguna
  -- puerta de escritura los toca), asi que leerlos sin lock antes de la
  -- transaccion es seguro: no hay escritor concurrente que pueda
  -- cambiarlos entre esta lectura y el UPDATE de abajo.
  SELECT id_terapeuta, id_paciente, id_dupla, fecha, hora_inicio, hora_fin
    INTO v_ter_sesion, v_id_paciente, v_dupla, v_fecha_ant, v_inicio_ant, v_fin_ant
    FROM sesiones
   WHERE id = p_id_sesion;

  IF v_ter_sesion IS NULL THEN
    SET p_mensaje = 'La sesion indicada no existe';
  ELSEIF p_id_terapeuta IS NULL OR p_id_terapeuta <> v_ter_sesion THEN
    SET p_mensaje = 'Solo el terapeuta que atendio la sesion puede editarla';
  ELSE
    START TRANSACTION;

    -- Ver ORDEN DE LOCKS arriba: SIEMPRE, no solo si cambia la fecha.
    SELECT id INTO v_lock
      FROM pacientes
     WHERE id = v_id_paciente
     FOR SHARE;

    -- DUPLAS (Entrega 5): una dupla comparte dia y horario. Reprogramar una
    -- de las dos sesiones MUEVE LAS DOS, en una sola sentencia: dos UPDATE
    -- sueltos dejarian a la primera fila viendo a la hermana todavia en el
    -- horario viejo. Estado, quien falto y notas siguen siendo de cada
    -- sesion y se actualizan abajo solo en la editada. Se toma tambien el
    -- lock de los pacientes de la dupla (en orden de id, como el resto).
    IF v_dupla IS NOT NULL
       AND (p_fecha <> v_fecha_ant
            OR p_hora_inicio <> v_inicio_ant
            OR NOT (p_hora_fin <=> v_fin_ant)) THEN
      SELECT COUNT(*) INTO v_pacientes
        FROM pacientes
       WHERE id IN (SELECT id_paciente FROM sesiones WHERE id_dupla = v_dupla)
       ORDER BY id
       FOR SHARE;

      UPDATE sesiones
         SET fecha       = p_fecha,
             hora_inicio = p_hora_inicio,
             hora_fin    = p_hora_fin
       WHERE id_dupla = v_dupla;
    END IF;

    UPDATE sesiones
       SET estado      = p_estado,
           ausencia_de = p_ausencia_de,
           notas       = p_notas,
           fecha       = p_fecha,
           hora_inicio = p_hora_inicio,
           hora_fin    = p_hora_fin
     WHERE id = p_id_sesion;

    COMMIT;
    SET p_editado = 1;
    SET p_mensaje = 'Sesion actualizada correctamente';
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_registrar_evolucion
--
-- Inserta y traduce el error de los triggers a un mensaje legible. Los
-- triggers ya emiten texto en castellano, asi que se propaga tal cual;
-- lo que se agrega es el manejo de la UNIQUE y del CHECK, que si no
-- saldrian como error crudo de MySQL.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_registrar_evolucion (
  IN  p_id_sesion      INT UNSIGNED,
  IN  p_id_objetivo    INT UNSIGNED,
  IN  p_valor          TINYINT UNSIGNED,
  IN  p_observaciones  TEXT,
  IN  p_id_terapeuta   INT UNSIGNED,
  OUT p_id_evolucion   INT UNSIGNED,
  OUT p_mensaje        VARCHAR(255)
)
BEGIN
  DECLARE v_error         VARCHAR(255) DEFAULT '';
  DECLARE v_ter_sesion    INT UNSIGNED DEFAULT NULL;

  -- Los SIGNAL de los triggers: ya vienen en castellano y acotados
  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_evolucion = NULL;
    SET p_mensaje = v_error;
  END;

  -- Violacion de integridad: duplicado de (sesion, objetivo) o FK rota
  DECLARE EXIT HANDLER FOR SQLSTATE '23000'
  BEGIN
    ROLLBACK;
    SET p_id_evolucion = NULL;
    SET p_mensaje =
      'Ya existe una evolucion para ese objetivo en esa sesion';
  END;

  -- Deadlock (40001) y lock wait timeout (1205) se propagan tal cual, ANTES
  -- del generico. Ver p_alta_paciente.
  --
  -- Este es EL caso que encontro la auditoria, y no es casual que sea este:
  -- es el escenario de la decision 12 —sesiones y objetivos_terapeuticos via
  -- el trigger de evoluciones—, el unico deadlock reproducible que el
  -- proyecto tiene documentado. El decorador estaba puesto justo donde no
  -- llegaba.
  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  -- Ver CRITERIO GENERAL DE ERRORES: mensaje fijo, nunca texto de MySQL
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_evolucion = NULL;
    SET p_mensaje = 'No se pudo registrar la evolucion por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_evolucion = NULL;

  -- --- Autoria de la evolucion ---
  --
  -- Una evolucion es la valoracion clinica de quien atendio la sesion.
  -- Cargarla en nombre de otro falsea la autoria de la historia clinica de
  -- forma irreversible, y estos registros respaldan el tratamiento ante
  -- obras sociales e instituciones.
  --
  -- HASTA DONDE LLEGA ESTA VALIDACION, Y HASTA DONDE NO:
  --
  -- No cierra el agujero del todo. La base NO sabe quien esta logueado, asi
  -- que un INSERT directo contra evoluciones sigue sin ningun control de
  -- autoria. No hay forma de resolver eso desde aca sin una sesion de base
  -- por usuario, que este proyecto no tiene.
  --
  -- Lo que si logra: que cualquier camino que use este procedimiento tenga
  -- que DECLARAR quien registra, en vez de asumirlo. Un script de carga
  -- masiva, una migracion o un endpoint nuevo no pueden llamarlo "de
  -- pasada" sin decidir a nombre de quien escriben. La validacion del
  -- backend deja de ser la unica.
  --
  -- ENTREGA 4 — DUPLAS TERAPEUTICAS: ESTA VALIDACION NO SE AFLOJA.
  --
  -- Hasta el 2026-08-07 esta nota decia lo contrario: que en la Entrega 4 la
  -- condicion se ampliaba de "quien atendio" a "quien atendio O SU DUPLA",
  -- con un OR EXISTS contra duplas_terapeuticas. Era falso, y salia de
  -- confundir dos conceptos distintos.
  --
  -- Una dupla es UNA terapeuta con DOS NINIOS. Hay una sola profesional y
  -- carga las dos evoluciones a su nombre, asi que la autoria nunca entra en
  -- conflicto: p_registrar_evolucion NO cambia por este motivo. Lo que la
  -- Entrega 4 abre es el SOLAPE de sesiones que comparten sesiones.id_dupla
  -- —regla 6, en los dos triggers de solape y en el conteo propio de
  -- p_registrar_sesion—, que es otra regla y esta en otro lado.
  --
  -- "Quien atendio O su dupla" describia el caso INTERDISCIPLINARIO (dos
  -- profesionales, un paciente), que queda fuera del alcance de AsisTO. La
  -- tabla duplas_terapeuticas, que modelaba ese caso, fue eliminada.
  --
  -- p_id_terapeuta NULL se rechaza a proposito: obliga a declararlo.
  SELECT id_terapeuta INTO v_ter_sesion FROM sesiones WHERE id = p_id_sesion;

  IF v_ter_sesion IS NOT NULL
     AND (p_id_terapeuta IS NULL OR p_id_terapeuta <> v_ter_sesion) THEN
    SET p_mensaje =
      'Solo el terapeuta que atendio la sesion puede cargarle evolucion';
  -- Se valida antes del INSERT para dar un mensaje claro en vez del
  -- error crudo del CHECK constraint
  ELSEIF p_valor IS NULL OR p_valor < 1 OR p_valor > 5 THEN
    SET p_mensaje = 'El valor de la evolucion debe estar entre 1 y 5';
  ELSE
    START TRANSACTION;

    INSERT INTO evoluciones (id_sesion, id_objetivo, valor, observaciones)
    VALUES (p_id_sesion, p_id_objetivo, p_valor, p_observaciones);

    SET p_id_evolucion = LAST_INSERT_ID();
    COMMIT;
    SET p_mensaje = 'Evolucion registrada correctamente';
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_evolucion_paciente
-- Historia de evoluciones de un paciente por rango de fechas.
-- La usan HDU3 (seguimiento), HDU7 (graficos) y HDU10 (informes).
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_evolucion_paciente (
  IN  p_id_paciente  INT UNSIGNED,
  IN  p_fecha_desde  DATE,
  IN  p_fecha_hasta  DATE,
  OUT p_mensaje      VARCHAR(255)
)
BEGIN
  DECLARE v_total    INT UNSIGNED DEFAULT 0;
  DECLARE v_existe   INT UNSIGNED DEFAULT 0;

  -- Ver CRITERIO GENERAL DE ERRORES: mensaje fijo, nunca texto de MySQL
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    SET p_mensaje = 'No se pudo consultar la evolucion por un problema inesperado. Intente nuevamente.';
  END;

  SELECT COUNT(*) INTO v_existe FROM pacientes WHERE id = p_id_paciente;

  IF v_existe = 0 THEN
    SET p_mensaje = 'El paciente indicado no existe';
  ELSE
    -- =================================================================
    -- UNA FILA POR (SESION, OBJETIVO VIVO EN ESA SESION).
    --
    -- Reescrito el 2026-08-13 para el modulo de graficos. Antes era un
    -- JOIN contra `evoluciones`, asi que solo devolvia lo CALIFICADO: una
    -- sesion donde ese objetivo no se califico no existia en la salida, y
    -- el grafico no tenia con que distinguir "no se midio" de "no hubo
    -- sesion". Son cosas distintas y la diferencia es clinica.
    --
    -- Ahora el LEFT JOIN devuelve las dos: `valor` NULL es exactamente
    -- "esa sesion ocurrio y este objetivo no se califico". El llamador no
    -- tiene que coser dos listas.
    --
    -- QUE OBJETIVOS SON SERIE: los que estaban VIVOS al momento de cada
    -- sesion, no los activos de hoy. Es la misma condicion de
    -- _conteo_de_objetivos (el denominador historico de H2), y va aca por
    -- el mismo motivo: si las series salieran de los activos de hoy, una
    -- sesion de marzo que califico un objetivo archivado en mayo no
    -- tendria linea a la que pertenecer y el pasado perderia datos.
    --
    -- fecha_archivado viaja para que la linea de un objetivo archivado
    -- pueda TERMINAR donde se archivo, en vez de quedar abierta.
    --
    -- LIMITE CONOCIDO, el mismo de H2: si un objetivo se archivo, se
    -- reactivo y se volvio a archivar, solo sobrevive la ultima
    -- fecha_archivado, asi que en el primer tramo puede no aparecer como
    -- vivo. Resolverlo pide una tabla de historial de estados.
    --
    -- SEGUNDO LIMITE: un objetivo sin NINGUNA sesion en el periodo no
    -- aparece. No tiene puntos que dibujar, asi que seria una serie vacia.
    -- =================================================================
    SELECT
      s.id                    AS id_sesion,
      s.fecha,
      s.hora_inicio,
      s.estado                AS estado_sesion,
      o.id                    AS id_objetivo,
      o.descripcion           AS objetivo,
      o.activo                AS objetivo_activo,
      o.fecha_archivado,
      e.valor,
      e.observaciones,
      CONCAT(u.apellido, ', ', u.nombre) AS terapeuta
      FROM sesiones s
      JOIN objetivos_terapeuticos o
        ON o.id_paciente = s.id_paciente
       AND o.fecha_creacion <= TIMESTAMP(s.fecha, s.hora_inicio)
       AND (o.activo = TRUE
            OR o.fecha_archivado > TIMESTAMP(s.fecha, s.hora_inicio))
      LEFT JOIN evoluciones e        ON e.id_sesion = s.id
                                    AND e.id_objetivo = o.id
      JOIN terapeutas t              ON t.id = s.id_terapeuta
      JOIN usuarios u                ON u.id = t.id_usuario
     WHERE s.id_paciente = p_id_paciente
       AND s.fecha BETWEEN p_fecha_desde AND p_fecha_hasta
     ORDER BY o.id, s.fecha, s.hora_inicio;

    SELECT COUNT(*) INTO v_total
      FROM sesiones s
      JOIN evoluciones e ON e.id_sesion = s.id
     WHERE s.id_paciente = p_id_paciente
       AND s.fecha BETWEEN p_fecha_desde AND p_fecha_hasta;

    SET p_mensaje = CONCAT('Se encontraron ', v_total, ' evoluciones en el periodo');
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_registrar_observacion_rrhh — modulo RRHH
--
-- LA UNICA ESCRITURA QUE TIENE EL ROL RRHH EN TODO EL SISTEMA. Hasta hoy
-- (2026-09-14) ese rol solo leia: `observaciones_rrhh` existia como tabla
-- desde el schema original y no tenia ningun camino de escritura.
--
-- QUE ES Y QUE NO ES. Es un comentario ADMINISTRATIVO sobre una sesion —
-- llego tarde, faltaba material, se aviso a coordinacion— para dejar
-- constancia. NO es contenido clinico y NO reemplaza ni toca
-- `sesiones.notas`, que es del terapeuta. Son dos campos de dos personas
-- distintas sobre el mismo hecho.
--
-- NO TOCA LA SESION. Ni un UPDATE sobre `sesiones`: la observacion es una
-- fila aparte que la referencia por FK. Una sesion puede tener varias, o
-- ninguna, y borrar la sesion se las lleva (ON DELETE CASCADE), que es lo
-- correcto: una observacion sobre una sesion que no existe no significa
-- nada.
--
-- ORDEN DE LOCKS: `sesiones` -> `observaciones_rrhh`.
--
-- `observaciones_rrhh` no estaba en el orden canonico porque hasta hoy nada
-- la escribia. Se ubica AL FINAL, despues de `evoluciones`, y no es una
-- decision nueva: es el criterio que ya fija el orden —una tabla se toma
-- despues de todas las que referencia— aplicado a una tabla que referencia
-- a `sesiones` y a `rrhh` y a la que no apunta nadie.
--
-- El SELECT sobre `sesiones` va FOR SHARE y no es decorativo: sin el, la
-- sesion puede borrarse entre la verificacion y el INSERT, y el INSERT
-- fallaria por FK con un errno que el usuario no puede interpretar. Con el
-- lock, o la sesion sigue estando o el rechazo sale con mensaje propio.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_registrar_observacion_rrhh (
  IN  p_id_sesion      INT UNSIGNED,
  IN  p_id_rrhh        INT UNSIGNED,
  IN  p_texto          TEXT,
  OUT p_id_observacion INT UNSIGNED,
  OUT p_mensaje        VARCHAR(255)
)
BEGIN
  DECLARE v_error     VARCHAR(255) DEFAULT '';
  DECLARE v_sesion    INT UNSIGNED DEFAULT NULL;
  DECLARE v_rrhh      INT UNSIGNED DEFAULT NULL;

  -- Ver CRITERIO GENERAL DE ERRORES
  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_observacion = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_observacion = NULL;
    SET p_mensaje = 'No se pudo registrar la observacion por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_observacion = NULL;

  -- El texto vacio se rechaza ACA y no se deja en la columna NOT NULL: una
  -- cadena de espacios pasa el NOT NULL y deja una observacion que no dice
  -- nada, que es peor que no tenerla.
  IF p_texto IS NULL OR TRIM(p_texto) = '' THEN
    SET p_mensaje = 'La observacion no puede estar vacia';
  ELSEIF p_id_rrhh IS NULL THEN
    SET p_mensaje = 'Falta indicar quien registra la observacion';
  ELSE
    START TRANSACTION;

    -- 1) sesiones, primero en el orden y con lock: es la fila de la que
    --    cuelga todo lo demas.
    SELECT id INTO v_sesion
      FROM sesiones
     WHERE id = p_id_sesion
     FOR SHARE;

    SELECT id INTO v_rrhh
      FROM rrhh
     WHERE id = p_id_rrhh;

    IF v_sesion IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'La sesion indicada no existe';
    ELSEIF v_rrhh IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El usuario de RRHH indicado no existe';
    ELSE
      -- 2) observaciones_rrhh, ultima. `fecha_registro` la pone la columna
      --    con su DEFAULT: la hora la decide la base y no el cliente.
      INSERT INTO observaciones_rrhh (id_sesion, id_rrhh, texto)
      VALUES (p_id_sesion, p_id_rrhh, TRIM(p_texto));

      SET p_id_observacion = LAST_INSERT_ID();

      COMMIT;
      SET p_mensaje = 'Observacion registrada correctamente';
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_abrir_asignacion / p_cerrar_asignacion — HDU 11 (2026-10-15)
--
-- Unico camino de escritura sobre `asignaciones` desde la aplicacion (con
-- p_baja_paciente, que cierra todas las vigentes de un paciente). Existen
-- por la misma razon que el resto de los procedimientos de escritura: el
-- orden de locks y la relectura dentro del lock no se pueden garantizar
-- desde un UPDATE del ORM.
--
-- ORDEN DE LOCKS: pacientes -> terapeutas -> asignaciones, el canonico. Los
-- triggers de asignaciones vuelven a tomar `pacientes FOR UPDATE` dentro de
-- la misma transaccion; es el mismo lock que ya se tiene, no abre nada.
--
-- Las reglas de fondo (una sola vigente por par, nada abierto sobre un
-- paciente de baja, fecha_hasta >= fecha_desde) las siguen aplicando los
-- triggers: aca solo se validan las existencias, para devolver un mensaje
-- propio en vez de dejar que la FK falle con un errno ilegible.
--
-- p_fecha_desde NULL = hoy. No se acepta una fecha futura: una asignacion
-- afirma que esa terapeuta atiende al paciente, y a futuro no se sabe.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_abrir_asignacion (
  IN  p_id_paciente    INT UNSIGNED,
  IN  p_id_terapeuta   INT UNSIGNED,
  IN  p_fecha_desde    DATE,
  OUT p_id_asignacion  INT UNSIGNED,
  OUT p_mensaje        VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_terapeuta  INT UNSIGNED DEFAULT NULL;
  DECLARE v_activo     BOOLEAN      DEFAULT NULL;
  DECLARE v_desde      DATE         DEFAULT NULL;
  DECLARE v_ingreso    DATE         DEFAULT NULL;

  -- Ver CRITERIO GENERAL DE ERRORES
  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_asignacion = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_asignacion = NULL;
    SET p_mensaje = 'No se pudo abrir la asignacion por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_asignacion = NULL;
  SET v_desde = IFNULL(p_fecha_desde, CURRENT_DATE);

  IF v_desde > CURRENT_DATE THEN
    SET p_mensaje = 'La asignacion no puede empezar en una fecha futura';
  ELSE
    START TRANSACTION;

    -- 1) pacientes, con lock: lo toman igual los triggers de asignaciones
    SELECT id, activo, fecha_alta INTO v_paciente, v_activo, v_ingreso
      FROM pacientes
     WHERE id = p_id_paciente
     FOR UPDATE;

    -- 2) terapeutas
    SELECT id INTO v_terapeuta
      FROM terapeutas
     WHERE id = p_id_terapeuta
     FOR SHARE;

    IF v_paciente IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El paciente indicado no existe';
    ELSEIF v_terapeuta IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El terapeuta indicado no existe';
    ELSEIF v_activo = FALSE THEN
      ROLLBACK;
      SET p_mensaje = 'El paciente no esta en tratamiento activo: no se le pueden abrir asignaciones';
    ELSEIF v_desde < v_ingreso THEN
      -- Una asignacion anterior al ingreso del paciente dejaria cargar
      -- sesiones de fechas en que todavia no era paciente del centro.
      ROLLBACK;
      SET p_mensaje = 'La asignacion no puede empezar antes del ingreso del paciente al centro';
    ELSE
      -- 3) asignaciones. Los triggers rechazan la segunda vigente del par.
      INSERT INTO asignaciones (id_terapeuta, id_paciente, fecha_desde)
      VALUES (p_id_terapeuta, p_id_paciente, v_desde);

      SET p_id_asignacion = LAST_INSERT_ID();

      COMMIT;
      SET p_mensaje = 'Asignacion abierta correctamente';
    END IF;
  END IF;
END$$


-- p_fecha_hasta NULL = hoy, pero nunca antes de fecha_desde (mismo criterio
-- que p_baja_paciente: GREATEST). Si se pasa una fecha explicita anterior al
-- inicio, el trigger de UPDATE la rechaza con su mensaje.
CREATE PROCEDURE p_cerrar_asignacion (
  IN  p_id_asignacion  INT UNSIGNED,
  IN  p_fecha_hasta    DATE,
  OUT p_cerrada        BOOLEAN,
  OUT p_mensaje        VARCHAR(255)
)
BEGIN
  DECLARE v_error       VARCHAR(255) DEFAULT '';
  DECLARE v_paciente    INT UNSIGNED DEFAULT NULL;
  DECLARE v_lock        INT UNSIGNED DEFAULT NULL;
  DECLARE v_desde       DATE         DEFAULT NULL;
  DECLARE v_hasta       DATE         DEFAULT NULL;
  DECLARE v_existe      INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_cerrada = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_cerrada = FALSE;
    SET p_mensaje = 'No se pudo cerrar la asignacion por un problema inesperado. Intente nuevamente.';
  END;

  SET p_cerrada = FALSE;

  -- El paciente hay que conocerlo ANTES del lock para respetar el orden
  -- (pacientes primero). Esta lectura es sin lock y se REPITE adentro.
  SELECT id_paciente INTO v_paciente
    FROM asignaciones
   WHERE id = p_id_asignacion;

  IF v_paciente IS NULL THEN
    SET p_mensaje = 'La asignacion indicada no existe';
  ELSE
    START TRANSACTION;

    SELECT id INTO v_lock
      FROM pacientes
     WHERE id = v_paciente
     FOR UPDATE;

    -- Relectura dentro del lock: dos cierres simultaneos no pueden los dos
    -- ver la asignacion vigente.
    SELECT id, fecha_desde, fecha_hasta INTO v_existe, v_desde, v_hasta
      FROM asignaciones
     WHERE id = p_id_asignacion
     FOR UPDATE;

    IF v_hasta IS NOT NULL THEN
      ROLLBACK;
      SET p_mensaje = 'La asignacion ya estaba cerrada';
    ELSE
      UPDATE asignaciones
         SET fecha_hasta = IFNULL(p_fecha_hasta, GREATEST(v_desde, CURRENT_DATE))
       WHERE id = p_id_asignacion;

      COMMIT;
      SET p_cerrada = TRUE;
      SET p_mensaje = 'Asignacion cerrada correctamente';
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- Vinculo familiar-paciente (Entrega 4)
--
-- p_vincular_familiar / p_desvincular_familiar / p_crear_familiar_y_vincular.
-- El vinculo es lo que le da al familiar acceso a la evolucion del paciente
-- y a sus avisos: sin fila en familiares_pacientes no ve nada.
--
-- Orden de locks: pacientes primero, despues familiares / usuarios, despues
-- familiares_pacientes (mismo criterio que el resto: pacientes siempre abre).
-- Un paciente de baja no admite vinculos nuevos; desvincular si se permite
-- siempre, para poder limpiar el acceso.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_vincular_familiar (
  IN  p_id_familiar  INT UNSIGNED,
  IN  p_id_paciente  INT UNSIGNED,
  OUT p_ok           BOOLEAN,
  OUT p_mensaje      VARCHAR(255)
)
BEGIN
  DECLARE v_error     VARCHAR(255) DEFAULT '';
  DECLARE v_paciente  INT UNSIGNED DEFAULT NULL;
  DECLARE v_activo    BOOLEAN      DEFAULT NULL;
  DECLARE v_familiar  INT UNSIGNED DEFAULT NULL;
  DECLARE v_usuario   INT UNSIGNED DEFAULT NULL;
  DECLARE v_habilitado BOOLEAN     DEFAULT NULL;
  DECLARE v_existente INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo vincular al familiar por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  START TRANSACTION;

  SELECT id, activo INTO v_paciente, v_activo
    FROM pacientes
   WHERE id = p_id_paciente
   FOR UPDATE;

  SELECT f.id, f.id_usuario INTO v_familiar, v_usuario
    FROM familiares f
   WHERE f.id = p_id_familiar
   FOR SHARE;

  IF v_usuario IS NOT NULL THEN
    SELECT activo INTO v_habilitado FROM usuarios WHERE id = v_usuario;
  END IF;

  SELECT id_familiar INTO v_existente
    FROM familiares_pacientes
   WHERE id_familiar = p_id_familiar AND id_paciente = p_id_paciente
   FOR UPDATE;

  IF v_paciente IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_familiar IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El familiar indicado no existe';
  ELSEIF v_activo = FALSE THEN
    ROLLBACK;
    SET p_mensaje = 'El paciente no esta en tratamiento activo: no se le pueden vincular familiares';
  ELSEIF v_habilitado = FALSE THEN
    ROLLBACK;
    SET p_mensaje = 'La cuenta del familiar esta deshabilitada';
  ELSEIF v_existente IS NOT NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El familiar ya esta vinculado a este paciente';
  ELSE
    INSERT INTO familiares_pacientes (id_familiar, id_paciente)
    VALUES (p_id_familiar, p_id_paciente);

    COMMIT;
    SET p_ok = TRUE;
    SET p_mensaje = 'Familiar vinculado correctamente';
  END IF;
END$$


CREATE PROCEDURE p_desvincular_familiar (
  IN  p_id_familiar  INT UNSIGNED,
  IN  p_id_paciente  INT UNSIGNED,
  OUT p_ok           BOOLEAN,
  OUT p_mensaje      VARCHAR(255)
)
BEGIN
  DECLARE v_error     VARCHAR(255) DEFAULT '';
  DECLARE v_paciente  INT UNSIGNED DEFAULT NULL;
  DECLARE v_existente INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo desvincular al familiar por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  START TRANSACTION;

  SELECT id INTO v_paciente
    FROM pacientes
   WHERE id = p_id_paciente
   FOR UPDATE;

  SELECT id_familiar INTO v_existente
    FROM familiares_pacientes
   WHERE id_familiar = p_id_familiar AND id_paciente = p_id_paciente
   FOR UPDATE;

  IF v_paciente IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_existente IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El familiar no esta vinculado a este paciente';
  ELSE
    DELETE FROM familiares_pacientes
     WHERE id_familiar = p_id_familiar AND id_paciente = p_id_paciente;

    COMMIT;
    SET p_ok = TRUE;
    SET p_mensaje = 'Vinculo eliminado correctamente';
  END IF;
END$$


-- Crea la cuenta del familiar (usuario con rol familiar + perfil) y lo
-- vincula en la misma transaccion: o queda todo, o no queda nada. El hash
-- de la contrasena lo calcula la aplicacion (bcrypt); aca solo se guarda.
CREATE PROCEDURE p_crear_familiar_y_vincular (
  IN  p_nombre       VARCHAR(100),
  IN  p_apellido     VARCHAR(100),
  IN  p_email        VARCHAR(180),
  IN  p_hash         VARCHAR(255),
  IN  p_parentesco   VARCHAR(60),
  IN  p_telefono     VARCHAR(40),
  IN  p_id_paciente  INT UNSIGNED,
  OUT p_id_familiar  INT UNSIGNED,
  OUT p_mensaje      VARCHAR(255)
)
BEGIN
  DECLARE v_error     VARCHAR(255) DEFAULT '';
  DECLARE v_paciente  INT UNSIGNED DEFAULT NULL;
  DECLARE v_activo    BOOLEAN      DEFAULT NULL;
  DECLARE v_usuario   INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_familiar = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  -- 1062: dos altas simultaneas con el mismo correo; gana una sola
  DECLARE EXIT HANDLER FOR 1062
  BEGIN
    ROLLBACK;
    SET p_id_familiar = NULL;
    SET p_mensaje = 'Ya existe una cuenta con ese correo electronico';
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_familiar = NULL;
    SET p_mensaje = 'No se pudo crear al familiar por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_familiar = NULL;

  START TRANSACTION;

  SELECT id, activo INTO v_paciente, v_activo
    FROM pacientes
   WHERE id = p_id_paciente
   FOR UPDATE;

  SELECT id INTO v_usuario
    FROM usuarios
   WHERE email = p_email
   FOR UPDATE;

  IF v_paciente IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_activo = FALSE THEN
    ROLLBACK;
    SET p_mensaje = 'El paciente no esta en tratamiento activo: no se le pueden vincular familiares';
  ELSEIF v_usuario IS NOT NULL THEN
    ROLLBACK;
    SET p_mensaje = 'Ya existe una cuenta con ese correo electronico';
  ELSE
    INSERT INTO usuarios (nombre, apellido, email, contrasena_hash, rol)
    VALUES (p_nombre, p_apellido, p_email, p_hash, 'familiar');

    SET v_usuario = LAST_INSERT_ID();

    INSERT INTO familiares (id_usuario, parentesco, telefono)
    VALUES (v_usuario, p_parentesco, p_telefono);

    SET p_id_familiar = LAST_INSERT_ID();

    INSERT INTO familiares_pacientes (id_familiar, id_paciente)
    VALUES (p_id_familiar, p_id_paciente);

    COMMIT;
    SET p_mensaje = 'Familiar creado y vinculado correctamente';
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_notificar_paciente (Entrega 4)
--
-- Un aviso por cada familiar vinculado al paciente, con cuenta activa y que
-- NO haya desactivado ese tipo. Sin fila en preferencias_notificacion el tipo
-- esta habilitado (los familiares nuevos no tienen filas). Una sola sentencia
-- INSERT ... SELECT: o salen todos los avisos o ninguno.
--
-- La aplicacion lo llama DESPUES de confirmar el cambio que se avisa, en una
-- transaccion aparte y sin que su falla deshaga ese cambio: un aviso perdido
-- no puede tirar abajo el registro de una sesion. p_enviadas dice a cuantos
-- familiares llego (0 es un resultado valido: nadie vinculado o tipo apagado).
--
-- Lock: pacientes FOR SHARE (orden general: pacientes primero). Protege
-- contra una baja o un cambio de vinculos a mitad del envio.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_notificar_paciente (
  IN  p_id_paciente  INT UNSIGNED,
  IN  p_tipo         VARCHAR(30),
  IN  p_texto        VARCHAR(500),
  OUT p_enviadas     INT,
  OUT p_mensaje      VARCHAR(255)
)
BEGIN
  DECLARE v_error     VARCHAR(255) DEFAULT '';
  DECLARE v_paciente  INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_enviadas = 0;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_enviadas = 0;
    SET p_mensaje = 'No se pudo enviar el aviso por un problema inesperado. Intente nuevamente.';
  END;

  SET p_enviadas = 0;

  IF p_tipo NOT IN ('nueva_sesion', 'informe_generado', 'cambio_objetivo') THEN
    SET p_mensaje = 'El tipo de aviso indicado no es valido';
  ELSEIF p_texto IS NULL OR TRIM(p_texto) = '' THEN
    SET p_mensaje = 'El aviso no puede estar vacio';
  ELSE
    START TRANSACTION;

    SELECT id INTO v_paciente
      FROM pacientes
     WHERE id = p_id_paciente
     FOR SHARE;

    IF v_paciente IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El paciente indicado no existe';
    ELSE
      INSERT INTO notificaciones (id_familiar, id_paciente, tipo, mensaje)
      SELECT fp.id_familiar, p_id_paciente, p_tipo, p_texto
        FROM familiares_pacientes fp
        JOIN familiares f ON f.id = fp.id_familiar
        JOIN usuarios u   ON u.id = f.id_usuario AND u.activo = TRUE
        LEFT JOIN preferencias_notificacion pn
               ON pn.id_familiar = fp.id_familiar AND pn.tipo = p_tipo
       WHERE fp.id_paciente = p_id_paciente
         AND COALESCE(pn.habilitada, TRUE) = TRUE;

      SET p_enviadas = ROW_COUNT();

      COMMIT;
      SET p_mensaje = 'Aviso enviado';
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- Flujo de ingreso (Entrega 4): p_iniciar_ingreso, p_guardar_ingreso_etapa,
-- p_cerrar_ingreso_etapa, p_reabrir_ingreso_etapa y p_completar_ingreso.
--
-- Como en la regla 8 de HDU 11, solo el terapeuta con asignacion VIGENTE
-- sobre el paciente escribe: el id_terapeuta viaja al procedimiento, que lo
-- revalida por su cuenta. Un ingreso completado no se modifica mas.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_iniciar_ingreso (
  IN  p_id_paciente   INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  OUT p_id_ingreso    INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_activo     BOOLEAN      DEFAULT NULL;
  DECLARE v_terapeuta  INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado   INT          DEFAULT 0;
  DECLARE v_existente  INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_ingreso = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_ingreso = NULL;
    SET p_mensaje = 'No se pudo iniciar el ingreso por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_ingreso = NULL;

  START TRANSACTION;

  SELECT id, activo INTO v_paciente, v_activo
    FROM pacientes
   WHERE id = p_id_paciente
   FOR UPDATE;

  SELECT id INTO v_terapeuta
    FROM terapeutas
   WHERE id = p_id_terapeuta
   FOR SHARE;

  SELECT COUNT(*) INTO v_asignado
    FROM asignaciones
   WHERE id_paciente = p_id_paciente
     AND id_terapeuta = p_id_terapeuta
     AND fecha_hasta IS NULL
     FOR SHARE;

  SELECT id INTO v_existente
    FROM ingresos
   WHERE id_paciente = p_id_paciente
   FOR UPDATE;

  IF v_paciente IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_terapeuta IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta indicado no existe';
  ELSEIF v_activo = FALSE THEN
    ROLLBACK;
    SET p_mensaje = 'El paciente no esta en tratamiento activo: no se le puede iniciar un ingreso';
  ELSEIF v_asignado = 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta no tiene asignado a este paciente';
  ELSEIF v_existente IS NOT NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El paciente ya tiene un ingreso registrado';
  ELSE
    INSERT INTO ingresos (id_paciente, id_terapeuta)
    VALUES (p_id_paciente, p_id_terapeuta);

    SET p_id_ingreso = LAST_INSERT_ID();

    INSERT INTO ingreso_etapas (id_ingreso, etapa)
    VALUES (p_id_ingreso, 'carpeta'), (p_id_ingreso, 'evaluacion'),
           (p_id_ingreso, 'entrevista'), (p_id_ingreso, 'pti');

    COMMIT;
    SET p_mensaje = 'Ingreso iniciado correctamente';
  END IF;
END$$


-- p_respuestas: arreglo JSON [{"clave": "...", "valor": "..."}]. Un valor
-- vacio borra la respuesta. Una clave que no es de un campo ACTIVO de la etapa
-- se rechaza (no se descarta en silencio).
CREATE PROCEDURE p_guardar_ingreso_etapa (
  IN  p_id_ingreso    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_etapa         VARCHAR(20),
  IN  p_respuestas    JSON,
  OUT p_ok            BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_lock       INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado   INT          DEFAULT 0;
  DECLARE v_estado     VARCHAR(20)  DEFAULT NULL;
  DECLARE v_estado_et  VARCHAR(20)  DEFAULT NULL;
  DECLARE v_invalidas  INT          DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo guardar la etapa por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  IF p_etapa NOT IN ('carpeta', 'evaluacion', 'entrevista', 'pti') THEN
    SET p_mensaje = 'La etapa indicada no existe';
  ELSEIF p_respuestas IS NULL OR JSON_TYPE(p_respuestas) <> 'ARRAY' THEN
    SET p_mensaje = 'Las respuestas tienen que enviarse como una lista';
  ELSE
  SELECT id_paciente INTO v_paciente
    FROM ingresos
   WHERE id = p_id_ingreso;

  IF v_paciente IS NULL THEN
    SET p_mensaje = 'El ingreso indicado no existe';
  ELSE
    START TRANSACTION;

    SELECT id INTO v_lock
      FROM pacientes
     WHERE id = v_paciente
     FOR UPDATE;

    SELECT COUNT(*) INTO v_asignado
      FROM asignaciones
     WHERE id_paciente = v_paciente
       AND id_terapeuta = p_id_terapeuta
       AND fecha_hasta IS NULL
       FOR SHARE;

    -- Relectura dentro del lock del paciente
    SELECT estado INTO v_estado
      FROM ingresos
     WHERE id = p_id_ingreso
     FOR UPDATE;

    SELECT estado INTO v_estado_et
      FROM ingreso_etapas
     WHERE id_ingreso = p_id_ingreso AND etapa = p_etapa
     FOR UPDATE;

    IF v_estado IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El ingreso indicado no existe';
    ELSEIF v_asignado = 0 THEN
      ROLLBACK;
      SET p_mensaje = 'Solo el terapeuta asignado puede cargar el ingreso de este paciente';
    ELSEIF v_estado = 'completado' THEN
      ROLLBACK;
      SET p_mensaje = 'El ingreso ya esta completado y no se puede modificar';
    ELSEIF v_estado_et = 'cerrada' THEN
      ROLLBACK;
      SET p_mensaje = 'La etapa esta cerrada: reabrala para modificarla';
    ELSE
      SELECT COUNT(*) INTO v_invalidas
        FROM JSON_TABLE(p_respuestas, '$[*]'
               COLUMNS (clave VARCHAR(40) COLLATE utf8mb4_unicode_ci PATH '$.clave')) j
        LEFT JOIN ingreso_campos c
               ON c.etapa = p_etapa AND c.clave = j.clave AND c.activo = TRUE
       WHERE c.id IS NULL;

      IF v_invalidas > 0 THEN
        ROLLBACK;
        SET p_mensaje = 'Hay campos que no pertenecen a esta etapa';
      ELSE
        -- Valor vacio: se borra la respuesta
        DELETE r
          FROM ingreso_respuestas r
          JOIN ingreso_campos c ON c.id = r.id_campo AND c.etapa = p_etapa
          JOIN JSON_TABLE(p_respuestas, '$[*]'
                 COLUMNS (clave VARCHAR(40) COLLATE utf8mb4_unicode_ci PATH '$.clave',
                          valor TEXT PATH '$.valor' NULL ON EMPTY)) j
            ON j.clave = c.clave
         WHERE r.id_ingreso = p_id_ingreso
           AND (j.valor IS NULL OR TRIM(j.valor) = '');

        INSERT INTO ingreso_respuestas (id_ingreso, id_campo, valor)
        SELECT p_id_ingreso, c.id, TRIM(j.valor)
          FROM JSON_TABLE(p_respuestas, '$[*]'
                 COLUMNS (clave VARCHAR(40) COLLATE utf8mb4_unicode_ci PATH '$.clave',
                          valor TEXT PATH '$.valor' NULL ON EMPTY)) j
          JOIN ingreso_campos c
            ON c.etapa = p_etapa AND c.clave = j.clave AND c.activo = TRUE
         WHERE j.valor IS NOT NULL AND TRIM(j.valor) <> ''
        ON DUPLICATE KEY UPDATE valor = VALUES(valor);

        IF v_estado_et = 'pendiente' THEN
          UPDATE ingreso_etapas SET estado = 'en_curso'
           WHERE id_ingreso = p_id_ingreso AND etapa = p_etapa;
        END IF;

        COMMIT;
        SET p_ok = TRUE;
        SET p_mensaje = 'Etapa guardada correctamente';
      END IF;
    END IF;
  END IF;
  END IF;
END$$


CREATE PROCEDURE p_cerrar_ingreso_etapa (
  IN  p_id_ingreso    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_etapa         VARCHAR(20),
  OUT p_ok            BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_lock       INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado   INT          DEFAULT 0;
  DECLARE v_estado     VARCHAR(20)  DEFAULT NULL;
  DECLARE v_estado_et  VARCHAR(20)  DEFAULT NULL;
  DECLARE v_faltan     INT          DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo cerrar la etapa por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  IF p_etapa NOT IN ('carpeta', 'evaluacion', 'entrevista', 'pti') THEN
    SET p_mensaje = 'La etapa indicada no existe';
  ELSE
  SELECT id_paciente INTO v_paciente
    FROM ingresos
   WHERE id = p_id_ingreso;

  IF v_paciente IS NULL THEN
    SET p_mensaje = 'El ingreso indicado no existe';
  ELSE
    START TRANSACTION;

    SELECT id INTO v_lock
      FROM pacientes
     WHERE id = v_paciente
     FOR UPDATE;

    SELECT COUNT(*) INTO v_asignado
      FROM asignaciones
     WHERE id_paciente = v_paciente
       AND id_terapeuta = p_id_terapeuta
       AND fecha_hasta IS NULL
       FOR SHARE;

    -- Relectura dentro del lock del paciente
    SELECT estado INTO v_estado
      FROM ingresos
     WHERE id = p_id_ingreso
     FOR UPDATE;

    SELECT estado INTO v_estado_et
      FROM ingreso_etapas
     WHERE id_ingreso = p_id_ingreso AND etapa = p_etapa
     FOR UPDATE;

    SELECT COUNT(*) INTO v_faltan
      FROM ingreso_campos c
      LEFT JOIN ingreso_respuestas r
             ON r.id_campo = c.id AND r.id_ingreso = p_id_ingreso
     WHERE c.etapa = p_etapa AND c.activo = TRUE AND c.obligatorio = TRUE
       AND r.id_campo IS NULL;

    IF v_estado IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El ingreso indicado no existe';
    ELSEIF v_asignado = 0 THEN
      ROLLBACK;
      SET p_mensaje = 'Solo el terapeuta asignado puede cargar el ingreso de este paciente';
    ELSEIF v_estado = 'completado' THEN
      ROLLBACK;
      SET p_mensaje = 'El ingreso ya esta completado y no se puede modificar';
    ELSEIF v_estado_et = 'cerrada' THEN
      ROLLBACK;
      SET p_mensaje = 'La etapa ya estaba cerrada';
    ELSEIF v_faltan > 0 THEN
      ROLLBACK;
      SET p_mensaje = IF(v_faltan = 1,
        'Falta completar 1 campo obligatorio de esta etapa',
        CONCAT('Faltan completar ', v_faltan, ' campos obligatorios de esta etapa'));
    ELSE
      UPDATE ingreso_etapas
         SET estado = 'cerrada', fecha_cierre = CURRENT_TIMESTAMP
       WHERE id_ingreso = p_id_ingreso AND etapa = p_etapa;

      COMMIT;
      SET p_ok = TRUE;
      SET p_mensaje = 'Etapa cerrada correctamente';
    END IF;
  END IF;
  END IF;
END$$


CREATE PROCEDURE p_reabrir_ingreso_etapa (
  IN  p_id_ingreso    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_etapa         VARCHAR(20),
  OUT p_ok            BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_lock       INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado   INT          DEFAULT 0;
  DECLARE v_estado     VARCHAR(20)  DEFAULT NULL;
  DECLARE v_estado_et  VARCHAR(20)  DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo reabrir la etapa por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  IF p_etapa NOT IN ('carpeta', 'evaluacion', 'entrevista', 'pti') THEN
    SET p_mensaje = 'La etapa indicada no existe';
  ELSE
  SELECT id_paciente INTO v_paciente
    FROM ingresos
   WHERE id = p_id_ingreso;

  IF v_paciente IS NULL THEN
    SET p_mensaje = 'El ingreso indicado no existe';
  ELSE
    START TRANSACTION;

    SELECT id INTO v_lock
      FROM pacientes
     WHERE id = v_paciente
     FOR UPDATE;

    SELECT COUNT(*) INTO v_asignado
      FROM asignaciones
     WHERE id_paciente = v_paciente
       AND id_terapeuta = p_id_terapeuta
       AND fecha_hasta IS NULL
       FOR SHARE;

    -- Relectura dentro del lock del paciente
    SELECT estado INTO v_estado
      FROM ingresos
     WHERE id = p_id_ingreso
     FOR UPDATE;

    SELECT estado INTO v_estado_et
      FROM ingreso_etapas
     WHERE id_ingreso = p_id_ingreso AND etapa = p_etapa
     FOR UPDATE;

    IF v_estado IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El ingreso indicado no existe';
    ELSEIF v_asignado = 0 THEN
      ROLLBACK;
      SET p_mensaje = 'Solo el terapeuta asignado puede cargar el ingreso de este paciente';
    ELSEIF v_estado = 'completado' THEN
      ROLLBACK;
      SET p_mensaje = 'El ingreso ya esta completado y no se puede modificar';
    ELSEIF v_estado_et <> 'cerrada' THEN
      ROLLBACK;
      SET p_mensaje = 'La etapa no esta cerrada';
    ELSE
      UPDATE ingreso_etapas
         SET estado = 'en_curso', fecha_cierre = NULL
       WHERE id_ingreso = p_id_ingreso AND etapa = p_etapa;

      COMMIT;
      SET p_ok = TRUE;
      SET p_mensaje = 'Etapa reabierta correctamente';
    END IF;
  END IF;
  END IF;
END$$


-- Completa el ingreso: las cuatro etapas cerradas y el paciente con sus
-- objetivos fijados (observacion para fijar objetivos: minimo 3 activos).
-- Guarda la copia de etiquetas y respuestas en historia_clinica.
CREATE PROCEDURE p_completar_ingreso (
  IN  p_id_ingreso    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  OUT p_ok            BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error       VARCHAR(255) DEFAULT '';
  DECLARE v_paciente    INT UNSIGNED DEFAULT NULL;
  DECLARE v_lock        INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado    INT          DEFAULT 0;
  DECLARE v_estado      VARCHAR(20)  DEFAULT NULL;
  DECLARE v_abiertas    INT          DEFAULT 0;
  DECLARE v_objetivos   INT          DEFAULT 0;
  DECLARE v_historia    JSON         DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo completar el ingreso por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  SELECT id_paciente INTO v_paciente
    FROM ingresos
   WHERE id = p_id_ingreso;

  IF v_paciente IS NULL THEN
    SET p_mensaje = 'El ingreso indicado no existe';
  ELSE
    START TRANSACTION;

    SELECT id INTO v_lock
      FROM pacientes
     WHERE id = v_paciente
     FOR UPDATE;

    SELECT COUNT(*) INTO v_asignado
      FROM asignaciones
     WHERE id_paciente = v_paciente
       AND id_terapeuta = p_id_terapeuta
       AND fecha_hasta IS NULL
       FOR SHARE;

    -- Relectura dentro del lock del paciente
    SELECT estado INTO v_estado
      FROM ingresos
     WHERE id = p_id_ingreso
     FOR UPDATE;

    SELECT COUNT(*) INTO v_abiertas
      FROM ingreso_etapas
     WHERE id_ingreso = p_id_ingreso AND estado <> 'cerrada';

    SELECT COUNT(*) INTO v_objetivos
      FROM objetivos_terapeuticos
     WHERE id_paciente = v_paciente AND activo = TRUE
       FOR SHARE;

    IF v_estado IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El ingreso indicado no existe';
    ELSEIF v_asignado = 0 THEN
      ROLLBACK;
      SET p_mensaje = 'Solo el terapeuta asignado puede cargar el ingreso de este paciente';
    ELSEIF v_estado = 'completado' THEN
      ROLLBACK;
      SET p_mensaje = 'El ingreso ya estaba completado';
    ELSEIF v_abiertas > 0 THEN
      ROLLBACK;
      SET p_mensaje = IF(v_abiertas = 1,
        'Falta cerrar 1 etapa del ingreso',
        CONCAT('Faltan cerrar ', v_abiertas, ' etapas del ingreso'));
    ELSEIF v_objetivos < 3 THEN
      ROLLBACK;
      SET p_mensaje = 'Faltan fijar los objetivos: el paciente necesita al menos 3 objetivos activos';
    ELSE
      -- Copia de lo que figuraba al momento de completar. El orden lo
      -- reconstruye la aplicacion con etapa y orden.
      SELECT JSON_ARRAYAGG(JSON_OBJECT(
               'etapa', x.etapa, 'orden', x.orden, 'clave', x.clave,
               'etiqueta', x.etiqueta, 'tipo', x.tipo, 'valor', x.valor))
        INTO v_historia
        FROM (
          SELECT c.etapa, c.orden, c.clave, c.etiqueta, c.tipo, r.valor
            FROM ingreso_campos c
            LEFT JOIN ingreso_respuestas r
                   ON r.id_campo = c.id AND r.id_ingreso = p_id_ingreso
           WHERE c.activo = TRUE OR r.id_campo IS NOT NULL
        ) x;

      UPDATE ingresos
         SET estado = 'completado',
             fecha_completado = CURRENT_TIMESTAMP,
             historia_clinica = v_historia
       WHERE id = p_id_ingreso;

      COMMIT;
      SET p_ok = TRUE;
      SET p_mensaje = 'Ingreso completado: la historia clinica quedo generada';
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- DUPLAS TERAPEUTICAS (Entrega 5)
--
-- Una dupla es UNA terapeuta con DOS ninios en el mismo horario, cada uno
-- con sus objetivos y su evolucion (ver la columna sesiones.id_dupla). No hay
-- tabla de parejas: dos sesiones que comparten id_dupla SON la dupla, y el
-- valor es el id de la primera sesion (unico por construccion, sin secuencia).
--
-- p_registrar_dupla      crea las DOS sesiones juntas, en una transaccion.
-- p_agregar_a_dupla      suma un segundo paciente a una sesion que ya existe.
-- p_crear_turno_dupla    crea el turno semanal en dupla (dos filas de agenda).
-- p_sumar_companero_a_turno  convierte un turno individual en turno en dupla.
--
-- Las reglas de fondo siguen en los triggers de sesiones: solape (la hermana
-- de dupla no cuenta), asignacion vigente de CADA paciente, paciente de baja,
-- maximo de dos y mismo horario. Aca se agregan las existencias y la
-- atomicidad, para que nunca quede una dupla a medias.
--
-- ORDEN DE LOCKS: pacientes (por id) -> terapeutas -> sesiones/agenda.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_registrar_dupla (
  IN  p_id_terapeuta   INT UNSIGNED,
  IN  p_id_paciente_1  INT UNSIGNED,
  IN  p_id_paciente_2  INT UNSIGNED,
  IN  p_fecha          DATE,
  IN  p_hora_inicio    TIME,
  IN  p_hora_fin       TIME,
  OUT p_id_dupla       INT UNSIGNED,
  OUT p_id_sesion_1    INT UNSIGNED,
  OUT p_id_sesion_2    INT UNSIGNED,
  OUT p_mensaje        VARCHAR(255)
)
BEGIN
  DECLARE v_error        VARCHAR(255) DEFAULT '';
  DECLARE v_hora_fin     TIME         DEFAULT NULL;
  DECLARE v_lock         INT UNSIGNED DEFAULT NULL;
  DECLARE v_existentes   INT UNSIGNED DEFAULT 0;
  DECLARE v_superpuestas INT UNSIGNED DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_dupla = NULL;
    SET p_id_sesion_1 = NULL;
    SET p_id_sesion_2 = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_dupla = NULL;
    SET p_id_sesion_1 = NULL;
    SET p_id_sesion_2 = NULL;
    SET p_mensaje = 'No se pudo registrar la dupla por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_dupla = NULL;
  SET p_id_sesion_1 = NULL;
  SET p_id_sesion_2 = NULL;
  SET v_hora_fin = IFNULL(p_hora_fin, ADDTIME(p_hora_inicio, '01:00:00'));

  IF p_id_paciente_1 IS NULL OR p_id_paciente_2 IS NULL
     OR p_id_paciente_1 = p_id_paciente_2 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Una dupla necesita dos pacientes distintos';
  END IF;

  IF v_hora_fin <= p_hora_inicio THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'La hora de fin debe ser posterior a la hora de inicio';
  END IF;

  SELECT COUNT(*) INTO v_existentes
    FROM pacientes
   WHERE id IN (p_id_paciente_1, p_id_paciente_2);

  IF v_existentes < 2 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Alguno de los pacientes indicados no existe';
  END IF;

  START TRANSACTION;

  SELECT id INTO v_lock FROM pacientes WHERE id = LEAST(p_id_paciente_1, p_id_paciente_2) FOR SHARE;
  SELECT id INTO v_lock FROM pacientes WHERE id = GREATEST(p_id_paciente_1, p_id_paciente_2) FOR SHARE;
  SELECT id INTO v_lock FROM terapeutas WHERE id = p_id_terapeuta FOR UPDATE;

  IF v_lock IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El terapeuta indicado no existe';
  END IF;

  SELECT COUNT(*) INTO v_superpuestas
    FROM sesiones
   WHERE id_terapeuta = p_id_terapeuta
     AND fecha = p_fecha
     AND p_hora_inicio < IFNULL(hora_fin, ADDTIME(hora_inicio, '01:00:00'))
     AND v_hora_fin > hora_inicio
   FOR SHARE;

  IF v_superpuestas > 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El terapeuta ya tiene sesiones que se superponen con ese horario';
  END IF;

  INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado)
  VALUES (p_id_terapeuta, p_id_paciente_1, p_fecha, p_hora_inicio, p_hora_fin, 'incompleta');
  SET p_id_sesion_1 = LAST_INSERT_ID();

  UPDATE sesiones SET id_dupla = p_id_sesion_1 WHERE id = p_id_sesion_1;

  INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, id_dupla)
  VALUES (p_id_terapeuta, p_id_paciente_2, p_fecha, p_hora_inicio, p_hora_fin, 'incompleta', p_id_sesion_1);
  SET p_id_sesion_2 = LAST_INSERT_ID();

  COMMIT;
  SET p_id_dupla = p_id_sesion_1;
  SET p_mensaje = 'Dupla registrada correctamente';
END$$


CREATE PROCEDURE p_agregar_a_dupla (
  IN  p_id_terapeuta     INT UNSIGNED,
  IN  p_id_sesion        INT UNSIGNED,
  IN  p_id_paciente      INT UNSIGNED,
  OUT p_id_dupla         INT UNSIGNED,
  OUT p_id_sesion_nueva  INT UNSIGNED,
  OUT p_mensaje          VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_ter        INT UNSIGNED DEFAULT NULL;
  DECLARE v_pac        INT UNSIGNED DEFAULT NULL;
  DECLARE v_lock       INT UNSIGNED DEFAULT NULL;
  DECLARE v_fecha      DATE         DEFAULT NULL;
  DECLARE v_inicio     TIME         DEFAULT NULL;
  DECLARE v_fin        TIME         DEFAULT NULL;
  DECLARE v_dupla      INT UNSIGNED DEFAULT NULL;
  DECLARE v_estado     VARCHAR(20)  DEFAULT NULL;
  DECLARE v_existe     INT UNSIGNED DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_dupla = NULL;
    SET p_id_sesion_nueva = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_dupla = NULL;
    SET p_id_sesion_nueva = NULL;
    SET p_mensaje = 'No se pudo armar la dupla por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_dupla = NULL;
  SET p_id_sesion_nueva = NULL;

  -- terapeuta y paciente de una sesion son inmutables: se pueden leer sin lock
  SELECT id_terapeuta, id_paciente INTO v_ter, v_pac
    FROM sesiones WHERE id = p_id_sesion;

  IF v_ter IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La sesion indicada no existe';
  END IF;

  IF p_id_terapeuta IS NULL OR p_id_terapeuta <> v_ter THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Solo el terapeuta que atendio la sesion puede armar la dupla';
  END IF;

  IF p_id_paciente IS NULL OR p_id_paciente = v_pac THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Una dupla necesita dos pacientes distintos';
  END IF;

  SELECT COUNT(*) INTO v_existe FROM pacientes WHERE id = p_id_paciente;
  IF v_existe = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El paciente indicado no existe';
  END IF;

  START TRANSACTION;

  SELECT id INTO v_lock FROM pacientes WHERE id = LEAST(v_pac, p_id_paciente) FOR SHARE;
  SELECT id INTO v_lock FROM pacientes WHERE id = GREATEST(v_pac, p_id_paciente) FOR SHARE;
  SELECT id INTO v_lock FROM terapeutas WHERE id = v_ter FOR UPDATE;

  -- Se vuelve a leer la sesion YA con los locks: el horario y la dupla pueden
  -- haber cambiado entre la primera lectura y ahora.
  SELECT fecha, hora_inicio, hora_fin, id_dupla, estado
    INTO v_fecha, v_inicio, v_fin, v_dupla, v_estado
    FROM sesiones WHERE id = p_id_sesion FOR UPDATE;

  IF v_dupla IS NOT NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La sesion ya integra una dupla';
  END IF;

  IF v_estado = 'ausencia' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'No se puede armar una dupla sobre una sesion marcada como ausencia';
  END IF;

  UPDATE sesiones SET id_dupla = p_id_sesion WHERE id = p_id_sesion;

  INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, id_dupla)
  VALUES (v_ter, p_id_paciente, v_fecha, v_inicio, v_fin, 'incompleta', p_id_sesion);
  SET p_id_sesion_nueva = LAST_INSERT_ID();

  COMMIT;
  SET p_id_dupla = p_id_sesion;
  SET p_mensaje = 'Dupla armada correctamente';
END$$


CREATE PROCEDURE p_crear_turno_dupla (
  IN  p_id_terapeuta   INT UNSIGNED,
  IN  p_id_paciente_1  INT UNSIGNED,
  IN  p_id_paciente_2  INT UNSIGNED,
  IN  p_dia_semana     TINYINT UNSIGNED,
  IN  p_hora_inicio    TIME,
  IN  p_hora_fin       TIME,
  OUT p_id_dupla       INT UNSIGNED,
  OUT p_mensaje        VARCHAR(255)
)
BEGIN
  DECLARE v_error        VARCHAR(255) DEFAULT '';
  DECLARE v_lock         INT UNSIGNED DEFAULT NULL;
  DECLARE v_id_1         INT UNSIGNED DEFAULT NULL;
  DECLARE v_pacientes    INT UNSIGNED DEFAULT 0;
  DECLARE v_activos      INT UNSIGNED DEFAULT 0;
  DECLARE v_asignados    INT UNSIGNED DEFAULT 0;
  DECLARE v_superpuestos INT UNSIGNED DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_dupla = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_dupla = NULL;
    SET p_mensaje = 'No se pudo crear el turno en dupla por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_dupla = NULL;

  IF p_id_paciente_1 IS NULL OR p_id_paciente_2 IS NULL
     OR p_id_paciente_1 = p_id_paciente_2 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Una dupla necesita dos pacientes distintos';
  END IF;

  IF p_dia_semana IS NULL OR p_dia_semana NOT BETWEEN 1 AND 5 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El dia tiene que ser de lunes (1) a viernes (5)';
  END IF;

  IF p_hora_inicio IS NULL OR p_hora_fin IS NULL OR p_hora_fin <= p_hora_inicio THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'La hora de fin debe ser posterior a la de inicio';
  END IF;

  START TRANSACTION;

  SELECT id INTO v_lock FROM pacientes WHERE id = LEAST(p_id_paciente_1, p_id_paciente_2) FOR SHARE;
  SELECT id INTO v_lock FROM pacientes WHERE id = GREATEST(p_id_paciente_1, p_id_paciente_2) FOR SHARE;
  SET v_lock = NULL;
  SELECT id INTO v_lock FROM terapeutas WHERE id = p_id_terapeuta FOR UPDATE;

  IF v_lock IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El terapeuta indicado no existe';
  END IF;

  SELECT COUNT(*), IFNULL(SUM(activo), 0) INTO v_pacientes, v_activos
    FROM pacientes WHERE id IN (p_id_paciente_1, p_id_paciente_2);

  IF v_pacientes < 2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Alguno de los pacientes indicados no existe';
  END IF;

  IF v_activos < 2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Alguno de los pacientes no esta en tratamiento activo';
  END IF;

  SELECT COUNT(DISTINCT id_paciente) INTO v_asignados
    FROM asignaciones
   WHERE id_terapeuta = p_id_terapeuta
     AND id_paciente IN (p_id_paciente_1, p_id_paciente_2)
     AND fecha_hasta IS NULL
   FOR SHARE;

  IF v_asignados < 2 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Los dos pacientes tienen que estar asignados al terapeuta';
  END IF;

  SELECT COUNT(*) INTO v_superpuestos
    FROM agenda_recurrente
   WHERE id_terapeuta = p_id_terapeuta
     AND activo = TRUE
     AND dia_semana = p_dia_semana
     AND p_hora_inicio < hora_fin
     AND p_hora_fin > hora_inicio
   FOR SHARE;

  IF v_superpuestos > 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Ese horario se superpone con otro turno de la agenda semanal';
  END IF;

  INSERT INTO agenda_recurrente (id_terapeuta, id_paciente, dia_semana, hora_inicio, hora_fin)
  VALUES (p_id_terapeuta, p_id_paciente_1, p_dia_semana, p_hora_inicio, p_hora_fin);
  SET v_id_1 = LAST_INSERT_ID();

  UPDATE agenda_recurrente SET id_dupla = v_id_1 WHERE id = v_id_1;

  INSERT INTO agenda_recurrente (id_terapeuta, id_paciente, dia_semana, hora_inicio, hora_fin, id_dupla)
  VALUES (p_id_terapeuta, p_id_paciente_2, p_dia_semana, p_hora_inicio, p_hora_fin, v_id_1);

  COMMIT;
  SET p_id_dupla = v_id_1;
  SET p_mensaje = 'Turno en dupla creado correctamente';
END$$


CREATE PROCEDURE p_sumar_companero_a_turno (
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_id_turno      INT UNSIGNED,
  IN  p_id_paciente   INT UNSIGNED,
  OUT p_id_dupla      INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error     VARCHAR(255) DEFAULT '';
  DECLARE v_lock      INT UNSIGNED DEFAULT NULL;
  DECLARE v_ter       INT UNSIGNED DEFAULT NULL;
  DECLARE v_pac       INT UNSIGNED DEFAULT NULL;
  DECLARE v_dia       TINYINT UNSIGNED DEFAULT NULL;
  DECLARE v_inicio    TIME         DEFAULT NULL;
  DECLARE v_fin       TIME         DEFAULT NULL;
  DECLARE v_activo    BOOLEAN      DEFAULT NULL;
  DECLARE v_dupla     INT UNSIGNED DEFAULT NULL;
  DECLARE v_en_dupla  INT UNSIGNED DEFAULT 0;
  DECLARE v_pac_act   BOOLEAN      DEFAULT NULL;
  DECLARE v_existe    INT UNSIGNED DEFAULT 0;
  DECLARE v_asignado  INT UNSIGNED DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_dupla = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_dupla = NULL;
    SET p_mensaje = 'No se pudo armar la dupla por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_dupla = NULL;

  SELECT id_terapeuta, id_paciente INTO v_ter, v_pac
    FROM agenda_recurrente WHERE id = p_id_turno;

  IF v_ter IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El turno indicado no existe';
  END IF;

  IF p_id_terapeuta IS NULL OR p_id_terapeuta <> v_ter THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo puede modificar su propia agenda';
  END IF;

  IF p_id_paciente IS NULL OR p_id_paciente = v_pac THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Una dupla necesita dos pacientes distintos';
  END IF;

  START TRANSACTION;

  SELECT id INTO v_lock FROM pacientes WHERE id = LEAST(v_pac, p_id_paciente) FOR SHARE;
  SELECT id INTO v_lock FROM pacientes WHERE id = GREATEST(v_pac, p_id_paciente) FOR SHARE;
  SET v_lock = NULL;
  SELECT id INTO v_lock FROM terapeutas WHERE id = v_ter FOR UPDATE;

  SELECT dia_semana, hora_inicio, hora_fin, activo, id_dupla
    INTO v_dia, v_inicio, v_fin, v_activo, v_dupla
    FROM agenda_recurrente WHERE id = p_id_turno FOR UPDATE;

  IF v_activo = FALSE THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El turno indicado no existe';
  END IF;

  -- Un turno que ya tiene hermana ACTIVA es una dupla completa. Si la hermana
  -- se quito, el turno quedo solo y puede recibir otro companero.
  IF v_dupla IS NOT NULL THEN
    SELECT COUNT(*) INTO v_en_dupla
      FROM agenda_recurrente
     WHERE id_dupla = v_dupla AND activo = TRUE;
    IF v_en_dupla >= 2 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El turno ya integra una dupla';
    END IF;
  END IF;

  SELECT COUNT(*), MAX(activo) INTO v_existe, v_pac_act
    FROM pacientes WHERE id = p_id_paciente;

  IF v_existe = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El paciente indicado no existe';
  END IF;

  IF v_pac_act = FALSE THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El paciente no esta en tratamiento activo';
  END IF;

  SELECT COUNT(*) INTO v_asignado
    FROM asignaciones
   WHERE id_terapeuta = v_ter AND id_paciente = p_id_paciente AND fecha_hasta IS NULL
   FOR SHARE;

  IF v_asignado = 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El paciente no esta asignado al terapeuta';
  END IF;

  IF v_dupla IS NULL THEN
    SET v_dupla = p_id_turno;
    UPDATE agenda_recurrente SET id_dupla = v_dupla WHERE id = p_id_turno;
  END IF;

  INSERT INTO agenda_recurrente (id_terapeuta, id_paciente, dia_semana, hora_inicio, hora_fin, id_dupla)
  VALUES (v_ter, p_id_paciente, v_dia, v_inicio, v_fin, v_dupla);

  COMMIT;
  SET p_id_dupla = v_dupla;
  SET p_mensaje = 'Dupla armada correctamente';
END$$


-- ---------------------------------------------------------------------
-- Plantillas de objetivos por area (Entrega 5). Catalogo que cura el
-- administrador y que el terapeuta usa al crear un objetivo: el texto se
-- COPIA al objetivo, que despues se edita libremente. Un objetivo no
-- guarda referencia a la plantilla, asi que editar o borrar una plantilla
-- no toca objetivos ya creados.
-- Reglas: area obligatoria (hasta 120), descripcion obligatoria (hasta
-- 700, el mismo tope que un objetivo) y sin duplicados dentro de un area.
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS p_crear_plantilla_objetivo$$
CREATE PROCEDURE p_crear_plantilla_objetivo (
  IN  p_area          VARCHAR(2000),
  IN  p_descripcion   VARCHAR(2000),
  OUT p_id_plantilla  INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error   VARCHAR(255) DEFAULT '';
  DECLARE v_area    VARCHAR(2000);
  DECLARE v_desc    VARCHAR(2000);
  DECLARE v_igual   INT UNSIGNED DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_plantilla = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_plantilla = NULL;
    SET p_mensaje = 'No se pudo crear la plantilla por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_plantilla = NULL;
  SET v_area = TRIM(COALESCE(p_area, ''));
  SET v_desc = TRIM(COALESCE(p_descripcion, ''));

  IF v_area = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El area es obligatoria';
  END IF;
  IF CHAR_LENGTH(v_area) > 120 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El area no puede superar 120 caracteres';
  END IF;
  IF v_desc = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La descripcion es obligatoria';
  END IF;
  IF CHAR_LENGTH(v_desc) > 700 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La descripcion no puede superar 700 caracteres';
  END IF;

  START TRANSACTION;

  SELECT COUNT(*) INTO v_igual FROM (
    SELECT id FROM plantillas_objetivos
     WHERE area = v_area AND descripcion = v_desc
       FOR UPDATE
  ) AS t;
  IF v_igual > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ya existe una plantilla igual en esa area';
  END IF;

  INSERT INTO plantillas_objetivos (area, descripcion) VALUES (v_area, v_desc);
  SET p_id_plantilla = LAST_INSERT_ID();

  COMMIT;
  SET p_mensaje = 'Plantilla creada correctamente';
END$$


DROP PROCEDURE IF EXISTS p_editar_plantilla_objetivo$$
CREATE PROCEDURE p_editar_plantilla_objetivo (
  IN  p_id_plantilla  INT UNSIGNED,
  IN  p_area          VARCHAR(2000),
  IN  p_descripcion   VARCHAR(2000),
  OUT p_ok            BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error   VARCHAR(255) DEFAULT '';
  DECLARE v_area    VARCHAR(2000);
  DECLARE v_desc    VARCHAR(2000);
  DECLARE v_id      INT UNSIGNED DEFAULT NULL;
  DECLARE v_igual   INT UNSIGNED DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo guardar la plantilla por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;
  SET v_area = TRIM(COALESCE(p_area, ''));
  SET v_desc = TRIM(COALESCE(p_descripcion, ''));

  IF v_area = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El area es obligatoria';
  END IF;
  IF CHAR_LENGTH(v_area) > 120 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El area no puede superar 120 caracteres';
  END IF;
  IF v_desc = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La descripcion es obligatoria';
  END IF;
  IF CHAR_LENGTH(v_desc) > 700 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La descripcion no puede superar 700 caracteres';
  END IF;

  START TRANSACTION;

  SELECT id INTO v_id FROM plantillas_objetivos WHERE id = p_id_plantilla FOR UPDATE;
  IF v_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La plantilla indicada no existe';
  END IF;

  SELECT COUNT(*) INTO v_igual FROM (
    SELECT id FROM plantillas_objetivos
     WHERE area = v_area AND descripcion = v_desc AND id <> p_id_plantilla
       FOR UPDATE
  ) AS t;
  IF v_igual > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ya existe una plantilla igual en esa area';
  END IF;

  UPDATE plantillas_objetivos SET area = v_area, descripcion = v_desc WHERE id = p_id_plantilla;

  COMMIT;
  SET p_ok = TRUE;
  SET p_mensaje = 'Plantilla actualizada correctamente';
END$$


DROP PROCEDURE IF EXISTS p_eliminar_plantilla_objetivo$$
CREATE PROCEDURE p_eliminar_plantilla_objetivo (
  IN  p_id_plantilla  INT UNSIGNED,
  OUT p_ok            BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error  VARCHAR(255) DEFAULT '';
  DECLARE v_id     INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo quitar la plantilla por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  START TRANSACTION;

  SELECT id INTO v_id FROM plantillas_objetivos WHERE id = p_id_plantilla FOR UPDATE;
  IF v_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La plantilla indicada no existe';
  END IF;

  DELETE FROM plantillas_objetivos WHERE id = p_id_plantilla;

  COMMIT;
  SET p_ok = TRUE;
  SET p_mensaje = 'Plantilla quitada correctamente';
END$$


-- ---------------------------------------------------------------------
-- p_tendencia_paciente (Entrega 5)
-- Indicadores de tendencia por objetivo, en palabras, para el periodo
-- [p_desde, p_hasta] y su comparacion con el periodo anterior de igual
-- largo (los dias inmediatamente previos a p_desde).
--
-- Dos criterios, los dos aca y no en la interfaz:
--   tendencia  DENTRO del periodo: con al menos 4 calificaciones, se compara
--              el promedio de la primera mitad (en orden cronologico) con el
--              de la segunda; la del medio, si son impares, no entra.
--              Diferencia >= 0.5 -> 'mejora'; <= -0.5 -> 'retrocede'; si no,
--              'se_mantiene'. Con menos de 4 -> 'sin_datos'.
--   cambio     ENTRE periodos: con al menos 2 calificaciones en cada uno,
--              promedio actual contra promedio previo con el mismo umbral
--              -> 'mejoro' / 'retrocedio' / 'igual'. Si no -> 'sin_datos'.
-- Los promedios NO salen: la escala es en palabras. Se devuelve el nivel
-- (promedio redondeado a la palabra mas cercana) y la cantidad de
-- calificaciones de cada periodo. Un objetivo sin calificaciones en ninguno
-- de los dos periodos solo aparece si esta activo.
-- Es lectura de historia clinica: incluye pacientes dados de baja.
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS p_tendencia_paciente$$
CREATE PROCEDURE p_tendencia_paciente (
  IN  p_id_paciente  INT UNSIGNED,
  IN  p_desde        DATE,
  IN  p_hasta        DATE,
  OUT p_mensaje      VARCHAR(255)
)
BEGIN
  DECLARE v_existe      INT UNSIGNED DEFAULT 0;
  DECLARE v_dias        INT DEFAULT 0;
  DECLARE v_prev_desde  DATE;
  DECLARE v_prev_hasta  DATE;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    SET p_mensaje = 'No se pudo consultar la tendencia por un problema inesperado. Intente nuevamente.';
  END;

  SET p_mensaje = NULL;

  IF p_desde IS NULL OR p_hasta IS NULL OR p_desde > p_hasta THEN
    SET p_mensaje = 'El periodo indicado no es valido';
  ELSE
    SELECT COUNT(*) INTO v_existe FROM pacientes WHERE id = p_id_paciente;
    IF v_existe = 0 THEN
      SET p_mensaje = 'El paciente indicado no existe';
    ELSE
      SET v_dias       = DATEDIFF(p_hasta, p_desde) + 1;
      SET v_prev_hasta = DATE_SUB(p_desde, INTERVAL 1 DAY);
      SET v_prev_desde = DATE_SUB(p_desde, INTERVAL v_dias DAY);

      WITH cal AS (
        SELECT e.id_objetivo, e.valor, s.fecha, s.hora_inicio, s.id AS id_sesion,
               CASE WHEN s.fecha BETWEEN p_desde AND p_hasta THEN 'a' ELSE 'p' END AS per
          FROM evoluciones e
          JOIN sesiones s ON s.id = e.id_sesion
         WHERE s.id_paciente = p_id_paciente
           AND s.fecha BETWEEN v_prev_desde AND p_hasta
      ),
      ord AS (
        SELECT cal.*,
               ROW_NUMBER() OVER (PARTITION BY id_objetivo, per
                                  ORDER BY fecha, hora_inicio, id_sesion) AS rn,
               COUNT(*)     OVER (PARTITION BY id_objetivo, per)           AS n
          FROM cal
      ),
      agg AS (
        SELECT id_objetivo,
               SUM(per = 'a')                                              AS n_actual,
               AVG(CASE WHEN per = 'a' THEN valor END)                     AS prom_actual,
               SUM(per = 'p')                                              AS n_previo,
               AVG(CASE WHEN per = 'p' THEN valor END)                     AS prom_previo,
               AVG(CASE WHEN per = 'a' AND n >= 4 AND rn <= FLOOR(n / 2) THEN valor END)     AS prom_ini,
               AVG(CASE WHEN per = 'a' AND n >= 4 AND rn >  n - FLOOR(n / 2) THEN valor END) AS prom_fin
          FROM ord
         GROUP BY id_objetivo
      )
      SELECT o.id                          AS id_objetivo,
             o.descripcion                 AS descripcion,
             o.activo                      AS activo,
             COALESCE(a.n_actual, 0)       AS n_actual,
             ROUND(a.prom_actual)          AS nivel_actual,
             COALESCE(a.n_previo, 0)       AS n_previo,
             ROUND(a.prom_previo)          AS nivel_previo,
             CASE
               WHEN COALESCE(a.n_actual, 0) < 4          THEN 'sin_datos'
               WHEN a.prom_fin - a.prom_ini >=  0.5      THEN 'mejora'
               WHEN a.prom_fin - a.prom_ini <= -0.5      THEN 'retrocede'
               ELSE 'se_mantiene'
             END                           AS tendencia,
             CASE
               WHEN COALESCE(a.n_actual, 0) < 2 OR COALESCE(a.n_previo, 0) < 2 THEN 'sin_datos'
               WHEN a.prom_actual - a.prom_previo >=  0.5 THEN 'mejoro'
               WHEN a.prom_actual - a.prom_previo <= -0.5 THEN 'retrocedio'
               ELSE 'igual'
             END                           AS cambio
        FROM objetivos_terapeuticos o
        LEFT JOIN agg a ON a.id_objetivo = o.id
       WHERE o.id_paciente = p_id_paciente
         AND (o.activo = TRUE OR a.id_objetivo IS NOT NULL)
       ORDER BY o.activo DESC, o.id;
    END IF;
  END IF;
END$$


-- ---------------------------------------------------------------------
-- Informes (Entrega 6, HDU 5 y 8): p_crear_informe, p_editar_informe,
-- p_publicar_informe, p_corregir_informe y p_descartar_informe.
--
-- Las reglas viven aca y no en el servicio:
--   * Solo escribe un terapeuta ASIGNADO al paciente durante el periodo del
--     informe (misma idea que la regla 8: se evalua contra el periodo, no
--     contra hoy, asi un informe de un mes anterior sigue siendo posible).
--   * Un informe PUBLICADO (estado final) no se edita nunca. Para corregirlo
--     se arma una version nueva (p_corregir_informe); al publicarla, la
--     anterior pasa a 'reemplazado'. El familiar ve solo los 'final'.
--   * No se publica con marcas [COMPLETAR ...] sin resolver: son los huecos
--     que deja la plantilla para que la terapeuta los escriba.
--   * El periodo no puede ser futuro.
--
-- Orden de locks: pacientes -> terapeutas -> asignaciones -> informes. La
-- tabla informes referencia a pacientes y terapeutas y nadie la referencia,
-- asi que va al final del orden global.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_crear_informe (
  IN  p_id_paciente   INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_tipo          VARCHAR(10),
  IN  p_periodo       VARCHAR(20),
  IN  p_fecha_desde   DATE,
  IN  p_fecha_hasta   DATE,
  IN  p_contenido     LONGTEXT,
  IN  p_generado_con  VARCHAR(10),
  IN  p_proveedor     VARCHAR(60),
  OUT p_id_informe    INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_terapeuta  INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado   INT          DEFAULT 0;
  DECLARE v_borrador   INT UNSIGNED DEFAULT NULL;
  DECLARE v_final      INT UNSIGNED DEFAULT NULL;
  DECLARE v_version    INT          DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_informe = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_informe = NULL;
    SET p_mensaje = 'No se pudo guardar el informe por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_informe = NULL;

  START TRANSACTION;

  SELECT id INTO v_paciente
    FROM pacientes
   WHERE id = p_id_paciente
   FOR UPDATE;

  SELECT id INTO v_terapeuta
    FROM terapeutas
   WHERE id = p_id_terapeuta
   FOR SHARE;

  SELECT COUNT(*) INTO v_asignado
    FROM asignaciones
   WHERE id_paciente = p_id_paciente
     AND id_terapeuta = p_id_terapeuta
     AND fecha_desde <= p_fecha_hasta
     AND (fecha_hasta IS NULL OR fecha_hasta >= p_fecha_desde)
     FOR SHARE;

  SELECT id INTO v_borrador
    FROM informes
   WHERE id_paciente = p_id_paciente AND tipo = p_tipo AND periodo = p_periodo
     AND estado = 'borrador'
   FOR UPDATE;

  SELECT id INTO v_final
    FROM informes
   WHERE id_paciente = p_id_paciente AND tipo = p_tipo AND periodo = p_periodo
     AND estado = 'final'
   FOR UPDATE;

  SELECT COALESCE(MAX(version), 0) INTO v_version
    FROM informes
   WHERE id_paciente = p_id_paciente AND tipo = p_tipo AND periodo = p_periodo;

  IF v_paciente IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_terapeuta IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta indicado no existe';
  ELSEIF p_tipo NOT IN ('mensual', 'semestral', 'pti') THEN
    ROLLBACK;
    SET p_mensaje = 'El tipo de informe no es valido';
  ELSEIF p_generado_con NOT IN ('plantilla', 'ia') THEN
    ROLLBACK;
    SET p_mensaje = 'El origen del informe no es valido';
  ELSEIF p_fecha_desde IS NULL OR p_fecha_hasta IS NULL OR p_fecha_desde > p_fecha_hasta THEN
    ROLLBACK;
    SET p_mensaje = 'El periodo del informe no es valido';
  ELSEIF p_fecha_hasta > CURDATE() THEN
    ROLLBACK;
    SET p_mensaje = 'El periodo del informe no puede ser futuro';
  ELSEIF p_contenido IS NULL OR CHAR_LENGTH(TRIM(p_contenido)) = 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El informe no puede estar vacio';
  ELSEIF CHAR_LENGTH(p_contenido) > 60000 THEN
    ROLLBACK;
    SET p_mensaje = 'El informe supera el largo maximo permitido';
  ELSEIF v_asignado = 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta no tiene asignado a este paciente en el periodo del informe';
  ELSEIF v_final IS NOT NULL THEN
    ROLLBACK;
    SET p_mensaje = 'Ya existe un informe publicado de este periodo: use corregir para armar una version nueva';
  ELSEIF v_borrador IS NOT NULL THEN
    UPDATE informes
       SET id_terapeuta = p_id_terapeuta,
           fecha_desde = p_fecha_desde,
           fecha_hasta = p_fecha_hasta,
           contenido = p_contenido,
           contenido_original = p_contenido,
           generado_con = p_generado_con,
           proveedor = p_proveedor,
           fecha_generacion = NOW(),
           fecha_edicion = NULL
     WHERE id = v_borrador;
    COMMIT;
    SET p_id_informe = v_borrador;
    SET p_mensaje = 'Informe regenerado correctamente';
  ELSE
    INSERT INTO informes
      (id_paciente, id_terapeuta, tipo, periodo, fecha_desde, fecha_hasta,
       version, contenido, contenido_original, generado_con, proveedor, estado)
    VALUES
      (p_id_paciente, p_id_terapeuta, p_tipo, p_periodo, p_fecha_desde, p_fecha_hasta,
       v_version + 1, p_contenido, p_contenido, p_generado_con, p_proveedor, 'borrador');
    SET p_id_informe = LAST_INSERT_ID();
    COMMIT;
    SET p_mensaje = 'Informe generado correctamente';
  END IF;
END$$


CREATE PROCEDURE p_editar_informe (
  IN  p_id_informe    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_contenido     LONGTEXT,
  OUT p_ok            BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_terapeuta  INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado   INT          DEFAULT 0;
  DECLARE v_informe    INT UNSIGNED DEFAULT NULL;
  DECLARE v_estado     VARCHAR(12)  DEFAULT NULL;
  DECLARE v_desde      DATE         DEFAULT NULL;
  DECLARE v_hasta      DATE         DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo guardar el informe por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  START TRANSACTION;

  -- Lectura sin lock solo para ubicar al paciente padre y tomar los locks en
  -- orden; el estado se vuelve a leer bajo lock mas abajo.
  SELECT id_paciente INTO v_paciente FROM informes WHERE id = p_id_informe;

  SELECT id INTO v_paciente FROM pacientes WHERE id = v_paciente FOR UPDATE;

  SELECT id INTO v_terapeuta FROM terapeutas WHERE id = p_id_terapeuta FOR SHARE;

  SELECT id, estado, fecha_desde, fecha_hasta
    INTO v_informe, v_estado, v_desde, v_hasta
    FROM informes
   WHERE id = p_id_informe
   FOR UPDATE;

  SELECT COUNT(*) INTO v_asignado
    FROM asignaciones
   WHERE id_paciente = v_paciente
     AND id_terapeuta = p_id_terapeuta
     AND fecha_desde <= v_hasta
     AND (fecha_hasta IS NULL OR fecha_hasta >= v_desde)
     FOR SHARE;

  IF v_informe IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El informe indicado no existe';
  ELSEIF v_terapeuta IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta indicado no existe';
  ELSEIF v_estado <> 'borrador' THEN
    ROLLBACK;
    SET p_mensaje = 'Solo se puede editar un borrador: un informe publicado no se modifica';
  ELSEIF v_asignado = 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta no tiene asignado a este paciente en el periodo del informe';
  ELSEIF p_contenido IS NULL OR CHAR_LENGTH(TRIM(p_contenido)) = 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El informe no puede estar vacio';
  ELSEIF CHAR_LENGTH(p_contenido) > 60000 THEN
    ROLLBACK;
    SET p_mensaje = 'El informe supera el largo maximo permitido';
  ELSE
    UPDATE informes
       SET contenido = p_contenido,
           id_terapeuta = p_id_terapeuta,
           fecha_edicion = NOW()
     WHERE id = p_id_informe;
    COMMIT;
    SET p_ok = TRUE;
    SET p_mensaje = 'Informe guardado correctamente';
  END IF;
END$$


CREATE PROCEDURE p_publicar_informe (
  IN  p_id_informe    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  OUT p_ok            BOOLEAN,
  OUT p_id_paciente   INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_terapeuta  INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado   INT          DEFAULT 0;
  DECLARE v_informe    INT UNSIGNED DEFAULT NULL;
  DECLARE v_estado     VARCHAR(12)  DEFAULT NULL;
  DECLARE v_tipo       VARCHAR(10)  DEFAULT NULL;
  DECLARE v_periodo    VARCHAR(20)  DEFAULT NULL;
  DECLARE v_desde      DATE         DEFAULT NULL;
  DECLARE v_hasta      DATE         DEFAULT NULL;
  DECLARE v_contenido  LONGTEXT     DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_id_paciente = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_id_paciente = NULL;
    SET p_mensaje = 'No se pudo publicar el informe por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;
  SET p_id_paciente = NULL;

  START TRANSACTION;

  SELECT id_paciente INTO v_paciente FROM informes WHERE id = p_id_informe;

  SELECT id INTO v_paciente FROM pacientes WHERE id = v_paciente FOR UPDATE;

  SELECT id INTO v_terapeuta FROM terapeutas WHERE id = p_id_terapeuta FOR SHARE;

  SELECT id, estado, tipo, periodo, fecha_desde, fecha_hasta, contenido
    INTO v_informe, v_estado, v_tipo, v_periodo, v_desde, v_hasta, v_contenido
    FROM informes
   WHERE id = p_id_informe
   FOR UPDATE;

  SELECT COUNT(*) INTO v_asignado
    FROM asignaciones
   WHERE id_paciente = v_paciente
     AND id_terapeuta = p_id_terapeuta
     AND fecha_desde <= v_hasta
     AND (fecha_hasta IS NULL OR fecha_hasta >= v_desde)
     FOR SHARE;

  IF v_informe IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El informe indicado no existe';
  ELSEIF v_terapeuta IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta indicado no existe';
  ELSEIF v_estado <> 'borrador' THEN
    ROLLBACK;
    SET p_mensaje = 'El informe ya esta publicado o fue reemplazado';
  ELSEIF v_asignado = 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta no tiene asignado a este paciente en el periodo del informe';
  ELSEIF v_contenido IS NULL OR CHAR_LENGTH(TRIM(v_contenido)) = 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El informe no puede estar vacio';
  ELSEIF LOCATE('[COMPLETAR', UPPER(v_contenido)) > 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El informe tiene partes marcadas como COMPLETAR sin resolver: escribalas o quite la marca antes de publicar';
  ELSE
    UPDATE informes
       SET estado = 'reemplazado'
     WHERE id_paciente = v_paciente AND tipo = v_tipo AND periodo = v_periodo
       AND estado = 'final' AND id <> p_id_informe;
    UPDATE informes
       SET estado = 'final',
           fecha_publicacion = NOW(),
           id_terapeuta = p_id_terapeuta
     WHERE id = p_id_informe;
    COMMIT;
    SET p_ok = TRUE;
    SET p_id_paciente = v_paciente;
    SET p_mensaje = 'Informe publicado correctamente';
  END IF;
END$$


CREATE PROCEDURE p_corregir_informe (
  IN  p_id_informe    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  OUT p_id_nuevo      INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_terapeuta  INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado   INT          DEFAULT 0;
  DECLARE v_informe    INT UNSIGNED DEFAULT NULL;
  DECLARE v_estado     VARCHAR(12)  DEFAULT NULL;
  DECLARE v_tipo       VARCHAR(10)  DEFAULT NULL;
  DECLARE v_periodo    VARCHAR(20)  DEFAULT NULL;
  DECLARE v_desde      DATE         DEFAULT NULL;
  DECLARE v_hasta      DATE         DEFAULT NULL;
  DECLARE v_contenido  LONGTEXT     DEFAULT NULL;
  DECLARE v_generado   VARCHAR(10)  DEFAULT NULL;
  DECLARE v_proveedor  VARCHAR(60)  DEFAULT NULL;
  DECLARE v_borrador   INT UNSIGNED DEFAULT NULL;
  DECLARE v_version    INT          DEFAULT 0;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_id_nuevo = NULL;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_nuevo = NULL;
    SET p_mensaje = 'No se pudo preparar la correccion por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_nuevo = NULL;

  START TRANSACTION;

  SELECT id_paciente INTO v_paciente FROM informes WHERE id = p_id_informe;

  SELECT id INTO v_paciente FROM pacientes WHERE id = v_paciente FOR UPDATE;

  SELECT id INTO v_terapeuta FROM terapeutas WHERE id = p_id_terapeuta FOR SHARE;

  SELECT id, estado, tipo, periodo, fecha_desde, fecha_hasta, contenido,
         generado_con, proveedor
    INTO v_informe, v_estado, v_tipo, v_periodo, v_desde, v_hasta, v_contenido,
         v_generado, v_proveedor
    FROM informes
   WHERE id = p_id_informe
   FOR UPDATE;

  SELECT COUNT(*) INTO v_asignado
    FROM asignaciones
   WHERE id_paciente = v_paciente
     AND id_terapeuta = p_id_terapeuta
     AND fecha_desde <= v_hasta
     AND (fecha_hasta IS NULL OR fecha_hasta >= v_desde)
     FOR SHARE;

  SELECT id INTO v_borrador
    FROM informes
   WHERE id_paciente = v_paciente AND tipo = v_tipo AND periodo = v_periodo
     AND estado = 'borrador'
   FOR UPDATE;

  SELECT COALESCE(MAX(version), 0) INTO v_version
    FROM informes
   WHERE id_paciente = v_paciente AND tipo = v_tipo AND periodo = v_periodo;

  IF v_informe IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El informe indicado no existe';
  ELSEIF v_terapeuta IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta indicado no existe';
  ELSEIF v_estado <> 'final' THEN
    ROLLBACK;
    SET p_mensaje = 'Solo se puede corregir un informe publicado y vigente';
  ELSEIF v_asignado = 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta no tiene asignado a este paciente en el periodo del informe';
  ELSEIF v_borrador IS NOT NULL THEN
    ROLLBACK;
    SET p_mensaje = 'Ya hay un borrador de este periodo: termine o descarte ese borrador antes de corregir';
  ELSE
    INSERT INTO informes
      (id_paciente, id_terapeuta, tipo, periodo, fecha_desde, fecha_hasta,
       version, contenido, contenido_original, generado_con, proveedor, estado)
    VALUES
      (v_paciente, p_id_terapeuta, v_tipo, v_periodo, v_desde, v_hasta,
       v_version + 1, v_contenido, v_contenido, v_generado, v_proveedor, 'borrador');
    SET p_id_nuevo = LAST_INSERT_ID();
    COMMIT;
    SET p_mensaje = 'Version de correccion creada como borrador';
  END IF;
END$$


CREATE PROCEDURE p_descartar_informe (
  IN  p_id_informe    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  OUT p_ok            BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_error      VARCHAR(255) DEFAULT '';
  DECLARE v_paciente   INT UNSIGNED DEFAULT NULL;
  DECLARE v_terapeuta  INT UNSIGNED DEFAULT NULL;
  DECLARE v_asignado   INT          DEFAULT 0;
  DECLARE v_informe    INT UNSIGNED DEFAULT NULL;
  DECLARE v_estado     VARCHAR(12)  DEFAULT NULL;
  DECLARE v_desde      DATE         DEFAULT NULL;
  DECLARE v_hasta      DATE         DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '45000'
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = v_error;
  END;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo descartar el borrador por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  START TRANSACTION;

  SELECT id_paciente INTO v_paciente FROM informes WHERE id = p_id_informe;

  SELECT id INTO v_paciente FROM pacientes WHERE id = v_paciente FOR UPDATE;

  SELECT id INTO v_terapeuta FROM terapeutas WHERE id = p_id_terapeuta FOR SHARE;

  SELECT id, estado, fecha_desde, fecha_hasta
    INTO v_informe, v_estado, v_desde, v_hasta
    FROM informes
   WHERE id = p_id_informe
   FOR UPDATE;

  SELECT COUNT(*) INTO v_asignado
    FROM asignaciones
   WHERE id_paciente = v_paciente
     AND id_terapeuta = p_id_terapeuta
     AND fecha_desde <= v_hasta
     AND (fecha_hasta IS NULL OR fecha_hasta >= v_desde)
     FOR SHARE;

  IF v_informe IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El informe indicado no existe';
  ELSEIF v_terapeuta IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta indicado no existe';
  ELSEIF v_estado <> 'borrador' THEN
    ROLLBACK;
    SET p_mensaje = 'Solo se puede descartar un borrador: un informe publicado queda en el historial';
  ELSEIF v_asignado = 0 THEN
    ROLLBACK;
    SET p_mensaje = 'El terapeuta no tiene asignado a este paciente en el periodo del informe';
  ELSE
    DELETE FROM informes WHERE id = p_id_informe;
    COMMIT;
    SET p_ok = TRUE;
    SET p_mensaje = 'Borrador descartado';
  END IF;
END$$


-- ---------------------------------------------------------------------
-- p_reporte_sesiones_periodo — modulo RRHH
--
-- LIMITE DURO: este procedimiento NO devuelve contenido clinico. Nada de
-- sesiones.notas, nada de evoluciones, nada de informes. RRHH verifica
-- asistencias, no lee la historia clinica. No agregar esas columnas.
--
-- La columna superposiciones cuenta, para cada sesion, cuantas otras
-- sesiones del MISMO terapeuta ese mismo dia pisan su horario. Sirve para
-- detectar cargas mal hechas. Se calcula sobre toda la agenda del
-- terapeuta, no solo sobre el periodo filtrado.
--
-- p_id_terapeuta NULL = todos los terapeutas.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_reporte_sesiones_periodo (
  IN  p_fecha_desde   DATE,
  IN  p_fecha_hasta   DATE,
  IN  p_id_terapeuta  INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_total  INT UNSIGNED DEFAULT 0;

  -- Ver CRITERIO GENERAL DE ERRORES: mensaje fijo, nunca texto de MySQL
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    SET p_mensaje = 'No se pudo generar el reporte por un problema inesperado. Intente nuevamente.';
  END;

  -- =====================================================================
  -- PROYECCION DE RRHH — LISTA CERRADA, SE AGREGA SOLO CON UNA HDU
  --
  -- RRHH verifica asistencias y NO accede a contenido clinico. Es un limite
  -- duro del proyecto, y HOY NO LO SOSTIENE LA BASE: no hay un usuario de
  -- MySQL separado ni GRANTs por columna que lo impidan (hallazgo A3, sigue
  -- abierto). Lo unico que lo sostiene es esta lista y la del endpoint.
  --
  -- Por eso las columnas van NOMBRADAS UNA POR UNA y nunca `s.*`: con `s.*`
  -- cualquier columna que se agregue manana a `sesiones` empieza a salir por
  -- este camino sin que nadie lo decida. `notas` es exactamente ese caso —
  -- vive en `sesiones`, al lado de las que si salen, y es contenido clinico.
  --
  -- NO PUEDEN ENTRAR ACA, aunque sea comodo: `s.notas`, nada de
  -- `evoluciones` (observaciones, valor), nada de `objetivos_terapeuticos`
  -- (descripcion) y `p.diagnostico`. Si alguna hace falta, no se agrega:
  -- se discute si RRHH cambio de alcance, que es una HDU, no una columna.
  -- =====================================================================
  SELECT
    s.id                                 AS id_sesion,
    s.fecha,
    s.hora_inicio,
    s.hora_fin,
    s.estado,
    -- Quien falto. Es el dato que hace utilizable el reporte: "hubo 12
    -- ausencias" no sirve para lo administrativo si no dice de quien.
    -- Viaja NULL en toda sesion que no sea ausencia (lo garantizan los dos
    -- triggers) y tambien en las ausencias anteriores al 2026-09-10, que
    -- se cargaron cuando la columna no existia. NULL aca significa "no
    -- declarado", NO significa "el paciente": el endpoint las cuenta en un
    -- balde propio y no las reparte.
    s.ausencia_de,
    -- El id VA ADEMAS del nombre, no en su lugar: el id identifica y el
    -- nombre se lee. Sin el id, dos terapeutas homonimos son la misma fila
    -- para un reporte administrativo, y el paciente ya tenia con que
    -- distinguirse (`nro_historia`) mientras que el terapeuta no.
    --
    -- No abre nada: `id_terapeuta` es la MISMA clave que RRHH ya podia pasar
    -- como filtro (`p_id_terapeuta`), asi que devolverla no le da ningun
    -- valor que no pudiera haber adivinado probando. Y no existe ningun
    -- endpoint clinico que el rol rrhh pueda llamar con ese id: el blueprint
    -- de RRHH no importa un solo servicio clinico. Verificado por HTTP.
    s.id_terapeuta,
    CONCAT(ut.apellido, ', ', ut.nombre) AS terapeuta,
    CONCAT(p.apellido, ', ', p.nombre)   AS paciente,
    p.nro_historia,
    (
      SELECT COUNT(*)
        FROM sesiones s2
       WHERE s2.id_terapeuta = s.id_terapeuta
         AND s2.fecha = s.fecha
         AND s2.id <> s.id
         AND (s.id_dupla IS NULL OR s2.id_dupla IS NULL OR s2.id_dupla <> s.id_dupla)
         AND s.hora_inicio < IFNULL(s2.hora_fin, ADDTIME(s2.hora_inicio, '01:00:00'))
         AND IFNULL(s.hora_fin, ADDTIME(s.hora_inicio, '01:00:00')) > s2.hora_inicio
    )                                    AS superposiciones,
    -- Cuantas observaciones ADMINISTRATIVAS tiene la sesion. Es un CONTEO,
    -- no el texto: para pintar el listado alcanza con saber si hay o no, y
    -- traer el texto de todas las sesiones del periodo seria traer cientos
    -- de campos largos que la grilla no muestra.
    --
    -- Esto NO afloja el limite clinico: una observacion de RRHH la escribe
    -- RRHH y es administrativa. Lo que sigue sin salir por aca es
    -- `sesiones.notas`, que es del terapeuta.
    (
      SELECT COUNT(*)
        FROM observaciones_rrhh o
       WHERE o.id_sesion = s.id
    )                                    AS obs_rrhh
    -- ORDEN DE LOCKS: este SELECT no toma ninguno. No lleva FOR UPDATE ni
    -- FOR SHARE, asi que es una lectura consistente y no entra en el orden
    -- canonico ni puede formar un ciclo con nadie. `pacientes` va escrito
    -- antes que `terapeutas` de todos modos, para que la fuente se lea en
    -- el orden de la convencion; es cosmetico y no cambia el plan, porque
    -- el orden de los JOIN no es el orden de ejecucion.
    FROM sesiones s
    JOIN pacientes p   ON p.id = s.id_paciente
    JOIN terapeutas t  ON t.id = s.id_terapeuta
    JOIN usuarios ut   ON ut.id = t.id_usuario
   WHERE s.fecha BETWEEN p_fecha_desde AND p_fecha_hasta
     AND (p_id_terapeuta IS NULL OR s.id_terapeuta = p_id_terapeuta)
   ORDER BY s.fecha, s.hora_inicio, terapeuta;

  SELECT COUNT(*) INTO v_total
    FROM sesiones s
   WHERE s.fecha BETWEEN p_fecha_desde AND p_fecha_hasta
     AND (p_id_terapeuta IS NULL OR s.id_terapeuta = p_id_terapeuta);

  SET p_mensaje = CONCAT('Se listaron ', v_total, ' sesiones en el periodo');
END$$


-- ---------------------------------------------------------------------
-- Seguridad de acceso — Entrega 3 (2026-10-15)
-- Bloqueo por intentos fallidos y recuperacion de contrasena.
--
-- Cada procedimiento toca UNA sola fila de `usuarios` con FOR UPDATE: no
-- hay orden de locks que cuidar, y dos intentos simultaneos se serializan,
-- asi que el contador no pierde cuentas (sin el lock, 5 intentos en
-- paralelo podian leer 0 y escribir 1).
--
-- El token de recuperacion NUNCA se guarda: llega ya hasheado (SHA-256) desde
-- la aplicacion. Quien lea la base no puede restablecer ninguna cuenta.
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_registrar_login_fallido (
  IN  p_id_usuario       INT UNSIGNED,
  IN  p_max_intentos     TINYINT UNSIGNED,
  IN  p_minutos_bloqueo  SMALLINT UNSIGNED,
  OUT p_bloqueado        BOOLEAN,
  OUT p_bloqueado_hasta  DATETIME
)
BEGIN
  DECLARE v_intentos  TINYINT UNSIGNED DEFAULT 0;
  DECLARE v_hasta     DATETIME         DEFAULT NULL;
  DECLARE v_existe    INT UNSIGNED     DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET p_bloqueado = FALSE;
  SET p_bloqueado_hasta = NULL;

  START TRANSACTION;

  SELECT id, intentos_fallidos, bloqueado_hasta INTO v_existe, v_intentos, v_hasta
    FROM usuarios
   WHERE id = p_id_usuario
   FOR UPDATE;

  IF v_existe IS NOT NULL THEN
    IF v_hasta IS NOT NULL AND v_hasta > NOW() THEN
      -- Ya bloqueado: el intento no suma ni extiende el bloqueo.
      SET p_bloqueado = TRUE;
      SET p_bloqueado_hasta = v_hasta;
    ELSE
      -- Un bloqueo vencido empieza la cuenta de cero.
      IF v_hasta IS NOT NULL THEN
        SET v_intentos = 0;
      END IF;
      SET v_intentos = v_intentos + 1;

      IF v_intentos >= p_max_intentos THEN
        SET v_hasta = NOW() + INTERVAL p_minutos_bloqueo MINUTE;
        UPDATE usuarios
           SET intentos_fallidos = 0, bloqueado_hasta = v_hasta
         WHERE id = p_id_usuario;
        SET p_bloqueado = TRUE;
        SET p_bloqueado_hasta = v_hasta;
      ELSE
        UPDATE usuarios
           SET intentos_fallidos = v_intentos, bloqueado_hasta = NULL
         WHERE id = p_id_usuario;
      END IF;
    END IF;
  END IF;

  COMMIT;
END$$


CREATE PROCEDURE p_registrar_login_ok (
  IN p_id_usuario INT UNSIGNED
)
BEGIN
  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
  UPDATE usuarios
     SET intentos_fallidos = 0, bloqueado_hasta = NULL
   WHERE id = p_id_usuario
     AND (intentos_fallidos <> 0 OR bloqueado_hasta IS NOT NULL);
  COMMIT;
END$$


-- Si el email no existe o la cuenta esta inactiva NO es un error: devuelve
-- p_id_usuario NULL y la aplicacion responde igual que si existiera, para no
-- revelar que direcciones tienen cuenta.
CREATE PROCEDURE p_solicitar_recuperacion (
  IN  p_email          VARCHAR(180),
  IN  p_token_hash     VARCHAR(255),
  IN  p_minutos        SMALLINT UNSIGNED,
  OUT p_id_usuario     INT UNSIGNED
)
BEGIN
  DECLARE v_id INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET p_id_usuario = NULL;

  START TRANSACTION;

  SELECT id INTO v_id
    FROM usuarios
   WHERE email = p_email AND activo = TRUE
   FOR UPDATE;

  IF v_id IS NOT NULL THEN
    -- Un pedido nuevo invalida el anterior: queda un solo token vigente.
    UPDATE usuarios
       SET token_recuperacion = p_token_hash,
           token_expira = NOW() + INTERVAL p_minutos MINUTE
     WHERE id = v_id;
    SET p_id_usuario = v_id;
  END IF;

  COMMIT;
END$$


CREATE PROCEDURE p_restablecer_contrasena (
  IN  p_token_hash     VARCHAR(255),
  IN  p_hash_nuevo     VARCHAR(255),
  OUT p_restablecida   BOOLEAN,
  OUT p_mensaje        VARCHAR(255)
)
BEGIN
  DECLARE v_id     INT UNSIGNED DEFAULT NULL;
  DECLARE v_expira DATETIME     DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_restablecida = FALSE;
    SET p_mensaje = 'No se pudo restablecer la contrasena por un problema inesperado. Intente nuevamente.';
  END;

  SET p_restablecida = FALSE;
  SET p_mensaje = 'El enlace de recuperacion no es valido o ya vencio';

  IF p_token_hash IS NOT NULL AND p_token_hash <> '' THEN
    START TRANSACTION;

    SELECT id, token_expira INTO v_id, v_expira
      FROM usuarios
     WHERE token_recuperacion = p_token_hash AND activo = TRUE
     FOR UPDATE;

    IF v_id IS NULL OR v_expira IS NULL OR v_expira < NOW() THEN
      ROLLBACK;
    ELSE
      -- El token es de un solo uso. Restablecer tambien levanta el bloqueo:
      -- es la salida natural de quien se quedo afuera por intentos fallidos.
      -- Tambien cierra todas las sesiones abiertas: si la clave se cambio
      -- porque alguien mas la conocia, sus tokens dejan de servir ya.
      UPDATE usuarios
         SET contrasena_hash = p_hash_nuevo,
             token_recuperacion = NULL,
             token_expira = NULL,
             intentos_fallidos = 0,
             bloqueado_hasta = NULL,
             sesiones_validas_desde = NOW(6)
       WHERE id = v_id;
      COMMIT;
      SET p_restablecida = TRUE;
      SET p_mensaje = 'Contrasena actualizada correctamente';
    END IF;
  END IF;
END$$


-- Auditoria de accesos (HDU de seguridad, Entrega 3). Una fila por intento de
-- login. Nunca guarda la contrasena. `id_usuario` es NULL cuando el email no
-- existe. La aplicacion no puede fallar un login porque falle su auditoria:
-- lo captura y lo loguea; aca solo se inserta.
CREATE PROCEDURE p_registrar_acceso (
  IN p_id_usuario  INT UNSIGNED,
  IN p_email       VARCHAR(180),
  IN p_resultado   VARCHAR(20),
  IN p_ip          VARCHAR(45)
)
BEGIN
  IF p_resultado IN ('exitoso', 'fallido', 'bloqueado', 'recuperacion', 'restablecida', 'inactiva') THEN
    INSERT INTO auditoria_accesos (id_usuario, email, resultado, ip)
    VALUES (p_id_usuario, p_email, p_resultado, p_ip);
  END IF;
END$$


-- ---------------------------------------------------------------------
-- Renglones de la sesion — Entrega 3 (ver CREATE TABLE sesion_renglones)
--
-- ORDEN DE LOCKS: sesiones -> sesion_renglones, el canonico (sesion_renglones
-- va despues de evoluciones). Estos procedimientos no escriben `sesiones`: la
-- fila se toma solo para leerla y para SERIALIZAR a quienes escriben renglones
-- de una misma sesion, asi el tope por sesion es exacto. Es UN solo lock sobre
-- sesiones y no se espera a nadie mientras se lo tiene: no puede cerrar un ciclo.
--
-- Autoria: solo el terapeuta de la sesion escribe renglones; la lectura es
-- abierta (ver renglones_service).
-- ---------------------------------------------------------------------
CREATE PROCEDURE p_agregar_renglon (
  IN  p_id_sesion     INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_momento       VARCHAR(10),
  IN  p_texto         VARCHAR(500),
  IN  p_destacado     BOOLEAN,
  OUT p_id_renglon    INT UNSIGNED,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_texto      VARCHAR(500)  DEFAULT TRIM(IFNULL(p_texto, ''));
  DECLARE v_ter        INT UNSIGNED  DEFAULT NULL;
  DECLARE v_estado     VARCHAR(12)   DEFAULT NULL;
  DECLARE v_fecha      DATE          DEFAULT NULL;
  DECLARE v_cantidad   INT UNSIGNED  DEFAULT 0;
  DECLARE v_orden      INT UNSIGNED  DEFAULT 1;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_renglon = NULL;
    SET p_mensaje = 'No se pudo guardar el renglon por un problema inesperado. Intente nuevamente.';
  END;

  SET p_id_renglon = NULL;

  IF p_momento IS NULL OR p_momento NOT IN ('plan', 'registro') THEN
    SET p_mensaje = 'El momento del renglon tiene que ser plan o registro';
  ELSEIF v_texto = '' THEN
    SET p_mensaje = 'El renglon no puede estar vacio';
  ELSEIF CHAR_LENGTH(v_texto) > 160 THEN
    SET p_mensaje = 'El renglon no puede superar los 160 caracteres';
  ELSE
    START TRANSACTION;

    SELECT id_terapeuta, estado, fecha INTO v_ter, v_estado, v_fecha
      FROM sesiones
     WHERE id = p_id_sesion
     FOR UPDATE;

    IF v_ter IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'La sesion indicada no existe';
    ELSEIF v_ter <> p_id_terapeuta THEN
      ROLLBACK;
      SET p_mensaje = 'Solo el terapeuta que atendio la sesion puede cargarle renglones';
    ELSEIF p_momento = 'registro' AND v_estado = 'ausencia' THEN
      ROLLBACK;
      SET p_mensaje = 'La sesion esta marcada como ausencia: no admite registro';
    ELSEIF p_momento = 'registro' AND v_fecha > CURRENT_DATE THEN
      ROLLBACK;
      SET p_mensaje = 'La sesion todavia no ocurrio: solo admite plan';
    ELSE
      SELECT COUNT(*), IFNULL(MAX(orden), 0) + 1 INTO v_cantidad, v_orden
        FROM sesion_renglones
       WHERE id_sesion = p_id_sesion AND momento = p_momento;

      IF v_cantidad >= 30 THEN
        ROLLBACK;
        SET p_mensaje = CONCAT('La sesion ya tiene 30 renglones de ', p_momento);
      ELSE
        INSERT INTO sesion_renglones (id_sesion, momento, texto, destacado, orden)
        VALUES (p_id_sesion, p_momento, v_texto, IFNULL(p_destacado, FALSE), v_orden);
        SET p_id_renglon = LAST_INSERT_ID();
        COMMIT;
        SET p_mensaje = 'Renglon guardado correctamente';
      END IF;
    END IF;
  END IF;
END$$


-- Edita texto y marca. No mueve el renglon de momento ni de sesion.
CREATE PROCEDURE p_editar_renglon (
  IN  p_id_renglon    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_texto         VARCHAR(500),
  IN  p_destacado     BOOLEAN,
  OUT p_editado       BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_texto   VARCHAR(500) DEFAULT TRIM(IFNULL(p_texto, ''));
  DECLARE v_sesion  INT UNSIGNED DEFAULT NULL;
  DECLARE v_ter     INT UNSIGNED DEFAULT NULL;
  DECLARE v_existe  INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_editado = FALSE;
    SET p_mensaje = 'No se pudo editar el renglon por un problema inesperado. Intente nuevamente.';
  END;

  SET p_editado = FALSE;

  IF v_texto = '' THEN
    SET p_mensaje = 'El renglon no puede estar vacio';
  ELSEIF CHAR_LENGTH(v_texto) > 160 THEN
    SET p_mensaje = 'El renglon no puede superar los 160 caracteres';
  ELSE
    -- La sesion se conoce ANTES del lock para respetar el orden (sesiones
    -- primero); la lectura es sin lock y se REPITE adentro.
    SELECT id_sesion INTO v_sesion FROM sesion_renglones WHERE id = p_id_renglon;

    IF v_sesion IS NULL THEN
      SET p_mensaje = 'El renglon indicado no existe';
    ELSE
      START TRANSACTION;

      SELECT id_terapeuta INTO v_ter FROM sesiones WHERE id = v_sesion FOR UPDATE;

      SELECT id INTO v_existe FROM sesion_renglones WHERE id = p_id_renglon FOR UPDATE;

      IF v_existe IS NULL THEN
        ROLLBACK;
        SET p_mensaje = 'El renglon indicado no existe';
      ELSEIF v_ter <> p_id_terapeuta THEN
        ROLLBACK;
        SET p_mensaje = 'Solo el terapeuta que atendio la sesion puede editar sus renglones';
      ELSE
        UPDATE sesion_renglones
           SET texto = v_texto, destacado = IFNULL(p_destacado, FALSE)
         WHERE id = p_id_renglon;
        COMMIT;
        SET p_editado = TRUE;
        SET p_mensaje = 'Renglon actualizado correctamente';
      END IF;
    END IF;
  END IF;
END$$


-- Cierra un renglon de PLAN ('hecho' o 'descartado') o lo reabre ('').
CREATE PROCEDURE p_cerrar_renglon (
  IN  p_id_renglon    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_cierre        VARCHAR(10),
  OUT p_cerrado       BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_sesion   INT UNSIGNED DEFAULT NULL;
  DECLARE v_ter      INT UNSIGNED DEFAULT NULL;
  DECLARE v_momento  VARCHAR(10)  DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_cerrado = FALSE;
    SET p_mensaje = 'No se pudo cerrar el renglon por un problema inesperado. Intente nuevamente.';
  END;

  SET p_cerrado = FALSE;

  IF p_cierre IS NULL OR p_cierre NOT IN ('hecho', 'descartado', '') THEN
    SET p_mensaje = 'El cierre tiene que ser hecho, descartado o vacio (para reabrir)';
  ELSE
    SELECT id_sesion INTO v_sesion FROM sesion_renglones WHERE id = p_id_renglon;

    IF v_sesion IS NULL THEN
      SET p_mensaje = 'El renglon indicado no existe';
    ELSE
      START TRANSACTION;

      SELECT id_terapeuta INTO v_ter FROM sesiones WHERE id = v_sesion FOR UPDATE;

      SELECT momento INTO v_momento FROM sesion_renglones WHERE id = p_id_renglon FOR UPDATE;

      IF v_momento IS NULL THEN
        ROLLBACK;
        SET p_mensaje = 'El renglon indicado no existe';
      ELSEIF v_ter <> p_id_terapeuta THEN
        ROLLBACK;
        SET p_mensaje = 'Solo el terapeuta que atendio la sesion puede cerrar sus renglones';
      ELSEIF v_momento <> 'plan' THEN
        ROLLBACK;
        SET p_mensaje = 'Solo los renglones de plan se cierran';
      ELSE
        UPDATE sesion_renglones
           SET cierre = NULLIF(p_cierre, '')
         WHERE id = p_id_renglon;
        COMMIT;
        SET p_cerrado = TRUE;
        SET p_mensaje = IF(p_cierre = '', 'Renglon reabierto', 'Renglon cerrado');
      END IF;
    END IF;
  END IF;
END$$


CREATE PROCEDURE p_borrar_renglon (
  IN  p_id_renglon    INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  OUT p_borrado       BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_sesion   INT UNSIGNED DEFAULT NULL;
  DECLARE v_ter      INT UNSIGNED DEFAULT NULL;
  DECLARE v_existe   INT UNSIGNED DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_borrado = FALSE;
    SET p_mensaje = 'No se pudo borrar el renglon por un problema inesperado. Intente nuevamente.';
  END;

  SET p_borrado = FALSE;

  SELECT id_sesion INTO v_sesion FROM sesion_renglones WHERE id = p_id_renglon;

  IF v_sesion IS NULL THEN
    SET p_mensaje = 'El renglon indicado no existe';
  ELSE
    START TRANSACTION;

    SELECT id_terapeuta INTO v_ter FROM sesiones WHERE id = v_sesion FOR UPDATE;

    SELECT id INTO v_existe FROM sesion_renglones WHERE id = p_id_renglon FOR UPDATE;

    IF v_existe IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El renglon indicado no existe';
    ELSEIF v_ter <> p_id_terapeuta THEN
      ROLLBACK;
      SET p_mensaje = 'Solo el terapeuta que atendio la sesion puede borrar sus renglones';
    ELSE
      DELETE FROM sesion_renglones WHERE id = p_id_renglon;
      COMMIT;
      SET p_borrado = TRUE;
      SET p_mensaje = 'Renglon borrado';
    END IF;
  END IF;
END$$

-- Marca o desmarca un objetivo del paciente como "a trabajar" en la sesion.
-- Idempotente: marcar lo ya marcado, o desmarcar lo no marcado, no es error.
-- ORDEN DE LOCKS: sesiones -> objetivos_terapeuticos -> sesion_objetivos (el
-- canonico). Solo se pueden marcar objetivos ACTIVOS del paciente de la
-- sesion; desmarcar no exige que siga activo.
CREATE PROCEDURE p_marcar_objetivo_sesion (
  IN  p_id_sesion     INT UNSIGNED,
  IN  p_id_terapeuta  INT UNSIGNED,
  IN  p_id_objetivo   INT UNSIGNED,
  IN  p_marcar        BOOLEAN,
  OUT p_ok            BOOLEAN,
  OUT p_mensaje       VARCHAR(255)
)
BEGIN
  DECLARE v_ter       INT UNSIGNED DEFAULT NULL;
  DECLARE v_paciente  INT UNSIGNED DEFAULT NULL;
  DECLARE v_obj_pac   INT UNSIGNED DEFAULT NULL;
  DECLARE v_obj_act   BOOLEAN      DEFAULT NULL;

  DECLARE EXIT HANDLER FOR SQLSTATE '40001'
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR 1205
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_ok = FALSE;
    SET p_mensaje = 'No se pudo actualizar el plan por un problema inesperado. Intente nuevamente.';
  END;

  SET p_ok = FALSE;

  START TRANSACTION;

  SELECT id_terapeuta, id_paciente INTO v_ter, v_paciente
    FROM sesiones
   WHERE id = p_id_sesion
   FOR UPDATE;

  IF v_ter IS NULL THEN
    ROLLBACK;
    SET p_mensaje = 'La sesion indicada no existe';
  ELSEIF v_ter <> p_id_terapeuta THEN
    ROLLBACK;
    SET p_mensaje = 'Solo el terapeuta que atendio la sesion puede armar su plan';
  ELSE
    SELECT id_paciente, activo INTO v_obj_pac, v_obj_act
      FROM objetivos_terapeuticos
     WHERE id = p_id_objetivo
     FOR SHARE;

    IF v_obj_pac IS NULL THEN
      ROLLBACK;
      SET p_mensaje = 'El objetivo indicado no existe';
    ELSEIF v_obj_pac <> v_paciente THEN
      ROLLBACK;
      SET p_mensaje = 'El objetivo no pertenece al paciente de esta sesion';
    ELSEIF IFNULL(p_marcar, TRUE) = FALSE THEN
      DELETE FROM sesion_objetivos
       WHERE id_sesion = p_id_sesion AND id_objetivo = p_id_objetivo;
      COMMIT;
      SET p_ok = TRUE;
      SET p_mensaje = 'Objetivo quitado del plan';
    ELSEIF v_obj_act = FALSE THEN
      ROLLBACK;
      SET p_mensaje = 'El objetivo esta archivado: no se puede planear';
    ELSE
      INSERT IGNORE INTO sesion_objetivos (id_sesion, id_objetivo)
      VALUES (p_id_sesion, p_id_objetivo);
      COMMIT;
      SET p_ok = TRUE;
      SET p_mensaje = 'Objetivo agregado al plan';
    END IF;
  END IF;
END$$

DELIMITER ;


-- =====================================================================
-- 9. VISTAS
-- =====================================================================

-- Objetivos activos por paciente con su ultimo valor de evolucion.
-- "Ultimo" se ordena por fecha y hora de la SESION, no por fecha_registro
-- de la evolucion: importa cuando ocurrio la sesion, no cuando se cargo.
CREATE VIEW v_objetivos_activos AS
SELECT
  o.id                                 AS id_objetivo,
  o.id_paciente,
  p.nombre                             AS paciente_nombre,
  p.apellido                           AS paciente_apellido,
  p.nro_historia,
  o.descripcion,
  o.fecha_creacion,
  (
    SELECT e.valor
      FROM evoluciones e
      JOIN sesiones s ON s.id = e.id_sesion
     WHERE e.id_objetivo = o.id
     ORDER BY s.fecha DESC, s.hora_inicio DESC, e.id DESC
     LIMIT 1
  )                                    AS ultimo_valor,
  (
    SELECT s.fecha
      FROM evoluciones e
      JOIN sesiones s ON s.id = e.id_sesion
     WHERE e.id_objetivo = o.id
     ORDER BY s.fecha DESC, s.hora_inicio DESC, e.id DESC
     LIMIT 1
  )                                    AS fecha_ultima_evolucion,
  (
    SELECT COUNT(*)
      FROM evoluciones e
     WHERE e.id_objetivo = o.id
  )                                    AS total_evoluciones
  FROM objetivos_terapeuticos o
  JOIN pacientes p ON p.id = o.id_paciente
 WHERE o.activo = TRUE;


-- Resumen de asistencia por paciente. TODOS los pacientes, activos o no.
--
-- LEFT JOIN a proposito: un paciente recien dado de alta, sin sesiones
-- todavia, tiene que aparecer con los contadores en cero.
--
-- EL FILTRO POR ESTADO ES POLITICA DEL CONSUMIDOR, NO DE LA VISTA. NO
-- agregar aca un WHERE p.activo = TRUE. Lo tuvo hasta el 2026-08-09 y se
-- saco a proposito:
--
--   Un total historico no puede cambiar por un hecho administrativo
--   POSTERIOR. Si un paciente se da de baja en septiembre, sus sesiones de
--   julio ocurrieron y tienen que seguir contando para julio. Con el filtro
--   puesto, el paciente desaparecia del resumen entero y los totales de
--   meses ya cerrados se reescribian solos.
--
-- Es ademas lo que ya hace p_reporte_sesiones_periodo, que nunca filtro por
-- activo: con el WHERE puesto las dos salidas de RRHH se contradecian entre
-- si sobre los mismos datos.
--
-- El consumidor que necesite solo los activos agrega `WHERE activo = TRUE`
-- en SU consulta, que es una linea. Al reves no se puede: una vista que
-- filtra le reescribe la historia a todos sin avisar.
--
-- Para que el consumidor pueda hacerlo, la vista EXPONE el estado. Ver la
-- columna `activo` de abajo.
CREATE VIEW v_resumen_sesiones AS
SELECT
  p.id                AS id_paciente,
  p.nombre,
  p.apellido,
  p.nro_historia,
  -- El estado viaja como dato para que el consumidor pueda filtrar por su
  -- cuenta. NO es contenido clinico: es administrativo, igual que fecha_alta.
  p.activo,
  COUNT(s.id)                                        AS total_sesiones,
  COALESCE(SUM(s.estado = 'completa'), 0)            AS sesiones_completas,
  COALESCE(SUM(s.estado = 'incompleta'), 0)          AS sesiones_incompletas,
  COALESCE(SUM(s.estado = 'ausencia'), 0)            AS ausencias,
  MAX(s.fecha)                                       AS fecha_ultima_sesion
  FROM pacientes p
  LEFT JOIN sesiones s ON s.id_paciente = p.id
 GROUP BY p.id, p.nombre, p.apellido, p.nro_historia, p.activo;


-- =====================================================================
-- FIN DEL SCHEMA
-- =====================================================================
SELECT 'Schema de AsisTO creado correctamente' AS resultado;
