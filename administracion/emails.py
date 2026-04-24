"""
Envío de correos electrónicos para el módulo de jurado.
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .pdf_oficio import generar_oficio_jurado_pdf


def enviar_notificacion_jurado(asignacion):
    """
    Envía correo al alumno y a cada miembro del jurado confirmando el acto protocolario.
    El correo a los profesores incluye el PDF del oficio adjunto.
    """
    expediente = asignacion.expediente
    alumno = expediente.alumno

    # Generar PDF
    try:
        pdf_bytes = generar_oficio_jurado_pdf(asignacion)
        pdf_disponible = True
    except Exception as e:
        print(f'[EMAIL] No se pudo generar PDF: {e}')
        pdf_disponible = False

    nombre_pdf = f'Oficio_Jurado_{alumno.last_name}_{alumno.first_name}.pdf'

    context = {
        'asignacion': asignacion,
        'expediente': expediente,
        'alumno': alumno,
    }

    # ── Correo a cada miembro del jurado ──────────────────────────
    miembros = [
        (asignacion.presidente, 'Presidente'),
        (asignacion.secretario, 'Secretario/a'),
        (asignacion.vocal_propietario, 'Vocal Propietario/a') if asignacion.vocal_propietario else None,
        (asignacion.vocal_suplente, 'Vocal Suplente') if asignacion.vocal_suplente else None,
    ]

    for item in miembros:
        if not item:
            continue
        profesor, rol = item
        if not profesor.email:
            continue

        ctx_prof = {**context, 'profesor': profesor, 'rol_jurado': rol}
        html_content = render_to_string('emails/notificacion_jurado_profesor.html', ctx_prof)
        text_content = (
            f'Estimado/a {profesor.get_full_name()},\n\n'
            f'Ha sido designado/a como {rol} del jurado para el examen profesional '
            f'de {alumno.get_full_name()}.\n\n'
            f'Fecha: {asignacion.fecha_acto.strftime("%d de %B de %Y a las %H:%M hrs") if asignacion.fecha_acto else "Por confirmar"}\n'
            f'Lugar: {asignacion.lugar_acto or "Por confirmar"}\n\n'
            f'Adjunto encontrará el oficio oficial de designación.\n\n'
            f'Atentamente,\nSistema de Titulación — ITA'
        )

        email = EmailMultiAlternatives(
            subject=f'Designación como {rol} de Jurado — {alumno.get_full_name()}',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[profesor.email],
        )
        email.attach_alternative(html_content, 'text/html')

        if pdf_disponible:
            email.attach(nombre_pdf, pdf_bytes, 'application/pdf')

        try:
            email.send(fail_silently=True)
        except Exception as e:
            print(f'[EMAIL] Error enviando a {profesor.email}: {e}')

    # ── Correo al alumno ──────────────────────────────────────────
    if alumno.email:
        ctx_alumno = {**context}
        html_alumno = render_to_string('emails/notificacion_jurado_alumno.html', ctx_alumno)
        text_alumno = (
            f'Estimado/a {alumno.get_full_name()},\n\n'
            f'Se ha asignado el jurado para tu acto protocolario de titulación.\n\n'
            f'Presidente: {asignacion.presidente.get_full_name()}\n'
            f'Secretario/a: {asignacion.secretario.get_full_name()}\n'
        )
        if asignacion.vocal_propietario:
            text_alumno += f'Vocal Propietario/a: {asignacion.vocal_propietario.get_full_name()}\n'
        if asignacion.vocal_suplente:
            text_alumno += f'Vocal Suplente: {asignacion.vocal_suplente.get_full_name()}\n'
        text_alumno += (
            f'\nFecha: {asignacion.fecha_acto.strftime("%d de %B de %Y a las %H:%M hrs") if asignacion.fecha_acto else "Por confirmar"}\n'
            f'Lugar: {asignacion.lugar_acto or "Por confirmar"}\n\n'
            f'Atentamente,\nSistema de Titulación — ITA'
        )

        email_alumno = EmailMultiAlternatives(
            subject='Jurado asignado para tu examen profesional',
            body=text_alumno,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[alumno.email],
        )
        email_alumno.attach_alternative(html_alumno, 'text/html')

        try:
            email_alumno.send(fail_silently=True)
        except Exception as e:
            print(f'[EMAIL] Error enviando al alumno: {e}')
