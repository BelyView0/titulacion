"""
Mixins de permisos por rol para vistas CBV.
Uso:
    class MiVista(RolRequeridoMixin, View):
        roles_permitidos = ['ADMIN', 'ESCOLARES']
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages

from django.contrib import messages


class FormMessageMixin:
    """
    Mixin para mostrar mensajes de error globales cuando un formulario no es válido.
    Ideal para CreateView y UpdateView.
    """
    def form_invalid(self, form):
        # Muestra una alerta emergente (toast/alert) indicando que hubo un error
        errores = " ".join([f"{field}: {error}" for field, errors in form.errors.items() for error in errors])
        if not errores:
            errores = "Por favor, revisa los datos ingresados. Puede que ya exista un registro con esta información clave."
        messages.error(self.request, f"Error al procesar el formulario. {errores}")
        return super().form_invalid(form)


class RolRequeridoMixin(LoginRequiredMixin):
    """
    Mixin que restringe el acceso a roles específicos.
    Define `roles_permitidos` como lista de strings.
    """
    roles_permitidos = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.roles_permitidos and request.user.rol not in self.roles_permitidos:
            messages.error(
                request,
                'No tienes permiso para acceder a esta sección.'
            )
            return redirect(request.user.get_dashboard_url())
        return super().dispatch(request, *args, **kwargs)


class AdminRequeridoMixin(RolRequeridoMixin):
    """Solo administradores."""
    roles_permitidos = ['ADMIN']


class EscolaresRequeridoMixin(RolRequeridoMixin):
    """Solo Servicios Escolares."""
    roles_permitidos = ['ESCOLARES']


class AcademicoRequeridoMixin(RolRequeridoMixin):
    """Solo División de Estudios Profesionales."""
    roles_permitidos = ['ACADEMICO']


class JefeProyectoRequeridoMixin(RolRequeridoMixin):
    """Solo Jefe de Proyectos / Academia."""
    roles_permitidos = ['JEFE_PROYECTO']


class AlumnoRequeridoMixin(RolRequeridoMixin):
    """Solo Alumnos."""
    roles_permitidos = ['ALUMNO']


class StaffRequeridoMixin(RolRequeridoMixin):
    """Admin, Escolares o Académico (cualquier personal)."""
    roles_permitidos = ['ADMIN', 'ESCOLARES', 'ACADEMICO']


class ExpedientePropioMixin(AlumnoRequeridoMixin):
    """
    Garantiza que el alumno solo pueda ver/editar SU expediente.
    Requiere que la vista tenga acceso a `expediente`.
    """
    def get_expediente(self):
        from expediente.models import Expediente
        try:
            return self.request.user.expediente
        except Expediente.DoesNotExist:
            return None

    def dispatch(self, request, *args, **kwargs):
        resp = super().dispatch(request, *args, **kwargs)
        return resp
