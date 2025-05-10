from reportlab.platypus import PageBreak, Paragraph, Spacer, SimpleDocTemplate
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from io import BytesIO
import datetime

from django.http import HttpResponse

def generate_report(request, elements, title):
    def primera_pagina(canvas, doc):
        '''
        Resumen:
            Esta función coloca la disposición del encabezado del PDF a generar.
        '''
        width, height = A4
        canvas.saveState()
        titleStyle = ParagraphStyle(
            'title',
            fontSize=20,
            fontFamily='Junge',
            textTransform='uppercase',
            alignment=1,
            leading=24,
            color = colors.red
        )

        header = Paragraph(reportHeader, titleStyle)
        header.wrapOn(canvas, width-200, height+350)
        header.drawOn(canvas,100,765)

        footer = Paragraph(f'<p>Reporte generado por el usuario {request.user.get_full_name()}. </p>')
        footer.wrapOn(canvas, width, height)
        footer.drawOn(canvas,40,745)

        time = Paragraph(date)
        time.wrapOn(canvas, width, height)
        time.drawOn(canvas,470,745)

        canvas.restoreState()

        canvas.saveState()
        canvas.setFont('Times-Roman', 10)
        page_number_text = "Página %d" % (doc.page)
        canvas.drawCentredString(
            4 * inch,
            0.3 * inch,
            page_number_text + ', ' + reportHeader + ', ' + date + '.'
        )
        canvas.restoreState()

    def footer(canvas, doc):
        '''
        Resumen:
            Esta función coloca la disposición del pie de página del PDF a generar.
        '''
        canvas.saveState()
        canvas.setFont('Times-Roman', 10)
        page_number_text = "Página %d" % (doc.page)
        canvas.drawCentredString(
            4 * inch,
            0.3 * inch,
            page_number_text + ', ' + reportHeader + ', ' + date + '.'
        )
        canvas.restoreState()

    reportHeader = title
    date = datetime.datetime.now().strftime('%d/%m/%Y - %H:%M:%S')
    buff = BytesIO()
    doc = SimpleDocTemplate(buff,pagesize=A4, topMargin=30, bottomMargin=30)
    story = []

    story = [
        Spacer(0, 1 * inch),
        Table(
            [
                [Paragraph('Nombre'), Paragraph('Descripción'), Paragraph('Monto'), Paragraph('Fecha')],
            ],
            hAlign='LEFT',
            style=TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ])
        )
    ]

    doc.build(story, 
        onFirstPage=primera_pagina,
        onLaterPages=footer,
    )
          
    response = HttpResponse(content_type='application/pdf')
    fecha = datetime.datetime.now()
    response['Content-Disposition'] = f'attachment; filename="report_{fecha.year}_{fecha.month}_{fecha.day}_{fecha.hour}_{fecha.minute}.pdf"'

    response.write(buff.getvalue())
    buff.close()

    return response
