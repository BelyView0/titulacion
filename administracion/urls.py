from django.urls import path
from . import views

app_name = 'administracion'

urlpatterns = [
    # ─── Admin (gestión de sistema) ──────────────────────────
    path('', views.DashboardAdminView.as_view(), name='dashboard'),

    # Usuarios
    path('usuarios/', views.UsuarioListView.as_view(), name='usuarios'),
    path('usuarios/nuevo/', views.UsuarioCreateView.as_view(), name='usuario_crear'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_editar'),

    # Configuración Institucional
    path('configuracion/', views.ConfiguracionUpdateView.as_view(), name='configuracion'),

    # Jefes de Departamento
    path('jefes/', views.JefeDepartamentoListView.as_view(), name='jefes'),
    path('jefes/nuevo/', views.JefeDepartamentoCreateView.as_view(), name='jefe_crear'),
    path('jefes/<int:pk>/editar/', views.JefeDepartamentoUpdateView.as_view(), name='jefe_editar'),
    path('jefes/<int:pk>/eliminar/', views.JefeDepartamentoDeleteView.as_view(), name='jefe_eliminar'),

    # Carreras
    path('carreras/', views.CarreraListView.as_view(), name='carreras'),
    path('carreras/nueva/', views.CarreraCreateView.as_view(), name='carrera_crear'),
    path('carreras/<int:pk>/editar/', views.CarreraUpdateView.as_view(), name='carrera_editar'),

    # ─── Jefe de Proyecto (administración por carrera) ────────
    path('jefe/', views.DashboardJefeProyectoView.as_view(), name='jefe_dashboard'),
    path('jefe/expedientes/', views.ExpedienteListaJefeView.as_view(), name='jefe_expedientes'),
    path('jefe/expedientes/<int:pk>/', views.ExpedienteDetalleJefeView.as_view(), name='jefe_detalle'),
    path('jefe/expedientes/<int:pk>/jurado/', views.AsignacionJuradoJefeView.as_view(), name='jefe_jurado'),
    path('jefe/expedientes/<int:pk>/oficio/', views.DescargarOficioJuradoJefeView.as_view(), name='jefe_oficio'),
    path('jefe/calendario/', views.CalendarioJefeView.as_view(), name='jefe_calendario'),
    path('jefe/estadisticas/', views.EstadisticasJefeView.as_view(), name='jefe_estadisticas'),
    path('jefe/confirmacion/<int:pk>/toggle/', views.ToggleConfirmacionJefeView.as_view(), name='jefe_toggle_confirmacion'),
]
