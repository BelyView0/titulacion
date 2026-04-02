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
    path('auth/password/', auth_views.PasswordChangeView.as_view(
        template_name='auth/password_change.html',
        success_url='/auth/password/done/'
    ), name='password_change'),
    path('auth/password/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='auth/password_change_done.html'
    ), name='password_change_done'),

    # Redirección inteligente de dashboard
    path('dashboard/', login_required(dashboard_redirect), name='dashboard'),

    # Módulos por rol
    path('admin-sistema/', include('administracion.urls')),
    path('alumno/', include('alumnos.urls')),
    path('escolares/', include('escolares.urls')),
    path('academico/', include('academico.urls')),

    # Home → login si no autenticado
    path('', lambda req: redirect('login'), name='home'),
]

# Servir archivos media en modo desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')