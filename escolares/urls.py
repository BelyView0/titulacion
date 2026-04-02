from django.urls import path
from . import views

app_name = 'escolares'

urlpatterns = [
    path('', views.DashboardEscolaresView.as_view(), name='dashboard'),
    path('expedientes/', views.ExpedienteListaEscolaresView.as_view(), name='expedientes'),
    path('expedientes/<int:pk>/', views.ExpedienteDetalleEscolaresView.as_view(), name='expediente_detalle'),
    path('expedientes/<int:pk>/integrar/', views.IntegrarExpedienteView.as_view(), name='integrar'),
    path('expedientes/<int:pk>/descargar/', views.DescargarExpedienteView.as_view(), name='descargar_expediente'),
    path('expedientes/<int:pk>/enviar-cdmx/', views.EnviarCDMXView.as_view(), name='enviar_cdmx'),
    path('documentos/<int:pk>/validar/', views.ValidarDocumentoEscolaresView.as_view(), name='validar_documento'),
    path('envios/<int:pk>/respuesta/', views.RespuestaCDMXView.as_view(), name='respuesta_cdmx'),
]
