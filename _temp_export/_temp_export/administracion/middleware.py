"""

Middleware de seguridad para el Sistema de Titulacion ITA.



1. ForcePasswordChangeMiddleware:

   Redirige al usuario a la pagina de cambio de contraseña obligatorio

   si tiene la bandera `debe_cambiar_password` activa.

2. ForceEmailVerificationMiddleware:

   Redirige al perfil si tiene correos pendientes de verificar.

3. ForceEmailConfigMiddleware:

   Fuerza configuración SMTP para administradores.

"""

from django.shortcuts import redirect

from django.urls import reverse





# Rutas permitidas durante configuración de correo / verificación

_EMAIL_SETUP_URL_NAMES = [

    'perfil',

    'perfil_verificar_enviar',

    'perfil_verificar_validar',

    'perfil_solicitar_correccion_control',

    'logout',

    'forzar_cambio_password',

    'administracion:configuracion_email',

    'administracion:configuracion_email_probar',

    'administracion:configuracion_email_revelar',

    'administracion:configuracion_inicial',

    'administracion:configuracion_database',

    'administracion:configuracion_completar',

]





def _allowed_paths(url_names):

    paths = []

    for name in url_names:

        try:

            if name in ('perfil_verificar_enviar', 'perfil_verificar_validar'):

                paths.append(reverse(name, args=['personal']))

                paths.append(reverse(name, args=['institucional']))

            else:

                paths.append(reverse(name))

        except Exception:

            pass

    return paths





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

    Bloquea el acceso si el usuario tiene correos registrados sin verificar.

    Los administradores pueden configurar SMTP antes de verificar correos.

    """

    ALLOWED_URL_NAMES = _EMAIL_SETUP_URL_NAMES



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



            if hasattr(user, 'requiere_verificacion_correo') and user.requiere_verificacion_correo():

                current_path = request.path



                for prefix in self.ALLOWED_PREFIXES:

                    if current_path.startswith(prefix):

                        return self.get_response(request)



                if current_path not in _allowed_paths(self.ALLOWED_URL_NAMES):

                    from django.contrib import messages

                    messages.warning(

                        request,

                        'Verifica tus correos registrados en tu perfil para continuar.'

                    )

                    return redirect('perfil')



        return self.get_response(request)





class ForceEmailConfigMiddleware:

    """

    Fuerza a los administradores a configurar el correo electrónico del sistema.

    """

    ALLOWED_URL_NAMES = _EMAIL_SETUP_URL_NAMES



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

            if not ConfiguracionInstitucional.smtp_configurado():

                current_path = request.path



                for prefix in self.ALLOWED_PREFIXES:

                    if current_path.startswith(prefix):

                        return self.get_response(request)



                if current_path not in _allowed_paths(self.ALLOWED_URL_NAMES):

                    from django.contrib import messages

                    messages.warning(

                        request,

                        'Configure el servidor de correo (SMTP) para que el sistema pueda enviar notificaciones y códigos de verificación.'

                    )

                    return redirect('administracion:configuracion_email')



        return self.get_response(request)





class ForceInitialSetupMiddleware:

    """Redirige al admin al dashboard si el sistema no está configurado."""

    ALLOWED_PREFIXES = ['/static/', '/media/', '/auth/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from administracion.setup_checks import SETUP_ALLOWED_URL_NAMES, ruta_permitida_durante_setup

        user = request.user
        if user.is_authenticated and getattr(user, 'es_admin', False):
            if getattr(user, 'debe_cambiar_password', False):
                return self.get_response(request)

            path = request.path
            for prefix in self.ALLOWED_PREFIXES:
                if path.startswith(prefix):
                    return self.get_response(request)

            from administracion.models import ConfiguracionInstitucional
            config = ConfiguracionInstitucional.objects.first()
            if config and not config.sistema_configurado:
                allowed = _allowed_paths(SETUP_ALLOWED_URL_NAMES)
                if not ruta_permitida_durante_setup(path, allowed):
                    from django.contrib import messages
                    messages.info(
                        request,
                        'Complete la configuración inicial del sistema en el panel de administración.'
                    )
                    return redirect('administracion:dashboard')
        return self.get_response(request)





class ForceUserActivityMiddleware:

    """Bloquea acceso si el usuario no tiene periodo activo vigente."""

    ALLOWED_PREFIXES = ['/static/', '/media/', '/auth/']

    ALLOWED_NAMES = ['logout', 'forzar_cambio_password', 'perfil'] + _EMAIL_SETUP_URL_NAMES



    def __init__(self, get_response):

        self.get_response = get_response



    def __call__(self, request):

        user = request.user

        if user.is_authenticated and hasattr(user, 'tiene_periodo_activo'):

            if not user.tiene_periodo_activo():

                path = request.path

                for prefix in self.ALLOWED_PREFIXES:

                    if path.startswith(prefix):

                        return self.get_response(request)

                if path not in _allowed_paths(self.ALLOWED_NAMES):

                    from django.contrib import messages

                    from django.contrib.auth import logout

                    messages.error(

                        request,

                        'Su cuenta no está activa en este periodo. Contacte al administrador.'

                    )

                    logout(request)

                    return redirect('login')

        return self.get_response(request)


