from django.urls import path

from .views import PerfilAlumnoView, DashboardAlumnoView


app_name = 'alumnos'

urlpatterns = [
    path(
        'perfil/',
        PerfilAlumnoView.as_view(),
        name='perfil'
    ),
    path(
        'dashboard/', 
        DashboardAlumnoView.as_view(),
        name='dashboard'
    ),
]