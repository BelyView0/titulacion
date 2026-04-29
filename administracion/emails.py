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

# ─── SISTEMA DE OTP (CONTRASEÑAS) ─────────────────────────────────────────────

def enviar_codigo_otp(user, codigo, context='reset'):
    """
    Envía el código de 6 dígitos al correo del usuario.
    context puede ser 'reset' (olvidé mi contraseña) o 'change' (cambio desde sesión).
    """
    subject = 'Tu código de seguridad de 6 dígitos'
    
    if context == 'reset':
        mensaje = f'Has solicitado restablecer tu contraseña. Tu código de seguridad es:\n\n{codigo}\n\nEste código expirará en 5 minutos.'
    else:
        mensaje = f'Has solicitado cambiar tu contraseña. Tu código de seguridad es:\n\n{codigo}\n\nEste código expirará en 5 minutos.'
        
    text_content = (
        f'Hola {user.get_full_name() or user.username},\n\n'
        f'{mensaje}\n\n'
        f'Si no solicitaste esto, ignora este mensaje y tu contraseña seguirá siendo la misma.\n\n'
        f'Atentamente,\nSistema de Titulación — ITA'
    )
    
    # Podríamos crear un template HTML aquí, pero para un código rápido el texto es funcional, o construimos el HTML directo
    html_content = f"""
    <div style="font-family: Arial, sans-serif; background-color: #f4f6f9; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="background-color: #003B73; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 20px;">Sistema de Titulación ITA</h1>
            </div>
            <div style="padding: 30px 20px; text-align: center;">
                <p style="font-size: 16px;">Hola <strong>{user.get_full_name() or user.username}</strong>,</p>
                <p style="font-size: 16px;">{mensaje.split('.')[0]}. Tu código de seguridad es:</p>
                
                <div style="margin: 30px 0;">
                    <span style="font-size: 36px; font-weight: bold; letter-spacing: 5px; color: #003B73; background: #f8f9fa; padding: 15px 25px; border-radius: 8px; border: 2px dashed #003B73;">
                        {codigo}
                    </span>
                </div>
                
                <p style="color: #dc3545; font-weight: bold;">⏱️ Este código expirará en 5 minutos.</p>
                <p style="color: #6c757d; font-size: 14px; margin-top: 30px;">Si no solicitaste este cambio, puedes ignorar este correo. Tu cuenta está segura.</p>
            </div>
        </div>
    </div>
    """

    email = EmailMultiAlternatives(
        subject=f'[ITA] Código de Seguridad: {codigo}',
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, 'text/html')

    try:
        email.send(fail_silently=True)
    except Exception as e:
        print(f'[EMAIL] Error enviando código OTP a {user.email}: {e}')

def enviar_alerta_cambio_password(user):
    """
    Envía una notificación de seguridad después de un cambio de contraseña exitoso.
    """
    text_content = (
        f'Hola {user.get_full_name() or user.username},\n\n'
        f'Te confirmamos que tu contraseña ha sido modificada exitosamente.\n\n'
        f'Si no realizaste este cambio, por favor contacta al administrador del sistema inmediatamente.\n\n'
        f'Atentamente,\nSistema de Titulación — ITA'
    )
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; background-color: #f4f6f9; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="background-color: #198754; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 20px;">🛡️ Alerta de Seguridad</h1>
            </div>
            <div style="padding: 30px 20px; text-align: center;">
                <p style="font-size: 16px;">Hola <strong>{user.get_full_name() or user.username}</strong>,</p>
                <p style="font-size: 16px; color: #198754; font-weight: bold;">Tu contraseña ha sido modificada exitosamente.</p>
                
                <p style="color: #6c757d; font-size: 14px; margin-top: 30px;">
                    Si tú realizaste este cambio, no es necesario hacer nada más.<br><br>
                    <strong>Si no fuiste tú</strong>, por favor contacta al administrador del sistema de inmediato.
                </p>
            </div>
        </div>
    </div>
    """

    email = EmailMultiAlternatives(
        subject='[ITA] Tu contraseña ha sido modificada',
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, 'text/html')

    try:
        email.send(fail_silently=True)
    except Exception as e:
        print(f'[EMAIL] Error enviando alerta de cambio de contraseña a {user.email}: {e}')
