# expediente/context_processors.py
def notificaciones_context(request):
    """Inyecta el conteo de notificaciones no leídas en todos los templates."""
    if request.user.is_authenticated and hasattr(request.user, 'rol') and request.user.rol == 'ALUMNO':
        try:
            from alumnos.models import Notificacion
            count = Notificacion.objects.filter(destinatario=request.user, leida=False).count()
            return {'notificaciones_no_leidas': count}
        except Exception:
            pass
    return {'notificaciones_no_leidas': 0}
