from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count, Prefetch, Case, When, Value, IntegerField
from django.http import JsonResponse
import json

from expediente.mixins import AdminRequeridoMixin, FormMessageMixin
from expediente.models import PlanEstudios, Modalidad, TipoDocumento
from administracion.forms_catalogos import PlanEstudiosForm, ModalidadForm, TipoDocumentoForm

# --- PLAN DE ESTUDIOS ---

class PlanEstudiosListView(AdminRequeridoMixin, ListView):
    model = PlanEstudios
    template_name = 'administracion/catalogos/planes_lista.html'
    context_object_name = 'planes'
    
    def get_queryset(self):
        return PlanEstudios.objects.annotate(num_modalidades=Count('modalidades')).order_by('-nombre')

class PlanEstudiosCreateView(AdminRequeridoMixin, FormMessageMixin, CreateView):
    model = PlanEstudios
    form_class = PlanEstudiosForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:planes')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Plan de Estudios'
        ctx['icono'] = 'bi-journal-bookmark'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Plan de estudios creado exitosamente.')
        return super().form_valid(form)

class PlanEstudiosUpdateView(AdminRequeridoMixin, FormMessageMixin, UpdateView):
    model = PlanEstudios
    form_class = PlanEstudiosForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:planes')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Plan: {self.object.nombre}'
        ctx['icono'] = 'bi-journal-bookmark'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Plan de estudios actualizado exitosamente.')
        return super().form_valid(form)

class PlanEstudiosDeleteView(AdminRequeridoMixin, DeleteView):
    model = PlanEstudios
    template_name = 'administracion/catalogos/confirmar_eliminar.html'
    success_url = reverse_lazy('administracion:planes')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Eliminar Plan de Estudios'
        ctx['mensaje'] = f'¿Estás seguro que deseas eliminar el plan "{self.object.nombre}"?'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Plan de estudios eliminado exitosamente.')
        return super().form_valid(form)

# --- MODALIDADES ---

class ModalidadListView(AdminRequeridoMixin, ListView):
    model = Modalidad
    template_name = 'administracion/catalogos/modalidades_lista.html'
    context_object_name = 'modalidades'
    
    def get_queryset(self):
        return Modalidad.objects.select_related('plan_estudios').annotate(num_documentos=Count('tipos_documento')).order_by('plan_estudios__nombre', 'nombre')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['planes_exist'] = PlanEstudios.objects.exists()
        return ctx

class ModalidadCreateView(AdminRequeridoMixin, FormMessageMixin, CreateView):
    model = Modalidad
    form_class = ModalidadForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:modalidades')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nueva Modalidad'
        ctx['icono'] = 'bi-layers'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Modalidad creada exitosamente.')
        return super().form_valid(form)

class ModalidadUpdateView(AdminRequeridoMixin, FormMessageMixin, UpdateView):
    model = Modalidad
    form_class = ModalidadForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:modalidades')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Modalidad: {self.object.nombre}'
        ctx['icono'] = 'bi-layers'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Modalidad actualizada exitosamente.')
        return super().form_valid(form)

class ModalidadDeleteView(AdminRequeridoMixin, DeleteView):
    model = Modalidad
    template_name = 'administracion/catalogos/confirmar_eliminar.html'
    success_url = reverse_lazy('administracion:modalidades')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Eliminar Modalidad'
        ctx['mensaje'] = f'¿Estás seguro que deseas eliminar la modalidad "{self.object.nombre}"?'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Modalidad eliminada exitosamente.')
        return super().form_valid(form)

# --- TIPOS DE DOCUMENTOS ---

class TipoDocumentoListView(AdminRequeridoMixin, ListView):
    model = Modalidad
    template_name = 'administracion/catalogos/documentos_lista.html'
    context_object_name = 'modalidades'
    
    def get_queryset(self):
        # Pre-cargar los documentos ordenados para cada modalidad
        documentos_ordenados = TipoDocumento.objects.order_by('orden')
        prefetch = Prefetch('tipos_documento', queryset=documentos_ordenados)
        
        return Modalidad.objects.select_related('plan_estudios') \
            .prefetch_related(prefetch) \
            .annotate(num_docs=Count('tipos_documento')) \
            .annotate(has_docs=Case(
                When(num_docs__gt=0, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )) \
            .order_by('-has_docs', 'plan_estudios__nombre', 'nombre')

class TipoDocumentoCreateView(AdminRequeridoMixin, FormMessageMixin, CreateView):
    model = TipoDocumento
    form_class = TipoDocumentoForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:documentos')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Tipo de Documento'
        ctx['icono'] = 'bi-file-earmark-text'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        mod_id = self.request.GET.get('modalidad')
        if mod_id:
            initial['modalidad'] = mod_id
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de documento creado exitosamente.')
        return super().form_valid(form)

class TipoDocumentoUpdateView(AdminRequeridoMixin, FormMessageMixin, UpdateView):
    model = TipoDocumento
    form_class = TipoDocumentoForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:documentos')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Documento: {self.object.nombre}'
        ctx['icono'] = 'bi-file-earmark-text'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de documento actualizado exitosamente.')
        return super().form_valid(form)

class TipoDocumentoDeleteView(AdminRequeridoMixin, DeleteView):
    model = TipoDocumento
    template_name = 'administracion/catalogos/confirmar_eliminar.html'
    success_url = reverse_lazy('administracion:documentos')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Eliminar Tipo de Documento'
        ctx['mensaje'] = f'¿Estás seguro que deseas eliminar el documento "{self.object.nombre}"?'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de documento eliminado exitosamente.')
        return super().form_valid(form)

class TipoDocumentoReorderView(AdminRequeridoMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            orden_ids = data.get('orden_ids', [])
            
            # Actualizar el orden de los IDs recibidos
            for i, doc_id in enumerate(orden_ids):
                TipoDocumento.objects.filter(pk=doc_id).update(orden=i + 1)
                
            return JsonResponse({'status': 'success', 'message': 'Orden guardado.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# ═══════════════════════════════════════════════════════════════════════════════
# DEPARTAMENTOS
# ═══════════════════════════════════════════════════════════════════════════════

from administracion.models import Departamento, Profesor
from administracion.forms import DepartamentoForm, ProfesorForm

class DepartamentoListView(AdminRequeridoMixin, ListView):
    model = Departamento
    template_name = 'administracion/registros/departamentos_lista.html'
    context_object_name = 'departamentos'
    ordering = ['nombre']


class DepartamentoCreateView(AdminRequeridoMixin, FormMessageMixin, CreateView):
    model = Departamento
    form_class = DepartamentoForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:departamentos')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Departamento'
        ctx['icono'] = 'bi-building'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Departamento creado exitosamente.')
        return super().form_valid(form)


class DepartamentoUpdateView(AdminRequeridoMixin, FormMessageMixin, UpdateView):
    model = Departamento
    form_class = DepartamentoForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:departamentos')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Departamento'
        ctx['icono'] = 'bi-pencil-square'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Departamento actualizado exitosamente.')
        return super().form_valid(form)


class DepartamentoDeleteView(AdminRequeridoMixin, DeleteView):
    model = Departamento
    template_name = 'administracion/catalogos/confirmar_eliminar.html'
    success_url = reverse_lazy('administracion:departamentos')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Eliminar Departamento'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Departamento eliminado exitosamente.')
        return super().form_valid(form)


# ═══════════════════════════════════════════════════════════════════════════════
# PROFESORES / SINODALES
# ═══════════════════════════════════════════════════════════════════════════════

from django.db.models import Q

class ProfesorListView(AdminRequeridoMixin, ListView):
    model = Profesor
    template_name = 'administracion/registros/profesores_lista.html'
    context_object_name = 'profesores'
    ordering = ['last_name', 'first_name']

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(apellido_materno__icontains=q) |
                Q(cedula__icontains=q)
            )
        return qs


class ProfesorCreateView(AdminRequeridoMixin, FormMessageMixin, CreateView):
    model = Profesor
    form_class = ProfesorForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:profesores')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Profesor / Sinodal'
        ctx['icono'] = 'bi-person-badge'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Profesor creado exitosamente.')
        return super().form_valid(form)


class ProfesorUpdateView(AdminRequeridoMixin, FormMessageMixin, UpdateView):
    model = Profesor
    form_class = ProfesorForm
    template_name = 'administracion/catalogos/form_generico.html'
    success_url = reverse_lazy('administracion:profesores')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Profesor / Sinodal'
        ctx['icono'] = 'bi-pencil-square'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Profesor actualizado exitosamente.')
        return super().form_valid(form)


class ProfesorDeleteView(AdminRequeridoMixin, DeleteView):
    model = Profesor
    template_name = 'administracion/catalogos/confirmar_eliminar.html'
    success_url = reverse_lazy('administracion:profesores')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Eliminar Profesor / Sinodal'
        ctx['url_cancelar'] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Profesor eliminado exitosamente.')
        return super().form_valid(form)
