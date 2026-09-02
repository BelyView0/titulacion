"""Generación de PDFs — Oficina de Titulación."""
from io import BytesIO
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from xhtml2pdf import pisa


def _html_to_pdf(html):
    result = BytesIO()
    pisa.CreatePDF(html, dest=result)
    if result.getvalue():
        return ContentFile(result.getvalue())
    return None


def generar_constancia_no_inconveniencia_pdf(expediente):
    """Genera PDF de constancia de no inconveniencia para acto de recepción profesional."""
    from django.conf import settings
    from django.utils import timezone
    from administracion.models import ConfiguracionInstitucional
    from administracion.pdf_oficio import link_callback

    alumno = expediente.alumno
    config = ConfiguracionInstitucional.objects.first()
    html_string = render_to_string(
        'oficina_titulacion/pdf/constancia_no_inconveniencia.html',
        {
            'expediente': expediente,
            'alumno': alumno,
            'config': config,
            'fecha_actual': timezone.now(),
            'lugar': getattr(settings, 'ITA_CIUDAD', 'Tzompantepec, Tlaxcala'),
        },
    )
    result = BytesIO()
    pdf = pisa.pisaDocument(
        BytesIO(html_string.encode('UTF-8')),
        result,
        link_callback=link_callback,
    )
    if pdf.err:
        raise Exception('Error al generar PDF de constancia: ' + str(pdf.err))
    return result.getvalue()


# Alias usado por vistas legacy
generar_constancia_pdf = generar_constancia_no_inconveniencia_pdf


def generar_constancia_no_adeudos_pdf(expediente):
    from administracion.models import ConfiguracionInstitucional
    config = ConfiguracionInstitucional.objects.first()
    html = render_to_string('oficina_titulacion/pdf/constancia_no_adeudos.html', {
        'expediente': expediente,
        'config': config,
        'alumno': expediente.alumno,
    })
    return _html_to_pdf(html)


def generar_oficio_publicacion_pdf(expediente):
    from administracion.models import ConfiguracionInstitucional
    config = ConfiguracionInstitucional.objects.first()
    html = render_to_string('oficina_titulacion/pdf/oficio_publicacion.html', {
        'expediente': expediente,
        'config': config,
        'alumno': expediente.alumno,
    })
    return _html_to_pdf(html)


def generar_certificacion_final_pdf(expediente):
    from administracion.models import ConfiguracionInstitucional
    config = ConfiguracionInstitucional.objects.first()
    jurado = getattr(expediente, 'jurado', None)
    html = render_to_string('oficina_titulacion/pdf/certificacion_exencion.html', {
        'expediente': expediente,
        'config': config,
        'alumno': expediente.alumno,
        'jurado': jurado,
    })
    return _html_to_pdf(html)
