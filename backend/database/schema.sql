-- =====================================================================
-- AsisTO — Schema de base de datos
-- MySQL 8.0+ / utf8mb4_unicode_ci
--
-- Script idempotente: se puede correr las veces que haga falta.
-- ATENCION: arranca con DROP DATABASE. Borra todo lo que haya.
--
--   mysql -u root -p < backend/database/schema.sql
-- =====================================================================

DROP DATABASE IF EXISTS asisto;
CREATE DATABASE asisto
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE asisto;


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
  rol                 ENUM('terapeuta','rrhh','familiar','paciente') NOT NULL,

  -- Campos de seguridad: se usan recien en la Entrega 3 (bloqueo por
  -- intentos fallidos y recuperacion de contrasena). Se crean ahora para
  -- no migrar la tabla despues.
  intentos_fallidos   TINYINT UNSIGNED NOT NULL DEFAULT 0,
  bloqueado_hasta     DATETIME     NULL DEFAULT NULL,
  token_recuperacion  VARCHAR(255) NULL DEFAULT NULL,
  token_expira        DATETIME     NULL DEFAULT NULL,

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

  PRIMARY KEY (id),
  UNIQUE KEY uq_pacientes_usuario (id_usuario),
  UNIQUE KEY uq_pacientes_nro_historia (nro_historia),
  KEY idx_pacientes_activo (activo),
  KEY idx_pacientes_apellido (apellido, nombre),
  CONSTRAINT fk_pacientes_usuario
    FOREIGN KEY (id_usuario) REFERENCES usuarios (id)
    ON DELETE SET NULL ON UPDATE CASCADE
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


-- =====================================================================
-- 6. INFORMES, PLANTILLAS Y AUDITORIA (Entrega 4)
-- =====================================================================

-- contenido_original guarda el texto tal como lo genero la IA;
-- contenido guarda la version editada por el terapeuta. Se conservan los
-- dos para poder auditar que cambio una persona sobre la salida del
-- modelo. Ningun informe se publica sin revision humana.
CREATE TABLE informes (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_paciente         INT UNSIGNED NOT NULL,
  id_terapeuta        INT UNSIGNED NOT NULL,
  periodo             VARCHAR(20)  NOT NULL,
  contenido           LONGTEXT     NULL DEFAULT NULL,
  contenido_original  LONGTEXT     NULL DEFAULT NULL,
  estado              ENUM('borrador','final') NOT NULL DEFAULT 'borrador',
  fecha_generacion    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_publicacion   DATETIME     NULL DEFAULT NULL,

  PRIMARY KEY (id),
  KEY idx_informes_paciente_periodo (id_paciente, periodo),
  CONSTRAINT fk_informes_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_informes_terapeuta
    FOREIGN KEY (id_terapeuta) REFERENCES terapeutas (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
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
  resultado   ENUM('exitoso','fallido','bloqueado') NOT NULL,
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
--      pacientes -> terapeutas -> sesiones -> objetivos_terapeuticos
--                -> evoluciones
--
-- Todo lo de este schema lo respeta:
--      pacientes   -> objetivos_terapeuticos   (triggers de objetivos)
--      terapeutas  -> sesiones                 (triggers de sesiones)
--      sesiones    -> objetivos_terapeuticos   (triggers de evoluciones)
--
-- Invertirlo introduce deadlocks. No es teorico: una transaccion que toma
-- objetivos_terapeuticos y despues sesiones, contra un INSERT de evolucion
-- concurrente, termina en ERROR 1213. Esta reproducido.
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
          'El paciente esta dado de baja: no se le pueden crear objetivos';
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
          'El paciente esta dado de baja: no se le pueden activar objetivos';
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
        'El paciente esta dado de baja: solo se pueden cargar sesiones hasta el dia de la baja';
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

  SET v_hora_fin = IFNULL(NEW.hora_fin, ADDTIME(NEW.hora_inicio, '01:00:00'));

  IF v_hora_fin <= NEW.hora_inicio THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'La hora de fin debe ser posterior a la hora de inicio';
  END IF;

  SELECT COUNT(*) INTO v_superpuestas
    FROM sesiones
   WHERE id_terapeuta = NEW.id_terapeuta
     AND fecha = NEW.fecha
     AND NEW.hora_inicio < IFNULL(hora_fin, ADDTIME(hora_inicio, '01:00:00'))
     AND v_hora_fin > hora_inicio
   FOR SHARE;

  IF v_superpuestas > 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'El terapeuta ya tiene sesiones que se superponen con ese horario';
  END IF;
END$$


-- ---------------------------------------------------------------------
-- Regla 6 en UPDATE + regla 2 al cambiar el estado a 'ausencia'
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
  DECLARE v_lock         INT UNSIGNED DEFAULT NULL;
  DECLARE v_activo_pac   BOOLEAN      DEFAULT NULL;
  DECLARE v_fecha_baja   DATE         DEFAULT NULL;

  -- =====================================================================
  -- SESION SOBRE UN PACIENTE DADO DE BAJA (2026-08-13)
  --
  -- Par del chequeo del trigger de INSERT, con el mismo mensaje. Ver alla
  -- el porque; aca cambian dos cosas.
  --
  -- 1. VA FUERA DEL "IF cambio el horario". Ese IF cubre el solape, que
  --    solo puede aparecer si se movio dia u hora. Esta regla no: mover la
  --    sesion a OTRO PACIENTE que esta dado de baja no toca el horario y
  --    tiene que rechazarse igual.
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
  SELECT activo, fecha_baja INTO v_activo_pac, v_fecha_baja
    FROM pacientes
   WHERE id = NEW.id_paciente
   FOR SHARE;

  IF v_activo_pac = FALSE
     AND (v_fecha_baja IS NULL OR NEW.fecha > v_fecha_baja) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'El paciente esta dado de baja: solo se pueden cargar sesiones hasta el dia de la baja';
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
-- Por que. Los triggers de arriba leen `pacientes` para decidir si la
-- sesion cae despues de la baja. En el INSERT eso no cuesta nada: el
-- trigger corre antes de que exista la fila, asi que el orden queda
-- pacientes -> terapeutas -> sesiones, el canonico. En el UPDATE es
-- distinto y no se puede arreglar desde el trigger: un BEFORE UPDATE corre
-- con el lock exclusivo de la fila YA tomado, o sea sesiones -> pacientes.
--
-- Medido, no deducido: un UPDATE directo sobre `sesiones` concurrente con
-- una baja del mismo paciente PRODUCE UN DEADLOCK (errno 1213), y InnoDB
-- elige como victima a la baja. Con la falsacion correspondiente: sin la
-- lectura de `pacientes` el 1213 no aparece.
--
-- Por que se aplico igual: la baja lleva @reintentar_en_deadlock, recibe el
-- 1213 gracias al RESIGNAL y entra en el PRIMER reintento. Cuatro corridas
-- end-to-end por la aplicacion, las cuatro iguales: 1 de 3 intentos.
--
-- Y aca esta lo que le toca a quien escriba el codigo nuevo: ese deadlock
-- SOLO lo produce quien entra por un UPDATE directo. Un llamador que tome
-- `pacientes FOR SHARE` primero llega al trigger con el lock ya en su
-- propia transaccion, el SELECT de adentro no espera a nadie y el ciclo no
-- puede cerrarse. Respetar el orden no es una formalidad: es la diferencia
-- entre que la baja de un paciente ande y que muera por deadlock.
--
-- Si el endpoint de editar sesion se escribe con un UPDATE del ORM y sin
-- procedimiento, va a funcionar en las pruebas de a uno y va a empezar a
-- matar bajas en cuanto haya dos personas trabajando a la vez.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Reglas 2, 3 y 4 — validacion unificada de evoluciones.
--
-- Un solo trigger a proposito, no tres. Motivo: las tres validaciones
-- necesitan los mismos dos SELECT (la sesion y el objetivo). Separarlas
-- multiplicaria las consultas por tres para el mismo INSERT, y el orden
-- de disparo entre triggers del mismo evento no seria explicito.
-- Cada regla conserva su propio mensaje de error.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_evoluciones_validar_insert
BEFORE INSERT ON evoluciones
FOR EACH ROW
BEGIN
  DECLARE v_estado_sesion     ENUM('completa','incompleta','ausencia') DEFAULT NULL;
  DECLARE v_paciente_sesion   INT UNSIGNED DEFAULT NULL;
  DECLARE v_paciente_objetivo INT UNSIGNED DEFAULT NULL;
  DECLARE v_objetivo_activo   BOOLEAN      DEFAULT NULL;

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
  SELECT estado, id_paciente
    INTO v_estado_sesion, v_paciente_sesion
    FROM sesiones
   WHERE id = NEW.id_sesion
   FOR SHARE;

  SELECT id_paciente, activo
    INTO v_paciente_objetivo, v_objetivo_activo
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
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_evoluciones_validar_update
BEFORE UPDATE ON evoluciones
FOR EACH ROW
BEGIN
  DECLARE v_estado_sesion     ENUM('completa','incompleta','ausencia') DEFAULT NULL;
  DECLARE v_paciente_sesion   INT UNSIGNED DEFAULT NULL;
  DECLARE v_paciente_objetivo INT UNSIGNED DEFAULT NULL;
  DECLARE v_objetivo_activo   BOOLEAN      DEFAULT NULL;

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
  SELECT estado, id_paciente
    INTO v_estado_sesion, v_paciente_sesion
    FROM sesiones
   WHERE id = NEW.id_sesion
   FOR SHARE;

  SELECT id_paciente, activo
    INTO v_paciente_objetivo, v_objetivo_activo
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
          'El paciente esta dado de baja: no se le pueden abrir asignaciones';
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
          'El paciente esta dado de baja: no se le pueden abrir asignaciones';
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
    SET p_mensaje = 'No se pudo dar de alta el paciente por un error interno';
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
    SET p_mensaje = 'Paciente dado de alta correctamente';
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
    SET p_mensaje = 'No se pudo editar el paciente por un error interno';
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
    SET p_mensaje = 'El paciente esta dado de baja: reactivelo antes de editarlo';
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
      SET p_mensaje = 'El paciente esta dado de baja: reactivelo antes de editarlo';
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
-- `asignaciones` NO esta en el orden canonico del CLAUDE.md, que se escribio
-- antes de que la tabla existiera (migracion del 2026-08-07). Se la ubica
-- entre `terapeutas` y `sesiones`, que es donde cae por dependencia: referencia
-- a pacientes y a terapeutas, y nada la referencia a ella. QUEDA PROPUESTO
-- para el chat de planeamiento; este procedimiento ya respeta esa ubicacion.
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
    SET p_mensaje = 'No se pudo dar de baja el paciente por un error interno';
  END;

  SET p_objetivos_archivados = NULL;
  SET p_asignaciones_cerradas = NULL;

  SELECT COUNT(*), MAX(activo) INTO v_existe, v_activo
    FROM pacientes
   WHERE id = p_id_paciente;

  IF v_existe = 0 THEN
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_activo = FALSE THEN
    SET p_mensaje = 'El paciente ya estaba dado de baja';
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
      SET p_mensaje = 'El paciente ya estaba dado de baja';
    ELSE

    UPDATE pacientes
       SET activo = FALSE,
           fecha_baja = CURRENT_DATE
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
    SET p_mensaje = 'Paciente dado de baja correctamente';
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
    SET p_mensaje = 'No se pudo reactivar el paciente por un error interno';
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
             fecha_baja = NULL
       WHERE id = p_id_paciente;

      COMMIT;
      SET p_reactivado = 1;
      SET p_mensaje = 'Paciente reactivado correctamente';
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
    SET p_mensaje = 'No se pudo registrar la sesion por un error interno';
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
    SET p_mensaje = 'El paciente esta dado de baja: solo se pueden cargar sesiones hasta el dia de la baja';
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
      SET p_mensaje = 'El paciente esta dado de baja: solo se pueden cargar sesiones hasta el dia de la baja';
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
      SET p_mensaje = CONCAT(
        'El terapeuta ya tiene ', v_superpuestas,
        ' sesion(es) que se superponen con ese horario');
    ELSE
      INSERT INTO sesiones (
        id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, notas
      ) VALUES (
        p_id_terapeuta, p_id_paciente, p_fecha, p_hora_inicio, p_hora_fin,
        IFNULL(p_estado, 'incompleta'), p_notas
      );

      SET p_id_sesion = LAST_INSERT_ID();
      COMMIT;
      SET p_mensaje = 'Sesion registrada correctamente';
    END IF;
    END IF;
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
    SET p_mensaje = 'No se pudo registrar la evolucion por un error interno';
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
    SET p_mensaje = 'No se pudo consultar la evolucion por un error interno';
  END;

  SELECT COUNT(*) INTO v_existe FROM pacientes WHERE id = p_id_paciente;

  IF v_existe = 0 THEN
    SET p_mensaje = 'El paciente indicado no existe';
  ELSE
    SELECT
      s.fecha,
      s.hora_inicio,
      s.estado                AS estado_sesion,
      o.id                    AS id_objetivo,
      o.descripcion           AS objetivo,
      o.activo                AS objetivo_activo,
      e.valor,
      e.observaciones,
      CONCAT(u.apellido, ', ', u.nombre) AS terapeuta
      FROM sesiones s
      JOIN evoluciones e             ON e.id_sesion = s.id
      JOIN objetivos_terapeuticos o  ON o.id = e.id_objetivo
      JOIN terapeutas t              ON t.id = s.id_terapeuta
      JOIN usuarios u                ON u.id = t.id_usuario
     WHERE s.id_paciente = p_id_paciente
       AND s.fecha BETWEEN p_fecha_desde AND p_fecha_hasta
     ORDER BY s.fecha, s.hora_inicio, o.id;

    SELECT COUNT(*) INTO v_total
      FROM sesiones s
      JOIN evoluciones e ON e.id_sesion = s.id
     WHERE s.id_paciente = p_id_paciente
       AND s.fecha BETWEEN p_fecha_desde AND p_fecha_hasta;

    SET p_mensaje = CONCAT('Se encontraron ', v_total, ' evoluciones en el periodo');
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
    SET p_mensaje = 'No se pudo generar el reporte por un error interno';
  END;

  SELECT
    s.id                                 AS id_sesion,
    s.fecha,
    s.hora_inicio,
    s.hora_fin,
    s.estado,
    CONCAT(ut.apellido, ', ', ut.nombre) AS terapeuta,
    CONCAT(p.apellido, ', ', p.nombre)   AS paciente,
    p.nro_historia,
    (
      SELECT COUNT(*)
        FROM sesiones s2
       WHERE s2.id_terapeuta = s.id_terapeuta
         AND s2.fecha = s.fecha
         AND s2.id <> s.id
         AND s.hora_inicio < IFNULL(s2.hora_fin, ADDTIME(s2.hora_inicio, '01:00:00'))
         AND IFNULL(s.hora_fin, ADDTIME(s.hora_inicio, '01:00:00')) > s2.hora_inicio
    )                                    AS superposiciones
    FROM sesiones s
    JOIN terapeutas t  ON t.id = s.id_terapeuta
    JOIN usuarios ut   ON ut.id = t.id_usuario
    JOIN pacientes p   ON p.id = s.id_paciente
   WHERE s.fecha BETWEEN p_fecha_desde AND p_fecha_hasta
     AND (p_id_terapeuta IS NULL OR s.id_terapeuta = p_id_terapeuta)
   ORDER BY s.fecha, s.hora_inicio, terapeuta;

  SELECT COUNT(*) INTO v_total
    FROM sesiones s
   WHERE s.fecha BETWEEN p_fecha_desde AND p_fecha_hasta
     AND (p_id_terapeuta IS NULL OR s.id_terapeuta = p_id_terapeuta);

  SET p_mensaje = CONCAT('Se listaron ', v_total, ' sesiones en el periodo');
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
