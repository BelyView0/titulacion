"""
Mixins de permisos por rol para vistas CBV — SIGET
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect


class FormMessageMixin:
    def form_invalid(self, form):
        errores = " ".join(
            f"{field}: {error}"
            for field, errors in form.errors.items()
            for error in errors
        )
        if not errores:
            errores = "Por favor, revisa los datos ingresados."
        messages.error(self.request, f"Error al procesar el formulario. {errores}")
        return super().form_invalid(form)


class RolRequeridoMixin(LoginRequiredMixin):
    roles_permitidos = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.roles_permitidos and request.user.rol not in self.roles_permitidos:
            messages.error(request, 'No tienes permiso para acceder a esta sección.')
            return redirect(request.user.get_dashboard_url())
        return super().dispatch(request, *args, **kwargs)


class AdminRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = ['ADMIN']


class OficinaTitulacionRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = ['ADMIN', 'OFICINA_TITULACION', 'ESCOLARES', 'ACADEMICO']


class EscolaresRequeridoMixin(OficinaTitulacionRequeridoMixin):
    pass


class AcademicoRequeridoMixin(OficinaTitulacionRequeridoMixin):
    pass


class FinanzasRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = ['ADMIN', 'FINANZAS']


class CentroComputoRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = ['ADMIN', 'CENTRO_COMPUTO']


class CentroInformacionRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = ['ADMIN', 'CENTRO_INFORMACION']


class JefeAcademiaRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = ['ADMIN', 'JEFE_ACADEMIA', 'JEFE_PROYECTO']


class JefeProyectoRequeridoMixin(JefeAcademiaRequeridoMixin):
    pass


class AlumnoRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = ['ALUMNO']


class StaffRequeridoMixin(RolRequeridoMixin):
    roles_permitidos = [
        'ADMIN', 'OFICINA_TITULACION', 'ESCOLARES', 'ACADEMICO',
        'FINANZAS', 'CENTRO_COMPUTO', 'CENTRO_INFORMACION',
        'JEFE_ACADEMIA', 'JEFE_PROYECTO',
    ]


class ExpedientePropioMixin(AlumnoRequeridoMixin):
    def get_expediente(self):
        from expediente.models import Expediente
        try:
            return self.request.user.expediente
        except Expediente.DoesNotExist:
            return None
