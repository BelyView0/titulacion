"""
Vistas del módulo Administración.
- Admin: gestión de usuarios, carreras, configuración del sistema.
- Jefe de Proyecto (Administración): vista de expedientes de su carrera,
  asignación de jurado, y estadísticas de titulados.
"""
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, TemplateView, DetailView
)
from django.views import View
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone

from expediente.mixins import AdminRequeridoMixin, JefeProyectoRequeridoMixin
from administracion.models import Carrera, Departamento
from expediente.models import (
    Expediente, Documento, AsignacionJurado,
    EstadoExpediente, EstadoDocumento
)
from expediente.notifications import notificar_alumno, registrar_cambio_estado

Usuario = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════════
# VISTAS PARA ROL: ADMIN (gestión de sistema)
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardAdminView(AdminRequeridoMixin, TemplateView):
    template_name = 'administracion/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_alumnos'] = Usuario.objects.filter(rol='ALUMNO').count()
        ctx['total_expedientes'] = Expediente.objects.count()
        ctx['expedientes_activos'] = Expediente.objects.exclude(
            estado__in=[EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO]
        ).count()
        ctx['expedientes_concluidos'] = Expediente.objects.filter(
            estado=EstadoExpediente.CONCLUIDO
        ).count()
        ctx['expedientes_recientes'] = Expediente.objects.select_related(
            'alumno', 'modalidad'
        ).order_by('-fecha_apertura')[:10]
        ctx['carreras'] = Carrera.objects.filter(activa=True).annotate(
            num_expedientes=Count('usuario__expediente')
        )
        return ctx


# ─── USUARIOS ────────────────────────────────────────────────
class UsuarioListView(AdminRequeridoMixin, ListView):
    model = Usuario
    template_name = 'administracion/usuarios/lista.html'
    context_object_name = 'usuarios'
    paginate_by = 20

    def get_queryset(self):
        qs = Usuario.objects.select_related('carrera').order_by('rol', 'last_name')
        rol = self.request.GET.get('rol')
        busqueda = self.request.GET.get('q')
        if rol:
            qs = qs.filter(rol=rol)
        if busqueda:
            qs = qs.filter(
                Q(first_name__icontains=busqueda) |
                Q(last_name__icontains=busqueda) |
                Q(username__icontains=busqueda) |
                Q(email__icontains=busqueda)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['rol_filtro'] = self.request.GET.get('rol', '')
        ctx['busqueda'] = self.request.GET.get('q', '')
        from administracion.models import Rol
        ctx['roles'] = Rol.choices
        return ctx


class UsuarioCreateView(AdminRequeridoMixin, CreateView):
    model = Usuario
    template_name = 'administracion/usuarios/form.html'
    fields = [
        'username', 'first_name', 'last_name', 'email', 'password',
        'rol', 'carrera', 'numero_empleado', 'telefono', 'genero', 'generacion'
    ]
    success_url = reverse_lazy('administracion:usuarios')

    def form_valid(self, form):
        usuario = form.save(commit=False)
        usuario.set_password(form.cleaned_data['password'])
        usuario.save()
        messages.success(self.request, f'Usuario {usuario.get_full_name()} creado exitosamente.')
        return super().form_valid(form)


class UsuarioUpdateView(AdminRequeridoMixin, UpdateView):
    model = Usuario
    template_name = 'administracion/usuarios/form.html'
    fields = [
        'first_name', 'last_name', 'email',
        'rol', 'carrera', 'numero_empleado', 'telefono', 'genero', 'generacion', 'is_active'
    ]
    success_url = reverse_lazy('administracion:usuarios')

    def form_valid(self, form):
        messages.success(self.request, 'Usuario actualizado exitosamente.')
        return super().form_valid(form)


# ─── CARRERAS ────────────────────────────────────────────────
class CarreraListView(AdminRequeridoMixin, ListView):
    model = Carrera
    template_name = 'administracion/carreras/lista.html'
    context_object_name = 'carreras'


class CarreraCreateView(AdminRequeridoMixin, CreateView):
    model = Carrera
    template_name = 'administracion/carreras/form.html'
    fields = ['nombre', 'clave', 'activa']
    success_url = reverse_lazy('administracion:carreras')

    def form_valid(self, form):
        messages.success(self.request, 'Carrera creada exitosamente.')
        return super().form_valid(form)


class CarreraUpdateView(AdminRequeridoMixin, UpdateView):
    model = Carrera
    template_name = 'administracion/carreras/form.html'
    fields = ['nombre', 'clave', 'activa']
    success_url = reverse_lazy('administracion:carreras')

    def form_valid(self, form):
        messages.success(self.request, 'Carrera actualizada.')
        return super().form_valid(form)


# ═══════════════════════════════════════════════════════════════════════════════
# VISTAS PARA ROL: JEFE DE PROYECTO (Administración / Jefes de carrera)
# Pueden ver expedientes de SU carrera y generar asignación de jurado
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardJefeProyectoView(JefeProyectoRequeridoMixin, TemplateView):
    template_name = 'administracion/jefe/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        carrera = self.request.user.carrera

        # Expedientes de la carrera del jefe de proyecto
        expedientes_carrera = Expediente.objects.filter(
            alumno__carrera=carrera
        ).select_related('alumno', 'modalidad')

        ctx['carrera'] = carrera
        ctx['total_expedientes'] = expedientes_carrera.count()
        ctx['expedientes_activos'] = expedientes_carrera.exclude(
            estado__in=[EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO]
        ).count()
        ctx['expedientes_concluidos'] = expedientes_carrera.filter(
            estado=EstadoExpediente.CONCLUIDO
        ).count()
        ctx['pendientes_jurado'] = expedientes_carrera.filter(
            estado=EstadoExpediente.EMPASTADO_RECIBIDO
        ).count()
        ctx['expedientes_recientes'] = expedientes_carrera.order_by(
            '-fecha_ultima_actualizacion'
        )[:10]
        return ctx


class ExpedienteListaJefeView(JefeProyectoRequeridoMixin, ListView):
    """Lista de expedientes filtrados por la carrera del jefe de proyecto."""
    template_name = 'administracion/jefe/expedientes_lista.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        carrera = self.request.user.carrera
        qs = Expediente.objects.filter(
            alumno__carrera=carrera
        ).select_related('alumno', 'modalidad').order_by('-fecha_ultima_actualizacion')

        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['carrera'] = self.request.user.carrera
        ctx['estado_filtro'] = self.request.GET.get('estado', '')
        ctx['estados'] = EstadoExpediente.choices
        return ctx


class ExpedienteDetalleJefeView(JefeProyectoRequeridoMixin, DetailView):
    """Vista de detalle de un expediente (solo lectura) para jefe de proyecto."""
    model = Expediente
    template_name = 'administracion/jefe/expediente_detalle.html'
    context_object_name = 'expediente'

    def get_queryset(self):
        # Solo puede ver expedientes de su carrera
        return Expediente.objects.filter(
            alumno__carrera=self.request.user.carrera
        ).select_related('alumno', 'modalidad')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['documentos'] = self.object.documentos.select_related(
            'tipo_documento'
        ).prefetch_related('validaciones').order_by('tipo_documento__orden')
        ctx['jurado'] = AsignacionJurado.objects.filter(
            expediente=self.object
        ).select_related('presidente', 'secretario', 'vocal').first()
        return ctx


class AsignacionJuradoJefeView(JefeProyectoRequeridoMixin, View):
    """
    El jefe de proyecto genera/actualiza la asignación de jurado
    para expedientes de su carrera.
    """

    def get(self, request, pk):
        expediente = get_object_or_404(
            Expediente, pk=pk, alumno__carrera=request.user.carrera
        )
        jurado = AsignacionJurado.objects.filter(expediente=expediente).first()
        # Obtener posibles sinodales (profesores de la misma carrera + académicos)
        sinodales = Usuario.objects.filter(
            Q(carrera=request.user.carrera) | Q(rol='ACADEMICO'),
            is_active=True
        ).exclude(rol='ALUMNO').order_by('last_name', 'first_name')

        from django.template.loader import render_to_string
        from django.http import HttpResponse
        context = {
            'expediente': expediente,
            'jurado': jurado,
            'sinodales': sinodales,
        }
        return HttpResponse(render_to_string(
            'administracion/jefe/jurado_asignar.html', context, request
        ))

    def post(self, request, pk):
        expediente = get_object_or_404(
            Expediente, pk=pk, alumno__carrera=request.user.carrera
        )

        presidente_id = request.POST.get('presidente')
        secretario_id = request.POST.get('secretario')
        vocal_id = request.POST.get('vocal')

        if not all([presidente_id, secretario_id, vocal_id]):
            messages.error(request, 'Debes asignar los tres miembros del jurado.')
            return redirect('administracion:jefe_jurado', pk=pk)

        if len({presidente_id, secretario_id, vocal_id}) < 3:
            messages.error(request, 'Los tres miembros del jurado deben ser personas diferentes.')
            return redirect('administracion:jefe_jurado', pk=pk)

        jurado, created = AsignacionJurado.objects.get_or_create(
            expediente=expediente,
            defaults={
                'presidente_id': presidente_id,
                'secretario_id': secretario_id,
                'vocal_id': vocal_id,
                'asignado_por': request.user,
                'fecha_carta': timezone.now().date(),
            }
        )
        if not created:
            jurado.presidente_id = presidente_id
            jurado.secretario_id = secretario_id
            jurado.vocal_id = vocal_id
            jurado.asignado_por = request.user
            jurado.fecha_carta = timezone.now().date()
            jurado.save()

        messages.success(request, 'Asignación de jurado registrada exitosamente.')

        # Actualizar estado del expediente
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.JURADO_ASIGNADO,
            realizado_por=request.user,
            descripcion=f'Jurado asignado por Jefe de Proyecto: Presidente {jurado.presidente}, Secretario {jurado.secretario}, Vocal {jurado.vocal}'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Jurado asignado para tu examen profesional',
            mensaje=f'Se ha asignado el jurado para tu acto protocolario. Presidente: {jurado.presidente.get_full_name()}.',
        )

        return redirect('administracion:jefe_detalle', pk=pk)


class EstadisticasJefeView(JefeProyectoRequeridoMixin, TemplateView):
    """
    Estadísticas de titulación para el Jefe de Proyecto:
    - Titulados por género (hombres, mujeres)
    - Titulados por generación
    - Porcentaje de titulados vs expedientes abiertos
    """
    template_name = 'administracion/jefe/estadisticas.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        carrera = self.request.user.carrera

        # Todos los expedientes de la carrera
        expedientes_carrera = Expediente.objects.filter(
            alumno__carrera=carrera
        ).select_related('alumno')

        total_expedientes = expedientes_carrera.count()
        expedientes_concluidos = expedientes_carrera.filter(
            estado=EstadoExpediente.CONCLUIDO
        )
        total_concluidos = expedientes_concluidos.count()
        expedientes_activos = expedientes_carrera.exclude(
            estado__in=[EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO]
        ).count()
        expedientes_cancelados = expedientes_carrera.filter(
            estado=EstadoExpediente.CANCELADO
        ).count()

        # Porcentaje de titulados
        porcentaje_titulados = round(
            (total_concluidos / total_expedientes * 100) if total_expedientes > 0 else 0, 1
        )

        # Titulados por género
        titulados_hombres = expedientes_concluidos.filter(alumno__genero='M').count()
        titulados_mujeres = expedientes_concluidos.filter(alumno__genero='F').count()
        titulados_otro = total_concluidos - titulados_hombres - titulados_mujeres

        # Titulados por generación
        titulados_por_generacion = (
            expedientes_concluidos
            .filter(alumno__generacion__isnull=False)
            .values('alumno__generacion')
            .annotate(total=Count('id'))
            .order_by('-alumno__generacion')
        )

        # Expedientes por estado (para gráfica)
        expedientes_por_estado = (
            expedientes_carrera
            .values('estado')
            .annotate(total=Count('id'))
            .order_by('estado')
        )
        # Convertir a display
        estado_display = dict(EstadoExpediente.choices)
        expedientes_por_estado_display = [
            {
                'estado': estado_display.get(item['estado'], item['estado']),
                'total': item['total'],
                'clave': item['estado'],
            }
            for item in expedientes_por_estado
        ]

        ctx.update({
            'carrera': carrera,
            'total_expedientes': total_expedientes,
            'total_concluidos': total_concluidos,
            'expedientes_activos': expedientes_activos,
            'expedientes_cancelados': expedientes_cancelados,
            'porcentaje_titulados': porcentaje_titulados,
            'titulados_hombres': titulados_hombres,
            'titulados_mujeres': titulados_mujeres,
            'titulados_otro': titulados_otro,
            'titulados_por_generacion': titulados_por_generacion,
            'expedientes_por_estado': expedientes_por_estado_display,
        })
        return ctx
