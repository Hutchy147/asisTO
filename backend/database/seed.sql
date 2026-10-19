-- =====================================================================
-- AsisTO — Datos de prueba
--
-- Se corre DESPUES de schema.sql. Las cuatro instancias locales arrancan
-- identicas: todos los id son explicitos, no dependen del AUTO_INCREMENT.
--
--   mysql -u root -p asisto < backend/database/seed.sql
--
-- IMPORTANTE — contrasenas:
-- Los contrasena_hash de abajo son PLACEHOLDERS, no son hashes validos.
-- Ningun login va a funcionar con estos datos. Cuando exista el modulo de
-- auth hay que reemplazarlos por hashes bcrypt reales generados desde el
-- backend, nunca escritos a mano en este archivo.
-- =====================================================================

-- ESTE ARCHIVO NO ELIGE BASE, Y ES UNA DECISION (2026-09-13).
--
-- Hasta hoy aca decia `USE asisto;`. Esa linea PISA el nombre de base que se
-- pasa por linea de comandos: `mysql --login-path=asisto otra_base < seed.sql`
-- escribia en `asisto`, no en `otra_base`, sin avisar nada. Paso de verdad y
-- dejo a `asisto` con los datos de la demo encima; se recupero del respaldo.
--
-- Un script de datos no decide sobre que base escribe: lo decide quien lo
-- invoca. Sin `USE`, el argumento de `mysql` (o el `-Database` de
-- `Invoke-Sql`) manda, que es lo unico que el que ejecuta puede ver.
--
-- Los dos scripts que ya lo cargaban pasan la base como argumento
-- (`build_test_db.ps1` y `test_seed_coherencia.ps1`), asi que siguen
-- funcionando igual: lo que tenian era un `-replace` de esta linea, que
-- ahora no encuentra nada y no hace falta.
--
-- Si lo corres a mano, el nombre va SIEMPRE explicito:
--     mysql --login-path=asisto la_base_que_quieras < seed.sql

-- Orden inverso al de las dependencias para poder recorrer el seed las
-- veces que haga falta sin recrear el schema entero.
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
-- USUARIOS
-- 2 terapeutas, 1 rrhh, 2 familiares, 1 paciente con login, 1 administrador
-- (sin perfil propio: solo asigna terapeutas a pacientes).
-- =====================================================================
INSERT INTO usuarios (id, nombre, apellido, email, contrasena_hash, activo, rol) VALUES
  (1, 'Laura',  'Fernandez', 'laura.fernandez@asisto.local', '$2b$12$PLACEHOLDER.reemplazar.con.bcrypt.real.terapeuta1', TRUE, 'terapeuta'),
  (2, 'Diego',  'Moyano',    'diego.moyano@asisto.local',    '$2b$12$PLACEHOLDER.reemplazar.con.bcrypt.real.terapeuta2', TRUE, 'terapeuta'),
  (3, 'Silvia', 'Quiroga',   'silvia.quiroga@asisto.local',  '$2b$12$PLACEHOLDER.reemplazar.con.bcrypt.real.rrhh00001', TRUE, 'rrhh'),
  (4, 'Marta',  'Ledesma',   'marta.ledesma@asisto.local',   '$2b$12$PLACEHOLDER.reemplazar.con.bcrypt.real.familiar1', TRUE, 'familiar'),
  (5, 'Jorge',  'Bustos',    'jorge.bustos@asisto.local',    '$2b$12$PLACEHOLDER.reemplazar.con.bcrypt.real.familiar2', TRUE, 'familiar'),
  (6, 'Camila', 'Rios',      'camila.rios@asisto.local',     '$2b$12$PLACEHOLDER.reemplazar.con.bcrypt.real.paciente1', TRUE, 'paciente'),
  (7, 'Ramiro', 'Acosta',    'admin@asisto.local',           '$2b$12$PLACEHOLDER.reemplazar.con.bcrypt.real.admin00001', TRUE, 'admin');


INSERT INTO terapeutas (id, id_usuario, matricula, especialidad, nro_licencia) VALUES
  (1, 1, 'MP-14523', 'Integracion sensorial infantil', 'LIC-2019-0087'),
  (2, 2, 'MP-16890', 'Rehabilitacion neurologica',     'LIC-2021-0154');

INSERT INTO rrhh (id, id_usuario, sector, nro_legajo) VALUES
  (1, 3, 'Administracion de personal', 'LEG-00231');

INSERT INTO familiares (id, id_usuario, parentesco, telefono) VALUES
  (1, 4, 'Madre', '+54 261 4155023'),
  (2, 5, 'Padre', '+54 261 4788910');


-- =====================================================================
-- PACIENTES — regla 5 en accion
--
-- DOS pacientes SIN login (id_usuario NULL): son menores, la familia no
-- les crea credenciales. Existen como registro clinico completo igual.
-- UNO con login (id_usuario 6): adulta, accede a sus propios objetivos.
--
-- Este contraste es intencional y no se debe "normalizar".
-- =====================================================================
INSERT INTO pacientes
  (id, id_usuario, nombre, apellido, fecha_nacimiento, diagnostico, nro_historia, activo, fecha_alta) VALUES
  (1, NULL, 'Tomas',     'Aguirre', '2015-03-12',
   'Trastorno del procesamiento sensorial. Dificultades en motricidad fina.',
   'HC-0001', TRUE, '2026-03-02'),

  (2, NULL, 'Valentina', 'Sosa',    '2017-08-25',
   'Retraso madurativo leve. Hipersensibilidad auditiva.',
   'HC-0002', TRUE, '2026-03-16'),

  (3, 6,    'Camila',    'Rios',    '1998-11-05',
   'Lesion de muneca derecha. Rehabilitacion funcional post quirurgica.',
   'HC-0003', TRUE, '2026-04-06');

-- ---------------------------------------------------------------------
-- Paciente 4 — DADO DE BAJA, y con historia completa detras.
--
-- Agregado el 2026-08-12 con el modulo de baja. El unico paciente de baja
-- que habia en el seed_demo no tenia NADA: 0 sesiones, 0 objetivos, 0
-- asignaciones. Un test de baja contra un paciente asi pasa en verde sin
-- probar nada, que es el patron que ya nos costo cuatro tests falsos.
--
-- Este tiene lo que hace falta para que la baja se pueda probar de verdad:
-- 3 sesiones, 4 evoluciones, 2 objetivos que quedaron archivados por la baja
-- y 1 asignacion cerrada el mismo dia. El estado es EXACTAMENTE el que deja
-- p_baja_paciente, pero escrito con fechas fijas: un fixture tiene que ser
-- un estado conocido, no uno que se recalcula en cada carga.
--
-- Con esto quedan los dos casos que un test necesita:
--   - paciente 4, YA dado de baja  -> lectura de su historia, y que toda
--     escritura sobre el se rechace;
--   - paciente 1, activo y con historia -> correrle p_baja_paciente encima
--     y verificar la transicion.
-- ---------------------------------------------------------------------
-- Entra ACTIVO y se da de baja al final del archivo. No es un rodeo: los
-- triggers rechazan crear objetivos activos sobre un paciente dado de baja,
-- asi que un seed que lo insertara ya inactivo no podria darle historia. El
-- orden del seed es el orden real de los hechos.
INSERT INTO pacientes
  (id, id_usuario, nombre, apellido, fecha_nacimiento, diagnostico,
   obra_social, nro_historia, activo, fecha_alta) VALUES
  (4, NULL, 'Ignacio', 'Peralta', '2016-01-19',
   'Trastorno del desarrollo de la coordinacion. Alta por mudanza.',
   'OSDE 210', 'HC-0004', TRUE, '2026-03-05');


-- =====================================================================
-- OBJETIVOS TERAPEUTICOS
--
-- Paciente 1: 3 ACTIVOS + 1 ARCHIVADO. Demuestra que el limite de 4 es
-- sobre activos y no sobre el total historico: tiene 4 filas y todavia
-- puede crear un objetivo mas.
-- Paciente 2: 2 activos. Paciente 3: 1 activo.
-- =====================================================================
INSERT INTO objetivos_terapeuticos
  (id, id_paciente, descripcion, activo, fecha_creacion, fecha_archivado) VALUES
  (1, 1, 'Mejorar la pinza fina para la escritura',          TRUE,  '2026-03-02 10:15:00', NULL),
  (2, 1, 'Tolerar texturas nuevas en la alimentacion',       TRUE,  '2026-03-02 10:20:00', NULL),
  (3, 1, 'Sostener la atencion en tareas de 10 minutos',     TRUE,  '2026-03-09 09:40:00', NULL),
  -- Archivado: se cumplio y se cerro. No consume cupo y su descripcion
  -- queda liberada para volver a usarse (ver verificacion 4).
  (4, 1, 'Vestirse de forma autonoma',                       FALSE, '2026-03-02 10:25:00', '2026-05-18 11:00:00'),

  (5, 2, 'Coordinar movimientos bilaterales',                TRUE,  '2026-03-16 14:05:00', NULL),
  (6, 2, 'Regular la respuesta a estimulos auditivos',       TRUE,  '2026-03-16 14:10:00', NULL),

  (7, 3, 'Recuperar rango de movimiento en muneca derecha',  TRUE,  '2026-04-06 16:30:00', NULL),

  -- Paciente 4 (dado de baja). Nacen ACTIVOS a proposito: la regla 4 impide
  -- cargar evolucion sobre un objetivo archivado, asi que si entraran ya
  -- archivados el trigger rechazaria las evoluciones de mas abajo. Se
  -- archivan al final del seed, que es ademas el orden real de los hechos:
  -- primero se trabajo con ellos, despues se dio de baja al paciente.
  (8, 4, 'Mejorar el equilibrio en apoyo monopodal',         TRUE,  '2026-03-05 09:30:00', NULL),
  (9, 4, 'Organizar la secuencia de vestido superior',       TRUE,  '2026-03-05 09:35:00', NULL);


-- =====================================================================
-- ASIGNACIONES
--
-- Va ANTES de SESIONES (2026-09-28, regla 8): el trigger de sesiones exige
-- una asignacion vigente a la fecha de cada sesion, asi que si este bloque
-- quedara mas abajo en el archivo -como estaba hasta esta fecha- el INSERT
-- de sesiones rechazaria la primera fila por falta de asignacion, aunque el
-- archivo terminara consistente al final. El orden de carga importa tanto
-- como el estado final.
--
-- Reemplaza al bloque de duplas_terapeuticas, que sembraba dos terapeutas
-- sobre un paciente: el caso interdisciplinario, fuera del alcance.
--
-- id_terapeuta apunta a terapeutas(id), igual que sesiones. Son las dos
-- terapeutas del seed chico: terapeuta 1 (Laura) y terapeuta 2 (Diego).
--
-- La segunda fila esta CERRADA (fecha_hasta no nula) a proposito: deja el
-- caso "el paciente 1 paso de una terapeuta a otra" sin violar la regla de
-- una sola asignacion vigente por par.
-- =====================================================================
INSERT INTO asignaciones
  (id, id_terapeuta, id_paciente, fecha_desde, fecha_hasta) VALUES
  (1, 1, 1, '2026-03-02', NULL),
  (2, 2, 1, '2026-03-02', '2026-05-04'),
  (3, 2, 2, '2026-03-16', NULL),
  (4, 1, 3, '2026-04-06', NULL),
  -- Paciente 4: cerrada el mismo dia de la baja, que es lo que hace
  -- p_baja_paciente. "Vigente" es fecha_hasta IS NULL y nada mas.
  --
  -- OJO CON LA FECHA DE BAJA (2026-07-20): la sesion 4 de este paciente,
  -- mas abajo, es del 2026-06-19, bastante antes. La regla 8 evalua contra
  -- la fecha de la SESION, no contra hoy, asi que esta asignacion tiene que
  -- cubrir ese rango completo -- fecha_desde <= toda fecha de sesion de este
  -- paciente <= fecha_hasta -- y lo cubre: las tres sesiones del paciente 4
  -- caen entre el 2026-06-05 y el 2026-06-19, dentro de [03-05, 07-20].
  (5, 1, 4, '2026-03-05', '2026-07-20');


-- =====================================================================
-- SESIONES — 10 sesiones
-- Incluye 2 ausencias (id 4 y 7) y 1 incompleta (id 3).
-- Terapeuta 1: pacientes 1 y 3. Terapeuta 2: paciente 2.
-- =====================================================================
-- ausencia_de en las dos filas de ausencia: 'paciente' para las dos,
-- no por uniformidad sino porque las notas ya escritas (mas abajo,
-- ninguna se toco) describen las dos como falta del paciente -- "avisó
-- la familia", "no asistió, sin aviso previo" -- y no hay margen para
-- inventar una ausencia del terapeuta sin reescribir ese texto. Con
-- sólo 2 filas ninguna proporción es representativa; la variedad real
-- (fue el criterio no uniforme que se pidió) va en seed_demo.sql, que
-- tiene volumen para que importe.
INSERT INTO sesiones
  (id, id_terapeuta, id_paciente, fecha, hora_inicio, hora_fin, estado, ausencia_de, notas) VALUES
  (1,  1, 1, '2026-06-02', '09:00:00', '10:00:00', 'completa',  NULL,
   'Buena disposicion. Trabajamos con masa y pinzas de ropa.'),
  (2,  1, 1, '2026-06-09', '09:00:00', '10:00:00', 'completa',  NULL,
   'Sostuvo la actividad de encastre sin ayuda fisica.'),
  (3,  1, 1, '2026-06-16', '09:00:00', '10:00:00', 'incompleta', NULL,
   'Se retiro 20 minutos antes por malestar.'),
  -- AUSENCIA: no lleva evolucion. El trigger lo impide (verificacion 1).
  (4,  1, 1, '2026-06-23', '09:00:00', NULL,       'ausencia', 'paciente',
   'La familia aviso el mismo dia.'),
  (5,  2, 2, '2026-06-03', '11:00:00', '12:00:00', 'completa',  NULL,
   'Tolero el circuito de integracion sensorial completo.'),
  (6,  2, 2, '2026-06-10', '11:00:00', '12:00:00', 'completa',  NULL,
   'Respondio bien a los auriculares de atenuacion.'),
  -- Segunda AUSENCIA, tampoco lleva evolucion.
  (7,  2, 2, '2026-06-17', '11:00:00', NULL,       'ausencia', 'paciente',
   'No asistio, sin aviso previo.'),
  (8,  1, 3, '2026-06-04', '15:00:00', '16:00:00', 'completa',  NULL,
   'Inicio de ejercicios de movilidad pasiva.'),
  (9,  1, 3, '2026-06-11', '15:00:00', '16:00:00', 'completa',  NULL,
   'Progreso en flexion. Sin dolor referido.'),
  (10, 1, 1, '2026-06-30', '09:00:00', '10:00:00', 'completa',  NULL,
   'Cierre de mes. Se evaluaron dos objetivos.'),

  -- Paciente 4, dado de baja despues. Las sesiones NO se tocan en la baja:
  -- son hechos que ocurrieron. Van a las 11:00 porque el terapeuta 1 ya
  -- tiene ocupadas las 09:00 y las 15:00 de esas semanas, y la regla 6
  -- rechazaria el solape.
  (11, 1, 4, '2026-06-05', '11:00:00', '12:00:00', 'completa', NULL,
   'Trabajo de equilibrio con circuito de obstaculos.'),
  (12, 1, 4, '2026-06-12', '11:00:00', '12:00:00', 'completa', NULL,
   'Secuencia de vestido con apoyo verbal.'),
  (13, 1, 4, '2026-06-19', '11:00:00', '12:00:00', 'completa', NULL,
   'Ultima sesion antes de la mudanza de la familia.');


-- =====================================================================
-- EVOLUCIONES
--
-- Solo para las sesiones que NO son ausencia. Las sesiones 4 y 7 quedan
-- deliberadamente sin evolucion: el trigger las rechaza, y esa es la
-- demostracion de la regla 2.
--
-- Las sesiones 2, 6 y 10 evaluan dos objetivos: la estructura lo permite
-- aunque lo habitual sea uno solo.
-- =====================================================================
INSERT INTO evoluciones (id, id_sesion, id_objetivo, valor, observaciones) VALUES
  (1,  1,  1, 2, 'Logra la pinza con apoyo verbal constante.'),
  (2,  2,  1, 3, 'Menos apoyo necesario que la semana pasada.'),
  (3,  2,  2, 2, 'Acepto probar una textura nueva sin rechazo.'),
  (4,  3,  2, 3, 'Sostuvo la actividad pese al malestar.'),
  (5,  5,  5, 2, 'Coordinacion aun irregular en el cruce de linea media.'),
  (6,  6,  5, 3, 'Mejora clara en el circuito bilateral.'),
  (7,  6,  6, 2, 'Reaccion mas leve a los ruidos del pasillo.'),
  (8,  8,  7, 3, 'Rango de flexion medido en 45 grados.'),
  (9,  9,  7, 4, 'Rango de flexion medido en 60 grados.'),
  (10, 10, 1, 4, 'Escritura sostenida durante 8 minutos.'),
  (11, 10, 3, 3, 'Atencion sostenida cerca del objetivo planteado.'),

  -- Paciente 4. Se cargan mientras sus objetivos siguen ACTIVOS; el archivado
  -- viene despues. Sobreviven a la baja intactas, que es justamente lo que
  -- hay que poder verificar.
  (12, 11, 8, 2, 'Sostiene el apoyo monopodal 3 segundos con apoyo.'),
  (13, 12, 9, 2, 'Ordena dos prendas de tres en la secuencia.'),
  (14, 13, 8, 3, 'Llega a 8 segundos sin apoyo externo.'),
  (15, 13, 9, 3, 'Completa la secuencia con una sola indicacion.');


-- =====================================================================
-- OBSERVACIONES TECNICAS DE RRHH
-- No es contenido clinico: es verificacion de asistencia y logistica.
-- =====================================================================
INSERT INTO observaciones_rrhh (id, id_sesion, id_rrhh, texto) VALUES
  (1, 3, 1, 'Sesion finalizada antes de horario. Se descuenta media hora.'),
  (2, 4, 1, 'Ausencia avisada el mismo dia, no computa como inasistencia sin aviso.'),
  (3, 7, 1, 'Ausencia sin aviso previo. Se notifico a coordinacion.');


-- =====================================================================
-- VINCULO FAMILIAR
-- =====================================================================
INSERT INTO familiares_pacientes (id_familiar, id_paciente, fecha_vinculo) VALUES
  (1, 1, '2026-03-02'),
  (2, 2, '2026-03-16');


-- =====================================================================
-- ETIQUETAS
-- Los colores salen de frontend/src/theme/theme.js. No inventar hex:
--   EUCALIPTO #3E8E7E  NAVY     #1B3B5C  ARCILLA  #C97B5A
--   SALVIA    #7FA99B  AMBAR    #D9A441  LADRILLO #B5544C
-- =====================================================================
INSERT INTO etiquetas (id, nombre, color_hex) VALUES
  (1, 'Motricidad fina',              '#3E8E7E'),
  (2, 'Integracion sensorial',        '#1B3B5C'),
  (3, 'Actividades de la vida diaria','#C97B5A'),
  (4, 'Trabajo con familia',          '#7FA99B'),
  (5, 'Requiere seguimiento',         '#D9A441'),
  (6, 'Sesion reprogramada',          '#B5544C');

INSERT INTO sesiones_etiquetas (id_sesion, id_etiqueta) VALUES
  (1, 1), (1, 3),
  (2, 1),
  (3, 1), (3, 5),
  (4, 6),
  (5, 2),
  (6, 2), (6, 4),
  (7, 6), (7, 5),
  (8, 1),
  (9, 1),
  (10, 1), (10, 3);


-- =====================================================================
-- NOTIFICACIONES Y PREFERENCIAS
-- =====================================================================
INSERT INTO notificaciones (id, id_familiar, id_paciente, tipo, mensaje, leida, fecha) VALUES
  (1, 1, 1, 'nueva_sesion',     'Se registro una nueva sesion para Tomas el 02/06/2026.',      TRUE,  '2026-06-02 10:05:00'),
  (2, 1, 1, 'cambio_objetivo',  'Se archivo el objetivo "Vestirse de forma autonoma".',        TRUE,  '2026-05-18 11:05:00'),
  (3, 1, 1, 'informe_generado', 'El informe del segundo trimestre esta disponible.',           FALSE, '2026-07-01 09:00:00'),
  (4, 2, 2, 'nueva_sesion',     'Se registro una nueva sesion para Valentina el 10/06/2026.',  FALSE, '2026-06-10 12:05:00'),
  -- El texto describe el alta de la sesion, no su resultado: el ENUM de
  -- notificaciones.tipo no tiene un valor para ausencias, y el tipo se usa
  -- para filtrar contra preferencias_notificacion. Un mensaje que hable de
  -- una ausencia bajo tipo 'nueva_sesion' se contradice con su etiqueta.
  (5, 2, 2, 'nueva_sesion',     'Se registro una nueva sesion para Valentina el 17/06/2026.',  FALSE, '2026-06-17 12:05:00');

INSERT INTO preferencias_notificacion (id_familiar, tipo, habilitada) VALUES
  (1, 'nueva_sesion',     TRUE),
  (1, 'informe_generado', TRUE),
  (1, 'cambio_objetivo',  TRUE),
  (2, 'nueva_sesion',     TRUE),
  (2, 'informe_generado', TRUE),
  -- Deshabilitada a proposito: sirve para probar que el filtro de
  -- preferencias efectivamente corta el envio.
  (2, 'cambio_objetivo',  FALSE);


-- =====================================================================
-- INFORMES
-- contenido_original = salida cruda de la IA.
-- contenido          = version revisada por el terapeuta.
-- =====================================================================
INSERT INTO informes
  (id, id_paciente, id_terapeuta, periodo, contenido, contenido_original, estado, fecha_generacion, fecha_publicacion) VALUES
  (1, 1, 1, '2026-T2',
   'Durante el segundo trimestre Tomas mostro avances sostenidos en motricidad fina, pasando de requerir apoyo verbal constante a sostener la escritura por periodos de 8 minutos. Se archivo el objetivo de vestido autonomo por cumplimiento.',
   'El paciente presento mejoras en el trimestre. Se observa progreso en motricidad fina y atencion.',
   'final', '2026-07-01 08:30:00', '2026-07-01 09:00:00'),

  (2, 2, 2, '2026-T2',
   NULL,
   'Valentina registra dos sesiones completas y una ausencia en el periodo. Se observa mejor tolerancia a estimulos auditivos.',
   'borrador', '2026-07-01 08:45:00', NULL);


-- =====================================================================
-- LA BAJA DEL PACIENTE 4 — al final, y en este orden exacto
--
-- El paciente entro activo y con historia. Recien ahora se lo da de baja,
-- porque los triggers no permiten construir ese estado al reves:
--
--   - la regla 4 rechaza cargar evolucion sobre un objetivo archivado, asi
--     que los objetivos tienen que nacer activos y archivarse despues;
--   - desde el 2026-08-12 los triggers ademas rechazan crear o activar
--     objetivos —y abrir asignaciones— sobre un paciente dado de baja, asi
--     que el paciente tiene que seguir activo hasta este punto.
--
-- El propio seed es entonces una prueba de que las dos reglas estan puestas:
-- si alguna se cayera, este bloque dejaria de ser necesario y el seed
-- cargaria igual en cualquier orden.
--
-- Los objetivos van en DOS updates y el segundo no es redundante:
--   1. El primero archiva. trg_objetivos_limite_activos_update le pone a
--      fecha_archivado el NOW() de la carga.
--   2. El segundo la fija en la fecha de la baja. Con activo pasando de
--      FALSE a FALSE ninguna rama del trigger se dispara, asi que el valor
--      queda como se escribe. Sin este paso el fixture cambiaria de
--      contenido en cada carga y ningun test podria afirmar la fecha.
--
-- La asignacion ya entro cerrada mas arriba, asi que no hace falta tocarla.
-- =====================================================================
-- La baja va PRIMERO: con el paciente de baja el trigger no exige el minimo
-- de 3 objetivos activos al archivar (rige solo para pacientes en tratamiento).
UPDATE pacientes
   SET activo = FALSE,
       fecha_baja = '2026-07-20',
       tipo_cierre = 'alta'
 WHERE id = 4;

UPDATE objetivos_terapeuticos
   SET activo = FALSE
 WHERE id_paciente = 4 AND activo = TRUE;

UPDATE objetivos_terapeuticos
   SET fecha_archivado = '2026-07-20 09:00:00'
 WHERE id_paciente = 4;


-- =====================================================================
-- PLANTILLAS DE OBJETIVOS
-- =====================================================================
INSERT INTO plantillas_objetivos (id, area, descripcion) VALUES
  (1, 'Motricidad fina',       'Mejorar la pinza fina para la escritura'),
  (2, 'Motricidad fina',       'Realizar encastres de piezas pequenas sin ayuda'),
  (3, 'Motricidad gruesa',     'Mantener el equilibrio en una pierna por 10 segundos'),
  (4, 'Integracion sensorial', 'Tolerar texturas nuevas en la alimentacion'),
  (5, 'Integracion sensorial', 'Regular la respuesta a estimulos auditivos'),
  (6, 'Vida diaria',           'Vestirse de forma autonoma'),
  (7, 'Vida diaria',           'Utilizar cubiertos de manera independiente'),
  (8, 'Atencion',              'Sostener la atencion en tareas de 10 minutos'),
  (9, 'Rehabilitacion',        'Recuperar rango de movimiento en muneca derecha');


-- =====================================================================
-- AUDITORIA DE ACCESOS
-- La fila 4 tiene id_usuario NULL a proposito: es un intento contra un
-- email que no existe en el sistema. Se audita igual.
-- =====================================================================
INSERT INTO auditoria_accesos (id, id_usuario, email, resultado, ip, fecha) VALUES
  (1, 1,    'laura.fernandez@asisto.local', 'exitoso',  '192.168.1.24',  '2026-06-02 08:45:00'),
  (2, 2,    'diego.moyano@asisto.local',    'exitoso',  '192.168.1.31',  '2026-06-03 10:50:00'),
  (3, 3,    'silvia.quiroga@asisto.local',  'fallido',  '192.168.1.15',  '2026-06-05 09:12:00'),
  (4, NULL, 'noexiste@asisto.local',        'fallido',  '201.190.44.10', '2026-06-05 09:14:00'),
  (5, 3,    'silvia.quiroga@asisto.local',  'exitoso',  '192.168.1.15',  '2026-06-05 09:15:00'),
  (6, 6,    'camila.rios@asisto.local',     'bloqueado','190.15.22.100', '2026-06-08 21:03:00');


-- =====================================================================
-- FIN DEL SEED
-- =====================================================================
SELECT 'Datos de prueba cargados correctamente' AS resultado;
SELECT
  (SELECT COUNT(*) FROM usuarios)               AS usuarios,
  (SELECT COUNT(*) FROM pacientes)              AS pacientes,
  (SELECT COUNT(*) FROM pacientes WHERE id_usuario IS NULL) AS pacientes_sin_login,
  (SELECT COUNT(*) FROM objetivos_terapeuticos) AS objetivos,
  (SELECT COUNT(*) FROM objetivos_terapeuticos WHERE activo = TRUE) AS objetivos_activos,
  (SELECT COUNT(*) FROM sesiones)               AS sesiones,
  (SELECT COUNT(*) FROM evoluciones)            AS evoluciones;
