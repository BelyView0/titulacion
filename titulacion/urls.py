"""URL raíz del proyecto de titulación ITA."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def dashboard_redirect(request):
    """Redirige al dashboard correcto según el rol del usuario."""
    if not request.user.is_authenticated:
        return redirect('login')
    return redirect(request.user.get_dashboard_url())


urlpatterns = [
    # Admin Django
    path('admin/', admin.site.urls),

    # Autenticación
    path('auth/login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('auth/logout/', auth_views.LogoutView.as_view(), name='logout'),
    # ─── CAMBIO DE CONTRASEÑA (Usuario autenticado) ───
    path('auth/password/', 
         __import__('administracion.views_auth', fromlist=['OTPPasswordChangeRequestView']).OTPPasswordChangeRequestView.as_view(), 
         name='password_change'),
    path('auth/password/verify/', 
         __import__('administracion.views_auth', fromlist=['OTPPasswordChangeVerifyView']).OTPPasswordChangeVerifyView.as_view(), 
         name='password_change_verify'),
    path('auth/password/done/', 
         __import__('administracion.views_auth', fromlist=['OTPPasswordChangeDoneView']).OTPPasswordChangeDoneView.as_view(), 
         name='password_change_done'),

    # ─── RECUPERACIÓN DE CONTRASEÑA (Desde login) ───
    path('auth/password-reset/', 
         __import__('administracion.views_auth', fromlist=['OTPPasswordResetRequestView']).OTPPasswordResetRequestView.as_view(), 
         name='password_reset'),
    path('auth/password-reset/verificar/', 
         __import__('administracion.views_auth', fromlist=['OTPPasswordResetVerifyView']).OTPPasswordResetVerifyView.as_view(), 
         name='password_reset_verify'),
    path('auth/password-reset/completado/', 
         __import__('administracion.views_auth', fromlist=['OTPPasswordResetCompleteView']).OTPPasswordResetCompleteView.as_view(), 
         name='password_reset_complete'),

    # Redirección inteligente de dashboard
    path('dashboard/', login_required(dashboard_redirect), name='dashboard'),

    # Módulos por rol
    path('admin-sistema/', include('administracion.urls')),
    path('alumno/', include('alumnos.urls')),
    path('escolares/', include('escolares.urls')),
    path('academico/', include('academico.urls')),

    # Confirmación de asistencia (pública, token-based)
    path('confirmar/<str:token>/',
        __import__('expediente.views_confirmacion', fromlist=['confirmar_asistencia']).confirmar_asistencia,
        name='confirmar_asistencia'),

    # API (calendario)
    path('api/calendario/eventos/', login_required(
        __import__('expediente.api_calendario', fromlist=['eventos_calendario']).eventos_calendario
    ), name='api_calendario_eventos'),

    # Home → login si no autenticado
    path('', lambda req: redirect('login'), name='home'),
]

# Servir archivos media en modo desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')