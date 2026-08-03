-- =====================================================================
-- AsisTO — Datos de DEMOSTRACION (volumen realista)
--
-- ALTERNATIVA a seed.sql, no lo reemplaza. Los dos cargan sobre el mismo
-- schema y son excluyentes: se corre uno u otro.
--
--   seed.sql       3 pacientes, 10 sesiones. Es el que usan los tests:
--                  chico, estable y con id conocidos.
--   seed_demo.sql  15 pacientes, ~7 semanas de agenda. Es para ver como se
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

USE asisto;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE auditoria_accesos;
TRUNCATE TABLE plantillas_objetivos;
TRUNCATE TABLE duplas_terapeuticas;
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
  (13, 'Andrea',   'Suarez',    'andrea.suarez@asisto.local',   '$2b$12$PLACEHOLDER.paciente.cinc', FALSE, 'paciente');

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
-- PACIENTES — 15
--
-- 10 SIN login (id_usuario NULL): menores, es lo normal. 5 CON login.
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
  -- Paciente DADO DE BAJA: no aparece en el listado, pero su historia
  -- clinica sigue existiendo. Sirve para probar ese estado.
  (16, NULL, 'Ignacio',   'Rivas',     '2011-04-25', 'Alta por cumplimiento de objetivos.',                                     'HC-0016', FALSE, '2026-02-02');

UPDATE pacientes SET fecha_baja = '2026-05-29' WHERE id = 16;


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
  DECLARE v_contador   INT DEFAULT 0;
  DECLARE v_id_sesion  INT;
  DECLARE v_n_obj      INT;
  DECLARE v_off        INT;
  DECLARE v_id_obj     INT;

  -- --- Objetivos: entre 2 y 4 activos por paciente ---
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
        TIMESTAMP('2026-05-04', SEC_TO_TIME(v_num * 900))
      );
      SET v_num = v_num + 1;
    END WHILE;
    SET v_pac = v_pac + 1;
  END WHILE;

  -- --- Agenda: 7 semanas, lunes a viernes, 3 terapeutas ---
  SET v_dia = '2026-06-01';
  SET v_fin = '2026-07-17';

  WHILE v_dia <= v_fin DO
    SET v_dow = DAYOFWEEK(v_dia);   -- 1 = domingo, 7 = sabado

    IF v_dow BETWEEN 2 AND 6 THEN
      SET v_ter = 1;
      WHILE v_ter <= 3 DO
        -- Entre 4 y 8 sesiones por dia y por terapeuta. Los dias con 8 son
        -- los que interesan para ver la interfaz cargada.
        SET v_slots = 4 + ((v_indice_dia + v_ter) MOD 5);
        SET v_slot = 0;

        WHILE v_slot < v_slots DO
          -- Franjas de una hora, con corte de 12 a 13
          SET v_hora = MAKETIME(IF(v_slot < 4, 8 + v_slot, 9 + v_slot), 0, 0);
          SET v_id_pac = (((v_ter - 1) * 5 + v_indice_dia + v_slot * 7) MOD 15) + 1;
          SET v_contador = v_contador + 1;

          SET v_estado = CASE
            WHEN v_contador MOD 11 = 0 THEN 'ausencia'
            WHEN v_contador MOD 7 = 0  THEN 'incompleta'
            ELSE 'completa'
          END;

          INSERT INTO sesiones
            (id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, notas)
          VALUES (
            v_ter, v_id_pac, v_dia, v_hora, ADDTIME(v_hora, '01:00:00'), v_estado,
            CASE v_estado
              WHEN 'ausencia'   THEN 'No asistio. Se aviso a la familia.'
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
          IF v_estado <> 'ausencia' AND (v_contador MOD 5) <> 0 THEN
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

    IF v_id_obj IS NOT NULL THEN
      UPDATE objetivos_terapeuticos SET activo = FALSE WHERE id = v_id_obj;
    END IF;

    SET v_pac = v_pac + 3;
  END WHILE;
END$$

DELIMITER ;

CALL p_generar_demo();
DROP PROCEDURE p_generar_demo;


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

INSERT INTO notificaciones (id_familiar, id_paciente, tipo, mensaje, leida, fecha) VALUES
  (1, 1,  'nueva_sesion',     'Se registro una nueva sesion para Tomas.',        TRUE,  '2026-06-02 10:05:00'),
  (1, 1,  'cambio_objetivo',  'Se archivo un objetivo de Tomas.',                TRUE,  '2026-06-20 11:05:00'),
  (1, 5,  'informe_generado', 'El informe del segundo trimestre esta listo.',    FALSE, '2026-07-01 09:00:00'),
  (2, 2,  'nueva_sesion',     'Se registro una nueva sesion para Valentina.',    FALSE, '2026-06-10 12:05:00'),
  (3, 7,  'nueva_sesion',     'Se registro una nueva sesion para Lucia.',        FALSE, '2026-06-11 09:30:00'),
  (3, 10, 'informe_generado', 'El informe de Benicio esta disponible.',          FALSE, '2026-07-01 09:10:00'),
  (4, 8,  'cambio_objetivo',  'Se agrego un objetivo nuevo para Thiago.',        TRUE,  '2026-06-15 16:20:00'),
  (4, 11, 'nueva_sesion',     'Se registro una nueva sesion para Renata.',       FALSE, '2026-06-18 11:00:00');

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

INSERT INTO duplas_terapeuticas (id_terapeuta_1, id_terapeuta_2, id_paciente, fecha_asignacion, activa) VALUES
  (1, 2, 1,  '2026-05-04', TRUE),
  (2, 3, 6,  '2026-05-11', TRUE),
  (1, 3, 11, '2026-05-18', TRUE);

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
