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


def notificar_usuarios_division(expediente, titulo, mensaje, url=''):
    """
    Notifica a todos los usuarios con rol ACADEMICO (División de Estudios).
    """
    from administracion.models import Usuario, Rol
    from alumnos.models import Notificacion

    academicos = Usuario.objects.filter(rol=Rol.ACADEMICO, is_active=True)
    
    notificaciones_creadas = []
    correos_destinos = []
    
    for academico in academicos:
        # Notificación interna
        notif = Notificacion.objects.create(
            destinatario=academico,
            tipo='INFO',
            titulo=titulo,
            mensaje=mensaje,
            url_relacionada=url,
        )
        notificaciones_creadas.append(notif)
        
        if academico.email:
            correos_destinos.append(academico.email)
            
    if correos_destinos:
        cuerpo = f"""
Estimado(a) Usuario de División de Estudios,

{mensaje}

---
Expediente: {expediente}
Alumno: {expediente.alumno.get_full_name()}
N° Control: {expediente.alumno.username}
Fecha: {timezone.now().strftime('%d/%m/%Y %H:%M')}

Este mensaje fue generado automáticamente por el Sistema de Gestión de Titulación
del Instituto Tecnológico de Apizaco.

Por favor no responda a este correo.
        """.strip()

        html_content = render_to_string('emails/notificacion_generica.html', {
            'titulo': titulo,
            'saludo': 'Estimado(a) Usuario de División de Estudios,',
            'mensaje': mensaje,
            'datos_adicionales': {
                'Expediente': str(expediente),
                'Alumno': expediente.alumno.get_full_name(),
                'N° Control': expediente.alumno.username,
                'Fecha': timezone.now().strftime('%d/%m/%Y %H:%M')
            }
        })

        try:
            msg = EmailMultiAlternatives(
                subject=f'[ITA Titulación] {titulo}',
                body=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=correos_destinos,
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)
        except Exception:
            pass
            
    return notificaciones_creadas


def notificar_usuarios_escolares(expediente, titulo, mensaje, url=''):
    """
    Notifica a todos los usuarios con rol ESCOLARES (Servicios Escolares).
    """
    from administracion.models import Usuario, Rol
    from alumnos.models import Notificacion

    escolares = Usuario.objects.filter(rol=Rol.ESCOLARES, is_active=True)
    
    notificaciones_creadas = []
    correos_destinos = []
    
    for esc in escolares:
        # Notificación interna
        notif = Notificacion.objects.create(
            destinatario=esc,
            tipo='URGENTE',
            titulo=titulo,
            mensaje=mensaje,
            url_relacionada=url,
        )
        notificaciones_creadas.append(notif)
        
        if esc.email:
            correos_destinos.append(esc.email)
            
    if correos_destinos:
        cuerpo = f"""
Estimado(a) Usuario de Servicios Escolares,

{mensaje}

---
Expediente: {expediente}
Alumno: {expediente.alumno.get_full_name()}
N° Control: {expediente.alumno.username}
Fecha: {timezone.now().strftime('%d/%m/%Y %H:%M')}

Este mensaje fue generado automáticamente por el Sistema de Gestión de Titulación
del Instituto Tecnológico de Apizaco.

Por favor no responda a este correo.
        """.strip()

        html_content = render_to_string('emails/notificacion_generica.html', {
            'titulo': titulo,
            'saludo': 'Estimado(a) Usuario de Servicios Escolares,',
            'mensaje': mensaje,
            'datos_adicionales': {
                'Expediente': str(expediente),
                'Alumno': expediente.alumno.get_full_name(),
                'N° Control': expediente.alumno.username,
                'Fecha': timezone.now().strftime('%d/%m/%Y %H:%M')
            }
        })

        try:
            msg = EmailMultiAlternatives(
                subject=f'[ITA Titulación] {titulo}',
                body=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=correos_destinos,
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)
        except Exception:
            pass
            
    return notificaciones_creadas



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
