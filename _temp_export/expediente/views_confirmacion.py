"""
Vista pública para confirmar asistencia al acto protocolario via token.
No requiere autenticación — el token es la autenticación.

Flujo:
1. Al confirmar → envía correo de "confirmación recibida" al participante
2. Si con esta confirmación se completan todas → envía correo final a TODOS
   con jurado completo y datos definitivos
"""
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from expediente.models import ConfirmacionActo


def confirmar_asistencia(request, token):
    """
    GET /confirmar/<token>/
    Confirma la asistencia de un participante al acto protocolario.
    """
    confirmacion = get_object_or_404(ConfirmacionActo, token=token)
    acto = confirmacion.acto
    ya_confirmado = confirmacion.confirmado
    expirado = acto.fecha_acto < timezone.now()
    recien_confirmado = False

    from datetime import timedelta
    
    # Validar deadline de 24 hrs para el alumno
    deadline_pasada = False
    if confirmacion.rol == 'ALUMNO' and not ya_confirmado:
        if timezone.now() > acto.fecha_acto - timedelta(days=1):
            deadline_pasada = True

    if not ya_confirmado and not expirado and not deadline_pasada:
        confirmacion.confirmado = True
        confirmacion.fecha_confirmacion = timezone.now()
        confirmacion.save()
        recien_confirmado = True

        # Enviar correo de "confirmación recibida"
        _enviar_correo_confirmacion_recibida(confirmacion, acto)

        # Si el alumno acaba de confirmar a tiempo, enviar las invitaciones al jurado
        if confirmacion.rol == 'ALUMNO':
            _enviar_correos_invitacion_jurado(acto, request)

        # Verificar si con esto ya se completaron todas
        if acto.confirmaciones_completas():
            _enviar_correo_acto_confirmado(acto)

    # Obtener estado de todas las confirmaciones
    todas = acto.confirmaciones.all().order_by('rol')

    context = {
        'confirmacion': confirmacion,
        'acto': acto,
        'ya_confirmado': ya_confirmado,
        'recien_confirmado': recien_confirmado,
        'expirado': expirado,
        'deadline_pasada': deadline_pasada,
        'todas': todas,
        'completas': acto.confirmaciones_completas(),
    }
    return render(request, 'confirmacion/confirmar.html', context)


def _enviar_correos_invitacion_jurado(acto, request):
    """Envía los correos iniciales de invitación al Jurado una vez que el alumno ha confirmado."""
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings
    
    expediente = acto.expediente
    fecha_fmt = acto.fecha_acto.strftime('%d de %B de %Y a las %H:%M')
    base_url = request.build_absolute_uri('/')[:-1]
    
    for conf in acto.confirmaciones.exclude(rol='ALUMNO').filter(confirmado=False):
        if not conf.email:
            continue
            
        nombre = conf.nombre_participante
        confirm_url = f'{base_url}/confirmar/{conf.token}/'
        rol_display = conf.get_rol_display()

        intro_html = (
            f'<p style="font-size:14px;color:#555;">Se le invita a participar como '
            f'<strong style="color:#0057B8;">{rol_display}</strong> en el acto de '
            f'recepci&oacute;n profesional del alumno(a):</p>'
        )
        alumno_row = (
            f'<tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Alumno(a)</td>'
            f'<td style="padding:6px 12px;font-size:14px;font-weight:700;">{expediente.alumno.get_full_name()}</td></tr>'
        )

        from django.template.loader import render_to_string
        html_content = render_to_string('emails/notificacion_generica.html', {
            'titulo': 'Invitación a Acto Protocolario',
            'saludo': f'Estimado(a) {nombre},',
            'mensaje': f'Se le invita a participar como {rol_display} en el acto de recepción profesional del alumno(a) {expediente.alumno.get_full_name()}.\n\nPor favor comuníquese con el Jefe de Departamento correspondiente para confirmar su asistencia.',
            'datos_adicionales': {
                'Alumno(a)': expediente.alumno.get_full_name(),
                'Carrera': expediente.alumno.carrera.nombre if expediente.alumno.carrera else '—',
                'Título del trabajo': expediente.titulo_trabajo or '—',
                'Fecha y lugar probable': f'{fecha_fmt} en {acto.lugar}'
            }
        })

        text_body = (
            f'Estimado(a) {nombre},\n\n'
            f'Se le invita como {rol_display} al acto protocolario.\n'
            f'Alumno: {expediente.alumno.get_full_name()}\n'
            f'Fecha probable: {fecha_fmt}\nLugar: {acto.lugar}\n\n'
            f'Comuníquese con el Jefe de Departamento para confirmar su asistencia.\n\n'
            f'Instituto Tecnológico de Apizaco — TecNM'
        )

        try:
            msg = EmailMultiAlternatives(
                subject=f'[ITA Titulación] Invitación a Acto Protocolario',
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[conf.email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)
        except Exception:
            pass


def _enviar_correo_confirmacion_recibida(confirmacion, acto):
    """Envía correo individual al participante confirmando que su asistencia fue registrada."""
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    nombre = confirmacion.nombre_participante
    rol_display = confirmacion.get_rol_display()
    alumno = acto.expediente.alumno.get_full_name()
    fecha_fmt = acto.fecha_acto.strftime('%d/%m/%Y a las %H:%M')

    # Texto diferente para alumno vs jurado
    if confirmacion.rol == 'ALUMNO':
        parrafo_intro = (
            '<p style="font-size:14px;color:#555;">Su asistencia al acto de '
            'recepci&oacute;n profesional ha sido registrada exitosamente.</p>'
        )
        alumno_row = ''
    else:
        parrafo_intro = (
            f'<p style="font-size:14px;color:#555;">Su asistencia como '
            f'<strong style="color:#16a34a;">{rol_display}</strong> '
            f'al acto protocolario ha sido registrada exitosamente.</p>'
        )
        alumno_row = (
            f'<tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Alumno(a)</td>'
            f'<td style="padding:6px 12px;font-size:14px;font-weight:700;">{alumno}</td></tr>'
        )

    from django.template.loader import render_to_string
    if confirmacion.rol == 'ALUMNO':
        mensaje = 'Su asistencia al acto de recepción profesional ha sido registrada exitosamente.\n\nUna vez que todos los participantes confirmen, recibirá un correo con los detalles completos del jurado asignado y la confirmación definitiva.'
    else:
        mensaje = f'Su asistencia como {rol_display} al acto protocolario ha sido registrada exitosamente.\n\nUna vez que todos los participantes confirmen, recibirá un correo con los detalles completos del jurado asignado y la confirmación definitiva.'
    
    html_content = render_to_string('emails/notificacion_generica.html', {
        'titulo': 'Asistencia Confirmada',
        'saludo': f'Estimado(a) {nombre},',
        'mensaje': mensaje,
        'datos_adicionales': {
            'Alumno(a)': alumno if confirmacion.rol != 'ALUMNO' else '',
            'Fecha probable': fecha_fmt,
            'Lugar': acto.lugar
        }
    })

    if confirmacion.rol == 'ALUMNO':
        text_body = (
            f'Estimado(a) {nombre},\n\n'
            f'Su asistencia al acto de recepción profesional ha sido confirmada.\n\n'
            f'Fecha: {fecha_fmt}\nLugar: {acto.lugar}\n\n'
            f'Recibirá un correo con los detalles completos cuando todos confirmen.\n\n'
            f'Instituto Tecnológico de Apizaco — TecNM'
        )
    else:
        text_body = (
            f'Estimado(a) {nombre},\n\n'
            f'Su asistencia como {rol_display} al acto protocolario del alumno(a) '
            f'{alumno} ha sido confirmada exitosamente.\n\n'
            f'Fecha: {fecha_fmt}\nLugar: {acto.lugar}\n\n'
            f'Recibirá un correo con los detalles completos cuando todos confirmen.\n\n'
            f'Instituto Tecnológico de Apizaco — TecNM'
        )

    try:
        msg = EmailMultiAlternatives(
            subject='[ITA Titulación] Asistencia Confirmada',
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[confirmacion.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception:
        pass


def _enviar_correo_acto_confirmado(acto):
    """
    Envía correo a TODOS los participantes cuando se completan las confirmaciones.
    Este correo SÍ incluye el jurado completo y la fecha/lugar definitivos.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    expediente = acto.expediente
    jurado_asig = acto.jurado
    alumno = expediente.alumno
    fecha_fmt = acto.fecha_acto.strftime('%d/%m/%Y a las %H:%M')

    # Determinar vocal activo (propietario o suplente)
    vocal_conf = acto.get_vocal_confirmado()
    vocal_activo = None
    vocal_label = 'Vocal'
    if vocal_conf:
        if vocal_conf.rol == 'VOCAL_PROPIETARIO' and jurado_asig.vocal_propietario:
            vocal_activo = jurado_asig.vocal_propietario
            vocal_label = 'Vocal Propietario/a'
        elif vocal_conf.rol == 'VOCAL_SUPLENTE' and jurado_asig.vocal_suplente:
            vocal_activo = jurado_asig.vocal_suplente
            vocal_label = 'Vocal Suplente'

    # Construir tabla de jurado
    jurado_rows = ''
    for label, prof in [
        ('Presidente', jurado_asig.presidente),
        ('Secretario/a', jurado_asig.secretario),
        (vocal_label, vocal_activo),
    ]:
        if prof:
            jurado_rows += (
                f'<tr><td style="padding:8px 12px;font-weight:700;color:#6c757d;font-size:13px;'
                f'border-bottom:1px solid #eee;">{label}</td>'
                f'<td style="padding:8px 12px;font-size:14px;font-weight:600;'
                f'border-bottom:1px solid #eee;">{prof.get_nombre_corto()}</td></tr>'
            )

    # Enviar a todos los confirmados
    for conf_dest in acto.confirmaciones.filter(confirmado=True):
        if not conf_dest.email:
            continue
        nombre_dest = conf_dest.nombre_participante

        # Texto de imprevisto diferente para alumno vs jurado
        if conf_dest.rol == 'ALUMNO':
            nota_imprevisto = (
                'En caso de cualquier imprevisto, favor de notificar al '
                '<strong>Jefe de Departamento de su carrera</strong>.'
            )
        else:
            nota_imprevisto = (
                'En caso de cualquier imprevisto, favor de notificar al '
                '<strong>Jefe de Departamento</strong> correspondiente.'
            )

        from django.template.loader import render_to_string
        mensaje_general = f'Le informamos que todos los participantes han confirmado su asistencia. El acto protocolario se llevará a cabo según lo programado.\n\nSe solicita puntual asistencia.\n{nota_imprevisto}'
        
        datos = {
            'Alumno(a)': alumno.get_full_name(),
            'Carrera': alumno.carrera.nombre if alumno.carrera else '—',
            'Modalidad': expediente.modalidad.nombre if expediente.modalidad else '—',
            'Título del trabajo': expediente.titulo_trabajo or '—',
            'Fecha confirmada': fecha_fmt,
            'Lugar confirmado': acto.lugar,
            'Presidente': jurado_asig.presidente.get_nombre_corto() if jurado_asig.presidente else '',
            'Secretario/a': jurado_asig.secretario.get_nombre_corto() if jurado_asig.secretario else '',
        }
        if vocal_activo:
            datos[vocal_label] = vocal_activo.get_nombre_corto()

        html_content = render_to_string('emails/notificacion_generica.html', {
            'titulo': 'Acto Protocolario Confirmado',
            'saludo': f'Estimado(a) {nombre_dest},',
            'mensaje': mensaje_general,
            'datos_adicionales': datos
        })

        text_body = (
            f'Estimado(a) {nombre_dest},\n\n'
            f'Todos los participantes han confirmado su asistencia al acto protocolario.\n\n'
            f'Alumno: {alumno.get_full_name()}\n'
            f'Fecha confirmada: {fecha_fmt}\n'
            f'Lugar: {acto.lugar}\n\n'
            f'Jurado:\n'
            f'  Presidente: {jurado_asig.presidente.get_nombre_corto()}\n'
            f'  Secretario/a: {jurado_asig.secretario.get_nombre_corto()}\n'
        )
        if vocal_activo:
            text_body += f'  {vocal_label}: {vocal_activo.get_nombre_corto()}\n'
        text_body += f'\nInstituto Tecnológico de Apizaco — TecNM'

        try:
            msg = EmailMultiAlternatives(
                subject=f'[ITA Titulación] Acto Protocolario Confirmado — {alumno.get_full_name()}',
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[conf_dest.email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)
        except Exception:
            pass
