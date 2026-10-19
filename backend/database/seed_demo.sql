-- =====================================================================
-- AsisTO — Datos de DEMOSTRACION (volumen realista)
--
-- ALTERNATIVA a seed.sql, no lo reemplaza. Los dos cargan sobre el mismo
-- schema y son excluyentes: se corre uno u otro.
--
--   seed.sql       3 pacientes, 10 sesiones. Es el que usan los tests:
--                  chico, estable y con id conocidos.
--   seed_demo.sql  17 pacientes, ~7 semanas de agenda. Es para ver como se
--                  comporta la interfaz con datos parecidos a los reales
--                  y para las pruebas con personas.
--
-- NINGUN test depende de este archivo. Los runners de tests/ construyen sus
-- bases con schema.sql + seed.sql.
--
--   mysql --login-path=asisto -e "source backend/database/seed_demo.sql"
--   python scripts/generar_hashes.py --aplicar --todos
--
-- El segundo paso es obligatorio: sin el, ningun login funciona.
--
-- Todo se genera de forma DETERMINISTICA (aritmetica modular, sin RAND):
-- las cuatro maquinas obtienen exactamente los mismos datos.
-- =====================================================================

-- ESTE ARCHIVO NO ELIGE BASE, Y ES UNA DECISION (2026-09-13).
--
-- Hasta hoy aca decia `USE asisto;`, y aca era peor que en `seed.sql`: a
-- este archivo NO lo carga ningun script del repo, se corre siempre a mano.
-- O sea que la linea no le ahorraba nada a nadie y solo podia hacer dano.
--
-- El dano concreto: `mysql --login-path=asisto otra_base < seed_demo.sql`
-- escribia en `asisto`. Paso el 2026-09-13 y dejo a `asisto` con 640/468 en
-- vez de 644/466; se recupero entera del respaldo previo.
--
-- El nombre de base va SIEMPRE explicito al invocar:
--     mysql --login-path=asisto la_base_que_quieras < seed_demo.sql

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE auditoria_accesos;
TRUNCATE TABLE plantillas_objetivos;
TRUNCATE TABLE informes;
TRUNCATE TABLE sesiones_etiquetas;
TRUNCATE TABLE etiquetas;
TRUNCATE TABLE preferencias_notificacion;
TRUNCATE TABLE notificaciones;
TRUNCATE TABLE familiares_pacientes;
TRUNCATE TABLE observaciones_rrhh;
TRUNCATE TABLE evoluciones;
TRUNCATE TABLE sesiones;
TRUNCATE TABLE objetivos_terapeuticos;
TRUNCATE TABLE asignaciones;
TRUNCATE TABLE pacientes;
TRUNCATE TABLE familiares;
TRUNCATE TABLE rrhh;
TRUNCATE TABLE terapeutas;
TRUNCATE TABLE usuarios;
SET FOREIGN_KEY_CHECKS = 1;


-- =====================================================================
-- USUARIOS — 3 terapeutas, 1 rrhh, 4 familiares, 5 pacientes con login
--
-- Los contrasena_hash son PLACEHOLDERS. Correr generar_hashes.py --todos.
-- =====================================================================
INSERT INTO usuarios (id, nombre, apellido, email, contrasena_hash, activo, rol) VALUES
  (1,  'Laura',    'Fernandez', 'laura.fernandez@asisto.local', '$2b$12$PLACEHOLDER.terapeuta.uno', TRUE,  'terapeuta'),
  (2,  'Diego',    'Moyano',    'diego.moyano@asisto.local',    '$2b$12$PLACEHOLDER.terapeuta.dos', TRUE,  'terapeuta'),
  (3,  'Paula',    'Cabrera',   'paula.cabrera@asisto.local',   '$2b$12$PLACEHOLDER.terapeuta.tre', TRUE,  'terapeuta'),
  (4,  'Silvia',   'Quiroga',   'silvia.quiroga@asisto.local',  '$2b$12$PLACEHOLDER.rrhh.uno.....', TRUE,  'rrhh'),
  (5,  'Marta',    'Ledesma',   'marta.ledesma@asisto.local',   '$2b$12$PLACEHOLDER.familiar.uno.', TRUE,  'familiar'),
  (6,  'Jorge',    'Bustos',    'jorge.bustos@asisto.local',    '$2b$12$PLACEHOLDER.familiar.dos.', TRUE,  'familiar'),
  (7,  'Rosa',     'Aguilar',   'rosa.aguilar@asisto.local',    '$2b$12$PLACEHOLDER.familiar.tres', TRUE,  'familiar'),
  (8,  'Hector',   'Nunez',     'hector.nunez@asisto.local',    '$2b$12$PLACEHOLDER.familiar.cuat', TRUE,  'familiar'),
  (9,  'Camila',   'Rios',      'camila.rios@asisto.local',     '$2b$12$PLACEHOLDER.paciente.uno.', TRUE,  'paciente'),
  (10, 'Nicolas',  'Ferreyra',  'nicolas.ferreyra@asisto.local','$2b$12$PLACEHOLDER.paciente.dos.', TRUE,  'paciente'),
  (11, 'Julieta',  'Vega',      'julieta.vega@asisto.local',    '$2b$12$PLACEHOLDER.paciente.tres', TRUE,  'paciente'),
  (12, 'Matias',   'Ojeda',     'matias.ojeda@asisto.local',    '$2b$12$PLACEHOLDER.paciente.cuat', TRUE,  'paciente'),
  -- Cuenta DESHABILITADA a proposito: sirve para probar que un usuario
  -- inactivo no puede loguear, sin tener que tocar la base a mano.
  (13, 'Andrea',   'Suarez',    'andrea.suarez@asisto.local',   '$2b$12$PLACEHOLDER.paciente.cinc', FALSE, 'paciente'),
  -- Administrador: asigna terapeutas a pacientes. No tiene perfil clinico.
  (14, 'Ramiro',   'Acosta',    'admin@asisto.local',           '$2b$12$PLACEHOLDER.admin.uno....', TRUE,  'admin');

INSERT INTO terapeutas (id, id_usuario, matricula, especialidad, nro_licencia) VALUES
  (1, 1, 'MP-14523', 'Integracion sensorial infantil', 'LIC-2019-0087'),
  (2, 2, 'MP-16890', 'Rehabilitacion neurologica',     'LIC-2021-0154'),
  (3, 3, 'MP-17402', 'Terapia de la mano',             'LIC-2022-0311');

INSERT INTO rrhh (id, id_usuario, sector, nro_legajo) VALUES
  (1, 4, 'Administracion de personal', 'LEG-00231');

INSERT INTO familiares (id, id_usuario, parentesco, telefono) VALUES
  (1, 5, 'Madre', '+54 261 4155023'),
  (2, 6, 'Padre', '+54 261 4788910'),
  (3, 7, 'Abuela', '+54 261 4300712'),
  (4, 8, 'Padre', '+54 261 4922184');


-- =====================================================================
-- PACIENTES — 17
--
-- 12 SIN login (id_usuario NULL): menores, es lo normal. 5 CON login.
-- El contraste es intencional (regla 5) y no hay que "normalizarlo".
-- =====================================================================
INSERT INTO pacientes
  (id, id_usuario, nombre, apellido, fecha_nacimiento, diagnostico, nro_historia, activo, fecha_alta) VALUES
  (1,  NULL, 'Tomas',     'Aguirre',   '2015-03-12', 'Trastorno del procesamiento sensorial. Dificultades en motricidad fina.', 'HC-0001', TRUE, '2026-03-02'),
  (2,  NULL, 'Valentina', 'Sosa',      '2017-08-25', 'Retraso madurativo leve. Hipersensibilidad auditiva.',                    'HC-0002', TRUE, '2026-03-16'),
  (3,  9,    'Camila',    'Rios',      '1998-11-05', 'Lesion de muneca derecha. Rehabilitacion funcional post quirurgica.',     'HC-0003', TRUE, '2026-04-06'),
  (4,  NULL, 'Bruno',     'Peralta',   '2014-09-01', 'Dificultades de coordinacion motora gruesa.',                             'HC-0004', TRUE, '2026-03-09'),
  (5,  NULL, 'Mia',       'Cardozo',   '2016-01-20', 'Trastorno del espectro autista. Nivel 1 de apoyo.',                       'HC-0005', TRUE, '2026-03-23'),
  (6,  10,   'Nicolas',   'Ferreyra',  '2001-06-14', 'Lesion medular incompleta. Reeducacion de actividades diarias.',          'HC-0006', TRUE, '2026-04-13'),
  (7,  NULL, 'Lucia',     'Molina',    '2018-04-03', 'Retraso en el desarrollo del lenguaje y la motricidad.',                  'HC-0007', TRUE, '2026-04-20'),
  (8,  NULL, 'Thiago',    'Ramirez',   '2013-12-11', 'Trastorno por deficit de atencion. Dificultades grafomotoras.',           'HC-0008', TRUE, '2026-03-30'),
  (9,  11,   'Julieta',   'Vega',      '1995-02-28', 'Sindrome del tunel carpiano bilateral. Post operatorio.',                 'HC-0009', TRUE, '2026-04-27'),
  (10, NULL, 'Benicio',   'Herrera',   '2019-07-19', 'Prematurez. Seguimiento del desarrollo psicomotor.',                      'HC-0010', TRUE, '2026-05-04'),
  (11, NULL, 'Renata',    'Godoy',     '2015-10-08', 'Disgrafia. Dificultades en la organizacion espacial.',                    'HC-0011', TRUE, '2026-05-11'),
  (12, 12,   'Matias',    'Ojeda',     '2003-05-22', 'Traumatismo de mano izquierda. Rehabilitacion funcional.',                'HC-0012', TRUE, '2026-05-18'),
  (13, NULL, 'Emilia',    'Paz',       '2017-03-30', 'Hipotonia leve. Trabajo de fuerza y estabilidad postural.',               'HC-0013', TRUE, '2026-05-25'),
  (14, NULL, 'Ciro',      'Maldonado', '2012-08-17', 'Trastorno del desarrollo de la coordinacion.',                            'HC-0014', TRUE, '2026-06-01'),
  (15, 13,   'Andrea',    'Suarez',    '1988-12-02', 'Artritis reumatoidea. Proteccion articular y adaptaciones.',              'HC-0015', TRUE, '2026-06-08'),
  -- Paciente DADO DE BAJA, y CON HISTORIA: sesiones, evoluciones, objetivos
  -- archivados y una asignacion cerrada. Ver el bloque "HISTORIA DEL
  -- PACIENTE 16" mas abajo.
  --
  -- ENTRA ACTIVO Y SE DA DE BAJA AL FINAL DEL ARCHIVO. No es un rodeo: los
  -- triggers rechazan crear objetivos y abrir asignaciones sobre un paciente
  -- dado de baja, y la regla 4 rechaza calificar un objetivo archivado. El
  -- orden del seed es el orden real de los hechos.
  --
  -- Hasta el 2026-08-15 este paciente entraba ya inactivo y sin nada colgando,
  -- asi que el estado "dado de baja" existia pero no se podia MOSTRAR: la
  -- ficha en modo lectura salia vacia y el grafico de evolucion tambien. El
  -- caso interesante no era demostrable en la base de la demo.
  (16, NULL, 'Ignacio',   'Rivas',     '2011-04-25', 'Alta por cumplimiento de objetivos.',                                     'HC-0016', TRUE,
   DATE_SUB(CURDATE(), INTERVAL 150 DAY)),
  -- Paciente RECIEN INGRESADO, con objetivos en FORMATO REAL DE TO.
  -- Ver el bloque "OBJETIVOS DEL PACIENTE 17" mas abajo, que explica de
  -- donde sale y por que la identidad esta cambiada.
  (17, NULL, 'Damian',    'Bustos',    '2009-06-30', 'Discapacidad intelectual leve. Planificacion motora, motricidad fina y autonomia en el vestido.', 'HC-0017', TRUE,
   DATE_SUB(CURDATE(), INTERVAL 4 DAY));


-- =====================================================================
-- ETIQUETAS — colores tomados de frontend/src/theme/theme.js
-- =====================================================================
INSERT INTO etiquetas (id, nombre, color_hex) VALUES
  (1, 'Motricidad fina',              '#3E8E7E'),
  (2, 'Integracion sensorial',        '#1B3B5C'),
  (3, 'Actividades de la vida diaria','#C97B5A'),
  (4, 'Trabajo con familia',          '#7FA99B'),
  (5, 'Requiere seguimiento',         '#D9A441'),
  (6, 'Sesion reprogramada',          '#B5544C');


-- =====================================================================
-- ASIGNACIONES — reemplaza al bloque de duplas_terapeuticas.
--
-- Va ACA, ANTES de la generacion de sesiones (2026-09-28, regla 8): el
-- trigger de sesiones exige una asignacion vigente a la fecha de cada
-- sesion, y `p_generar_demo()`, mas abajo, crea sesiones para los pacientes
-- 1 a 15. Si este bloque quedara despues de la generacion -como estaba
-- hasta esta fecha, junto a "informes"- el primer INSERT de sesiones
-- rechazaria la fila entera por falta de asignacion.
--
-- id_terapeuta apunta a terapeutas(id), igual que sesiones. Las tres
-- terapeutas del seed de demostracion son las terapeutas 1, 2 y 3.
--
-- Una vigente por paciente para los 15, repartidas en round-robin, mas dos
-- CERRADAS que dejan el caso "cambio de terapeuta" representado sin violar
-- la regla de una sola vigente por par.
INSERT INTO asignaciones (id_terapeuta, id_paciente, fecha_desde, fecha_hasta) VALUES
  (1,  1, '2026-03-02', NULL),
  (2,  2, '2026-03-16', NULL),
  (3,  3, '2026-04-06', NULL),
  (1,  4, '2026-03-09', NULL),
  (2,  5, '2026-03-23', NULL),
  (3,  6, '2026-04-13', NULL),
  (1,  7, '2026-04-20', NULL),
  (2,  8, '2026-03-30', NULL),
  (3,  9, '2026-04-27', NULL),
  (1, 10, '2026-05-04', NULL),
  (2, 11, '2026-05-11', NULL),
  (3, 12, '2026-05-18', NULL),
  (1, 13, '2026-05-25', NULL),
  (2, 14, '2026-06-01', NULL),
  (3, 15, '2026-06-08', NULL),
  (2,  1, '2026-03-02', '2026-05-04'),
  (1, 11, '2026-04-06', '2026-05-11');


-- =====================================================================
-- GENERACION DE OBJETIVOS, SESIONES Y EVOLUCIONES
--
-- Se hace con un procedimiento temporal que se borra al final. Escribir a
-- mano ~700 sesiones seria ilegible y se desincronizaria al primer cambio.
--
-- Reglas que respeta la generacion, por construccion:
--
--  * Maximo 4 objetivos activos por paciente (regla 1): se crean entre 2 y
--    4, nunca mas.
--  * Sin solape del terapeuta (regla 6): cada terapeuta usa franjas fijas
--    de una hora (08 a 12 y 13 a 17), una sesion por franja.
--  * UNIQUE (id_paciente, fecha, hora_inicio): en una misma franja los tres
--    terapeutas atienden a pacientes DISTINTOS. El indice de paciente es
--    ((terapeuta-1)*5 + dia + franja*7) MOD 15 — como 7 y 15 son coprimos,
--    un terapeuta ve 8 pacientes distintos en el dia, y el desfasaje de 5
--    entre terapeutas evita que dos coincidan en la misma franja.
--  * Sin evolucion sobre ausencias (regla 2).
--  * La evolucion siempre va contra un objetivo ACTIVO del paciente de esa
--    sesion (reglas 3 y 4). Los objetivos se archivan DESPUES de generar
--    las evoluciones, para que queden archivados CON historia — que es el
--    caso realista.
--  * Asignacion vigente a la fecha de la sesion (regla 8): la cubre el
--    bloque de ASIGNACIONES de arriba, cargado ANTES por eso mismo. Las 15
--    son vigentes sin fecha_hasta desde 2026-03/06, y la ventana que genera
--    este procedimiento son las ultimas 7 semanas contadas desde CURDATE(),
--    siempre muy posterior.
-- =====================================================================

DROP PROCEDURE IF EXISTS p_generar_demo;

DELIMITER $$

CREATE PROCEDURE p_generar_demo()
BEGIN
  DECLARE v_pac        INT DEFAULT 1;
  DECLARE v_num        INT;
  DECLARE v_cant       INT;
  DECLARE v_dia        DATE;
  DECLARE v_fin        DATE;
  DECLARE v_dow        INT;
  DECLARE v_indice_dia INT DEFAULT 0;
  DECLARE v_ter        INT;
  DECLARE v_slot       INT;
  DECLARE v_slots      INT;
  DECLARE v_hora       TIME;
  DECLARE v_id_pac     INT;
  DECLARE v_estado     VARCHAR(20);
  DECLARE v_ausencia_de VARCHAR(20);
  DECLARE v_contador   INT DEFAULT 0;
  DECLARE v_id_sesion  INT;
  DECLARE v_n_obj      INT;
  DECLARE v_off        INT;
  DECLARE v_id_obj     INT;

  -- La agenda termina HOY y arranca siete semanas antes.
  --
  -- Antes eran fechas fijas y el panel del dia quedaba vacio apenas
  -- pasaba la ventana: la pantalla en la que cae el terapeuta al entrar
  -- no mostraba nada. Con fechas relativas siempre hay algo que ver.
  --
  -- Sigue siendo deterministico PARA UNA MISMA FECHA DE CORRIDA: dos
  -- maquinas que carguen el seed el mismo dia obtienen exactamente los
  -- mismos datos. Lo que cambia entre dias es la ventana, no el contenido.
  --
  -- Nunca pasa de hoy: en la Entrega 1 no hay agenda a futuro, las
  -- sesiones se registran cuando ocurren o despues.
  SET v_fin = CURDATE();
  SET v_dia = DATE_SUB(v_fin, INTERVAL 48 DAY);

  -- --- Objetivos: entre 2 y 4 activos por paciente ---
  -- Creados un mes antes de la primera sesion, para que toda la agenda
  -- los cuente en el denominador de "objetivos calificados".
  WHILE v_pac <= 15 DO
    SET v_cant = 2 + (v_pac MOD 3);
    SET v_num = 1;
    WHILE v_num <= v_cant DO
      INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo, fecha_creacion)
      VALUES (
        v_pac,
        CASE v_num
          WHEN 1 THEN 'Mejorar la precision en actividades de motricidad fina'
          WHEN 2 THEN 'Tolerar estimulos sensoriales nuevos sin rechazo'
          WHEN 3 THEN 'Sostener la atencion en tareas de diez minutos'
          ELSE        'Realizar actividades de la vida diaria de forma autonoma'
        END,
        TRUE,
        TIMESTAMP(DATE_SUB(v_dia, INTERVAL 30 DAY), SEC_TO_TIME(v_num * 900))
      );
      SET v_num = v_num + 1;
    END WHILE;
    SET v_pac = v_pac + 1;
  END WHILE;

  -- --- Un objetivo en el FORMATO REAL de la practica ---
  --
  -- Los cuatro de arriba son frases cortas de 46 a 56 caracteres, y con eso
  -- se valido toda la Entrega 1. El formato que usan las terapeutas de
  -- verdad es "Que [paciente] [verbo de logro] [conducta observable], [nivel
  -- de apoyo], [criterio de medicion], [contexto], [plazo]", y ronda los 400
  -- caracteres. Este objetivo existe para que las pantallas se prueben contra
  -- el largo que van a tener y no contra el que era comodo.
  --
  -- DATOS SINTETICOS: la conducta, el criterio y el plazo son inventados para
  -- el seed. No salen de ningun caso real. Tomas Aguirre es un paciente
  -- ficticio de este mismo archivo.
  --
  -- Va al paciente 1, que queda con 3 objetivos de la vuelta anterior (v_cant
  -- = 2 + (1 MOD 3) = 3) y tiene cupo para un cuarto. Se crea con la misma
  -- fecha que los otros para que toda la agenda lo cuente en el denominador
  -- de "objetivos calificados".
  --
  -- Los demas objetivos del seed NO se reescriben: es una tarea aparte.
  INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo, fecha_creacion)
  VALUES (
    1,
    'Que Tomas logre sostener el trazo dentro del renglon al copiar palabras '
    'de cinco letras en letra cursiva, con apoyo verbal intermitente y sin '
    'sujecion fisica de la mano, alcanzando cuatro de cada cinco intentos '
    'correctos en dos evaluaciones consecutivas realizadas en semanas '
    'distintas, en el consultorio y en el cuaderno de tareas de la escuela, '
    'dos veces por semana durante el segundo semestre del 2026.',
    TRUE,
    TIMESTAMP(DATE_SUB(v_dia, INTERVAL 30 DAY), SEC_TO_TIME(4 * 900))
  );

  -- --- Agenda: 7 semanas hasta hoy, lunes a viernes, 3 terapeutas ---
  WHILE v_dia <= v_fin DO
    SET v_dow = DAYOFWEEK(v_dia);   -- 1 = domingo, 7 = sabado

    IF v_dow BETWEEN 2 AND 6 THEN
      SET v_ter = 1;
      WHILE v_ter <= 3 DO
        -- Entre 3 y 5 sesiones por dia y por terapeuta (cinco pacientes
        -- asignados a cada una, regla 8). Los dias con 5 son los que
        -- interesan para ver la interfaz cargada.
        SET v_slots = 3 + ((v_indice_dia + v_ter) MOD 3);
        SET v_slot = 0;

        WHILE v_slot < v_slots DO
          -- Franjas de una hora, con corte de 12 a 13
          SET v_hora = MAKETIME(IF(v_slot < 4, 8 + v_slot, 9 + v_slot), 0, 0);
          -- Regla 8: cada terapeuta atiende SOLO a sus cinco pacientes
          -- asignados (v_ter, v_ter + 3, v_ter + 6, ...), que es el reparto
          -- round-robin del bloque de ASIGNACIONES. Como v_slot < 5, las
          -- sesiones de un mismo dia caen en pacientes distintos.
          SET v_id_pac = v_ter + 3 * ((v_slot + v_indice_dia) MOD 5);
          SET v_contador = v_contador + 1;

          SET v_estado = CASE
            WHEN v_contador MOD 11 = 0 THEN 'ausencia'
            WHEN v_contador MOD 7 = 0  THEN 'incompleta'
            ELSE 'completa'
          END;

          -- QUIEN FALTO, solo cuando v_estado = 'ausencia' (2026-09-11).
          -- Distribucion NO uniforme, a proposito: un seed donde todas las
          -- ausencias son del paciente describe un mundo donde el terapeuta
          -- nunca falta, y RRHH se prueba contra este seed. v_contador llega
          -- aca ya siendo multiplo de 11 (es la condicion de arriba), asi
          -- que v_contador DIV 11 es el numero de orden de ESTA ausencia
          -- (1a, 2a, 3a...). Una de cada cinco (la 5a, 10a, 15a...) se marca
          -- 'terapeuta'; el resto, 'paciente'. Sobre 59 ausencias totales
          -- (medido en la base) da 11 terapeuta / 48 paciente, ~19%/81%:
          -- minoria real, no cero.
          SET v_ausencia_de = CASE
            WHEN v_estado = 'ausencia' AND (v_contador DIV 11) MOD 5 = 0
              THEN 'terapeuta'
            WHEN v_estado = 'ausencia'
              THEN 'paciente'
            ELSE NULL
          END;

          INSERT INTO sesiones
            (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado,
             ausencia_de, notas)
          VALUES (
            v_ter, v_id_pac, v_dia, v_hora, ADDTIME(v_hora, '01:00:00'), v_estado,
            v_ausencia_de,
            CASE v_estado
              WHEN 'ausencia' THEN
                CASE v_ausencia_de
                  WHEN 'terapeuta' THEN 'El terapeuta debio reprogramar por una urgencia.'
                  ELSE                  'No asistio. Se aviso a la familia.'
                END
              WHEN 'incompleta' THEN 'Se trabajo parcialmente, la sesion se corto antes.'
              ELSE                   'Sesion trabajada segun el plan previsto.'
            END
          );
          SET v_id_sesion = LAST_INSERT_ID();

          -- Etiqueta: una cada tres sesiones, rotando el catalogo
          IF v_contador MOD 3 = 0 THEN
            INSERT INTO sesiones_etiquetas (id_sesion, id_etiqueta)
            VALUES (v_id_sesion, 1 + (v_contador MOD 6));
          END IF;

          -- Evolucion. Se saltea una de cada cinco a proposito: son las
          -- que la interfaz tiene que mostrar como pendientes.
          --
          -- Y se saltea SIEMPRE la segunda sesion de hoy de cada terapeuta:
          -- asi el panel del dia —que es la pantalla de entrada— muestra
          -- siempre el marcador de "falta la evolucion". Sin esto, que se
          -- vea o no dependia de donde caia el contador ese dia.
          IF v_estado <> 'ausencia'
             AND (v_contador MOD 5) <> 0
             AND NOT (v_dia = v_fin AND v_slot = 1) THEN
            SELECT COUNT(*) INTO v_n_obj
              FROM objetivos_terapeuticos
             WHERE id_paciente = v_id_pac AND activo = TRUE;

            IF v_n_obj > 0 THEN
              SET v_off = v_contador MOD v_n_obj;
              SELECT id INTO v_id_obj
                FROM objetivos_terapeuticos
               WHERE id_paciente = v_id_pac AND activo = TRUE
               ORDER BY id
               LIMIT 1 OFFSET v_off;

              INSERT INTO evoluciones (id_sesion, id_objetivo, valor, observaciones)
              VALUES (
                v_id_sesion, v_id_obj, 1 + (v_contador MOD 5),
                CASE v_contador MOD 4
                  WHEN 0 THEN 'Buena disposicion durante toda la actividad.'
                  WHEN 1 THEN 'Necesito apoyo verbal en la segunda mitad.'
                  WHEN 2 THEN 'Avance respecto de la semana anterior.'
                  ELSE        'Sostuvo la consigna con ayuda puntual.'
                END
              );
            END IF;
          END IF;

          SET v_slot = v_slot + 1;
        END WHILE;

        SET v_ter = v_ter + 1;
      END WHILE;

      SET v_indice_dia = v_indice_dia + 1;
    END IF;

    SET v_dia = DATE_ADD(v_dia, INTERVAL 1 DAY);
  END WHILE;

  -- --- Archivado: uno de cada tres pacientes archiva un objetivo ---
  -- Se hace al final, para que el objetivo archivado conserve las
  -- evoluciones que se le cargaron mientras estaba activo.
  -- fecha_archivado la completa el trigger.
  SET v_pac = 3;
  WHILE v_pac <= 15 DO
    SELECT MAX(id) INTO v_id_obj
      FROM objetivos_terapeuticos
     WHERE id_paciente = v_pac AND activo = TRUE;

    -- Solo si quedan al menos 3 activos (minimo de la Entrega 3).
    IF v_id_obj IS NOT NULL AND (
         SELECT COUNT(*) FROM objetivos_terapeuticos
          WHERE id_paciente = v_pac AND activo = TRUE) > 3 THEN
      UPDATE objetivos_terapeuticos SET activo = FALSE WHERE id = v_id_obj;
    END IF;

    SET v_pac = v_pac + 3;
  END WHILE;
END$$

DELIMITER ;

CALL p_generar_demo();
DROP PROCEDURE p_generar_demo;


-- =====================================================================
-- HISTORIA DEL PACIENTE 16 — el que despues queda dado de baja
--
-- DATOS SINTETICOS. Ignacio Rivas es un paciente ficticio de este archivo;
-- las conductas, las observaciones y las fechas son inventadas para el seed.
--
-- POR QUE ESTA SEPARADO DE LA GENERACION DE ARRIBA: esa recorre los
-- pacientes 1..15 y les arma la agenda de las ultimas 7 semanas. Este
-- tratamiento TERMINO, asi que su historia va en una ventana anterior —de
-- 140 a 91 dias atras— y no se cruza con esa agenda. Al no compartir ninguna
-- fecha con ella, no puede violar la regla 6 ni la UNIQUE de paciente por
-- franja, sin importar que franja use.
--
-- EL ORDEN DE ESTE BLOQUE ES LA PARTE FRAGIL, y esta impuesto por los
-- triggers, no por gusto:
--   1. objetivos ACTIVOS  (un objetivo no se puede crear sobre un paciente
--      dado de baja, ni calificar si esta archivado)
--   2. asignacion, ANTES de las sesiones (2026-09-28, regla 8: el trigger de
--      sesiones exige asignacion vigente a la fecha de cada una)
--   3. sesiones y evoluciones
--   4. archivado de los objetivos
--   5. cerrar la asignacion el dia de la baja
--   6. la baja del paciente, al final
-- Invertir cualquiera de los pasos hace fallar la carga, no la degrada en
-- silencio. El seed es, en ese sentido, una prueba de que las reglas estan.
-- =====================================================================

-- 1. Tres objetivos, creados poco despues del alta.
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo, fecha_creacion) VALUES
  (16, 'Recuperar la fuerza de prension en la mano derecha', TRUE,
   TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 145 DAY), '09:00:00')),
  (16, 'Retomar la escritura sostenida durante quince minutos', TRUE,
   TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 145 DAY), '09:15:00')),
  (16, 'Vestirse y calzarse de forma autonoma antes de salir', TRUE,
   TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 145 DAY), '09:30:00'));

-- 2. Asignacion con la terapeuta 2, ABIERTA por ahora (se cierra en el paso
--    5, el dia de la baja). Tiene que cubrir las ocho sesiones del paso 3,
--    de 140 a 91 dias atras: fecha_desde en 150 alcanza sobra.
INSERT INTO asignaciones (id_terapeuta, id_paciente, fecha_desde, fecha_hasta) VALUES
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 150 DAY), NULL);

-- 3. Ocho sesiones semanales con la terapeuta 2, en una franja que la agenda
--    generada no usa en esas fechas porque no llega hasta ahi.
--
--    Dos sesiones caen EL MISMO DIA (la de 140 y una segunda a las 18:00):
--    es el caso que hace visible el apilado de marcas del grafico, y ocurre
--    de verdad —un paciente puede tener dos turnos el mismo dia—.
-- Las dos ausencias de esta historia van 'paciente': el mismo criterio que
-- seed.sql -- las notas ya escritas ("avisó la familia", "no asistió, sin
-- aviso") describen falta del paciente, no del terapeuta, y esta es una
-- historia fija de un solo paciente, no la muestra grande donde importa la
-- variedad (esa es la del generador de arriba).
INSERT INTO sesiones (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, ausencia_de, notas) VALUES
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 140 DAY), '17:00:00', '18:00:00', 'completa', NULL,
   'Primera sesion. Se toma linea de base de fuerza y escritura.'),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 140 DAY), '18:00:00', '19:00:00', 'incompleta', NULL,
   'Segundo turno del mismo dia. Se corto antes por cansancio.'),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 133 DAY), '17:00:00', '18:00:00', 'completa', NULL,
   'Trabajo de prension con masa y pinzas.'),
  -- Este dia tiene DOS sesiones y una es ausencia: es el caso que hace
  -- visible por que las marcas se apilan. Si se superpusieran, el ambar de
  -- la sesion trabajada taparia el ladrillo de la ausencia —o al reves— y
  -- una ausencia desapareceria del grafico. Eso es informacion clinica
  -- oculta, no una molestia de densidad.
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 126 DAY), '17:00:00', '18:00:00', 'ausencia', 'paciente',
   'La familia aviso el dia anterior.'),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 126 DAY), '18:00:00', '19:00:00', 'completa', NULL,
   'Se recupero el turno mas tarde. No se llego a calificar.'),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 119 DAY), '17:00:00', '18:00:00', 'completa', NULL,
   'Retoma el trazo con apoyo verbal.'),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 112 DAY), '17:00:00', '18:00:00', 'completa', NULL,
   'Practica de vestido con prendas propias.'),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 105 DAY), '17:00:00', '18:00:00', 'ausencia', 'paciente',
   'No asistio, sin aviso.'),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL  98 DAY), '17:00:00', '18:00:00', 'completa', NULL,
   'Escritura sostenida sin recordatorios.'),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL  91 DAY), '17:00:00', '18:00:00', 'completa', NULL,
   'Cierre del tratamiento. Se repasan los tres objetivos.');

-- 4. Evoluciones. NO se califican todos los objetivos en todas las sesiones
--    —que es lo habitual— asi que el grafico queda con tramos punteados, que
--    es justamente lo que hay que poder mirar. Las dos ausencias no llevan
--    evolucion: la regla 2 lo impide.
INSERT INTO evoluciones (id_sesion, id_objetivo, valor, observaciones)
SELECT s.id, o.id, x.valor, x.obs
  FROM (
    SELECT 140 AS dias, '17:00:00' AS hora, 1 AS n_obj, 1 AS valor,
           'Prension debil, sin sostener el agarre.' AS obs
    UNION ALL SELECT 140, '17:00:00', 2, 1, 'No sostiene el trazo mas de dos minutos.'
    UNION ALL SELECT 133, '17:00:00', 1, 2, 'Sostiene el agarre con apoyo.'
    UNION ALL SELECT 119, '17:00:00', 2, 2, 'Trazo mas firme, con recordatorios.'
    UNION ALL SELECT 112, '17:00:00', 3, 2, 'Se calza solo, con ayuda para el cierre.'
    UNION ALL SELECT  98, '17:00:00', 1, 4, 'Prension funcional en actividades largas.'
    UNION ALL SELECT  98, '17:00:00', 2, 4, 'Quince minutos sostenidos sin recordatorio.'
    UNION ALL SELECT  91, '17:00:00', 1, 5, 'Objetivo alcanzado.'
    UNION ALL SELECT  91, '17:00:00', 2, 5, 'Objetivo alcanzado.'
    UNION ALL SELECT  91, '17:00:00', 3, 4, 'Autonomo salvo cordones.'
  ) AS x
  JOIN sesiones s
    ON s.id_paciente = 16
   AND s.fecha = DATE_SUB(CURDATE(), INTERVAL x.dias DAY)
   AND s.hora_inicio = x.hora
  JOIN (
    SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS n
      FROM objetivos_terapeuticos WHERE id_paciente = 16
  ) AS o ON o.n = x.n_obj;

-- 5. Cierra la asignacion abierta en el paso 2: esa terapeuta lo atendio y
--    ya no. UPDATE y no un segundo INSERT -la fila ya existe desde el
--    paso 2, y el trigger de asignaciones rechazaria una segunda vigente
--    para el mismo par mientras la primera siga abierta.
UPDATE asignaciones
   SET fecha_hasta = DATE_SUB(CURDATE(), INTERVAL 90 DAY)
 WHERE id_terapeuta = 2 AND id_paciente = 16 AND fecha_hasta IS NULL;

-- 6. Archivado de los objetivos. Son DOS updates y el segundo no sobra: el
--    primero archiva y el trigger le pone a fecha_archivado el NOW() de la
--    carga; el segundo la fija en el dia de la baja. Con activo pasando de
--    FALSE a FALSE ninguna rama del trigger se dispara, asi que el valor
--    queda como se escribe y el fixture no cambia de contenido en cada carga.
--    La baja va ANTES: con el paciente de baja el trigger no exige el minimo
--    de 3 objetivos activos al archivar (rige solo en tratamiento).
UPDATE pacientes
   SET activo = FALSE,
       fecha_baja = DATE_SUB(CURDATE(), INTERVAL 90 DAY),
       tipo_cierre = 'alta'
 WHERE id = 16;

UPDATE objetivos_terapeuticos
   SET activo = FALSE
 WHERE id_paciente = 16 AND activo = TRUE;

UPDATE objetivos_terapeuticos
   SET fecha_archivado = TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 90 DAY), '12:00:00')
 WHERE id_paciente = 16;


-- =====================================================================
-- OBJETIVOS DEL PACIENTE 17 — el formato real, medido contra un caso real
--
-- DE DONDE SALE. El 2026-08-15 una terapeuta ocupacional externa uso el
-- sistema sin que nadie le explicara nada y cargo un paciente con tres
-- objetivos. Es la unica muestra que tuvo este proyecto de como escribe una
-- TO cuando no la esta mirando nadie, y desmintio de primera mano el
-- supuesto con el que se valido toda la Entrega 1: sus tres objetivos miden
-- 145, 210 y 182 caracteres contra los 46-56 del resto del seed.
--
-- IDENTIDAD CAMBIADA, Y NO ES UN DETALLE. Lo que se conserva es la FORMA:
-- el largo exacto (145 / 210 / 182), el verbo de logro, la conducta
-- observable, el nivel de apoyo, el criterio de medicion, el contexto y el
-- plazo. Lo que NO entra al repositorio es su texto: nombre, fecha de
-- nacimiento, diagnostico y las conductas concretas estan cambiados, porque
-- detras de ese registro puede haber un chico real y la autorizacion de la
-- terapeuta no alcanza para el. Damian Bustos es un paciente ficticio de
-- este archivo, igual que Tomas Aguirre e Ignacio Rivas. El material
-- original queda fuera del repositorio.
--
-- POR QUE SIN TILDES. Todo el dato de este seed es ASCII —los unicos bytes
-- altos del archivo son guiones largos de comentario— y aca se respeta.
-- Ojo con una en particular: "ano" sin la enie no es la palabra que se
-- quiere en un texto clinico, asi que el plazo va como "del primer semestre
-- del 2026", igual que el objetivo largo del paciente 1.
--
-- POR QUE NO HAY SESIONES NI EVOLUCION. Ella tambien agendo una sesion (dos
-- dias en el futuro) y le cargo la evolucion en el acto. Ese caso NO se
-- siembra: mete en el fixture una sesion futura declarada "completa", que
-- es justo el hallazgo abierto sobre el default del modal de sesiones. El
-- paciente queda con objetivos y sin agenda, que es el estado real de
-- cualquier alta reciente. Sin sesiones no hay serie que graficar y la
-- pestania Progreso muestra su estado vacio, que aca SI es verdadero.
--
-- Los tres se crean el mismo dia del alta y de noche, con pocos minutos
-- entre uno y otro, porque asi se cargaron: es parte del registro de como
-- se usa el sistema de verdad.
-- =====================================================================
INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo, fecha_creacion) VALUES
  (17,
   'Que Damian logre subir y bajar escaleras alternando los pies, con '
   'supervision cercana del terapeuta a cargo, durante el primer semestre '
   'del 2026.',
   TRUE, TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 4 DAY), '22:14:00')),
  (17,
   'Que Damian logre abrochar botones medianos en prendas cotidianas '
   '(camisa y campera), con asistencia fisica y verbal, en 2 de 3 '
   'oportunidades, en el contexto del consultorio, durante el primer '
   'semestre del 2026.',
   TRUE, TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 4 DAY), '22:16:00')),
  (17,
   'Que Damian logre servirse agua de una jarra liviana sin derramar sobre '
   'la mesada, con asistencia moderada del terapeuta, en 2 de 5 '
   'oportunidades, durante el primer semestre del 2026.',
   TRUE, TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 4 DAY), '22:20:00'));

-- ASIGNACION DEL PACIENTE 17 (2026-09-28, regla 8 — asignacion vigente a la
-- fecha de la sesion).
--
-- Hasta esta fecha el paciente 17 quedaba activo y con objetivos, pero sin
-- ninguna fila en `asignaciones` (medido el 2026-09-22, ver ESTADO.md). Con
-- la regla 8 en el trigger de sesiones eso lo vuelve INATENDIBLE: ningun
-- terapeuta podria registrarle una sesion nueva, en un seed cuyo relato es
-- justo "paciente recien ingresado, todavia sin agenda".
--
-- Terapeuta 2 por el mismo round-robin que el bloque de arriba
-- (id_paciente % 3 == 2 -> terapeuta 2). Misma fecha que el alta, relativa
-- a CURDATE() como el resto de este paciente: fijarla en un literal la
-- desincroniza de `fecha_alta` la proxima vez que alguien cargue este seed
-- en otro dia, y una asignacion anterior al alta no tiene sentido clinico.
INSERT INTO asignaciones (id_terapeuta, id_paciente, fecha_desde, fecha_hasta) VALUES
  (2, 17, DATE_SUB(CURDATE(), INTERVAL 4 DAY), NULL);


-- =====================================================================
-- VINCULOS FAMILIARES, NOTIFICACIONES Y RESTO
-- =====================================================================
INSERT INTO familiares_pacientes (id_familiar, id_paciente, fecha_vinculo) VALUES
  (1, 1, '2026-03-02'), (1, 5, '2026-03-23'),
  (2, 2, '2026-03-16'),
  (3, 7, '2026-04-20'), (3, 10, '2026-05-04'),
  (4, 8, '2026-03-30'), (4, 11, '2026-05-11');

INSERT INTO preferencias_notificacion (id_familiar, tipo, habilitada) VALUES
  (1, 'nueva_sesion', TRUE),  (1, 'informe_generado', TRUE),  (1, 'cambio_objetivo', TRUE),
  (2, 'nueva_sesion', TRUE),  (2, 'informe_generado', TRUE),  (2, 'cambio_objetivo', FALSE),
  (3, 'nueva_sesion', FALSE), (3, 'informe_generado', TRUE),  (3, 'cambio_objetivo', TRUE),
  (4, 'nueva_sesion', TRUE),  (4, 'informe_generado', FALSE), (4, 'cambio_objetivo', TRUE);

-- Los textos llevan tildes pero el archivo es ASCII: se escriben como bytes
-- UTF-8 en hexadecimal y se convierten (Windows carga este archivo sin
-- depender de la codificacion de consola).
INSERT INTO notificaciones (id_familiar, id_paciente, tipo, mensaje, leida, fecha) VALUES
  (1, 1, 'nueva_sesion', CONVERT(0x53652072656769737472C3B3206C612073657369C3B36E2064656C2030322F30362F3230323620646520546F6D61732E USING utf8mb4), TRUE, '2026-06-02 10:05:00'),
  (1, 1, 'cambio_objetivo', CONVERT(0x536520617263686976C3B320756E206F626A657469766F2064656C20706C616E20646520546F6D61733A20536F7374656E6572206C61206174656E6369C3B36E20656E207461726561732064652063696E636F206D696E75746F732E USING utf8mb4), TRUE, '2026-06-20 11:05:00'),
  (1, 5, 'informe_generado', CONVERT(0x596120657374C3A120646973706F6E69626C6520756E20696E666F726D65206E7565766F206465204D69612E USING utf8mb4), FALSE, '2026-07-01 09:00:00'),
  (2, 2, 'nueva_sesion', CONVERT(0x53652072656769737472C3B3206C612073657369C3B36E2064656C2030332F30362F323032362064652056616C656E74696E612E USING utf8mb4), FALSE, '2026-06-10 12:05:00'),
  (3, 7, 'nueva_sesion', CONVERT(0x53652072656769737472C3B3206C612073657369C3B36E2064656C2030342F30362F32303236206465204C7563C3AD612E USING utf8mb4), FALSE, '2026-06-11 09:30:00'),
  (3, 10, 'informe_generado', CONVERT(0x596120657374C3A120646973706F6E69626C6520756E20696E666F726D65206E7565766F2064652042656E6963696F2E USING utf8mb4), FALSE, '2026-07-01 09:10:00'),
  (4, 8, 'cambio_objetivo', CONVERT(0x5365206167726567C3B320756E206F626A657469766F20616C20706C616E2064652054686961676F3A205265636F6E6F6365722079206E6F6D627261722063756174726F20656D6F63696F6E65732062C3A173696361732E USING utf8mb4), TRUE, '2026-06-15 16:20:00'),
  (4, 11, 'nueva_sesion', CONVERT(0x53652072656769737472C3B3206C612073657369C3B36E2064656C2031372F30362F323032362064652052656E6174612E USING utf8mb4), FALSE, '2026-06-18 11:00:00');

-- Observaciones tecnicas de RRHH sobre las primeras ausencias registradas
INSERT INTO observaciones_rrhh (id_sesion, id_rrhh, texto)
SELECT id, 1, 'Ausencia registrada. Se notifico a coordinacion.'
  FROM sesiones WHERE estado = 'ausencia' ORDER BY id LIMIT 12;

INSERT INTO informes
  (id_paciente, id_terapeuta, periodo, contenido, contenido_original, estado, fecha_generacion, fecha_publicacion) VALUES
  (1, 1, '2026-T2',
   'Durante el segundo trimestre se observaron avances sostenidos en motricidad fina y en tolerancia a estimulos nuevos.',
   'El paciente mostro mejoras en el trimestre.',
   'final', '2026-07-01 08:30:00', '2026-07-01 09:00:00'),
  (5, 1, '2026-T2', NULL,
   'Registro de asistencia regular con avances parciales en autonomia.',
   'borrador', '2026-07-01 08:45:00', NULL),
  (7, 2, '2026-T2', NULL,
   'Progreso en lenguaje y coordinacion durante el periodo.',
   'borrador', '2026-07-02 10:15:00', NULL);

INSERT INTO plantillas_objetivos (area, descripcion) VALUES
  ('Motricidad fina',       'Mejorar la pinza fina para la escritura'),
  ('Motricidad fina',       'Realizar encastres de piezas pequenas sin ayuda'),
  ('Motricidad gruesa',     'Mantener el equilibrio en una pierna por 10 segundos'),
  ('Motricidad gruesa',     'Subir y bajar escaleras alternando los pies'),
  ('Integracion sensorial', 'Tolerar texturas nuevas en la alimentacion'),
  ('Integracion sensorial', 'Regular la respuesta a estimulos auditivos'),
  ('Vida diaria',           'Vestirse de forma autonoma'),
  ('Vida diaria',           'Utilizar cubiertos de manera independiente'),
  ('Atencion',              'Sostener la atencion en tareas de 10 minutos'),
  ('Rehabilitacion',        'Recuperar rango de movimiento en muneca derecha'),
  ('Rehabilitacion',        'Reintegrarse a la actividad laboral habitual');

INSERT INTO auditoria_accesos (id_usuario, email, resultado, ip, fecha) VALUES
  (1,    'laura.fernandez@asisto.local', 'exitoso',   '192.168.1.24',  '2026-06-01 08:45:00'),
  (2,    'diego.moyano@asisto.local',    'exitoso',   '192.168.1.31',  '2026-06-01 08:50:00'),
  (3,    'paula.cabrera@asisto.local',   'exitoso',   '192.168.1.44',  '2026-06-01 08:52:00'),
  (4,    'silvia.quiroga@asisto.local',  'fallido',   '192.168.1.15',  '2026-06-05 09:12:00'),
  (NULL, 'noexiste@asisto.local',        'fallido',   '201.190.44.10', '2026-06-05 09:14:00'),
  (4,    'silvia.quiroga@asisto.local',  'exitoso',   '192.168.1.15',  '2026-06-05 09:15:00'),
  (13,   'andrea.suarez@asisto.local',   'bloqueado', '190.15.22.100', '2026-06-08 21:03:00');


-- =====================================================================
-- RESUMEN
-- =====================================================================
SELECT 'Datos de demostracion cargados' AS resultado;

SELECT
  (SELECT COUNT(*) FROM usuarios)                                        AS usuarios,
  (SELECT COUNT(*) FROM pacientes)                                       AS pacientes,
  (SELECT COUNT(*) FROM pacientes WHERE id_usuario IS NULL)              AS sin_login,
  (SELECT COUNT(*) FROM pacientes WHERE activo = FALSE)                  AS dados_de_baja,
  (SELECT COUNT(*) FROM objetivos_terapeuticos)                          AS objetivos,
  (SELECT COUNT(*) FROM objetivos_terapeuticos WHERE activo = FALSE)     AS archivados,
  (SELECT COUNT(*) FROM sesiones)                                        AS sesiones,
  (SELECT COUNT(*) FROM evoluciones)                                     AS evoluciones;

SELECT estado, COUNT(*) AS cantidad FROM sesiones GROUP BY estado ORDER BY cantidad DESC;

SELECT 'Sesiones sin evolucion (pendientes)' AS detalle, COUNT(*) AS cantidad
  FROM sesiones s
 WHERE s.estado <> 'ausencia'
   AND NOT EXISTS (SELECT 1 FROM evoluciones e WHERE e.id_sesion = s.id);

SELECT 'Dia mas cargado' AS detalle, fecha, id_terapeuta, COUNT(*) AS sesiones
  FROM sesiones GROUP BY fecha, id_terapeuta ORDER BY sesiones DESC, fecha LIMIT 1;
