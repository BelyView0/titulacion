from django.urls import path

from centro_informacion.views import (
    AdeudosPendientesView,
    ConfirmarAdeudoView,
    DashboardCentroInformacionView,
    NotificacionesBandejaView,
)

app_name = 'centro_informacion'

urlpatterns = [
    path('', DashboardCentroInformacionView.as_view(), name='dashboard'),
    path('adeudos-pendientes/', AdeudosPendientesView.as_view(), name='adeudos_pendientes'),
    path('adeudos/<int:pk>/confirmar/', ConfirmarAdeudoView.as_view(), name='confirmar_adeudo'),
    path('notificaciones/', NotificacionesBandejaView.as_view(), name='notificaciones'),
]
