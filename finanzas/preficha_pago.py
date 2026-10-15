"""Generación de preficha de depósito para pago de titulación."""
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from administracion.models import ConfiguracionInstitucional
from administracion.pdf_oficio import link_callback

CONCEPTO_LICENCIATURA = 'TRÁMITE DE TITULACIÓN NIVEL LICENCIATURA'


def numero_control_alumno(alumno):
    return alumno.numero_control or alumno.username


def generar_referencia_bancaria(alumno):
    return f'A2201L{numero_control_alumno(alumno)}X'


def concepto_pago_expediente(expediente):
    return CONCEPTO_LICENCIATURA


def monto_default_pago():
    return Decimal(getattr(settings, 'PAGO_TITULACION_MONTO_DEFAULT', '2700.00'))


def formato_monto(monto):
    return f'${monto:,.2f}'


def formato_hora_preficha(fecha_dt):
    hora = fecha_dt.hour % 12 or 12
    minutos = fecha_dt.strftime('%M')
    sufijo = 'a. m.' if fecha_dt.hour < 12 else 'p. m.'
    return f'{hora}:{minutos} {sufijo}'


def _contexto_preficha(referencia):
    expediente = referencia.expediente
    alumno = expediente.alumno
    config = ConfiguracionInstitucional.objects.first()
    fecha_gen = timezone.localtime(referencia.fecha_generacion)

    return {
        'referencia': referencia,
        'expediente': expediente,
        'alumno': alumno,
        'config': config,
        'fecha_pago': fecha_gen,
        'hora_pago': formato_hora_preficha(fecha_gen),
        'monto_formateado': formato_monto(referencia.monto),
        'banco': getattr(settings, 'PAGO_TITULACION_BANCO', 'BANAMEX'),
        'sucursal': getattr(settings, 'PAGO_TITULACION_SUCURSAL', '0648'),
        'cuenta': getattr(settings, 'PAGO_TITULACION_CUENTA', '6530500'),
        'numero_control': numero_control_alumno(alumno),
        'concepto': referencia.concepto,
        'referencia_bancaria': referencia.referencia_bancaria,
        'nombre_alumno': alumno.get_full_name().upper(),
    }


def generar_preficha_pago_pdf(referencia):
    html_string = render_to_string(
        'finanzas/pdf/preficha_deposito.html',
        _contexto_preficha(referencia),
    )
    result = BytesIO()
    pdf = pisa.pisaDocument(
        BytesIO(html_string.encode('UTF-8')),
        result,
        link_callback=link_callback,
    )
    if pdf.err:
        raise Exception('Error al generar preficha de pago: ' + str(pdf.err))
    return result.getvalue()


def guardar_preficha_pdf(referencia):
    pdf_bytes = generar_preficha_pago_pdf(referencia)
    nombre = f'preficha_{referencia.referencia_bancaria}.pdf'
    referencia.pdf_referencia.save(nombre, ContentFile(pdf_bytes), save=True)
