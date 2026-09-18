"""Vistas de configuración inicial SIGET."""
from django.views import View
from django.views.generic import FormView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy

from administracion.forms_database import DatabaseConfigForm
from titulacion.db_config import load_database_config, normalize_database_config
from titulacion.db_migrate import DatabaseMigrationError, apply_database_config_change
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['config_actual'] = load_database_config()
        return ctx

    def form_valid(self, form):
        config = form.cleaned_data.copy()
        if config['engine'] == 'sqlite':
            from django.conf import settings
            config['name'] = str(settings.BASE_DIR / 'db.sqlite3')
        config = normalize_database_config(config)

        try:
            result = apply_database_config_change(config)
        except DatabaseMigrationError as e:
            messages.error(
                self.request,
                f'No se migró ni se cambió la configuración. {e}',
            )
            return self.form_invalid(form)
        except Exception as e:
            messages.error(
                self.request,
                f'Error al aplicar la configuración de base de datos: {e}. '
                'Se mantuvo la base de datos actual.',
            )
            return self.form_invalid(form)

        if result.get('migrated'):
            messages.success(
                self.request,
                f"{result.get('message', 'Datos migrados.')} "
                'Reinicie el servicio del sistema para que todos los procesos '
                'usen la nueva base de datos.',
            )
        else:
            messages.success(
                self.request,
                result.get('message', 'Configuración de base de datos guardada.'),
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
