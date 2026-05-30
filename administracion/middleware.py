"""
Middleware de seguridad para el Sistema de Titulacion ITA.

1. ForcePasswordChangeMiddleware:
   Redirige al usuario a la pagina de cambio de contrasena obligatorio
   si tiene la bandera `debe_cambiar_password` activa.
"""
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """
    Si el usuario autenticado tiene `debe_cambiar_password=True`,
    lo redirige a la vista de cambio obligatorio en CADA request,
    sin importar a donde intente navegar.

    Excepciones: logout, la propia vista de cambio forzado,
    y archivos estaticos/media.
    """

    # URLs que el usuario SI puede visitar sin haber cambiado su password
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
            # Permitir URLs seguras
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
    y se le redirige a su perfil para que verifique al menos uno.
    """

    # URLs permitidas durante el bloqueo
    ALLOWED_URL_NAMES = [
        'perfil',
        'perfil_verificar_enviar',
        'perfil_verificar_validar',
        'perfil_solicitar_correccion_control',
        'logout',
        'forzar_cambio_password',  # Permitimos cambio de password si está bloqueado por ambas cosas
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
            # Si tiene contraseña por cambiar, eso toma prioridad (el otro middleware lo manejará)
            if getattr(user, 'debe_cambiar_password', False):
                return self.get_response(request)

            # Validar si tiene al menos un correo verificado
            if not getattr(user, 'email_verificado', False) and not getattr(user, 'correo_institucional_verificado', False):
                current_path = request.path

                # Permitir prefixes estáticos
                for prefix in self.ALLOWED_PREFIXES:
                    if current_path.startswith(prefix):
                        return self.get_response(request)

                # Obtener las rutas permitidas
                allowed_paths = []
                for name in self.ALLOWED_URL_NAMES:
                    try:
                        # Algunas URLs requieren argumentos, las tratamos diferente
                        if name == 'perfil_verificar_enviar' or name == 'perfil_verificar_validar':
                            allowed_paths.append(reverse(name, args=['personal']))
                            allowed_paths.append(reverse(name, args=['institucional']))
                        else:
                            allowed_paths.append(reverse(name))
                    except Exception:
                        pass
                
                if current_path not in allowed_paths:
                    from django.contrib import messages
                    messages.warning(request, 'Tu acceso está restringido. Por favor, verifica al menos uno de tus correos electrónicos para continuar usando el sistema.')
                    return redirect('perfil')

        return self.get_response(request)
