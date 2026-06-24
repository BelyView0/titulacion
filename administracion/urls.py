from django.urls import path
from . import views
from . import views_import
from . import views_jefe
from . import views_catalogos
from . import export_views
app_name = 'administracion'

urlpatterns = [
    # ─── Admin (gestión de sistema) ──────────────────────────
    path('', views.DashboardAdminView.as_view(), name='dashboard'),

    # Usuarios
    path('usuarios/', views.UsuarioListView.as_view(), name='usuarios'),
    path('usuarios/nuevo/', views.UsuarioCreateView.as_view(), name='usuario_crear'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_editar'),
    path('usuarios/<int:pk>/eliminar/', views.UsuarioDeleteView.as_view(), name='usuario_eliminar'),

    # Configuración Institucional
    path('configuracion/', views.ConfiguracionUpdateView.as_view(), name='configuracion'),
    path('configuracion/email/', views.ConfiguracionEmailUpdateView.as_view(), name='configuracion_email'),
    path('configuracion/email/probar/', views.ProbarConfiguracionEmailView.as_view(), name='configuracion_email_probar'),
    path('configuracion/email/revelar/', views.RevelarPasswordSMTPView.as_view(), name='configuracion_email_revelar'),

    # Tiempo Real / API
    path('api/realtime/check/', views.CheckRealTimeUpdatesView.as_view(), name='api_realtime_check'),

    # Jefes de Departamento
    path('jefes/', views_jefe.JefeDepartamentoListView.as_view(), name='jefes'),
    path('jefes/nuevo/', views_jefe.JefeDepartamentoCreateView.as_view(), name='jefe_crear'),
    path('jefes/<int:pk>/editar/', views_jefe.JefeDepartamentoUpdateView.as_view(), name='jefe_editar'),
    path('jefes/<int:pk>/eliminar/', views_jefe.JefeDepartamentoDeleteView.as_view(), name='jefe_eliminar'),
    
    # Solicitudes de cambio
    path('jefes/solicitudes/', views_jefe.SolicitudesCambioJefeListView.as_view(), name='solicitudes_jefe'),
    path('jefes/solicitudes/<int:pk>/<str:accion>/', views_jefe.ResolucionSolicitudView.as_view(), name='resolucion_solicitud'),

    # Carreras
    path('carreras/', views.CarreraListView.as_view(), name='carreras'),
    path('carreras/nueva/', views.CarreraCreateView.as_view(), name='carrera_crear'),
    path('carreras/<int:pk>/editar/', views.CarreraUpdateView.as_view(), name='carrera_editar'),

    # Catálogos (Planes, Modalidades, Documentos)
    path('planes/', views_catalogos.PlanEstudiosListView.as_view(), name='planes'),
    path('planes/nuevo/', views_catalogos.PlanEstudiosCreateView.as_view(), name='plan_crear'),
    path('planes/<int:pk>/editar/', views_catalogos.PlanEstudiosUpdateView.as_view(), name='plan_editar'),
    path('planes/<int:pk>/eliminar/', views_catalogos.PlanEstudiosDeleteView.as_view(), name='plan_eliminar'),
    
    path('modalidades/', views_catalogos.ModalidadListView.as_view(), name='modalidades'),
    path('modalidades/nueva/', views_catalogos.ModalidadCreateView.as_view(), name='modalidad_crear'),
    path('modalidades/<int:pk>/editar/', views_catalogos.ModalidadUpdateView.as_view(), name='modalidad_editar'),
    path('modalidades/<int:pk>/eliminar/', views_catalogos.ModalidadDeleteView.as_view(), name='modalidad_eliminar'),
    
    path('departamentos/', views_catalogos.DepartamentoListView.as_view(), name='departamentos'),
    path('departamentos/nuevo/', views_catalogos.DepartamentoCreateView.as_view(), name='departamento_crear'),
    path('departamentos/<int:pk>/editar/', views_catalogos.DepartamentoUpdateView.as_view(), name='departamento_editar'),
    path('departamentos/<int:pk>/eliminar/', views_catalogos.DepartamentoDeleteView.as_view(), name='departamento_eliminar'),

    path('profesores/', views_catalogos.ProfesorListView.as_view(), name='profesores'),
    path('profesores/nuevo/', views_catalogos.ProfesorCreateView.as_view(), name='profesor_crear'),
    path('profesores/<int:pk>/editar/', views_catalogos.ProfesorUpdateView.as_view(), name='profesor_editar'),
    path('profesores/<int:pk>/eliminar/', views_catalogos.ProfesorDeleteView.as_view(), name='profesor_eliminar'),

    path('documentos/', views_catalogos.TipoDocumentoListView.as_view(), name='documentos'),
    path('documentos/nuevo/', views_catalogos.TipoDocumentoCreateView.as_view(), name='documento_crear'),
    path('documentos/<int:pk>/editar/', views_catalogos.TipoDocumentoUpdateView.as_view(), name='documento_editar'),
    path('documentos/<int:pk>/eliminar/', views_catalogos.TipoDocumentoDeleteView.as_view(), name='documento_eliminar'),
    path('documentos/reordenar/', views_catalogos.TipoDocumentoReorderView.as_view(), name='documento_reordenar'),

    # Importación y Exportación Masiva vía Excel
    path('importar-exportar/', views_import.ImportarExportarHubView.as_view(), name='importar_exportar'),
    path('importar-exportar/descargar/', views_import.DescargarPlantillaView.as_view(), name='descargar_plantilla'),
    path('importar-exportar/subir/', views_import.SubirArchivoMasivoView.as_view(), name='subir_archivo_masivo'),

    # ─── Jefe de Proyectos / Academia(administración por carrera) ────────
    path('jefe/', views.DashboardJefeProyectoView.as_view(), name='jefe_dashboard'),
    path('jefe/expedientes/', views.ExpedienteListaJefeView.as_view(), name='jefe_expedientes'),
    path('jefe/expedientes/<int:pk>/', views.ExpedienteDetalleJefeView.as_view(), name='jefe_detalle'),
    path('jefe/expedientes/<int:pk>/jurado/', views.AsignacionJuradoJefeView.as_view(), name='jefe_jurado'),
    path('jefe/expedientes/<int:pk>/oficio/', views.DescargarOficioJuradoJefeView.as_view(), name='jefe_oficio'),
    path('jefe/expedientes/<int:pk>/programar/', views.ActoProtocolarioView.as_view(), name='jefe_programar'),
    path('jefe/acto/<int:pk>/reprogramar/', views.ReprogramarActoView.as_view(), name='jefe_reprogramar'),
    path('jefe/calendario/', views.CalendarioJefeView.as_view(), name='jefe_calendario'),
    path('jefe/estadisticas/', views.EstadisticasJefeView.as_view(), name='jefe_estadisticas'),
    path('jefe/estadisticas/excel/', export_views.ExportarEstadisticasExcelView.as_view(), name='jefe_estadisticas_excel'),
    path('jefe/estadisticas/pptx/', export_views.ExportarEstadisticasPPTXView.as_view(), name='jefe_estadisticas_pptx'),
    path('jefe/confirmacion/<int:pk>/toggle/', views.ToggleConfirmacionJefeView.as_view(), name='jefe_toggle_confirmacion'),
    path('jefe/acto/<int:pk>/confirmar-realizado/', views.ConfirmarActoLlevadoAcaboJefeView.as_view(), name='jefe_confirmar_acto_realizado'),
    path('jefe/solicitar-cambio/', views.SolicitarCambioJefeView.as_view(), name='solicitar_cambio_jefe'),
]
