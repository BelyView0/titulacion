import sys

from django.apps import AppConfig


class AdministracionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'administracion'
    verbose_name = 'Administracion del Sistema'

    def ready(self):
        """
        Conecta la senal post_migrate para verificar que el superusuario
        adminITA exista despues de cada migracion o al iniciar el servidor.
        """
        from django.db.models.signals import post_migrate
        post_migrate.connect(_ensure_admin_exists, sender=self)

        import administracion.signals


def _ensure_admin_exists(sender, **kwargs):
    """
    Callback de post_migrate: crea o verifica el superusuario adminITA.
    Se ejecuta despues de que las tablas estan listas, sin warnings.
    """
    from administracion.models import Rol, Usuario

    try:
        if not Usuario.objects.filter(username='adminITA').exists():
            # Solo crear automaticamente si estamos en runserver o migrate
            from django.core.management import call_command
            call_command('ensure_admin', verbosity=1)
        else:
            # Verificar integridad silenciosamente
            user = Usuario.objects.get(username='adminITA')
            changed = False
            if user.rol != Rol.ADMINISTRADOR:
                user.rol = Rol.ADMINISTRADOR
                changed = True
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if changed:
                user.save()
    except Exception:
        # Si la tabla no existe aun, silenciar
        pass
