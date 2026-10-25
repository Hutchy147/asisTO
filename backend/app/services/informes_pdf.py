# backend/app/services/informes_pdf.py
# Exportacion de un informe a PDF (Entrega 6, HDU 8).
#
# Se genera en el servidor, con el contenido guardado, para que el archivo
# sea el mismo lo pida quien lo pida (la terapeuta o el familiar). Un
# BORRADOR sale con la marca "BORRADOR" en cada pagina: nadie puede confundir
# un texto sin revisar con un informe publicado. Solo la terapeuta puede pedir
# el PDF de un borrador; el familiar solo ve publicados.
#
# El texto del informe usa una convencion minima: "## Titulo" abre una seccion,
# "- " abre un item de lista, y una linea en blanco separa parrafos.

import io
import re
import unicodedata
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

NAVY = colors.HexColor('#1F3A5F')
GRIS = colors.HexColor('#5B6573')
EUCALIPTO = colors.HexColor('#2F7A6B')
FONDO_FICHA = colors.HexColor('#F3F1EC')
BORDE = colors.HexColor('#D5DAE1')


def _estilos():
    base = getSampleStyleSheet()
    return {
        'titulo': ParagraphStyle('titulo', parent=base['Title'], fontName='Helvetica-Bold', fontSize=18,
                                 textColor=NAVY, alignment=TA_LEFT, spaceAfter=4, leading=22),
        'subtitulo': ParagraphStyle('subtitulo', parent=base['Normal'], fontSize=10, textColor=GRIS, leading=14),
        'seccion': ParagraphStyle('seccion', parent=base['Heading2'], fontName='Helvetica-Bold', fontSize=12, keepWithNext=1,
                                  textColor=NAVY, spaceBefore=14, spaceAfter=4, leading=15),
        'texto': ParagraphStyle('texto', parent=base['Normal'], fontSize=10.5, leading=15, spaceAfter=6),
        'meta_etiqueta': ParagraphStyle('meta_etiqueta', parent=base['Normal'], fontSize=9, textColor=GRIS, leading=12),
        'meta_valor': ParagraphStyle('meta_valor', parent=base['Normal'], fontSize=10.5, leading=14),
        'objetivo': ParagraphStyle('objetivo', parent=base['Normal'], fontName='Helvetica-Bold', fontSize=10.5, leading=14),
        'detalle': ParagraphStyle('detalle', parent=base['Normal'], fontSize=9, leading=12, textColor=GRIS),
        'nivel': ParagraphStyle('nivel', parent=base['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13,
                                textColor=EUCALIPTO, alignment=TA_RIGHT),
        'aclaracion': ParagraphStyle('aclaracion', parent=base['Normal'], fontSize=9, leading=12, textColor=GRIS, spaceAfter=6),
    }


def _parrafo(texto, estilo):
    return Paragraph(escape(texto).replace('\n', '<br/>'), estilo)


_NIVELES = 'No logrado|Inicial|En proceso|Avanzado|Logrado'
_RE_OBJETIVO = re.compile(rf'^(.*?): ({_NIVELES}) \(calificado en (una sesión|\d+ sesi(?:ón|ones))\)(?:; (.*?))?\.?$')
_RE_SIN_CALIFICAR = re.compile(r'^(.*?): no se calificó en el período\.?$')
_RE_OBSERVACION = re.compile(r'^(\d{2}/\d{2}): (.*)$')
# Secciones que el PDF muestra en el recuadro de arriba y no en el cuerpo.
_DE_LA_FICHA = ('datos del paciente', 'periodo')


def _normalizar(texto):
    sin = unicodedata.normalize('NFD', texto.lower())
    return ''.join(c for c in sin if unicodedata.category(c) != 'Mn').strip()


def _tabla_objetivos(items, estilos):
    """Objetivos con su nivel a la derecha; None si algun item no tiene la forma esperada."""
    filas = []
    for it in items:
        o = _RE_OBJETIVO.match(it)
        if o:
            detalle = ' · '.join(x for x in (f'Calificado en {o.group(3)}', o.group(4)) if x)
            filas.append((o.group(1), detalle[:1].upper() + detalle[1:], o.group(2)))
            continue
        sin = _RE_SIN_CALIFICAR.match(it)
        if not sin:
            return None
        filas.append((sin.group(1), 'No se calificó en el período', 'Sin calificar'))
    tabla = Table(
        [[[_parrafo(o, estilos['objetivo']), _parrafo(d, estilos['detalle'])], _parrafo(n, estilos['nivel'])]
         for o, d, n in filas],
        colWidths=[12.0 * cm, 4.6 * cm],
    )
    tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, BORDE),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return tabla


def _cuerpo(contenido, estilos):
    """Convierte el texto del informe en flowables. Devuelve (piezas, ficha)."""
    piezas, parrafo, items = [], [], []
    ficha = {}
    seccion = ''

    def cerrar_parrafo():
        if parrafo:
            texto = '\n'.join(parrafo)
            if seccion in _DE_LA_FICHA:
                ficha[seccion] = texto
            else:
                estilo = estilos['aclaracion'] if seccion.startswith('objetivos') else estilos['texto']
                piezas.append(_parrafo(texto, estilo))
            parrafo.clear()

    def cerrar_lista():
        if not items:
            return
        if seccion.startswith('objetivos'):
            tabla = _tabla_objetivos(items, estilos)
            if tabla is not None:
                piezas.extend([tabla, Spacer(1, 6)])
                items.clear()
                return
        if seccion.startswith('observaciones') and all(_RE_OBSERVACION.match(t) for t in items):
            for t in items:
                m = _RE_OBSERVACION.match(t)
                piezas.append(Paragraph(f'<b><font color="#2F7A6B">{escape(m.group(1))}</font></b>  {escape(m.group(2))}',
                                        estilos['texto']))
            items.clear()
            return
        piezas.append(ListFlowable(
            [ListItem(_parrafo(t, estilos['texto']), leftIndent=14) for t in items],
            bulletType='bullet', bulletFontSize=7, leftIndent=14, start='•',
        ))
        items.clear()

    for linea in (contenido or '').replace('\r\n', '\n').split('\n'):
        recortada = linea.strip()
        if recortada.startswith('## '):
            cerrar_parrafo(); cerrar_lista()
            titulo = recortada[3:].strip()
            seccion = _normalizar(titulo)
            if seccion not in _DE_LA_FICHA:
                piezas.append(Paragraph(escape(titulo), estilos['seccion']))
                piezas.append(HRFlowable(width='100%', thickness=0.6, color=BORDE, spaceAfter=5))
        elif re.match(r'^[-*]\s+', recortada):
            cerrar_parrafo()
            items.append(re.sub(r'^[-*]\s+', '', recortada))
        elif recortada == '':
            cerrar_parrafo(); cerrar_lista()
        else:
            cerrar_lista()
            parrafo.append(recortada)
    cerrar_parrafo(); cerrar_lista()
    return piezas, ficha


def generar_pdf(informe, paciente, autor):
    """
    `informe`: dict de informes_service.obtener(). `paciente`: nombre completo.
    `autor`: nombre del profesional (o None). Devuelve los bytes del PDF.
    """
    estilos = _estilos()
    es_borrador = informe['estado'] == 'borrador'
    salida = io.BytesIO()
    documento = SimpleDocTemplate(
        salida, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2.2 * cm, bottomMargin=2.2 * cm,
        title=f"{informe['tipo_etiqueta']} - {paciente}", author='AsisTO',
    )

    if informe['estado'] == 'final' and informe.get('fecha_publicacion'):
        fecha = informe['fecha_publicacion'][:10].split('-')
        publicado = f'Publicado el {fecha[2]}/{fecha[1]}/{fecha[0]}'
    elif es_borrador:
        publicado = 'BORRADOR: todavía no fue revisado ni publicado'
    else:
        publicado = 'Versión reemplazada por una posterior'

    version = f" · versión {informe['version']}" if informe['version'] > 1 else ''
    cuerpo, ficha = _cuerpo(informe.get('contenido'), estilos)
    meta = Table(
        [
            [Paragraph('Paciente', estilos['meta_etiqueta']), Paragraph('Período', estilos['meta_etiqueta']),
             Paragraph('Profesional', estilos['meta_etiqueta'])],
            [Paragraph(escape(ficha.get('datos del paciente') or paciente), estilos['meta_valor']),
             Paragraph(escape(str(informe['periodo_etiqueta']).capitalize()), estilos['meta_valor']),
             Paragraph(escape(autor or '-'), estilos['meta_valor'])],
        ],
        colWidths=[7.0 * cm, 4.8 * cm, 4.8 * cm],
    )
    meta.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), FONDO_FICHA),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDE),
        ('TOPPADDING', (0, 0), (-1, 0), 7), ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
        ('TOPPADDING', (0, 1), (-1, 1), 0), ('BOTTOMPADDING', (0, 1), (-1, 1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))

    historia = [
        Paragraph(escape(informe['tipo_etiqueta']), estilos['titulo']),
        Paragraph(escape(publicado + version), estilos['subtitulo']),
        Spacer(1, 10),
        meta,
    ]
    historia += cuerpo

    def pie(canvas, doc):
        canvas.saveState()
        if es_borrador:
            canvas.setFont('Helvetica-Bold', 70)
            canvas.setFillColor(colors.Color(0.85, 0.85, 0.85, alpha=0.45))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, 'BORRADOR')
            canvas.rotate(-45)
            canvas.translate(-A4[0] / 2, -A4[1] / 2)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(GRIS)
        canvas.drawString(2.2 * cm, 1.4 * cm, 'AsisTO · Documento clínico confidencial')
        canvas.drawRightString(A4[0] - 2.2 * cm, 1.4 * cm, f'Página {doc.page}')
        canvas.restoreState()

    documento.build(historia, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()


def nombre_de_archivo(informe, paciente):
    """Nombre seguro y legible: informe-mensual-2026-09-apellido-nombre.pdf"""
    sin_tildes = unicodedata.normalize('NFKD', paciente).encode('ascii', 'ignore').decode()
    limpio = re.sub(r'[^a-z0-9]+', '-', sin_tildes.lower()).strip('-')
    return f"informe-{informe['tipo']}-{informe['periodo']}-{limpio or 'paciente'}.pdf"
