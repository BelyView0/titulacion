
from django.urls import path

from .views import (
    PerfilAlumnoView,
    DashboardAlumnoView,
    DocumentosAlumnoView,
    CargarDocumentoAlumnoView,
    EnviarVerificacionCorreoAPIView,
    ValidarVerificacionCorreoAPIView,
)

app_name = 'alumnos'

urlpatterns = [
    path(
        'perfil/',
        PerfilAlumnoView.as_view(),
        name='perfil'
    ),

    path(
        'perfil/verificar/<str:tipo>/enviar/',
        EnviarVerificacionCorreoAPIView.as_view(),
        name='enviar-verificacion-correo'
    ),

    path(
        'perfil/verificar/<str:tipo>/validar/',
        ValidarVerificacionCorreoAPIView.as_view(),
        name='validar-verificacion-correo'
    ),

    path(
        'dashboard/',
        DashboardAlumnoView.as_view(),
        name='dashboard'
    ),

    path(
        'documentos/',
        DocumentosAlumnoView.as_view(),
        name='documentos'
    ),

    path(
        'documentos/<int:pk>/cargar/',
        CargarDocumentoAlumnoView.as_view(),
        name='cargar-documento'
    ),
]
