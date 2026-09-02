"""
Sistema de notificaciones del sistema.
- Notificaciones internas (Notificacion model)
- Notificaciones por correo institucional
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone


def notificar_alumno(expediente, tipo, titulo, mensaje, url=''):
    """
    Crea una notificación interna al alumno Y envía correo institucional.

    Args:
        expediente: instancia de Expediente
        tipo: uno de [INFO, APROBADO, RECHAZADO, CORRECCION, AVANCE, URGENTE]
        titulo: str - Asunto/título de la notificación
        mensaje: str - Cuerpo del mensaje
        url: str - URL relacionada (opcional)
    """
    from alumnos.models import Notificacion

    alumno = expediente.alumno

    # 1 — Notificación interna
    notif = Notificacion.objects.create(
        destinatario=alumno,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
        url_relacionada=url,
    )

    # 2 — Correo electrónico al correo institucional
    _enviar_correo_alumno(alumno, expediente, titulo, mensaje)

    return notif


def notificar_oficina_titulacion(expediente, titulo, mensaje, url='', tipo='INFO'):
    """Notifica a usuarios de Oficina de Titulación (incluye roles legados)."""
    from administracion.models import Usuario, roles_oficina_titulacion
    from alumnos.models import Notificacion

    usuarios = Usuario.objects.filter(rol__in=roles_oficina_titulacion(), is_active=True)
    creadas = []
    for u in usuarios:
        creadas.append(Notificacion.objects.create(
            destinatario=u, tipo=tipo, titulo=titulo, mensaje=mensaje, url_relacionada=url,
        ))
    return creadas


def notificar_usuarios_division(expediente, titulo, mensaje, url=''):
    return notificar_oficina_titulacion(expediente, titulo, mensaje, url)


def notificar_usuarios_escolares(expediente, titulo, mensaje, url=''):
    return notificar_oficina_titulacion(expediente, titulo, mensaje, url, tipo='URGENTE')


def notificar_usuarios_por_rol(roles, titulo, mensaje, url='', tipo='INFO'):
    from administracion.models import Usuario
    from alumnos.models import Notificacion
    usuarios = Usuario.objects.filter(rol__in=roles, is_active=True)
    return [
        Notificacion.objects.create(
            destinatario=u, tipo=tipo, titulo=titulo, mensaje=mensaje, url_relacionada=url,
        )
        for u in usuarios
    ]


def _enviar_correo_alumno(alumno, expediente, titulo, mensaje):
    correos_destino = set()
    
    # 1. Correo institucional (Siempre debería enviarse si existe, porque es el obligatorio)
    if alumno.correo_institucional:
        correos_destino.add(alumno.correo_institucional)
        
    # 2. Correo personal (Opcional, solo si el usuario lo verificó para recibir copias)
    if getattr(alumno, 'email_verificado', False) and alumno.email:
        correos_destino.add(alumno.email)

    correos_destino = list(correos_destino)
    if not correos_destino:
        return  # sin correos configurados, no enviar

    cuerpo = f"""
Estimado(a) {alumno.get_full_name()},

{mensaje}

---
Expediente: {expediente}
Matrícula: {getattr(getattr(alumno, 'perfil_alumno', None), 'numero_control', 'N/A')}
Fecha: {timezone.now().strftime('%d/%m/%Y %H:%M')}

Este mensaje fue generado automáticamente por el Sistema de Gestión de Titulación
del Instituto Tecnológico de Apizaco.

Por favor no responda a este correo.
    """.strip()

    html_content = render_to_string('emails/notificacion_generica.html', {
        'titulo': titulo,
        'saludo': f'Estimado(a) {alumno.get_full_name()},',
        'mensaje': mensaje,
        'datos_adicionales': {
            'Expediente': str(expediente),
            'Matrícula': getattr(getattr(alumno, 'perfil_alumno', None), 'numero_control', 'N/A'),
            'Fecha': timezone.now().strftime('%d/%m/%Y %H:%M')
        }
    })

    try:
        msg = EmailMultiAlternatives(
            subject=f'[ITA Titulación] {titulo}',
            body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=correos_destino,
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception:
        pass  # Silencio: las notificaciones internas siguen funcionando


def registrar_cambio_estado(expediente, estado_nuevo, realizado_por, descripcion):
    """
    Registra en el historial un cambio de estado del expediente.
    """
    from expediente.models import HistorialExpediente
    HistorialExpediente.objects.create(
        expediente=expediente,
        estado_anterior=expediente.estado,
        estado_nuevo=estado_nuevo,
        realizado_por=realizado_por,
        descripcion=descripcion,
    )
    expediente.estado = estado_nuevo
    expediente.save(update_fields=['estado', 'fecha_ultima_actualizacion'])


def registrar_cambio_documento(documento, accion, realizado_por, observaciones='', departamento=''):
    """Registra en el historial un cambio de estado de un documento."""
    from expediente.models import HistorialDocumento
    HistorialDocumento.objects.create(
        documento=documento,
        accion=accion,
        departamento=departamento,
        realizado_por=realizado_por,
        observaciones=observaciones,
    )
