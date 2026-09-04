"""Generación de PDFs — Oficina de Titulación."""
from io import BytesIO

from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from administracion.pdf_oficio import link_callback


MESES_ES = (
    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
)


def _html_to_pdf(html):
    result = BytesIO()
    pdf = pisa.pisaDocument(
        BytesIO(html.encode('UTF-8')),
        result,
        link_callback=link_callback,
    )
    if pdf.err or not result.getvalue():
        return None
    return ContentFile(result.getvalue())


def _numero_a_texto(n):
    unidades = {
        1: 'un', 2: 'dos', 3: 'tres', 4: 'cuatro', 5: 'cinco',
        6: 'seis', 7: 'siete', 8: 'ocho', 9: 'nueve', 10: 'diez',
        11: 'once', 12: 'doce', 13: 'trece', 14: 'catorce', 15: 'quince',
        16: 'dieciséis', 17: 'diecisiete', 18: 'dieciocho', 19: 'diecinueve',
        20: 'veinte', 21: 'veintiún', 22: 'veintidós', 23: 'veintitrés',
        24: 'veinticuatro', 25: 'veinticinco', 26: 'veintiséis',
        27: 'veintisiete', 28: 'veintiocho', 29: 'veintinueve', 30: 'treinta',
        31: 'treinta y un',
    }
    return unidades.get(n, str(n))


def _datos_jefe_escolares(config):
    from administracion.models import ContactoArea

    nombre = (config.jefe_escolares_nombre if config else '') or ''
    cargo = (
        (config.jefe_escolares_cargo if config else '')
        or 'Jefe del Departamento de Servicios Escolares'
    )
    if not nombre:
        contacto = ContactoArea.servicios_escolares()
        if contacto:
            nombre = contacto.nombre_responsable
    if not nombre:
        nombre = 'Martín Rojas Ramírez'
    return nombre, cargo


def _recortar_bordes_blancos(ruta_imagen):
    """
    Recorta márgenes blancos/transparentes de una imagen institucional.
    Devuelve ruta a un PNG temporal (o la original si no hay nada que recortar).
    """
    import os
    import tempfile

    from PIL import Image, ImageChops

    if not ruta_imagen or not os.path.isfile(ruta_imagen):
        return None

    im = Image.open(ruta_imagen)
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        rgba = im.convert('RGBA')
        fondo = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        im = Image.alpha_composite(fondo, rgba).convert('RGB')
    else:
        im = im.convert('RGB')

    bg = Image.new('RGB', im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg)
    # Sensibilidad a blancos casi puros
    diff = ImageChops.add(diff, diff, 2.0, -25)
    bbox = diff.getbbox()
    if bbox:
        im = im.crop(bbox)

    fd, tmp_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    im.save(tmp_path, format='PNG', optimize=True)
    return tmp_path


def _preparar_pie_ancho_pagina(ruta_imagen, ancho_pt=584):
    """
    Recorta blancos y redimensiona el pie al ancho exacto de la hoja (pt≈px a 72dpi)
    para que xhtml2pdf lo dibuje de lado a lado sin depender de width CSS.
    """
    import os
    import tempfile

    from PIL import Image

    ruta = _recortar_bordes_blancos(ruta_imagen)
    if not ruta:
        return None, None

    im = Image.open(ruta).convert('RGB')
    w, h = im.size
    if w <= 0:
        return ruta, None

    nuevo_alto = max(1, int(round(ancho_pt * h / float(w))))
    im = im.resize((int(ancho_pt), nuevo_alto), Image.Resampling.LANCZOS)

    fd, tmp_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    im.save(tmp_path, format='PNG', dpi=(72, 72), optimize=True)

    if ruta != ruta_imagen:
        try:
            os.unlink(ruta)
        except OSError:
            pass

    return tmp_path, nuevo_alto


def generar_constancia_no_inconveniencia_pdf(expediente):
    """Genera PDF de constancia de no inconveniencia (formato Servicios Escolares)."""
    import os

    from administracion.models import ConfiguracionInstitucional

    alumno = expediente.alumno
    config = ConfiguracionInstitucional.objects.first()
    ahora = timezone.localtime(timezone.now())
    jefe_nombre, jefe_cargo = _datos_jefe_escolares(config)

    # Un poco más grande, centrado respecto al texto
    ANCHO_PIE_PT = 530

    temps = []
    try:
        encabezado_path = None
        pie_path = None
        pie_alto = None
        if config and config.imagen_encabezado:
            encabezado_path = config.imagen_encabezado.path
        if config and config.imagen_pie_pagina:
            pie_path, pie_alto = _preparar_pie_ancho_pagina(
                config.imagen_pie_pagina.path, ancho_pt=ANCHO_PIE_PT,
            )
            if pie_path:
                temps.append(pie_path)

        html = render_to_string(
            'oficina_titulacion/pdf/constancia_no_inconveniencia.html',
            {
                'expediente': expediente,
                'alumno': alumno,
                'config': config,
                'fecha_corta': ahora.strftime('%d/%m/%Y').lstrip('0').replace('/0', '/'),
                'jefe_nombre': jefe_nombre.upper(),
                'jefe_cargo': jefe_cargo.upper(),
                'encabezado_path': encabezado_path,
                'pie_path': pie_path,
                'pie_ancho': ANCHO_PIE_PT,
                'pie_alto': pie_alto or 80,
            },
        )
        return _html_to_pdf(html)
    finally:
        for ruta in temps:
            try:
                os.unlink(ruta)
            except OSError:
                pass


# Alias usado por vistas legacy
generar_constancia_pdf = generar_constancia_no_inconveniencia_pdf


def generar_constancia_no_adeudos_pdf(expediente):
    """Genera PDF de constancia de no adeudos con firmas de las 3 áreas."""
    import os

    from administracion.models import ConfiguracionInstitucional, ContactoArea

    config = ConfiguracionInstitucional.objects.first()
    ahora = timezone.localtime(timezone.now())

    areas_orden = [
        (ContactoArea.Area.FINANZAS, 'RECURSOS FINANCIEROS'),
        (ContactoArea.Area.CENTRO_INFORMACION, 'CENTRO DE INFORMACIÓN'),
        (ContactoArea.Area.CENTRO_COMPUTO, 'LABORATORIO DE CÓMPUTO'),
    ]
    contactos = {c.area: c for c in ContactoArea.areas_adeudo()}
    firmas = []
    for codigo, etiqueta in areas_orden:
        contacto = contactos.get(codigo)
        firmas.append({
            'area': etiqueta,
            'responsable': (
                contacto.nombre_responsable if contacto
                else '________________________'
            ),
        })

    ANCHO_PIE_PT = 530
    temps = []
    try:
        encabezado_path = None
        pie_path = None
        pie_alto = None
        if config and config.imagen_encabezado:
            encabezado_path = config.imagen_encabezado.path
        if config and config.imagen_pie_pagina:
            pie_path, pie_alto = _preparar_pie_ancho_pagina(
                config.imagen_pie_pagina.path, ancho_pt=ANCHO_PIE_PT,
            )
            if pie_path:
                temps.append(pie_path)

        html = render_to_string(
            'oficina_titulacion/pdf/constancia_no_adeudos.html',
            {
                'expediente': expediente,
                'config': config,
                'alumno': expediente.alumno,
                'firmas': firmas,
                'dia_texto': _numero_a_texto(ahora.day),
                'mes_texto': MESES_ES[ahora.month],
                'anio': ahora.year,
                'encabezado_path': encabezado_path,
                'pie_path': pie_path,
                'pie_ancho': ANCHO_PIE_PT,
                'pie_alto': pie_alto or 80,
            },
        )
        return _html_to_pdf(html)
    finally:
        for ruta in temps:
            try:
                os.unlink(ruta)
            except OSError:
                pass


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
