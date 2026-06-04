from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from expediente.mixins import FormMessageMixin
from .models import JefeDepartamento, SolicitudCambioJefe, Rol
from .utils import procesar_resolucion_solicitud

class AdminRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.rol == Rol.ADMINISTRADOR

# ─────────────────────────────────────────────────────────────
# GESTIÓN DE JEFES DE DEPARTAMENTO (CRUD)
# ─────────────────────────────────────────────────────────────

class JefeDepartamentoListView(AdminRequeridoMixin, ListView):
    model = JefeDepartamento
    template_name = 'administracion/jefe_departamento_list.html'
    context_object_name = 'jefes'

class JefeDepartamentoCreateView(AdminRequeridoMixin, FormMessageMixin, CreateView):
    model = JefeDepartamento
    template_name = 'administracion/jefe_departamento_form.html'
    fields = ['departamento', 'titulo_academico', 'nombre', 'apellido_paterno', 'apellido_materno', 'genero']
    success_url = reverse_lazy('administracion:jefes')

    def form_valid(self, form):
        # Asegurar un solo jefe vigente por departamento
        depto = form.cleaned_data['departamento']
        if JefeDepartamento.objects.filter(departamento=depto).exists():
            messages.error(self.request, 'Ya existe un jefe registrado para este departamento. Por favor edite el existente en lugar de crear uno nuevo.')
            return self.form_invalid(form)
        messages.success(self.request, 'Jefe de Departamento creado exitosamente.')
        return super().form_valid(form)

class JefeDepartamentoUpdateView(AdminRequeridoMixin, FormMessageMixin, UpdateView):
    model = JefeDepartamento
    from administracion.forms import JefeDepartamentoUpdateForm
    form_class = JefeDepartamentoUpdateForm
    template_name = 'administracion/jefe_departamento_form.html'
    success_url = reverse_lazy('administracion:jefes')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Jefe de Departamento actualizado exitosamente.')
        return super().form_valid(form)

class JefeDepartamentoDeleteView(AdminRequeridoMixin, DeleteView):
    model = JefeDepartamento
    template_name = 'administracion/jefes/eliminar.html'
    success_url = reverse_lazy('administracion:jefes')

    def dispatch(self, request, *args, **kwargs):
        messages.error(request, 'No se puede eliminar un Jefe de Departamento porque se requiere al menos uno activo para la firma de oficios. Por favor, edite el registro actual para cambiar al titular.')
        return redirect('administracion:jefes')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Jefe de Departamento eliminado exitosamente.')
        return super().delete(request, *args, **kwargs)

# ─────────────────────────────────────────────────────────────
# GESTIÓN DE SOLICITUDES DE CAMBIO DE JEFE (TICKETS)
# ─────────────────────────────────────────────────────────────

class SolicitudesCambioJefeListView(AdminRequeridoMixin, ListView):
    model = SolicitudCambioJefe
    template_name = 'administracion/solicitudes_cambio_jefe.html'
    context_object_name = 'solicitudes'
    
    def get_queryset(self):
        return SolicitudCambioJefe.objects.order_by('-fecha_solicitud')

class ResolucionSolicitudView(AdminRequeridoMixin, View):
    def post(self, request, pk, accion):
        solicitud = get_object_or_404(SolicitudCambioJefe, pk=pk)
        
        if solicitud.estado != 'PENDIENTE':
            messages.error(request, 'Esta solicitud ya ha sido procesada o expirada.')
            return redirect('administracion:solicitudes_jefe')
            
        if accion == 'aprobar':
            solicitud.estado = 'APROBADO'
            procesar_resolucion_solicitud(solicitud, aprobada=True)
            messages.success(request, 'Solicitud aprobada y Jefe de Departamento actualizado.')
        elif accion == 'rechazar':
            solicitud.estado = 'RECHAZADO'
            procesar_resolucion_solicitud(solicitud, aprobada=False)
            messages.info(request, 'Solicitud rechazada. Los PDFs de emergencia han sido regenerados con la firma del Jefe oficial.')
        else:
            messages.error(request, 'Acción no válida.')
            
        return redirect('administracion:solicitudes_jefe')
