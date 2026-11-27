"""
Notificaciones del alumno para la app móvil (SIGET).

Replica lo que hace la campana de la web (templates/base.html):

  GET /api/v1/alumnos/notificaciones/
      Equivale a NotificacionesApiView (administracion/views.py).
      Devuelve las últimas notificaciones del usuario y, por defecto,
      las marca como leídas al abrir el panel (marcar_leidas=1, limit=40,
      máximo 80). `unread` es el total ANTES de marcarlas en la lista y
      llega en 0 cuando se marcaron.

  GET /api/v1/alumnos/notificaciones/resumen/
      Equivale a CheckRealTimeUpdatesView: consulta ligera con el número
      de notificaciones no leídas. La web la repite cada 8 segundos.
"""
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from administracion.models import ConfiguracionInstitucional
from alumnos.models import Notificacion
from expediente.notifications import marcar_notificaciones_leidas

from .permissions import IsAlumno, IsCorreoVerificado

LIMITE_POR_DEFECTO = 40
LIMITE_MAXIMO = 80

# Igual que la web: este mensaje es una guía larga que solo se lee completa
# en el detalle, así que el panel muestra un resumen.
PREFIJO_DGP = 'DGP_INSTRUCCIONES'
RESUMEN_DGP = (
    'Instrucciones del proceso DGP / cédula. '
    'Abre el detalle para ver los pasos.'
)


def serializar_notificacion(n):
    """Mismos campos que el JSON del panel de la web."""
    mensaje = n.mensaje or ''

    if mensaje.startswith(PREFIJO_DGP):
        mensaje = RESUMEN_DGP

    return {
        'id': n.id,
        'titulo': n.titulo,
        'mensaje': mensaje,
        'tipo': n.tipo,
        'tipo_display': n.get_tipo_display(),
        'color': n.get_tipo_color(),
        'icono': n.get_tipo_icono(),
        'leida': n.leida,
        'fecha': timezone.localtime(n.fecha).strftime('%d/%m/%Y %H:%M'),
        'url': n.url_relacionada or '',
    }


class NotificacionesAlumnoAPIView(APIView):
    """Panel de notificaciones (campana)."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def get(self, request):
        marcar = request.query_params.get('marcar_leidas', '1') == '1'

        try:
            limite = min(
                int(request.query_params.get('limit', LIMITE_POR_DEFECTO)
                    or LIMITE_POR_DEFECTO),
                LIMITE_MAXIMO,
            )
        except (TypeError, ValueError):
            limite = LIMITE_POR_DEFECTO

        limite = max(limite, 1)

        consulta = Notificacion.objects.filter(
            destinatario=request.user
        ).order_by('-fecha')

        no_leidas = consulta.filter(leida=False).count()

        # Se serializa ANTES de marcar para que la app pueda resaltar
        # las que eran nuevas (igual que la web).
        items = [serializar_notificacion(n) for n in consulta[:limite]]

        if marcar and no_leidas:
            marcar_notificaciones_leidas(request.user)
            no_leidas = 0

        return Response({
            'unread': no_leidas,
            'notificaciones': items,
        })


class NotificacionesResumenAPIView(APIView):
    """Conteo ligero de no leídas para el polling de la app."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def get(self, request):
        configuracion = ConfiguracionInstitucional.objects.first()

        return Response({
            'unread': Notificacion.objects.filter(
                destinatario=request.user,
                leida=False,
            ).count(),
            'global_timestamp': (
                configuracion.ultima_actualizacion if configuracion else 0.0
            ),
        })