"""
Generación de Constancia de No Inconveniencia en PDF.
"""
from django.template.loader import render_to_string
from django.conf import settings
from administracion.models import ConfiguracionInstitucional
from administracion.pdf_oficio import link_callback
from xhtml2pdf import pisa
from io import BytesIO
from django.utils import timezone


def generar_constancia_pdf(expediente):
    """
    Recibe una instancia de Expediente y retorna los bytes del PDF
    de la Constancia de No Inconveniencia.
    """
    alumno = expediente.alumno
    config = ConfiguracionInstitucional.objects.first()

    context = {
        'expediente': expediente,
        'alumno': alumno,
        'config': config,
        'fecha_actual': timezone.now(),
        'lugar': getattr(settings, 'ITA_CIUDAD', 'Tzompantepec, Tlaxcala'),
    }

    html_string = render_to_string('escolares/pdf/constancia_no_inconveniencia.html', context)

    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result, link_callback=link_callback)
    
    if not pdf.err:
        return result.getvalue()
    else:
        raise Exception("Error al generar PDF de constancia: " + str(pdf.err))
