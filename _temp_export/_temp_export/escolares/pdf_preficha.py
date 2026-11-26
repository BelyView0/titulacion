"""
Generación de Preficha de Pago en PDF.
"""
import os
from django.template.loader import render_to_string
from django.conf import settings
from xhtml2pdf import pisa
from io import BytesIO
from django.utils import timezone
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Registrar la fuente Noto Sans programáticamente con ruta relativa para evitar errores en Windows
try:
    font_path = os.path.relpath(os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSans-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Noto Sans', font_path))
except Exception:
    pass


def link_callback(uri, rel):
    r"""
    Resolvedor de recursos de xhtml2pdf.
    Convierte URIs (/static/...) a rutas relativas para evitar problemas
    con letras de unidad en Windows (C:\...) que reportlab interpreta como URLs.
    """
    sUrl = settings.STATIC_URL
    mUrl = settings.MEDIA_URL
    
    if uri.startswith(sUrl):
        relative_path = uri.replace(sUrl, "")
        for d in settings.STATICFILES_DIRS:
            test_path = os.path.join(d, relative_path)
            if os.path.isfile(test_path):
                return os.path.relpath(test_path)
    elif uri.startswith(mUrl):
        relative_path = uri.replace(mUrl, "")
        test_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        if os.path.isfile(test_path):
            return os.path.relpath(test_path)
            
    if os.path.isabs(uri):
        if os.path.isfile(uri):
            return os.path.relpath(uri)
        return uri
        
    return uri


def generar_preficha_pdf(expediente):
    """
    Recibe una instancia de Expediente y retorna los bytes del PDF
    de la Preficha de Pago.
    """
    alumno = expediente.alumno
    ahora = timezone.now()
    
    # Referencia format: A2201L + control_number + X
    # Example: A2201L21370856X
    control_number = alumno.numero_control or ""
    referencia = f"A2201L{control_number}X"
    
    context = {
        'expediente': expediente,
        'alumno': alumno,
        'fecha': ahora,
        'hora': ahora,
        'referencia': referencia,
        'STATIC_ROOT': settings.BASE_DIR / 'static',
    }

    html_string = render_to_string('escolares/pdf/preficha_pago.html', context)

    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result, link_callback=link_callback)
    
    if not pdf.err:
        return result.getvalue()
    else:
        raise Exception("Error al generar PDF de preficha: " + str(pdf.err))
