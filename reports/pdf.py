from reportlab.platypus import PageBreak, Paragraph, Spacer
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from io import BytesIO

from django.http import HttpResponse

def generate_report(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'

    doc = canvas.Canvas(response, pagesize=A4)
    styles = getSampleStyleSheet()

    # Encabezado
    title = Paragraph("Reporte de prueba", styles['Title'])
    title.wrapOn(doc, 6 * inch, 1 * inch)
    title.drawOn(doc, 1.5 * inch, 10.5 * inch)

    elements = [
        title,
    ]

    # Table
    data = [['', 'col1', 'col2', 'col3'],
            ['row1', '1', '2', '3'],
            ['row2', '4', '5', '6'],
            ['row3', '7', '8', '9']]

    t = Table(data, colWidths=[1.5 * inch] * 4)
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                          ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
                          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))

    elements.append(t)

    for element in elements:
        element.drawOn(doc, 0.5 * inch,  0.5 * inch)

    # Pie de página
    page_num = Paragraph("Página 1/1", styles['BodyText'])
    page_num.wrapOn(doc, 1.5 * inch, 1 * inch)
    page_num.drawOn(doc, 0.5 * inch, 0.5 * inch)

    doc.showPage()
    doc.save()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'
    buffer = BytesIO()
    doc = canvas.Canvas(buffer, pagesize=A4)

    return response

