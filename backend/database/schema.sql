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
-- ---------------------------------------------------------------------
CREATE TABLE objetivos_terapeuticos (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_paciente         INT UNSIGNED NOT NULL,
  descripcion         VARCHAR(500) NOT NULL,
  activo              BOOLEAN      NOT NULL DEFAULT TRUE,
  fecha_creacion      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_archivado     DATETIME     NULL DEFAULT NULL,

  descripcion_activa  VARCHAR(500)
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
  fecha_registro  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE KEY uq_sesiones_paciente_fecha_hora (id_paciente, fecha, hora_inicio),
  KEY idx_sesiones_terapeuta_fecha (id_terapeuta, fecha),
  KEY idx_sesiones_paciente_fecha (id_paciente, fecha),
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
-- 6. INFORMES, DUPLAS, PLANTILLAS Y AUDITORIA (Entrega 4)
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


CREATE TABLE duplas_terapeuticas (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_terapeuta_1    INT UNSIGNED NOT NULL,
  id_terapeuta_2    INT UNSIGNED NOT NULL,
  id_paciente       INT UNSIGNED NOT NULL,
  fecha_asignacion  DATE         NOT NULL DEFAULT (CURRENT_DATE),
  activa            BOOLEAN      NOT NULL DEFAULT TRUE,

  PRIMARY KEY (id),
  KEY idx_duplas_paciente (id_paciente),
  KEY idx_duplas_terapeuta_2 (id_terapeuta_2),
  CONSTRAINT chk_duplas_terapeutas_distintos
    CHECK (id_terapeuta_1 <> id_terapeuta_2),
  -- ON UPDATE RESTRICT y no CASCADE, a diferencia del resto del schema:
  -- MySQL 8.0 (error 3823) prohibe que una columna con accion referencial
  -- participe de un CHECK. terapeutas.id es un surrogate AUTO_INCREMENT
  -- que nunca se actualiza, asi que el CASCADE no aportaba nada y el
  -- CHECK de "los dos terapeutas distintos" si importa.
  CONSTRAINT fk_duplas_terapeuta_1
    FOREIGN KEY (id_terapeuta_1) REFERENCES terapeutas (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_duplas_terapeuta_2
    FOREIGN KEY (id_terapeuta_2) REFERENCES terapeutas (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_duplas_paciente
    FOREIGN KEY (id_paciente) REFERENCES pacientes (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


CREATE TABLE plantillas_objetivos (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  area         VARCHAR(120) NOT NULL,
  descripcion  VARCHAR(500) NOT NULL,

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
-- Orden de adquisicion de locks, respetado en triggers y procedimientos:
--      pacientes   -> objetivos_terapeuticos -> evoluciones
--      terapeutas  -> sesiones               -> evoluciones
--      sesiones    -> objetivos_terapeuticos   (triggers de evoluciones)
--
-- Ese grafo no tiene ciclos: nada bloquea objetivos_terapeuticos y despues
-- sesiones. Mantener el orden. Invertirlo entre dos rutas de escritura
-- introduce deadlocks donde hoy no hay.
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

  -- Un objetivo que nace archivado no consume cupo
  IF NEW.activo = TRUE THEN
    -- Ver NOTA DE CONCURRENCIA
    SELECT id INTO v_lock
      FROM pacientes
     WHERE id = NEW.id_paciente
     FOR UPDATE;

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
    SELECT id INTO v_lock
      FROM pacientes
     WHERE id = NEW.id_paciente
     FOR UPDATE;

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
  SELECT COUNT(*) INTO v_existe_pac FROM pacientes  WHERE id = p_id_paciente;

  IF v_existe_ter = 0 THEN
    SET p_mensaje = 'El terapeuta indicado no existe';
  ELSEIF v_existe_pac = 0 THEN
    SET p_mensaje = 'El paciente indicado no existe';
  ELSEIF v_hora_fin <= p_hora_inicio THEN
    SET p_mensaje = 'La hora de fin debe ser posterior a la hora de inicio';
  ELSE
    START TRANSACTION;

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
  OUT p_id_evolucion   INT UNSIGNED,
  OUT p_mensaje        VARCHAR(255)
)
BEGIN
  DECLARE v_error VARCHAR(255) DEFAULT '';

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

  -- Ver CRITERIO GENERAL DE ERRORES: mensaje fijo, nunca texto de MySQL
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_id_evolucion = NULL;
    SET p_mensaje = 'No se pudo registrar la evolucion por un error interno';
  END;

  SET p_id_evolucion = NULL;

  -- Se valida antes del INSERT para dar un mensaje claro en vez del
  -- error crudo del CHECK constraint
  IF p_valor IS NULL OR p_valor < 1 OR p_valor > 5 THEN
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


-- Resumen de asistencia por paciente activo.
-- LEFT JOIN a proposito: un paciente recien dado de alta, sin sesiones
-- todavia, tiene que aparecer con los contadores en cero.
CREATE VIEW v_resumen_sesiones AS
SELECT
  p.id                AS id_paciente,
  p.nombre,
  p.apellido,
  p.nro_historia,
  COUNT(s.id)                                        AS total_sesiones,
  COALESCE(SUM(s.estado = 'completa'), 0)            AS sesiones_completas,
  COALESCE(SUM(s.estado = 'incompleta'), 0)          AS sesiones_incompletas,
  COALESCE(SUM(s.estado = 'ausencia'), 0)            AS ausencias,
  MAX(s.fecha)                                       AS fecha_ultima_sesion
  FROM pacientes p
  LEFT JOIN sesiones s ON s.id_paciente = p.id
 WHERE p.activo = TRUE
 GROUP BY p.id, p.nombre, p.apellido, p.nro_historia;


-- =====================================================================
-- FIN DEL SCHEMA
-- =====================================================================
SELECT 'Schema de AsisTO creado correctamente' AS resultado;
