from django.urls import path

from centro_computo.views import (
    AdeudosPendientesView,
    ConfirmarAdeudoView,
    DashboardCentroComputoView,
    NotificacionesBandejaView,
)

app_name = 'centro_computo'

urlpatterns = [
    path('', DashboardCentroComputoView.as_view(), name='dashboard'),
    path('adeudos-pendientes/', AdeudosPendientesView.as_view(), name='adeudos_pendientes'),
    path('adeudos/<int:pk>/confirmar/', ConfirmarAdeudoView.as_view(), name='confirmar_adeudo'),
    path('notificaciones/', NotificacionesBandejaView.as_view(), name='notificaciones'),
]
