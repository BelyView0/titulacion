from django.urls import path
from . import views

app_name = 'academico'

urlpatterns = [
    path('', views.DashboardAcademicoView.as_view(), name='dashboard'),
    path('expedientes/', views.ExpedienteListaAcademicoView.as_view(), name='expedientes'),
    path('expedientes/<int:pk>/', views.ExpedienteDetalleAcademicoView.as_view(), name='expediente_detalle'),
    path('expedientes/<int:pk>/validar-inicial/', views.ValidarExpedienteInicialView.as_view(), name='validar_inicial'),
    path('documentos/<int:pk>/validar/', views.ValidarDocumentoAcademicoView.as_view(), name='validar_documento'),
    path('expedientes/<int:pk>/empastado/', views.RecepcionEmpastadoView.as_view(), name='recibir_empastado'),
    path('expedientes/<int:pk>/acto/', views.ActoProtocolarioView.as_view(), name='programar_acto'),
    path('actos/<int:pk>/resultado/', views.RegistrarResultadoActoView.as_view(), name='resultado_acto'),
    path('expedientes/<int:pk>/foto-fisica/', views.MarcarFotografiaAcademicoView.as_view(), name='marcar_fotografia'),
]