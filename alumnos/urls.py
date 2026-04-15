from django.urls import path
from . import views

app_name = 'alumnos'

urlpatterns = [
    path('', views.DashboardAlumnoView.as_view(), name='dashboard'),
    path('expediente/', views.ExpedienteDetalleView.as_view(), name='expediente'),
    path('expediente/crear/', views.ExpedienteCreateView.as_view(), name='expediente_crear'),
    path('expediente/editar/<int:pk>/', views.ExpedienteUpdateView.as_view(), name='expediente_editar'),
    path('expediente/solicitar-revision/', views.SolicitarRevisionView.as_view(), name='solicitar_revision'),
    path('expediente/enviar-documentos/', views.EnviarDocumentosRevisionView.as_view(), name='enviar_documentos'),
    path('expediente/timeline/', views.TimelineView.as_view(), name='timeline'),
    path('documentos/<int:pk>/cargar/', views.DocumentoCargarView.as_view(), name='documento_cargar'),
    path('notificaciones/', views.NotificacionListView.as_view(), name='notificaciones'),
]
