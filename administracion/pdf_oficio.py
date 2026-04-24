"""
Generación del Oficio de Asignación de Jurado en PDF.
Usa xhtml2pdf para convertir el template HTML al PDF institucional del ITA.
"""
from django.template.loader import render_to_string
from django.conf import settings
from administracion.models import ConfiguracionInstitucional
from xhtml2pdf import pisa
from io import BytesIO
import os


def link_callback(uri, rel):
    """
    Convierte URIs de Django (ej. /static/img/logo.png) a rutas de archivo locales
    para que xhtml2pdf pueda encontrarlas.
    """
    if os.path.isabs(uri):
        return uri
    
    sUrl = settings.STATIC_URL
    sRoot = settings.STATIC_ROOT
    mUrl = settings.MEDIA_URL
    mRoot = settings.MEDIA_ROOT
    
    if uri.startswith(mUrl):
        path = os.path.join(mRoot, uri.replace(mUrl, ""))
    elif uri.startswith(sUrl):
        path = os.path.join(sRoot, uri.replace(sUrl, "")) if sRoot else ""
        if not os.path.isfile(path) and hasattr(settings, 'STATICFILES_DIRS'):
            for d in settings.STATICFILES_DIRS:
                test_path = os.path.join(d, uri.replace(sUrl, ""))
                if os.path.isfile(test_path):
                    path = test_path
                    break
    else:
        path = uri
        
    return path


def generar_oficio_jurado_pdf(asignacion):
    """
    Recibe una instancia de AsignacionJurado y retorna los bytes del PDF.
    """
    expediente = asignacion.expediente
    alumno = expediente.alumno
    config = ConfiguracionInstitucional.objects.first()
    
    departamento_alumno = alumno.carrera.departamento if alumno.carrera else None
    jefe_depto = None
    if departamento_alumno and hasattr(departamento_alumno, 'jefe_asignado'):
        jefe_depto = departamento_alumno.jefe_asignado

    context = {
        'asignacion': asignacion,
        'expediente': expediente,
        'alumno': alumno,
        'presidente': asignacion.presidente,
        'secretario': asignacion.secretario,
        'vocal_propietario': asignacion.vocal_propietario,
        'vocal_suplente': asignacion.vocal_suplente,
        'lugar': getattr(settings, 'ITA_CIUDAD', 'Tzompantepec, Tlaxcala'),
        'config': config,
        'jefe_depto': jefe_depto,
    }

    html_string = render_to_string('administracion/jefe/oficio_jurado.html', context)

    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result, link_callback=link_callback)
    
    if not pdf.err:
        return result.getvalue()
    else:
        raise Exception("Error al generar PDF: " + str(pdf.err))
