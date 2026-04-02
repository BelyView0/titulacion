"""
Sistema de notificaciones del sistema.
- Notificaciones internas (Notificacion model)
- Notificaciones por correo institucional
"""
from django.core.mail import send_mail
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


def _enviar_correo_alumno(alumno, expediente, titulo, mensaje):
    """Envía correo electrónico al alumno (correo institucional o email registrado)."""
    # Preferencia: correo institucional del perfil, luego email del usuario
    try:
        perfil = alumno.perfil_alumno
        correo_destino = perfil.correo_institucional or alumno.email
    except Exception:
        correo_destino = alumno.email

    if not correo_destino:
        return  # sin correo configurado, no enviar

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

    try:
        send_mail(
            subject=f'[ITA Titulación] {titulo}',
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[correo_destino],
            fail_silently=True,  # El proceso no debe fallar por problemas de correo
        )
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
