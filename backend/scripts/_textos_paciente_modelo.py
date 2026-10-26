"""
Textos de los informes de Mateo Gómez (paciente modelo), redactados como los
dejaría la terapeuta despues de revisar el borrador. Los usa
crear_paciente_modelo.py.

`niveles` es la huella de lo que calcula el sistema para ese periodo (escritura,
autorregulacion, vida diaria, juego): si el generador cambia y los niveles ya
no coinciden, el script avisa para que se revise el texto.
"""

MENSUAL = {
    '2026-03': {
        'niveles': ('Inicial', 'No logrado', 'En proceso', 'No logrado'),
        'evolucion': [
            'Mateo comenzó el tratamiento con buena disposición y mucha curiosidad por los materiales, '
            'aunque con poca tolerancia a la frustración. Fue necesario anticipar cada actividad con apoyo '
            'visual para que pudiera iniciarla sin ansiedad.',
            'En escritura se observó un agarre palmar del lápiz y una presión excesiva, con cansancio a los '
            'pocos minutos. En la rutina de vestido ya logra algunos botones grandes, que es lo que se tomó '
            'como punto de partida.',
            'En los juegos con reglas le costó esperar el turno y aceptar que la actividad terminara. Estas '
            'situaciones se acompañaron con la estrategia de pausa y respiración, todavía con mucha guía.',
        ],
        'cierre': 'Se continúa con dos sesiones semanales. Próximos pasos: instalar la rutina de la sesión '
                  'con agenda visual, iniciar la práctica de la pinza trípode con actividades de modelado y '
                  'acordar con la familia cinco minutos diarios de práctica de botones en casa.',
    },
    '2026-04': {
        'niveles': ('Inicial', 'Inicial', 'En proceso', 'Inicial'),
        'evolucion': [
            'Durante abril la rutina de la sesión quedó establecida y Mateo ingresa al consultorio con más '
            'seguridad. La agenda visual le permite anticipar los cambios de actividad con menos tensión.',
            'En autorregulación empezó a reconocer que se enoja y aceptó usar la respiración guiada con '
            'apoyo verbal. En juego mejoró la espera del turno en actividades breves, con recordatorios.',
            'La escritura se mantiene en un nivel inicial: alterna el agarre inmaduro con la pinza cuando se '
            'le ofrece una guía de posición. Se registró una falta del paciente, avisada por la familia.',
        ],
        'cierre': 'Se continúa con el mismo plan. Próximos pasos: sumar actividades de fortalecimiento de la '
                  'mano antes de escribir, practicar el rincón de pausa fuera de los momentos de enojo y '
                  'pedir a la escuela una muestra de sus cuadernos para ajustar la tarea escrita.',
    },
    '2026-05': {
        'niveles': ('Inicial', 'Inicial', 'En proceso', 'Inicial'),
        'evolucion': [
            'Mayo fue un mes de altibajos. Hubo una falta del paciente y una sesión que se cortó antes de '
            'tiempo, y el sistema marca un retroceso en escritura y en vida diaria respecto del mes anterior.',
            'Cuando retomó la continuidad semanal volvió a sostener los botones con tiempo extra y sin ayuda '
            'física. En escritura recuperó la pinza trípode con la guía de posición, aunque con fatiga '
            'rápida en las tareas largas.',
            'En autorregulación y en juego los avances son pequeños pero consistentes: usa la pausa con una '
            'sola indicación y tolera mejor perder una ronda cuando se le anticipa el final.',
        ],
        'cierre': 'Se mantiene la frecuencia de dos sesiones semanales. Próximos pasos: reforzar con la '
                  'familia la asistencia regular, retomar los ejercicios de fortalecimiento de la mano y '
                  'seguir de cerca la escritura el mes próximo.',
    },
    '2026-06': {
        'niveles': ('En proceso', 'Inicial', 'Avanzado', 'Inicial'),
        'evolucion': [
            'En junio se destacó el avance en vida diaria: Mateo se abrocha los botones de forma '
            'independiente y está empezando a practicar el primer nudo de los cordones. También la '
            'escritura pasó a un nivel En proceso, con mejor presión y más renglones sostenidos.',
            'La autorregulación tuvo un período más difícil. Por las evaluaciones de la escuela llegó '
            'inquieto a varias sesiones y volvió a necesitar acompañamiento para calmarse, por lo que el '
            'objetivo permanece en nivel Inicial.',
            'Se habló con la familia sobre el cansancio de fin de cuatrimestre y se acordó simplificar '
            'las rutinas de la tarde. Hubo una falta del paciente, avisada con anticipación.',
        ],
        'cierre': 'Cierra el primer semestre de tratamiento. Próximos pasos: priorizar la regulación '
                  'sensorial al inicio de cada sesión, sostener la práctica de cordones y acordar con la '
                  'escuela una adaptación de los tiempos de evaluación escrita.',
    },
    '2026-07': {
        'niveles': ('En proceso', 'En proceso', 'Logrado', 'Inicial'),
        'evolucion': [
            'Julio mostró una recuperación clara en autorregulación: Mateo pide una pausa por iniciativa '
            'propia en varias ocasiones y vuelve a la tarea sin ayuda. Aun así, el sistema señala semanas '
            'de más dificultad dentro del mes, por lo que se sigue de cerca.',
            'El objetivo de vida diaria alcanzó el nivel Logrado: se abrocha y desabrocha el guardapolvo y '
            'se ata los cordones sin ayuda del adulto. En escritura mejora la tolerancia: copia oraciones '
            'cortas respetando el renglón.',
            'El juego con reglas es el área que más cuesta. Sostiene el turno en juegos conocidos, pero '
            'reclama cuando pierde. Una sesión del mes no se realizó por la ausencia de la terapeuta, '
            'que asistió a una capacitación del centro.',
        ],
        'cierre': 'Se continúa con dos sesiones semanales. Próximos pasos: mantener el objetivo de vida '
                  'diaria en seguimiento sin trabajarlo en forma activa, dedicar más tiempo al juego con '
                  'reglas y proponer a la familia juegos de mesa breves en casa.',
    },
    '2026-08': {
        'niveles': ('En proceso', 'En proceso', 'Logrado', 'En proceso'),
        'evolucion': [
            'Agosto fue un mes estable y con buen ritmo de trabajo. Mateo llega a las sesiones con más '
            'predisposición y puede explicar con sus palabras qué le pasó cuando se frustra.',
            'La autorregulación y el juego con reglas avanzaron al nivel En proceso. Usa las estrategias '
            'practicadas con una sola indicación y acepta mejor el final de las actividades.',
            'La escritura se mantiene en proceso, con trazo más regular y menos fatiga. Hubo una falta '
            'del paciente y una sesión que se interrumpió antes de tiempo.',
        ],
        'cierre': 'Se mantiene el plan. Próximos pasos: avanzar en la copia de oraciones más largas, '
                  'ensayar el cambio de actividad sin anticipación visual y preparar la revisión semestral '
                  'del plan terapéutico de septiembre.',
    },
    '2026-09': {
        'niveles': ('Avanzado', 'En proceso', 'Logrado', 'En proceso'),
        'evolucion': [
            'En septiembre Mateo alcanzó el nivel Avanzado en escritura: sostiene la pinza trípode durante '
            'toda la actividad y copia oraciones completas respetando el renglón y el tamaño de las letras. '
            'Pide pausas antes de que aparezca el cansancio.',
            'En autorregulación y en juego se consolida el nivel En proceso. Ya prueba dos estrategias por '
            'su cuenta antes de pedir ayuda y puede perder una ronda sin enojarse en la mayoría de los '
            'casos. Hubo una falta del paciente y una sesión incompleta.',
            'Se realizó la revisión del plan terapéutico con la familia y la escuela. Se acordó mantener '
            'los cuatro objetivos y elevar el nivel de exigencia en escritura y en juego.',
        ],
        'cierre': 'Se continúa con dos sesiones semanales. Próximos pasos: ampliar la escritura a tareas '
                  'con copia desde el pizarrón, practicar la espera del turno con más de un compañero y '
                  'evaluar el alta del objetivo de vida diaria si se sostiene en el próximo informe.',
    },
}

SEMESTRAL = {
    '2026-S1': {
        'niveles': ('Inicial', 'Inicial', 'En proceso', 'Inicial'),
        'evolucion': [
            'Mateo ingresó al centro en marzo con dificultades marcadas de motricidad fina, de '
            'autorregulación y de autonomía en el vestido. En estos meses se instaló una rutina de trabajo '
            'estable, con agenda visual, pausas sensoriales y apoyo gradual, y se logró una asistencia '
            'regular: asistió a 24 de las 27 sesiones del semestre.',
            'La vida diaria fue el área de mayor avance. Pasó de abrochar solo botones grandes con ayuda '
            'a abrocharse de forma independiente y a practicar el primer nudo de los cordones. El nivel '
            'del semestre resume todo el período; hacia junio ya se ubicaba en Avanzado.',
            'En escritura pasó del agarre palmar a la pinza trípode con guía de posición, con una '
            'tendencia de mejora sostenida. La autorregulación y el juego con reglas permanecen en nivel '
            'Inicial, con avances pequeños y un tramo de mayor dificultad en mayo y junio, ligado a las '
            'exigencias de la escuela.',
            'La familia acompañó el proceso con la práctica diaria en casa y la comunicación mensual. La '
            'escuela aceptó reducir la carga de escritura manual mientras se consolida el agarre.',
        ],
        'cierre': 'Para el segundo semestre se propone sostener las dos sesiones semanales, priorizar '
                  'la autorregulación y el juego con reglas, dejar la vida diaria en seguimiento y '
                  'consolidar la escritura. El plan terapéutico se revisa en septiembre.',
    },
}

PTI_COORDINACION = (
    'Frecuencia: dos sesiones semanales de una hora, los lunes y jueves.\n\n'
    'Coordinación: reunión trimestral con la escuela para acordar adaptaciones de las tareas escritas y '
    'comunicación mensual con la familia a través de los informes publicados. No hay otros '
    'profesionales intervinientes por el momento.\n\n'
    'Revisión: los objetivos se evalúan cada seis meses; la primera revisión del plan está prevista '
    'para el 14/09/2026. Un objetivo se da de alta cuando se sostiene en distintos contextos.'
)
