from django.urls import path
from escolares.views import (
    DashboardEscolaresView,
    ExpedienteListaEscolaresView,
    ExpedienteDetalleEscolaresView,
    ValidarDocumentoEscolaresView,
    MarcarPapelesRecibidosView,
    SubirConstanciaEscolaresView,
    ValidarPagoEscolaresView,
    CalendarioEscolaresView,
    MarcarFotografiaEntregadaView,
    DescargarExpedienteView,
    EnviarRecordatorioEscolaresView,
    ExportarExpedientesExcelView,
    RegistrarActaExencionView,
    IniciarTramiteDGPView,
    ValidarCedulaEscolaresView,
    AgendarCitaEntregaView,
    ConcluirProcesoView,
    IntegrarExpedienteView,
    EstadisticasEscolaresView,
)

app_name = 'escolares'

urlpatterns = [
    path('', DashboardEscolaresView.as_view(), name='dashboard'),
    path('estadisticas/', EstadisticasEscolaresView.as_view(), name='estadisticas'),
    path('expedientes/', ExpedienteListaEscolaresView.as_view(), name='expedientes'),
    path('calendario/', CalendarioEscolaresView.as_view(), name='calendario'),
    path('expedientes/<int:pk>/', ExpedienteDetalleEscolaresView.as_view(), name='expediente_detalle'),
    
    path('documentos/<int:pk>/validar/', ValidarDocumentoEscolaresView.as_view(), name='validar_documento'),
    path('expedientes/<int:pk>/recibir-papeles/', MarcarPapelesRecibidosView.as_view(), name='recibir_papeles'),
    path('expedientes/<int:pk>/validar-pago/', ValidarPagoEscolaresView.as_view(), name='validar_pago'),
    path('expedientes/<int:pk>/subir-constancia/', SubirConstanciaEscolaresView.as_view(), name='subir_constancia'),
    
    path('expedientes/<int:pk>/foto-fisica/', MarcarFotografiaEntregadaView.as_view(), name='marcar_foto_fisica'),
    path('expedientes/<int:pk>/descargar/', DescargarExpedienteView.as_view(), name='descargar_expediente'),
    
    path('expedientes/<int:pk>/recordatorio/', EnviarRecordatorioEscolaresView.as_view(), name='enviar_recordatorio'),
    path('expedientes/exportar-excel/', ExportarExpedientesExcelView.as_view(), name='exportar_excel'),
    path('expedientes/<int:pk>/acta-exencion/', RegistrarActaExencionView.as_view(), name='acta_exencion'),

    # DGP y Cédula Profesional
    path('expedientes/<int:pk>/iniciar-dgp/', IniciarTramiteDGPView.as_view(), name='iniciar_dgp'),
    path('expedientes/<int:pk>/validar-cedula/', ValidarCedulaEscolaresView.as_view(), name='validar_cedula'),
    path('expedientes/<int:pk>/agendar-cita/', AgendarCitaEntregaView.as_view(), name='agendar_cita'),
    path('expedientes/<int:pk>/concluir/', ConcluirProcesoView.as_view(), name='concluir_proceso'),
    path('expedientes/<int:pk>/integrar/', IntegrarExpedienteView.as_view(), name='integrar'),
]
