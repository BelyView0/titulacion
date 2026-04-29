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

    if not ya_confirmado and not expirado:
        confirmacion.confirmado = True
        confirmacion.fecha_confirmacion = timezone.now()
        confirmacion.save()
        recien_confirmado = True

        # Enviar correo de "confirmación recibida"
        _enviar_correo_confirmacion_recibida(confirmacion, acto)

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
        'todas': todas,
        'completas': acto.confirmaciones_completas(),
    }
    return render(request, 'confirmacion/confirmar.html', context)


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

    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f8;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:linear-gradient(135deg,#16a34a,#15803d);border-radius:12px 12px 0 0;padding:30px;text-align:center;">
    <div style="font-size:42px;color:#fff;">&#10004;</div>
    <h2 style="color:#fff;margin:10px 0 5px;font-size:20px;">Asistencia Confirmada</h2>
    <p style="color:rgba(255,255,255,.8);margin:0;font-size:13px;">Instituto Tecnol&oacute;gico de Apizaco &mdash; TecNM</p>
  </div>
  <div style="background:#fff;padding:30px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,.08);">
    <p style="font-size:15px;color:#333;">Estimado(a) <strong>{nombre}</strong>,</p>
    {parrafo_intro}

    <div style="background:#f0fdf4;border-radius:8px;padding:16px;margin:20px 0;border-left:4px solid #16a34a;">
      <table style="width:100%;border-collapse:collapse;">
        {alumno_row}
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Fecha probable</td>
            <td style="padding:6px 12px;font-size:14px;">{fecha_fmt}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Lugar</td>
            <td style="padding:6px 12px;font-size:14px;">{acto.lugar}</td></tr>
      </table>
    </div>

    <div style="background:#f8f9fa;border-radius:8px;padding:14px;margin:20px 0;text-align:center;">
      <p style="font-size:13px;color:#555;margin:0;">
        Una vez que todos los participantes confirmen, recibir&aacute; un correo con los
        <strong>detalles completos del jurado asignado</strong> y la confirmaci&oacute;n definitiva.
      </p>
    </div>
  </div>
  <p style="text-align:center;font-size:11px;color:#999;margin-top:16px;">
    Sistema de Gesti&oacute;n de Titulaci&oacute;n &mdash; TecNM / Instituto Tecnol&oacute;gico de Apizaco
  </p>
</div>
</body></html>"""

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
        msg.attach_alternative(html_body, "text/html")
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

        html_body = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f8;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:linear-gradient(135deg,#7c3aed,#5b21b6);border-radius:12px 12px 0 0;padding:30px;text-align:center;">
    <div style="font-size:42px;color:#fff;">&#x1F393;</div>
    <h2 style="color:#fff;margin:10px 0 5px;font-size:20px;">Acto Protocolario Confirmado</h2>
    <p style="color:rgba(255,255,255,.8);margin:0;font-size:13px;">Todas las asistencias han sido confirmadas</p>
  </div>
  <div style="background:#fff;padding:30px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,.08);">
    <p style="font-size:15px;color:#333;">Estimado(a) <strong>{nombre_dest}</strong>,</p>
    <p style="font-size:14px;color:#555;">Le informamos que <strong style="color:#16a34a;">todos los participantes han confirmado
       su asistencia</strong>. El acto protocolario se llevar&aacute; a cabo seg&uacute;n lo programado.</p>

    <div style="background:#f8f9fa;border-radius:8px;padding:16px;margin:20px 0;border-left:4px solid #7c3aed;">
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Alumno(a)</td>
            <td style="padding:6px 12px;font-size:14px;font-weight:700;">{alumno.get_full_name()}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Carrera</td>
            <td style="padding:6px 12px;font-size:14px;">{alumno.carrera or '&mdash;'}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Modalidad</td>
            <td style="padding:6px 12px;font-size:14px;">{expediente.modalidad or '&mdash;'}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">T&iacute;tulo del trabajo</td>
            <td style="padding:6px 12px;font-size:14px;">{expediente.titulo_trabajo or '&mdash;'}</td></tr>
      </table>
    </div>

    <div style="background:linear-gradient(135deg,#f0fdf4,#dcfce7);border-radius:8px;padding:20px;margin:20px 0;text-align:center;">
      <div style="font-size:12px;color:#16a34a;font-weight:700;text-transform:uppercase;letter-spacing:1px;">&#10004; Fecha y lugar confirmados</div>
      <div style="font-size:22px;font-weight:700;color:#15803d;margin:8px 0;">{fecha_fmt}</div>
      <div style="font-size:15px;color:#333;font-weight:600;">&#128205; {acto.lugar}</div>
    </div>

    <div style="background:#f8f9fa;border-radius:8px;padding:16px;margin:20px 0;">
      <div style="font-size:13px;font-weight:700;color:#7c3aed;margin-bottom:10px;text-transform:uppercase;letter-spacing:1px;">
        &#128101; Jurado Asignado
      </div>
      <table style="width:100%;border-collapse:collapse;">{jurado_rows}</table>
    </div>

    <div style="background:#dbeafe;border-radius:8px;padding:14px 16px;font-size:13px;color:#1e40af;text-align:center;">
      <strong>Se solicita puntual asistencia.</strong><br>
      {nota_imprevisto}
    </div>
  </div>
  <p style="text-align:center;font-size:11px;color:#999;margin-top:16px;">
    Sistema de Gesti&oacute;n de Titulaci&oacute;n &mdash; TecNM / Instituto Tecnol&oacute;gico de Apizaco
  </p>
</div>
</body></html>"""

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
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=True)
        except Exception:
            pass
