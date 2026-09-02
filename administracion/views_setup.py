"""Vistas de configuración inicial SIGET."""
from django.views import View
from django.views.generic import FormView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy

from administracion.forms_database import DatabaseConfigForm
from titulacion.db_config import load_database_config, save_database_config, test_database_connection
from expediente.mixins import AdminRequeridoMixin
from administracion.models import ConfiguracionInstitucional
from administracion.setup_checks import evaluar_configuracion_sistema, sincronizar_sistema_configurado


class ConfiguracionInicialView(AdminRequeridoMixin, View):
    """Redirige al checklist integrado en el dashboard."""

    def get(self, request, *args, **kwargs):
        return redirect('administracion:dashboard')


class ConfiguracionDatabaseView(AdminRequeridoMixin, FormView):
    template_name = 'administracion/configuracion_database.html'
    form_class = DatabaseConfigForm
    success_url = reverse_lazy('administracion:dashboard')

    def get_initial(self):
        return load_database_config()

    def form_valid(self, form):
        config = form.cleaned_data.copy()
        if config['engine'] == 'sqlite':
            from django.conf import settings
            config['name'] = str(settings.BASE_DIR / 'db.sqlite3')
        try:
            test_database_connection(config)
        except Exception as e:
            messages.error(
                self.request,
                f'No se pudo conectar a la base de datos: {e}. Verifique los datos.'
            )
            return self.form_invalid(form)
        save_database_config(config)
        messages.success(
            self.request,
            'Configuración guardada. Reinicie el servicio del sistema para aplicar los cambios.'
        )
        return super().form_valid(form)


class MarcarSistemaConfiguradoView(AdminRequeridoMixin, View):
    def post(self, request):
        evaluacion = evaluar_configuracion_sistema()
        if evaluacion['pendiente']:
            messages.warning(
                request,
                f'Aún faltan {len(evaluacion["pendientes"])} paso(s) por completar.'
            )
            return redirect('administracion:dashboard')

        config, _ = ConfiguracionInstitucional.objects.get_or_create(pk=1)
        config.sistema_configurado = True
        config.save(update_fields=['sistema_configurado'])
        sincronizar_sistema_configurado()
        messages.success(request, '¡Configuración inicial completada! El sistema está listo.')
        return redirect('administracion:dashboard')
