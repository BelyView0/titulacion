from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from alumnos.models import Notificacion

from .permissions import IsAlumno
from .serializers import (
    PerfilAlumnoSerializer,
    DashboardAlumnoSerializer,
    NotificacionDashboardSerializer,
)


class PerfilAlumnoView(APIView):
    """
    Consulta y actualiza el perfil del alumno autenticado.
    """

    permission_classes = [IsAlumno]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        """
        Obtiene el perfil del alumno autenticado.
        """

        serializer = PerfilAlumnoSerializer(
            request.user,
            context={'request': request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        """
        Actualiza los datos permitidos del perfil.
        """

        serializer = PerfilAlumnoSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


class DashboardAlumnoView(APIView):
    permission_classes = [IsAlumno]

    def get(self, request):
        notificaciones_no_leidas = Notificacion.objects.filter(
            destinatario=request.user,
            leida=False
        ).count()

        notificaciones_recientes = Notificacion.objects.filter(
            destinatario=request.user
        ).order_by('-fecha')[:5]

        serializer = DashboardAlumnoSerializer(
            request.user
        )

        data = serializer.data

        data['notificaciones_no_leidas'] = notificaciones_no_leidas

        data['notificaciones_recientes'] = NotificacionDashboardSerializer(
            notificaciones_recientes,
            many=True
        ).data

        return Response(
            data,
            status=status.HTTP_200_OK
        )