from django.apps import AppConfig


class OficinaTitulacionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'oficina_titulacion'
    verbose_name = 'Oficina de Titulación'

    def ready(self):
        import oficina_titulacion.signals  # noqa: F401
