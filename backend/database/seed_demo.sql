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
TRUNCATE TABLE agenda_recurrente;
TRUNCATE TABLE plantillas_objetivos;
TRUNCATE TABLE informes;
TRUNCATE TABLE sesiones_etiquetas;
TRUNCATE TABLE etiquetas;
TRUNCATE TABLE preferencias_notificacion;
TRUNCATE TABLE notificaciones;
TRUNCATE TABLE ingreso_respuestas;
TRUNCATE TABLE ingreso_etapas;
TRUNCATE TABLE ingresos;
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
  (1,  'Laura',    CONVERT(0x4665726EC3A16E64657A USING utf8mb4), 'laura.fernandez@asisto.local', '$2b$12$PLACEHOLDER.terapeuta.uno', TRUE,  'terapeuta'),
  (2,  'Diego',    'Moyano',    'diego.moyano@asisto.local',    '$2b$12$PLACEHOLDER.terapeuta.dos', TRUE,  'terapeuta'),
  (3,  'Paula',    'Cabrera',   'paula.cabrera@asisto.local',   '$2b$12$PLACEHOLDER.terapeuta.tre', TRUE,  'terapeuta'),
  (4,  'Silvia',   'Quiroga',   'silvia.quiroga@asisto.local',  '$2b$12$PLACEHOLDER.rrhh.uno.....', TRUE,  'rrhh'),
  (5,  'Marta',    'Ledesma',   'marta.ledesma@asisto.local',   '$2b$12$PLACEHOLDER.familiar.uno.', TRUE,  'familiar'),
  (6,  'Jorge',    'Bustos',    'jorge.bustos@asisto.local',    '$2b$12$PLACEHOLDER.familiar.dos.', TRUE,  'familiar'),
  (7,  'Rosa',     'Aguilar',   'rosa.aguilar@asisto.local',    '$2b$12$PLACEHOLDER.familiar.tres', TRUE,  'familiar'),
  (8,  CONVERT(0x48C3A963746F72 USING utf8mb4),   CONVERT(0x4EC3BAC3B1657A USING utf8mb4),     'hector.nunez@asisto.local',    '$2b$12$PLACEHOLDER.familiar.cuat', TRUE,  'familiar'),
  (9,  'Camila',   CONVERT(0x52C3AD6F73 USING utf8mb4),      'camila.rios@asisto.local',     '$2b$12$PLACEHOLDER.paciente.uno.', TRUE,  'paciente'),
  (10, CONVERT(0x4E69636F6CC3A173 USING utf8mb4),  'Ferreyra',  'nicolas.ferreyra@asisto.local','$2b$12$PLACEHOLDER.paciente.dos.', TRUE,  'paciente'),
  (11, 'Julieta',  'Vega',      'julieta.vega@asisto.local',    '$2b$12$PLACEHOLDER.paciente.tres', TRUE,  'paciente'),
  (12, CONVERT(0x4D6174C3AD6173 USING utf8mb4),   'Ojeda',     'matias.ojeda@asisto.local',    '$2b$12$PLACEHOLDER.paciente.cuat', TRUE,  'paciente'),
  -- Cuenta DESHABILITADA a proposito: sirve para probar que un usuario
  -- inactivo no puede loguear, sin tener que tocar la base a mano.
  (13, 'Andrea',   CONVERT(0x5375C3A172657A USING utf8mb4),    'andrea.suarez@asisto.local',   '$2b$12$PLACEHOLDER.paciente.cinc', FALSE, 'paciente'),
  -- Administrador: asigna terapeutas a pacientes. No tiene perfil clinico.
  (14, 'Ramiro',   'Acosta',    'admin@asisto.local',           '$2b$12$PLACEHOLDER.admin.uno....', TRUE,  'admin');

INSERT INTO terapeutas (id, id_usuario, matricula, especialidad, nro_licencia) VALUES
  (1, 1, 'MP-14523', CONVERT(0x496E74656772616369C3B36E2073656E736F7269616C20696E66616E74696C USING utf8mb4), 'LIC-2019-0087'),
  (2, 2, 'MP-16890', CONVERT(0x5265686162696C6974616369C3B36E206E6575726F6CC3B367696361 USING utf8mb4),     'LIC-2021-0154'),
  (3, 3, 'MP-17402', 'Terapia de la mano',             'LIC-2022-0311');

INSERT INTO rrhh (id, id_usuario, sector, nro_legajo) VALUES
  (1, 4, CONVERT(0x41646D696E69737472616369C3B36E20646520706572736F6E616C USING utf8mb4), 'LEG-00231');

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
  (1,  NULL, CONVERT(0x546F6DC3A173 USING utf8mb4),     'Aguirre',   '2015-03-12', 'Trastorno del procesamiento sensorial. Dificultades en motricidad fina.', 'HC-0001', TRUE, '2026-03-02'),
  (2,  NULL, 'Valentina', 'Sosa',      '2017-08-25', 'Retraso madurativo leve. Hipersensibilidad auditiva.',                    'HC-0002', TRUE, '2026-03-16'),
  (3,  9,    'Camila',    CONVERT(0x52C3AD6F73 USING utf8mb4),      '1998-11-05', CONVERT(0x4C657369C3B36E206465206D75C3B165636120646572656368612E205265686162696C6974616369C3B36E2066756E63696F6E616C20706F73742071756972C3BA72676963612E USING utf8mb4),     'HC-0003', TRUE, '2026-04-06'),
  (4,  NULL, 'Bruno',     'Peralta',   '2014-09-01', CONVERT(0x4469666963756C746164657320646520636F6F7264696E616369C3B36E206D6F746F7261206772756573612E USING utf8mb4),                             'HC-0004', TRUE, '2026-03-09'),
  (5,  NULL, CONVERT(0x4DC3AD61 USING utf8mb4),       'Cardozo',   '2016-01-20', 'Trastorno del espectro autista. Nivel 1 de apoyo.',                       'HC-0005', TRUE, '2026-03-23'),
  (6,  10,   CONVERT(0x4E69636F6CC3A173 USING utf8mb4),   'Ferreyra',  '2001-06-14', CONVERT(0x4C657369C3B36E206D6564756C617220696E636F6D706C6574612E20526565647563616369C3B36E20646520616374697669646164657320646961726961732E USING utf8mb4),          'HC-0006', TRUE, '2026-04-13'),
  (7,  NULL, CONVERT(0x4C7563C3AD61 USING utf8mb4),     'Molina',    '2018-04-03', 'Retraso en el desarrollo del lenguaje y la motricidad.',                  'HC-0007', TRUE, '2026-04-20'),
  (8,  NULL, 'Thiago',    CONVERT(0x52616DC3AD72657A USING utf8mb4),   '2013-12-11', CONVERT(0x54726173746F726E6F20706F722064C3A96669636974206465206174656E6369C3B36E2E204469666963756C746164657320677261666F6D6F746F7261732E USING utf8mb4),           'HC-0008', TRUE, '2026-03-30'),
  (9,  11,   'Julieta',   'Vega',      '1995-02-28', CONVERT(0x53C3AD6E64726F6D652064656C2074C3BA6E656C206361727069616E6F2062696C61746572616C2E20506F7374206F70657261746F72696F2E USING utf8mb4),                 'HC-0009', TRUE, '2026-04-27'),
  (10, NULL, 'Benicio',   'Herrera',   '2019-07-19', 'Prematurez. Seguimiento del desarrollo psicomotor.',                      'HC-0010', TRUE, '2026-05-04'),
  (11, NULL, 'Renata',    'Godoy',     '2015-10-08', CONVERT(0x4469736772616669612E204469666963756C746164657320656E206C61206F7267616E697A616369C3B36E20657370616369616C2E USING utf8mb4),                    'HC-0011', TRUE, '2026-05-11'),
  (12, 12,   CONVERT(0x4D6174C3AD6173 USING utf8mb4),    'Ojeda',     '2003-05-22', CONVERT(0x547261756D617469736D6F206465206D616E6F20697A717569657264612E205265686162696C6974616369C3B36E2066756E63696F6E616C2E USING utf8mb4),                'HC-0012', TRUE, '2026-05-18'),
  (13, NULL, 'Emilia',    'Paz',       '2017-03-30', CONVERT(0x4869706F746F6EC3AD61206C6576652E2054726162616A6F20646520667565727A612079206573746162696C6964616420706F73747572616C2E USING utf8mb4),               'HC-0013', TRUE, '2026-05-25'),
  (14, NULL, 'Ciro',      'Maldonado', '2012-08-17', CONVERT(0x54726173746F726E6F2064656C206465736172726F6C6C6F206465206C6120636F6F7264696E616369C3B36E2E USING utf8mb4),                            'HC-0014', TRUE, '2026-06-01'),
  (15, 13,   'Andrea',    CONVERT(0x5375C3A172657A USING utf8mb4),    '1988-12-02', CONVERT(0x4172747269746973207265756D61746F696465612E2050726F7465636369C3B36E206172746963756C617220792061646170746163696F6E65732E USING utf8mb4),              'HC-0015', TRUE, '2026-06-08'),
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
  -- El diagnostico es un diagnostico: antes decia "Alta por cumplimiento de
  -- objetivos." y aparecia en la columna Diagnostico (usabilidad).
  (16, NULL, 'Ignacio',   'Rivas',     '2011-04-25', 'Dispraxia del desarrollo. Motricidad fina y escritura.',                  'HC-0016', TRUE,
   DATE_SUB(CURDATE(), INTERVAL 150 DAY)),
  -- Paciente RECIEN INGRESADO, con objetivos en FORMATO REAL DE TO.
  -- Ver el bloque "OBJETIVOS DEL PACIENTE 17" mas abajo, que explica de
  -- donde sale y por que la identidad esta cambiada.
  (17, NULL, CONVERT(0x44616D69C3A16E USING utf8mb4),    'Bustos',    '2009-06-30', CONVERT(0x44697363617061636964616420696E74656C65637475616C206C6576652E20506C616E69666963616369C3B36E206D6F746F72612C206D6F74726963696461642066696E612079206175746F6E6F6DC3AD6120656E20656C207665737469646F2E USING utf8mb4), 'HC-0017', TRUE,
   DATE_SUB(CURDATE(), INTERVAL 4 DAY));


-- =====================================================================
-- ETIQUETAS — colores tomados de frontend/src/theme/theme.js
-- =====================================================================
INSERT INTO etiquetas (id, nombre, color_hex) VALUES
  (1, 'Motricidad fina',              '#3E8E7E'),
  (2, CONVERT(0x496E74656772616369C3B36E2073656E736F7269616C USING utf8mb4),        '#1B3B5C'),
  (3, 'Actividades de la vida diaria','#C97B5A'),
  (4, 'Trabajo con familia',          '#7FA99B'),
  (5, 'Requiere seguimiento',         '#D9A441'),
  (6, CONVERT(0x53657369C3B36E20726570726F6772616D616461 USING utf8mb4),          '#B5544C');


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
  DECLARE v_adulto     BOOLEAN DEFAULT FALSE;

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

  -- --- Objetivos: 3 o 4 activos por paciente (minimo del sistema: 3) ---
  -- Creados un mes antes de la primera sesion, para que toda la agenda
  -- los cuente en el denominador de "objetivos calificados".
  -- Antes era 2 + (pac MOD 3): los pacientes 3, 6, 9, 12 y 15 quedaban con
  -- 2, debajo del minimo que la propia pantalla exige (QA, H28). El 1 queda
  -- con 3 porque mas abajo recibe un cuarto en formato real.
  WHILE v_pac <= 15 DO
    SET v_cant = 3 + ((v_pac + 1) MOD 2);
    SELECT fecha_nacimiento < '2006-01-01' INTO v_adulto FROM pacientes WHERE id = v_pac;
    SET v_num = 1;
    WHILE v_num <= v_cant DO
      INSERT INTO objetivos_terapeuticos (id_paciente, descripcion, activo, fecha_creacion)
      VALUES (
        v_pac,
        -- Adultos (los pacientes con cuenta propia) con objetivos de adulto: antes
        -- un traumatismo de mano tenia "tolerar estimulos sensoriales" (usabilidad).
        IF(v_adulto,
          CASE v_num
            WHEN 1 THEN CONVERT(0x526563757065726172206C6120667565727A61206465207072656E7369C3B36E206465206C61206D616E6F206166656374616461 USING utf8mb4)
            WHEN 2 THEN 'Realizar las tareas de la vida diaria sin dolor ni ayuda'
            WHEN 3 THEN 'Retomar las tareas laborales con las adaptaciones necesarias'
            ELSE        CONVERT(0x4D656A6F726172206C61206465737472657A61206D616E75616C20706172612065736372696269722079207573617220656C2074656CC3A9666F6E6F USING utf8mb4)
          END,
          CASE v_num
            WHEN 1 THEN CONVERT(0x4D656A6F726172206C612070726563697369C3B36E20656E206163746976696461646573206465206D6F74726963696461642066696E61 USING utf8mb4)
            WHEN 2 THEN CONVERT(0x546F6C6572617220657374C3AD6D756C6F732073656E736F7269616C6573206E7565766F732073696E2072656368617A6F USING utf8mb4)
            WHEN 3 THEN CONVERT(0x536F7374656E6572206C61206174656E6369C3B36E20656E20746172656173206465206469657A206D696E75746F73 USING utf8mb4)
            ELSE        CONVERT(0x5265616C697A6172206163746976696461646573206465206C6120766964612064696172696120646520666F726D6120617574C3B36E6F6D61 USING utf8mb4)
          END),
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
    CONVERT(0x51756520546F6DC3A173206C6F67726520736F7374656E657220656C207472617A6F2064656E74726F2064656C2072656E676CC3B36E20616C20636F706961722070616C61627261732064652063696E636F206C657472617320656E206C6574726120637572736976612C20636F6E2061706F796F2076657262616C20696E7465726D6974656E746520792073696E2073756A656369C3B36E2066C3AD73696361206465206C61206D616E6F2C20616C63616E7A616E646F2063756174726F20646520636164612063696E636F20696E74656E746F7320636F72726563746F7320656E20646F73206576616C756163696F6E657320636F6E736563757469766173207265616C697A6164617320656E2073656D616E61732064697374696E7461732C20656E20656C20636F6E73756C746F72696F207920656E20656C206375616465726E6F20646520746172656173206465206C612065736375656C612C20646F7320766563657320706F722073656D616E6120647572616E746520656C20736567756E646F2073656D65737472652064656C20323032362E USING utf8mb4),
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
                  WHEN 'terapeuta' THEN CONVERT(0x456C207465726170657574612064656269C3B320726570726F6772616D617220706F7220756E6120757267656E6369612E USING utf8mb4)
                  ELSE                  CONVERT(0x4E6F20617369737469C3B32E2053652061766973C3B32061206C612066616D696C69612E USING utf8mb4)
                END
              WHEN 'incompleta' THEN CONVERT(0x53652074726162616A6F207061726369616C6D656E74652C206C612073657369C3B36E20736520636F72746F20616E7465732E USING utf8mb4)
              ELSE                   CONVERT(0x53657369C3B36E2074726162616A61646120736567C3BA6E20656C20706C616E20707265766973746F2E USING utf8mb4)
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
                  WHEN 0 THEN CONVERT(0x4275656E6120646973706F73696369C3B36E20647572616E746520746F6461206C61206163746976696461642E USING utf8mb4)
                  WHEN 1 THEN CONVERT(0x4E656365736974C3B32061706F796F2076657262616C20656E206C6120736567756E6461206D697461642E USING utf8mb4)
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
-- DUPLAS Y TURNOS SEMANALES DE LA TERAPEUTA 1 (Entrega 5)
--
-- DATOS SINTETICOS. Laura atiende en dupla a los pacientes 4 y 10 los lunes
-- y los jueves de 15:00 a 15:45 (el generador de arriba no pasa de las 14).
-- Las sesiones se crean con p_registrar_dupla, o sea con las mismas reglas
-- que la aplicacion. Las pasadas quedan completas y con una evolucion cada
-- una: el paciente 4 sube de a poco y el 10 se mantiene, para que la linea de
-- tiempo y los indicadores de tendencia tengan algo que mostrar. La de hoy
-- queda sin registrar, para que el panel del dia la muestre pendiente.
--
-- Tambien se carga la semana tipo de Laura (agenda_recurrente), con la dupla
-- como un turno compartido.
-- =====================================================================
DELIMITER $$

CREATE PROCEDURE p_demo_duplas()
BEGIN
  DECLARE v_dia   DATE;
  DECLARE v_fin   DATE;
  DECLARE v_dow   INT;
  DECLARE v_n     INT DEFAULT 0;
  DECLARE v_obj_a INT;
  DECLARE v_obj_b INT;
  DECLARE v_val_a INT;
  DECLARE v_val_b INT;

  SET v_fin = CURDATE();
  SET v_dia = DATE_SUB(v_fin, INTERVAL 48 DAY);

  SELECT MIN(id) INTO v_obj_a FROM objetivos_terapeuticos
   WHERE id_paciente = 4 AND activo = TRUE;
  SELECT MIN(id) INTO v_obj_b FROM objetivos_terapeuticos
   WHERE id_paciente = 10 AND activo = TRUE;

  WHILE v_dia <= v_fin DO
    SET v_dow = WEEKDAY(v_dia);   -- 0 = lunes

    IF v_dow IN (0, 3) OR (v_dia = v_fin AND v_dow <= 4) THEN
      CALL p_registrar_dupla(1, 4, 10, v_dia, '15:00:00', '15:45:00',
                             @d_dupla, @d_s1, @d_s2, @d_msg);

      IF v_dia < v_fin THEN
        UPDATE sesiones SET estado = 'completa' WHERE id IN (@d_s1, @d_s2);

        SET v_val_a = LEAST(5, 1 + FLOOR(v_n / 3));
        SET v_val_b = 3 + (v_n MOD 3 = 2);

        INSERT INTO evoluciones (id_sesion, id_objetivo, valor, observaciones)
        VALUES (@d_s1, v_obj_a, v_val_a, NULL),
               (@d_s2, v_obj_b, v_val_b, NULL);
        SET v_n = v_n + 1;
      END IF;
    END IF;

    SET v_dia = DATE_ADD(v_dia, INTERVAL 1 DAY);
  END WHILE;
END$$

DELIMITER ;

CALL p_demo_duplas();
DROP PROCEDURE p_demo_duplas;

INSERT INTO agenda_recurrente (id_terapeuta, id_paciente, dia_semana, hora_inicio, hora_fin, id_dupla) VALUES
  (1, 1, 1, '16:00:00', '16:45:00', NULL),
  (1, 7, 3, '16:00:00', '16:45:00', NULL),
  (1, 13, 5, '16:00:00', '16:45:00', NULL),
  (1, 4, 1, '15:00:00', '15:45:00', 4),
  (1, 10, 1, '15:00:00', '15:45:00', 4),
  (1, 4, 4, '15:00:00', '15:45:00', 6),
  (1, 10, 4, '15:00:00', '15:45:00', 6);


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
  (16, CONVERT(0x526563757065726172206C6120667565727A61206465207072656E7369C3B36E20656E206C61206D616E6F2064657265636861 USING utf8mb4), TRUE,
   TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 145 DAY), '09:00:00')),
  (16, 'Retomar la escritura sostenida durante quince minutos', TRUE,
   TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 145 DAY), '09:15:00')),
  (16, CONVERT(0x566573746972736520792063616C7A6172736520646520666F726D6120617574C3B36E6F6D6120616E7465732064652073616C6972 USING utf8mb4), TRUE,
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
   CONVERT(0x5072696D6572612073657369C3B36E2E20536520746F6D61206CC3AD6E6561206465206261736520646520667565727A612079206573637269747572612E USING utf8mb4)),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 140 DAY), '18:00:00', '19:00:00', 'incompleta', NULL,
   CONVERT(0x536567756E646F207475726E6F2064656C206D69736D6F2064C3AD612E20536520636F72746F20616E74657320706F722063616E73616E63696F2E USING utf8mb4)),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 133 DAY), '17:00:00', '18:00:00', 'completa', NULL,
   CONVERT(0x54726162616A6F206465207072656E7369C3B36E20636F6E206D61736120792070696E7A61732E USING utf8mb4)),
  -- Este dia tiene DOS sesiones y una es ausencia: es el caso que hace
  -- visible por que las marcas se apilan. Si se superpusieran, el ambar de
  -- la sesion trabajada taparia el ladrillo de la ausencia —o al reves— y
  -- una ausencia desapareceria del grafico. Eso es informacion clinica
  -- oculta, no una molestia de densidad.
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 126 DAY), '17:00:00', '18:00:00', 'ausencia', 'paciente',
   CONVERT(0x4C612066616D696C696120617669736F20656C2064C3AD6120616E746572696F722E USING utf8mb4)),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 126 DAY), '18:00:00', '19:00:00', 'completa', NULL,
   CONVERT(0x53652072656375706572C3B320656C207475726E6F206DC3A1732074617264652E204E6F207365206C6C6567C3B320612063616C6966696361722E USING utf8mb4)),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 119 DAY), '17:00:00', '18:00:00', 'completa', NULL,
   'Retoma el trazo con apoyo verbal.'),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 112 DAY), '17:00:00', '18:00:00', 'completa', NULL,
   CONVERT(0x5072C3A16374696361206465207665737469646F20636F6E207072656E6461732070726F706961732E USING utf8mb4)),
  (2, 16, DATE_SUB(CURDATE(), INTERVAL 105 DAY), '17:00:00', '18:00:00', 'ausencia', 'paciente',
   CONVERT(0x4E6F20617369737469C3B32C2073696E20617669736F2E USING utf8mb4)),
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
           CONVERT(0x5072656E7369C3B36E2064C3A962696C2C2073696E20736F7374656E657220656C206167617272652E USING utf8mb4) AS obs
    UNION ALL SELECT 140, '17:00:00', 2, 1, CONVERT(0x4E6F20736F737469656E6520656C207472617A6F206DC3A17320646520646F73206D696E75746F732E USING utf8mb4)
    UNION ALL SELECT 133, '17:00:00', 1, 2, 'Sostiene el agarre con apoyo.'
    UNION ALL SELECT 119, '17:00:00', 2, 2, CONVERT(0x5472617A6F206DC3A173206669726D652C20636F6E207265636F726461746F72696F732E USING utf8mb4)
    UNION ALL SELECT 112, '17:00:00', 3, 2, 'Se calza solo, con ayuda para el cierre.'
    UNION ALL SELECT  98, '17:00:00', 1, 4, CONVERT(0x5072656E7369C3B36E2066756E63696F6E616C20656E206163746976696461646573206C61726761732E USING utf8mb4)
    UNION ALL SELECT  98, '17:00:00', 2, 4, 'Quince minutos sostenidos sin recordatorio.'
    UNION ALL SELECT  91, '17:00:00', 1, 5, 'Objetivo alcanzado.'
    UNION ALL SELECT  91, '17:00:00', 2, 5, 'Objetivo alcanzado.'
    UNION ALL SELECT  91, '17:00:00', 3, 4, CONVERT(0x417574C3B36E6F6D6F2073616C766F20636F72646F6E65732E USING utf8mb4)
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
       tipo_cierre = 'alta',
       motivo_baja = 'Alta por cumplimiento de objetivos'
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
   CONVERT(0x5175652044616D69C3A16E206C6F67726520737562697220792062616A617220657363616C6572617320616C7465726E616E646F206C6F7320706965732C20636F6E20737570657276697369C3B36E2063657263616E612064656C20746572617065757461206120636172676F2C20647572616E746520656C207072696D65722073656D65737472652064656C20323032362E USING utf8mb4),
   TRUE, TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 4 DAY), '22:14:00')),
  (17,
   CONVERT(0x5175652044616D69C3A16E206C6F677265206162726F6368617220626F746F6E6573206D656469616E6F7320656E207072656E64617320636F74696469616E6173202863616D69736120792063616D70657261292C20636F6E206173697374656E6369612066C3AD7369636120792076657262616C2C20656E20322064652033206F706F7274756E6964616465732C20656E20656C20636F6E746578746F2064656C20636F6E73756C746F72696F2C20647572616E746520656C207072696D65722073656D65737472652064656C20323032362E USING utf8mb4),
   TRUE, TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 4 DAY), '22:16:00')),
  (17,
   CONVERT(0x5175652044616D69C3A16E206C6F677265207365727669727365206167756120646520756E61206A61727261206C697669616E612073696E2064657272616D617220736F627265206C61206D65736164612C20636F6E206173697374656E636961206D6F6465726164612064656C207465726170657574612C20656E20322064652035206F706F7274756E6964616465732C20647572616E746520656C207072696D65722073656D65737472652064656C20323032362E USING utf8mb4),
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
  (1, CONVERT(0x6E756576615F73657369C3B36E USING utf8mb4), TRUE),  (1, 'informe_generado', TRUE),  (1, 'cambio_objetivo', TRUE),
  (2, CONVERT(0x6E756576615F73657369C3B36E USING utf8mb4), TRUE),  (2, 'informe_generado', TRUE),  (2, 'cambio_objetivo', FALSE),
  (3, CONVERT(0x6E756576615F73657369C3B36E USING utf8mb4), FALSE), (3, 'informe_generado', TRUE),  (3, 'cambio_objetivo', TRUE),
  (4, CONVERT(0x6E756576615F73657369C3B36E USING utf8mb4), TRUE),  (4, 'informe_generado', FALSE), (4, 'cambio_objetivo', TRUE);

-- Los textos llevan tildes pero el archivo es ASCII: se escriben como bytes
-- UTF-8 en hexadecimal y se convierten (Windows carga este archivo sin
-- depender de la codificacion de consola).
--
-- Los avisos salen de los datos que existen (QA, H24): antes eran fijos de
-- junio y nombraban sesiones e informes que el seed no tiene. Mismo texto
-- que emite notificaciones_service.
-- Avisos de sesion: las dos ultimas realizadas de cada paciente vinculado.
INSERT INTO notificaciones (id_familiar, id_paciente, tipo, mensaje, leida, fecha)
SELECT fp.id_familiar, s.id_paciente, CONVERT(0x6E756576615F73657369C3B36E USING utf8mb4),
       CONCAT(CONVERT(0x53652072656769737472C3B3206C612073657369C3B36E2064656C20 USING utf8mb4), DATE_FORMAT(s.fecha, '%d/%m/%Y'), ' a las ',
              TIME_FORMAT(s.hora_inicio, '%H:%i'), ' de ', p.nombre, '.'),
       s.fecha < DATE_SUB(CURDATE(), INTERVAL 3 DAY),
       TIMESTAMP(s.fecha, ADDTIME(s.hora_inicio, '01:00:00'))
  FROM familiares_pacientes fp
  JOIN pacientes p ON p.id = fp.id_paciente
  JOIN sesiones s ON s.id_paciente = fp.id_paciente AND s.estado = 'completa'
  -- Todas las realizadas de las ultimas dos semanas y solo si el familiar
  -- quiere ese aviso: con solo las dos ultimas, la opcion "un aviso cada vez
  -- que..." no se cumplia a la vista (usabilidad, madre).
  JOIN preferencias_notificacion pn
    ON pn.id_familiar = fp.id_familiar AND pn.habilitada = TRUE
   AND pn.tipo NOT IN ('informe_generado', 'cambio_objetivo')
 WHERE s.fecha >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
   AND TIMESTAMP(s.fecha, ADDTIME(s.hora_inicio, '01:00:00')) <= NOW();

-- Aviso de objetivo: el plan inicial de cada paciente vinculado.
INSERT INTO notificaciones (id_familiar, id_paciente, tipo, mensaje, leida, fecha)
SELECT fp.id_familiar, o.id_paciente, 'cambio_objetivo',
       CONCAT(CONVERT(0x5365206167726567C3B320756E206F626A657469766F20616C20706C616E20646520 USING utf8mb4), p.nombre, ': ', LEFT(o.descripcion, 280)),
       TRUE, o.fecha_creacion
  FROM familiares_pacientes fp
  JOIN pacientes p ON p.id = fp.id_paciente
  JOIN objetivos_terapeuticos o ON o.id_paciente = fp.id_paciente
 WHERE o.id = (SELECT MIN(o2.id) FROM objetivos_terapeuticos o2 WHERE o2.id_paciente = o.id_paciente);

-- Observaciones tecnicas de RRHH sobre las primeras ausencias registradas
-- Fechadas al dia siguiente de cada ausencia: con la hora de la carga
-- parecian escritas por RRHH minutos antes de entrar (usabilidad).
INSERT INTO observaciones_rrhh (id_sesion, id_rrhh, texto, fecha_registro)
SELECT id, 1, CONVERT(0x417573656E63696120726567697374726164612E205365206E6F7469666963C3B3206120636F6F7264696E616369C3B36E2E USING utf8mb4),
       LEAST(TIMESTAMP(fecha + INTERVAL 1 DAY, '09:30:00'), NOW())
  FROM sesiones WHERE estado = 'ausencia' ORDER BY id LIMIT 12;

INSERT INTO informes
  (id_paciente, id_terapeuta, tipo, periodo, fecha_desde, fecha_hasta, version, contenido, contenido_original, generado_con, estado, fecha_generacion, fecha_publicacion) VALUES
  (1, 1, 'mensual', '2026-09', '2026-09-01', '2026-09-30', 1, CONVERT(0x2323204461746F732064656C2070616369656E74650A546F6DC3A17320416775697272652E0A0A232320506572C3AD6F646F0A5365707469656D62726520646520323032362E0A0A2323204173697374656E6369610A5365207265616C697A61726F6E20313720736573696F6E657320656E20656C206D65732C2073696E20617573656E636961732E0A0A2323204F626A657469766F732074726162616A61646F730A2D20536F7374656E6572206C612065736372697475726120636F6E20616761727265207472C3AD706F64653A204176616E7A61646F2E205365206D616E7469656E6520656E20756E206E6976656C20616C746F20647572616E746520746F646F20656C206D65732E0A2D20546F6C65726172207465787475726173206E756576617320656E206C6120616C696D656E74616369C3B36E3A20456E2070726F6365736F2E204D656A6F726120726573706563746F2064656C206D657320616E746572696F722E0A0A2323204F62736572766163696F6E6573206465206C617320736573696F6E65730A5365206F627365727661206D656A6F7220746F6C6572616E636961206120657374C3AD6D756C6F73206E7565766F732079206D61796F722070657273697374656E63696120656E206C612074617265612E0A0A2323204369657272650A536520636F6E74696EC3BA6120636F6E20656C20706C616E20766967656E74652E USING utf8mb4), CONVERT(0x5365707469656D62726520646520323032362E205365207265616C697A61726F6E20313720736573696F6E65732E204F626A657469766F733A2065736372697475726120636F6E20616761727265207472C3AD706F646520284176616E7A61646F292079207465787475726173206E75657661732028456E2070726F6365736F292E0A0A5B434F4D504C455441523A206F62736572766163696F6E65732079206369657272655D USING utf8mb4), 'plantilla', 'final', '2026-10-01 08:30:00', '2026-10-01 09:00:00'),
  (1, 1, 'semestral', '2026-S1', '2026-01-01', '2026-06-30', 1, CONVERT(0x2323204461746F732064656C2070616369656E74650A546F6DC3A17320416775697272652E0A0A232320506572C3AD6F646F0A5072696D65722073656D657374726520646520323032362028646520656E65726F2061206A756E696F292E0A0A23232045766F6C756369C3B36E2067656E6572616C0A546F6DC3A17320696E67726573C3B320616C2063656E74726F20656E206D61727A6F2E20447572616E746520656C2073656D6573747265207365207265616C697AC3B3206C61206576616C75616369C3B36E20696E696369616C2064652074657261706961206F6375706163696F6E616C207920736520646566696E6965726F6E206C617320C3A17265617320612074726162616A61723A206D6F74726963696461642066696E612C20746F6C6572616E636961206120657374C3AD6D756C6F732073656E736F7269616C65732079206174656E6369C3B36E20736F7374656E6964612E204C6F73206F626A657469766F732064656C20706C616E20736520666F726D616C697A61726F6E20616C20636F6D69656E7A6F2064656C20736567756E646F2073656D65737472652E0A0A2323205072C3B378696D6F73207061736F730A536520736F737469656E65206C61206672656375656E6369612073656D616E616C2079207365207265766973616E206C6F73206F626A657469766F7320616C20696E6963696F2064656C20736567756E646F2073656D65737472652E USING utf8mb4), CONVERT(0x447572616E746520656C2073656D6573747265207365207265616C697AC3B3206C61206576616C75616369C3B36E20696E696369616C207920736520646566696E6965726F6E206C617320C3A17265617320612074726162616A61722E0A0A5B434F4D504C455441523A207072C3B378696D6F73207061736F735D USING utf8mb4), 'plantilla', 'final', '2026-07-01 08:30:00', '2026-07-01 09:00:00'),
  (5, 2, 'mensual', '2026-09', '2026-09-01', '2026-09-30', 1, NULL, CONVERT(0x2323204461746F732064656C2070616369656E74650A4DC3AD6120436172646F7A6F2E0A0A232320506572C3AD6F646F0A5365707469656D62726520646520323032362E0A0A2323204173697374656E6369610A526567697374726F206465206173697374656E63696120726567756C61722E0A0A2323204F626A657469766F732074726162616A61646F730A2D204176616E636573207061726369616C657320656E206175746F6E6F6DC3AD612E0A0A2323204369657272650A5B434F4D504C455441523A206369657272652079207265636F6D656E646163696F6E65735D USING utf8mb4), 'plantilla', 'borrador', '2026-10-01 08:45:00', NULL),
  (7, 1, 'mensual', '2026-09', '2026-09-01', '2026-09-30', 1, NULL, CONVERT(0x2323204461746F732064656C2070616369656E74650A4C7563C3AD61204D6F6C696E612E0A0A232320506572C3AD6F646F0A5365707469656D62726520646520323032362E0A0A2323204173697374656E6369610A526567697374726F206465206173697374656E63696120726567756C61722E0A0A2323204F626A657469766F732074726162616A61646F730A2D204176616E636573207061726369616C657320656E206175746F6E6F6DC3AD612E0A0A2323204369657272650A5B434F4D504C455441523A206369657272652079207265636F6D656E646163696F6E65735D USING utf8mb4), 'plantilla', 'borrador', '2026-10-02 10:15:00', NULL);

-- Un borrador recien generado todavia no fue editado: su contenido es el original.
UPDATE informes SET contenido = contenido_original WHERE contenido IS NULL;

-- Los informes MENSUALES del seed se reescriben con los datos reales del mes
-- anterior a la carga (usabilidad: el fijo decia "17 sesiones sin ausencias" y
-- otros objetivos, y la familia veia lo contrario en la evolucion).
SET @inf_desde = DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01');
SET @inf_hasta = LAST_DAY(@inf_desde);
SET @inf_mes = ELT(MONTH(@inf_desde), 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                   'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre');

DROP TEMPORARY TABLE IF EXISTS tmp_informe_objetivos;
CREATE TEMPORARY TABLE tmp_informe_objetivos AS
SELECT x.id_paciente, GROUP_CONCAT(x.linea ORDER BY x.id_objetivo SEPARATOR '\n') AS lineas
  FROM (
    SELECT s.id_paciente, o.id AS id_objetivo,
           CONCAT('- ', TRIM(TRAILING '.' FROM o.descripcion), ': ',
                  ELT(ROUND(AVG(e.valor)), 'No logrado', 'Inicial', 'En proceso', 'Avanzado', 'Logrado'),
                  ' (calificado en ', COUNT(*), IF(COUNT(*) = 1, CONVERT(0x2073657369C3B36E292E USING utf8mb4), ' sesiones).')) AS linea
      FROM evoluciones e
      JOIN sesiones s ON s.id = e.id_sesion
      JOIN objetivos_terapeuticos o ON o.id = e.id_objetivo
     WHERE s.fecha BETWEEN @inf_desde AND @inf_hasta AND e.valor IS NOT NULL
     GROUP BY s.id_paciente, o.id
  ) x
 GROUP BY x.id_paciente;

UPDATE informes i
  JOIN pacientes p ON p.id = i.id_paciente
  LEFT JOIN tmp_informe_objetivos t ON t.id_paciente = i.id_paciente
   SET i.periodo = DATE_FORMAT(@inf_desde, '%Y-%m'),
       i.fecha_desde = @inf_desde,
       i.fecha_hasta = @inf_hasta,
       i.fecha_generacion = TIMESTAMP(DATE_ADD(@inf_hasta, INTERVAL 1 DAY), '08:30:00'),
       i.fecha_publicacion = IF(i.estado = 'final', TIMESTAMP(DATE_ADD(@inf_hasta, INTERVAL 1 DAY), '09:00:00'), NULL),
       i.contenido = CONCAT(
         '## Datos del paciente\n', p.nombre, ' ', p.apellido, '.\n\n',
         CONVERT(0x232320506572C3AD6F646F0A USING utf8mb4), CONCAT(UPPER(LEFT(@inf_mes, 1)), SUBSTRING(@inf_mes, 2)), ' de ', YEAR(@inf_desde), '.\n\n',
         '## Asistencia\n',
         (SELECT CONCAT('Se registraron ', SUM(s.estado = 'completa'), ' sesiones realizadas y ',
                        SUM(s.estado = 'ausencia'), IF(SUM(s.estado = 'ausencia') = 1, ' ausencia.', ' ausencias.'))
            FROM sesiones s WHERE s.id_paciente = i.id_paciente AND s.fecha BETWEEN @inf_desde AND @inf_hasta),
         '\n\n## Objetivos trabajados\n',
         CONVERT(0x456C206E6976656C2064652063616461206F626A657469766F20726573756D6520746F646173207375732063616C696669636163696F6E65732064656C20706572C3AD6F646F3B206E6F206573206C6120C3BA6C74696D612063616C69666963616369C3B36E2E0A0A USING utf8mb4),
         COALESCE(t.lineas, CONVERT(0x4E6F206875626F2063616C696669636163696F6E657320656E20656C20706572C3AD6F646F2E USING utf8mb4)),
         CONVERT(0x0A0A2323204369657272652079207072C3B378696D6F73207061736F730A USING utf8mb4),
         IF(i.estado = 'final',
            CONVERT(0x4275656E20636F6D70726F6D69736F20656E206C617320736573696F6E65732E20536520636F6E74696EC3BA6120636F6E20656C20706C616E20766967656E74652079207365207265766973616E206C6F73206F626A657469766F7320656C206D6573207072C3B378696D6F2E USING utf8mb4),
            CONVERT(0x5B434F4D504C455441523A206369657272652064656C20706572C3AD6F646F2079207072C3B378696D6F73207061736F735D USING utf8mb4))),
       i.contenido_original = i.contenido
 WHERE i.tipo = 'mensual';
-- (contenido_original = contenido: MySQL asigna de izquierda a derecha y ya
-- toma el valor nuevo.)

DROP TEMPORARY TABLE tmp_informe_objetivos;


-- Aviso de informe: solo los publicados y para quien lo tiene encendido.
INSERT INTO notificaciones (id_familiar, id_paciente, tipo, mensaje, leida, fecha)
SELECT fp.id_familiar, i.id_paciente, 'informe_generado',
       CONCAT(CONVERT(0x596120657374C3A120646973706F6E69626C6520756E20696E666F726D65206E7565766F20646520 USING utf8mb4), p.nombre, '.'),
       TRUE, i.fecha_publicacion
  FROM informes i
  JOIN pacientes p ON p.id = i.id_paciente
  JOIN familiares_pacientes fp ON fp.id_paciente = i.id_paciente
  JOIN preferencias_notificacion pn
    ON pn.id_familiar = fp.id_familiar AND pn.tipo = 'informe_generado' AND pn.habilitada = TRUE
 WHERE i.estado = 'final';

INSERT INTO plantillas_objetivos (area, descripcion) VALUES
  ('Motricidad fina', CONVERT(0x4d656a6f726172206c612070696e7a612066696e612070617261206c61206573637269747572612c20736f7374656e69656e646f20656c206cc3a170697a20636f6e20616761727265207472c3ad706f646520647572616e7465203130206d696e75746f732c20636f6e2061797564612076657262616c206dc3ad6e696d61 USING utf8mb4)),
  ('Motricidad fina', CONVERT(0x5265616c697a617220656e63617374726573206465207069657a6173207065717565c3b161732073696e206179756461 USING utf8mb4)),
  ('Motricidad gruesa', 'Mantener el equilibrio en una pierna durante 10 segundos'),
  ('Motricidad gruesa', 'Subir y bajar escaleras alternando los pies'),
  (CONVERT(0x496e74656772616369c3b36e2073656e736f7269616c USING utf8mb4), CONVERT(0x546f6c65726172207465787475726173206e756576617320656e206c6120616c696d656e74616369c3b36e USING utf8mb4)),
  (CONVERT(0x496e74656772616369c3b36e2073656e736f7269616c USING utf8mb4), CONVERT(0x526567756c6172206c6120726573707565737461206120657374c3ad6d756c6f7320617564697469766f73 USING utf8mb4)),
  ('Vida diaria', CONVERT(0x566573746972736520646520666f726d6120617574c3b36e6f6d61 USING utf8mb4)),
  ('Vida diaria', 'Utilizar cubiertos de manera independiente'),
  (CONVERT(0x4174656e6369c3b36e USING utf8mb4), CONVERT(0x536f7374656e6572206c61206174656e6369c3b36e20656e20746172656173206465203130206d696e75746f73 USING utf8mb4)),
  (CONVERT(0x5265686162696c6974616369c3b36e USING utf8mb4), CONVERT(0x52656375706572617220656c2072616e676f206465206d6f76696d69656e746f206465206c61206d75c3b16563612064657265636861 USING utf8mb4)),
  (CONVERT(0x5265686162696c6974616369c3b36e USING utf8mb4), 'Reintegrarse a la actividad laboral habitual'),
  (CONVERT(0x436f6d756e6963616369c3b36e USING utf8mb4), 'Pedir lo que necesita mediante palabras o pictogramas'),
  (CONVERT(0x4a7565676f207920736f6369616c697a616369c3b36e USING utf8mb4), CONVERT(0x436f6d70617274697220756e206a7565676f20636f6e206f74726f206e69c3b16f20647572616e74652035206d696e75746f732c20726573706574616e646f207475726e6f73 USING utf8mb4)),
  (CONVERT(0x4175746f6e6f6dc3ad6120656e206c612065736375656c61 USING utf8mb4), CONVERT(0x4f7267616e697a61722073757320c3ba74696c6573206573636f6c617265732073696e20617975646120616e74657320646520636f6d656e7a6172206c6120636c617365 USING utf8mb4));

INSERT INTO auditoria_accesos (id_usuario, email, resultado, ip, fecha) VALUES
  (1,    'laura.fernandez@asisto.local', 'exitoso',   '192.168.1.24',  '2026-06-01 08:45:00'),
  (2,    'diego.moyano@asisto.local',    'exitoso',   '192.168.1.31',  '2026-06-01 08:50:00'),
  (3,    'paula.cabrera@asisto.local',   'exitoso',   '192.168.1.44',  '2026-06-01 08:52:00'),
  (4,    'silvia.quiroga@asisto.local',  'fallido',   '192.168.1.15',  '2026-06-05 09:12:00'),
  (NULL, 'noexiste@asisto.local',        'fallido',   '201.190.44.10', '2026-06-05 09:14:00'),
  (4,    'silvia.quiroga@asisto.local',  'exitoso',   '192.168.1.15',  '2026-06-05 09:15:00'),
  (13,   'andrea.suarez@asisto.local',   'bloqueado', '190.15.22.100', '2026-06-08 21:03:00');

-- Intentos recientes, relativos a la carga: la auditoria de "esta semana" no
-- quedaba vacia en la demostracion.
INSERT INTO auditoria_accesos (id_usuario, email, resultado, ip, fecha) VALUES
  (2,    'diego.moyano@asisto.local',    'fallido',      '192.168.1.31', DATE_SUB(NOW(), INTERVAL 2 DAY)),
  (2,    'diego.moyano@asisto.local',    'exitoso',      '192.168.1.31', DATE_SUB(NOW(), INTERVAL 2 DAY) + INTERVAL 1 MINUTE),
  (NULL, 'laura.fernandes@asisto.local', 'fallido',      '186.12.40.7',  DATE_SUB(NOW(), INTERVAL 1 DAY)),
  (7,    'rosa.aguilar@asisto.local',    'recuperacion', '181.47.3.92',  DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 3 HOUR),
  (7,    'rosa.aguilar@asisto.local',    'restablecida', '181.47.3.92',  DATE_SUB(NOW(), INTERVAL 1 DAY) + INTERVAL 3 HOUR + INTERVAL 5 MINUTE);



-- =====================================================================
-- RESUMEN
-- =====================================================================
SELECT CONVERT(0x4461746F732064652064656D6F737472616369C3B36E206361726761646F73 USING utf8mb4) AS resultado;

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

SELECT CONVERT(0x536573696F6E65732073696E2065766F6C756369C3B36E202870656E6469656E74657329 USING utf8mb4) AS detalle, COUNT(*) AS cantidad
  FROM sesiones s
 WHERE s.estado <> 'ausencia'
   AND NOT EXISTS (SELECT 1 FROM evoluciones e WHERE e.id_sesion = s.id);

SELECT CONVERT(0x44C3AD61206DC3A173206361726761646F USING utf8mb4) AS detalle, fecha, id_terapeuta, COUNT(*) AS sesiones
  FROM sesiones GROUP BY fecha, id_terapeuta ORDER BY sesiones DESC, fecha LIMIT 1;
