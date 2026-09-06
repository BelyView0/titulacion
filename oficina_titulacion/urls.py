from django.urls import path

from . import views

app_name = 'oficina_titulacion'

urlpatterns = [
    path('', views.DashboardOficinaView.as_view(), name='dashboard'),
    path('notificaciones/', views.NotificacionesOficinaView.as_view(), name='notificaciones'),
    path('expedientes/', views.ExpedienteListaView.as_view(), name='expedientes'),
    path('expedientes/<int:pk>/', views.ExpedienteDetalleView.as_view(), name='expediente_detalle'),

    path('documentos/<int:pk>/validar/', views.ValidarDocumentoView.as_view(), name='validar_documento'),
    path('expedientes/<int:pk>/aprobar/', views.AprobarExpedienteView.as_view(), name='aprobar_expediente'),
    path('expedientes/<int:pk>/marcar-certificado/', views.MarcarCertificadoListoView.as_view(), name='marcar_certificado'),
    path('expedientes/<int:pk>/generar-oficio/', views.GenerarOficioPublicacionView.as_view(), name='generar_oficio'),
    path('expedientes/<int:pk>/programar-cita-oficio/', views.ProgramarCitaOficioView.as_view(), name='programar_cita_oficio'),
    path('expedientes/<int:pk>/no-inconveniencia/', views.GenerarNoInconvenienciaView.as_view(), name='generar_no_inconveniencia'),
    path('expedientes/<int:pk>/regenerar-no-adeudos/', views.RegenerarNoAdeudosView.as_view(), name='regenerar_no_adeudos'),
    path('expedientes/<int:pk>/generar-certificacion/', views.GenerarCertificacionView.as_view(), name='generar_certificacion'),

    path('citacion-masiva/', views.CitacionMasivaView.as_view(), name='citacion_masiva'),
    path('citas/', views.CitasPendientesView.as_view(), name='citas_pendientes'),
    path('citas/<int:pk>/completar/', views.CompletarCitaView.as_view(), name='completar_cita'),
    path('citas/<int:pk>/aprobar-reprogramacion/', views.AprobarReprogramacionView.as_view(), name='aprobar_reprogramacion'),

    path('protocolo/', views.GrupoProtocoloListCreateView.as_view(), name='grupos_protocolo'),
    path('protocolo/<int:pk>/asignar/', views.AsignarProtocoloView.as_view(), name='asignar_protocolo'),
    path('acto/<int:pk>/confirmar/', views.ConfirmarActoView.as_view(), name='confirmar_acto'),
    path('acto/<int:pk>/reprogramar/', views.ReprogramarActoView.as_view(), name='reprogramar_acto'),

    path('tabla-global/', views.TablaGlobalAlumnosView.as_view(), name='tabla_global'),
]
