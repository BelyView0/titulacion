"""
Middleware de seguridad para el Sistema de Titulacion ITA.

1. ForcePasswordChangeMiddleware:
   Redirige al usuario a la pagina de cambio de contrasena obligatorio
   si tiene la bandera `debe_cambiar_password` activa.
2. ForceEmailVerificationMiddleware:
   Redirige al perfil si no tiene correo verificado.
3. ForceEmailConfigMiddleware:
   Fuerza configuración SMTP para administradores.
"""
from django.shortcuts import redirect
from django.urls import reverse

class ForcePasswordChangeMiddleware:
    """
    Si el usuario autenticado tiene `debe_cambiar_password=True`,
    lo redirige a la vista de cambio obligatorio en CADA request.
    """
    ALLOWED_URL_NAMES = [
        'forzar_cambio_password',
        'logout',
    ]

    ALLOWED_PREFIXES = [
        '/static/',
        '/media/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, 'debe_cambiar_password', False):
            current_path = request.path

            for prefix in self.ALLOWED_PREFIXES:
                if current_path.startswith(prefix):
                    return self.get_response(request)

            try:
                force_url = reverse('forzar_cambio_password')
                logout_url = reverse('logout')
            except Exception:
                return self.get_response(request)

            if current_path not in (force_url, logout_url):
                return redirect('forzar_cambio_password')

        return self.get_response(request)


class ForceEmailVerificationMiddleware:
    """
    Si el usuario autenticado NO tiene ningún correo verificado
    (ni personal ni institucional), se le restringe el acceso al sistema
    y se le redirige a su perfil.
    """
    ALLOWED_URL_NAMES = [
        'perfil',
        'perfil_verificar_enviar',
        'perfil_verificar_validar',
        'perfil_solicitar_correccion_control',
        'logout',
        'forzar_cambio_password',
        'administracion:configuracion_email',
    ]

    ALLOWED_PREFIXES = [
        '/static/',
        '/media/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
            if getattr(user, 'debe_cambiar_password', False):
                return self.get_response(request)

            if not getattr(user, 'correo_institucional_verificado', False):
                current_path = request.path

                for prefix in self.ALLOWED_PREFIXES:
                    if current_path.startswith(prefix):
                        return self.get_response(request)

                allowed_paths = []
                for name in self.ALLOWED_URL_NAMES:
                    try:
                        if name == 'perfil_verificar_enviar' or name == 'perfil_verificar_validar':
                            allowed_paths.append(reverse(name, args=['personal']))
                            allowed_paths.append(reverse(name, args=['institucional']))
                        else:
                            allowed_paths.append(reverse(name))
                    except Exception:
                        pass
                
                if current_path not in allowed_paths:
                    from django.contrib import messages
                    messages.warning(request, 'Tu acceso está restringido. Por favor, verifica tu correo electrónico institucional para continuar usando el sistema.')
                    return redirect('perfil')

        return self.get_response(request)


class ForceEmailConfigMiddleware:
    """
    Fuerza a los administradores a configurar el correo electrónico del sistema.
    Si el usuario es administrador y no hay correo configurado, lo redirige.
    """
    ALLOWED_URL_NAMES = [
        'administracion:configuracion_email',
        'logout',
        'forzar_cambio_password',
        'perfil',
    ]

    ALLOWED_PREFIXES = [
        '/static/',
        '/media/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, 'es_admin', False):
            if getattr(user, 'debe_cambiar_password', False):
                return self.get_response(request)
            
            from administracion.models import ConfiguracionInstitucional
            config = ConfiguracionInstitucional.objects.first()
            if not config or not config.email_remitente or not config.email_password:
                current_path = request.path
                
                for prefix in self.ALLOWED_PREFIXES:
                    if current_path.startswith(prefix):
                        return self.get_response(request)
                
                allowed_paths = []
                for name in self.ALLOWED_URL_NAMES:
                    try:
                        allowed_paths.append(reverse(name))
                    except Exception:
                        pass
                        
                if current_path not in allowed_paths:
                    from django.contrib import messages
                    messages.warning(request, 'Atención: Es obligatorio configurar las credenciales de envío de correo para que el sistema funcione correctamente.')
                    return redirect('administracion:configuracion_email')

        return self.get_response(request)
