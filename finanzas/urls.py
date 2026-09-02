from django.urls import path

from finanzas.views import (
    AdeudosPendientesView,
    ConfirmarAdeudoView,
    DashboardFinanzasView,
    ExpedientePagoDetalleView,
    ExpedientesPagoView,
    GenerarReferenciaPagoView,
    NotificacionesBandejaView,
    ValidarPagoView,
)

app_name = 'finanzas'

urlpatterns = [
    path('', DashboardFinanzasView.as_view(), name='dashboard'),
    path('expedientes-pago/', ExpedientesPagoView.as_view(), name='expedientes_pago'),
    path('expedientes-pago/<int:pk>/', ExpedientePagoDetalleView.as_view(), name='expediente_pago_detalle'),
    path('expedientes-pago/<int:pk>/generar-referencia/', GenerarReferenciaPagoView.as_view(), name='generar_referencia'),
    path('expedientes-pago/<int:pk>/validar-pago/', ValidarPagoView.as_view(), name='validar_pago'),
    path('adeudos-pendientes/', AdeudosPendientesView.as_view(), name='adeudos_pendientes'),
    path('adeudos/<int:pk>/confirmar/', ConfirmarAdeudoView.as_view(), name='confirmar_adeudo'),
    path('notificaciones/', NotificacionesBandejaView.as_view(), name='notificaciones'),
]
