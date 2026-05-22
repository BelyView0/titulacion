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
