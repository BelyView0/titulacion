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
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone

from expediente.mixins import AdminRequeridoMixin, JefeProyectoRequeridoMixin
from administracion.models import Carrera, Departamento, Usuario, Rol, ConfiguracionInstitucional, JefeDepartamento
from administracion.forms import UsuarioCreateForm, UsuarioUpdateForm, ConfiguracionInstitucionalForm, JefeDepartamentoForm
from expediente.models import (
    Expediente, Documento, AsignacionJurado,
    EstadoExpediente, EstadoDocumento
)
from expediente.notifications import notificar_alumno, registrar_cambio_estado

Usuario = get_user_model()


class ConfiguracionUpdateView(AdminRequeridoMixin, UpdateView):
    model = ConfiguracionInstitucional
    form_class = ConfiguracionInstitucionalForm
    template_name = 'administracion/configuracion.html'
    success_url = reverse_lazy('administracion:configuracion')

    def get_object(self, queryset=None):
        obj, created = ConfiguracionInstitucional.objects.get_or_create(id=1)
        return obj

    def form_valid(self, form):
        messages.success(self.request, 'Membretes institucionales actualizados correctamente.')
        return super().form_valid(form)


# ═══════════════════════════════════════════════════════════════════════════════
# VISTAS PARA JEFES DE DEPARTAMENTO
# ═══════════════════════════════════════════════════════════════════════════════
class JefeDepartamentoListView(AdminRequeridoMixin, ListView):
    model = JefeDepartamento
    template_name = 'administracion/jefe_departamento_list.html'
    context_object_name = 'jefes'

class JefeDepartamentoCreateView(AdminRequeridoMixin, CreateView):
    model = JefeDepartamento
    form_class = JefeDepartamentoForm
    template_name = 'administracion/jefe_departamento_form.html'
    success_url = reverse_lazy('administracion:jefes')
    
    def form_valid(self, form):
        messages.success(self.request, 'Jefe de Departamento creado correctamente.')
        return super().form_valid(form)

class JefeDepartamentoUpdateView(AdminRequeridoMixin, UpdateView):
    model = JefeDepartamento
    form_class = JefeDepartamentoForm
    template_name = 'administracion/jefe_departamento_form.html'
    success_url = reverse_lazy('administracion:jefes')

    def form_valid(self, form):
        messages.success(self.request, 'Jefe de Departamento actualizado correctamente.')
        return super().form_valid(form)

class JefeDepartamentoDeleteView(AdminRequeridoMixin, DeleteView):
    model = JefeDepartamento
    success_url = reverse_lazy('administracion:jefes')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Jefe de Departamento eliminado.')
        return super().delete(request, *args, **kwargs)

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

        # Expedientes con búsqueda y paginación
        qs = Expediente.objects.select_related(
            'alumno', 'modalidad', 'alumno__carrera'
        ).order_by('-fecha_apertura')
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__icontains=busqueda) |
                Q(alumno__last_name__icontains=busqueda) |
                Q(alumno__username__icontains=busqueda) |
                Q(alumno__numero_control__icontains=busqueda)
            )
        ctx['busqueda'] = busqueda
        paginator = Paginator(qs, 20)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['expedientes_recientes'] = page_obj
        ctx['page_obj'] = page_obj
        ctx['is_paginated'] = page_obj.has_other_pages()

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
    form_class = UsuarioCreateForm
    template_name = 'administracion/usuarios/form.html'
    success_url = reverse_lazy('administracion:usuarios')

    def form_valid(self, form):
        usuario = form.save(commit=False)
        usuario.set_password(form.cleaned_data['password'])
        usuario.save()
        messages.success(self.request, f'Usuario {usuario.get_full_name()} creado exitosamente.')
        return redirect(self.success_url)


class UsuarioUpdateView(AdminRequeridoMixin, UpdateView):
    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = 'administracion/usuarios/form.html'
    success_url = reverse_lazy('administracion:usuarios')

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Usuario actualizado exitosamente.')
        return redirect(self.success_url)


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
        user = self.request.user
        departamento = user.departamento

        # Expedientes de las carreras pertenecientes al departamento del jefe
        if departamento:
            expedientes_dept = Expediente.objects.filter(
                alumno__carrera__departamento=departamento
            )
        else:
            # Fallback a carrera si no hay departamento (compatibilidad)
            expedientes_dept = Expediente.objects.filter(
                alumno__carrera=user.carrera
            )
        
        expedientes_dept = expedientes_dept.select_related('alumno', 'modalidad', 'alumno__carrera')

        ctx['departamento'] = departamento
        ctx['carrera'] = user.carrera # Mantenemos carrera por compatibilidad en template
        ctx['total_expedientes'] = expedientes_dept.count()
        ctx['expedientes_activos'] = expedientes_dept.exclude(
            estado__in=[EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO]
        ).count()
        ctx['expedientes_concluidos'] = expedientes_dept.filter(
            estado=EstadoExpediente.CONCLUIDO
        ).count()
        ctx['pendientes_jurado'] = expedientes_dept.filter(
            estado=EstadoExpediente.EMPASTADO_RECIBIDO
        ).count()

        # Búsqueda y paginación
        qs = expedientes_dept.order_by('-fecha_ultima_actualizacion')
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__icontains=busqueda) |
                Q(alumno__last_name__icontains=busqueda) |
                Q(alumno__username__icontains=busqueda) |
                Q(alumno__numero_control__icontains=busqueda)
            )
        ctx['busqueda'] = busqueda
        paginator = Paginator(qs, 20)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['expedientes_recientes'] = page_obj
        ctx['page_obj'] = page_obj
        ctx['is_paginated'] = page_obj.has_other_pages()
        return ctx


class ExpedienteListaJefeView(JefeProyectoRequeridoMixin, ListView):
    """Lista de expedientes filtrados por la carrera del jefe de proyecto."""
    template_name = 'administracion/jefe/expedientes_lista.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        if user.departamento:
            qs = Expediente.objects.filter(alumno__carrera__departamento=user.departamento)
        else:
            qs = Expediente.objects.filter(alumno__carrera=user.carrera)

        qs = qs.select_related('alumno', 'modalidad').order_by('-fecha_ultima_actualizacion')

        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__icontains=busqueda) |
                Q(alumno__last_name__icontains=busqueda) |
                Q(alumno__username__icontains=busqueda) |
                Q(alumno__numero_control__icontains=busqueda)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['carrera'] = self.request.user.carrera
        ctx['estado_filtro'] = self.request.GET.get('estado', '')
        ctx['busqueda'] = self.request.GET.get('q', '')
        ctx['estados'] = EstadoExpediente.choices
        return ctx


class ExpedienteDetalleJefeView(JefeProyectoRequeridoMixin, DetailView):
    """Vista de detalle de un expediente (solo lectura) para jefe de proyecto."""
    model = Expediente
    template_name = 'administracion/jefe/expediente_detalle.html'
    context_object_name = 'expediente'

    def get_queryset(self):
        # Solo puede ver expedientes de su departamento
        user = self.request.user
        if user.departamento:
            return Expediente.objects.filter(
                alumno__carrera__departamento=user.departamento
            ).select_related('alumno', 'modalidad')
        return Expediente.objects.filter(
            alumno__carrera=user.carrera
        ).select_related('alumno', 'modalidad')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['documentos'] = self.object.documentos.select_related(
            'tipo_documento'
        ).prefetch_related('validaciones').order_by('tipo_documento__orden')
        ctx['jurado'] = AsignacionJurado.objects.filter(
            expediente=self.object
        ).select_related('presidente', 'secretario', 'vocal_propietario', 'vocal_suplente').first()
        return ctx


class AsignacionJuradoJefeView(JefeProyectoRequeridoMixin, View):
    """
    El jefe de proyecto genera/actualiza la asignación de jurado
    para expedientes de su carrera.
    """

    def get(self, request, pk):
        user = request.user
        if user.departamento:
            filter_q = Q(alumno__carrera__departamento=user.departamento)
        else:
            filter_q = Q(alumno__carrera=user.carrera)

        expediente = get_object_or_404(Expediente, Q(pk=pk) & filter_q)
        jurado = AsignacionJurado.objects.filter(expediente=expediente).first()

        # Obtener posibles sinodales desde el catálogo Profesor
        from administracion.models import Profesor
        sinodales = Profesor.objects.filter(activo=True).order_by('last_name', 'first_name')

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
        user = request.user
        if user.departamento:
            filter_q = Q(alumno__carrera__departamento=user.departamento)
        else:
            filter_q = Q(alumno__carrera=user.carrera)

        expediente = get_object_or_404(Expediente, Q(pk=pk) & filter_q)

        presidente_id = request.POST.get('presidente')
        secretario_id = request.POST.get('secretario')
        vocal_id = request.POST.get('vocal')
        suplente_id = request.POST.get('suplente')
        
        numero_oficio = request.POST.get('numero_oficio')
        fecha_acto = request.POST.get('fecha_acto')
        lugar_acto = request.POST.get('lugar_acto')

        if not all([presidente_id, secretario_id, vocal_id, suplente_id, numero_oficio, fecha_acto, lugar_acto]):
            messages.error(request, 'Debes llenar todos los campos (roles, oficio, fecha y lugar).')
            return redirect('administracion:jefe_jurado', pk=pk)

        if len({presidente_id, secretario_id, vocal_id, suplente_id}) < 4:
            messages.error(request, 'Los cuatro miembros del jurado deben ser personas diferentes.')
            return redirect('administracion:jefe_jurado', pk=pk)

        jurado, created = AsignacionJurado.objects.get_or_create(
            expediente=expediente,
            defaults={
                'presidente_id': presidente_id,
                'secretario_id': secretario_id,
                'vocal_propietario_id': vocal_id,
                'vocal_suplente_id': suplente_id,
                'numero_oficio': numero_oficio,
                'fecha_acto': fecha_acto,
                'lugar_acto': lugar_acto,
                'fecha_oficio': timezone.now().date(),
                'asignado_por': request.user,
            }
        )
        if not created:
            jurado.presidente_id = presidente_id
            jurado.secretario_id = secretario_id
            jurado.vocal_propietario_id = vocal_id
            jurado.vocal_suplente_id = suplente_id
            jurado.numero_oficio = numero_oficio
            jurado.fecha_acto = fecha_acto
            jurado.lugar_acto = lugar_acto
            jurado.fecha_oficio = timezone.now().date()
            jurado.asignado_por = request.user
            jurado.save()

        messages.success(request, 'Asignación de jurado registrada exitosamente.')

        # Actualizar estado del expediente
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.JURADO_ASIGNADO,
            realizado_por=request.user,
            descripcion=f'Jurado asignado. Oficio {numero_oficio}. Acto: {fecha_acto} en {lugar_acto}'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Jurado asignado para tu examen profesional',
            mensaje=f'Se ha asignado el jurado y fecha para tu acto protocolario. Fecha: {fecha_acto} en {lugar_acto}.',
        )

        # Enviar correos
        from django.core.mail import send_mail
        from django.conf import settings
        
        correos_destinos = [
            jurado.presidente.email,
            jurado.secretario.email,
            jurado.vocal_propietario.email,
            jurado.vocal_suplente.email,
            expediente.alumno.email
        ]
        correos_destinos = [c for c in correos_destinos if c]
        
        if correos_destinos:
            cuerpo = f'''Estimados Profesores y Alumno(a),

Se notifica que han sido designados como jurado para el acto de recepción profesional del alumno(a) {expediente.alumno.get_full_name()} ({expediente.alumno.carrera}).

Lugar: {lugar_acto}
Fecha y hora: {fecha_acto}

Jurado:
- Presidente: {jurado.presidente.get_nombre_con_titulo()}
- Secretario/a: {jurado.secretario.get_nombre_con_titulo()}
- Vocal Propietario/a: {jurado.vocal_propietario.get_nombre_con_titulo()}
- Vocal Suplente: {jurado.vocal_suplente.get_nombre_con_titulo()}

Instituto Tecnológico de Apizaco
'''
            send_mail(
                subject=f'{settings.EMAIL_SUBJECT_PREFIX}Oficio Asignación Jurado - {expediente.alumno.get_full_name()}',
                message=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=correos_destinos,
                fail_silently=True,
            )

        return redirect('administracion:jefe_detalle', pk=pk)


class DescargarOficioJuradoJefeView(JefeProyectoRequeridoMixin, View):
    """Descarga el PDF del Oficio de Asignación de Jurado."""
    def get(self, request, pk):
        user = request.user
        if user.departamento:
            filter_q = Q(alumno__carrera__departamento=user.departamento)
        else:
            filter_q = Q(alumno__carrera=user.carrera)

        expediente = get_object_or_404(Expediente, Q(pk=pk) & filter_q)
        asignacion = get_object_or_404(AsignacionJurado, expediente=expediente)

        from administracion.pdf_oficio import generar_oficio_jurado_pdf
        from django.http import HttpResponse

        pdf_bytes = generar_oficio_jurado_pdf(asignacion)
        
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f'Oficio_Jurado_{expediente.alumno.username}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class CalendarioJefeView(JefeProyectoRequeridoMixin, TemplateView):
    """Calendario de actos protocolarios para el Jefe de Proyecto."""
    template_name = 'administracion/jefe/calendario.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.departamento:
            ctx['carreras'] = Carrera.objects.filter(
                departamento=user.departamento, activa=True
            ).order_by('nombre')
        elif user.carrera:
            ctx['carreras'] = Carrera.objects.filter(
                pk=user.carrera_id, activa=True
            )
        else:
            ctx['carreras'] = Carrera.objects.filter(activa=True).order_by('nombre')
        return ctx


class EstadisticasJefeView(JefeProyectoRequeridoMixin, TemplateView):
    """
    Estadísticas de titulación para el Jefe de Proyecto (RE-01 a RE-07).
    Filtra por departamento del usuario.
    """
    template_name = 'administracion/jefe/estadisticas.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        departamento = user.departamento

        # ─── Base queryset por departamento ───────────────────────
        if departamento:
            qs_base = Expediente.objects.filter(
                alumno__carrera__departamento=departamento
            )
        else:
            qs_base = Expediente.objects.filter(
                alumno__carrera=user.carrera
            )

        qs = qs_base.select_related('alumno', 'modalidad')

        # ─── RE-01: Estudiantes que iniciaron proceso ──────────────
        total_expedientes = qs.count()

        # ─── RE-02: Estudiantes que concluyeron ────────────────────
        qs_concluidos = qs.filter(estado=EstadoExpediente.CONCLUIDO)
        total_concluidos = qs_concluidos.count()
        expedientes_activos = qs.exclude(
            estado__in=[EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO,
                        EstadoExpediente.BORRADOR]
        ).count()
        expedientes_cancelados = qs.filter(estado=EstadoExpediente.CANCELADO).count()

        porcentaje_titulados = round(
            (total_concluidos / total_expedientes * 100) if total_expedientes > 0 else 0, 1
        )

        # ─── RE-03: Estadísticas por género ───────────────────────
        # De todos los que iniciaron proceso
        iniciados_hombres = qs.filter(alumno__genero='M').count()
        iniciados_mujeres = qs.filter(alumno__genero='F').count()
        iniciados_sin_dato = total_expedientes - iniciados_hombres - iniciados_mujeres

        # De los titulados
        titulados_hombres = qs_concluidos.filter(alumno__genero='M').count()
        titulados_mujeres = qs_concluidos.filter(alumno__genero='F').count()
        titulados_sin_dato = total_concluidos - titulados_hombres - titulados_mujeres

        # ─── RE-04: Estadísticas por generación ───────────────────
        por_generacion = (
            qs.filter(alumno__generacion__isnull=False)
            .values('alumno__generacion')
            .annotate(
                total=Count('id'),
                concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO))
            )
            .order_by('-alumno__generacion')
        )

        # ─── RE-05: Por tipo de opción de titulación (modalidad) ──
        por_modalidad = (
            qs.filter(modalidad__isnull=False)
            .values('modalidad__nombre')
            .annotate(
                total=Count('id'),
                concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO))
            )
            .order_by('-total')
        )

        # ─── RE-06: Por carrera ────────────────────────────────────
        por_carrera = (
            qs.values('alumno__carrera__nombre')
            .annotate(
                total=Count('id'),
                concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO)),
                hombres=Count('id', filter=Q(alumno__genero='M')),
                mujeres=Count('id', filter=Q(alumno__genero='F')),
            )
            .order_by('-total')
        )

        # ─── Distribución por estado (RE-07 apoyo decisiones) ─────
        estado_display = dict(EstadoExpediente.choices)
        expedientes_por_estado = [
            {
                'estado': estado_display.get(item['estado'], item['estado']),
                'total': item['total'],
                'clave': item['estado'],
            }
            for item in (
                qs.values('estado')
                .annotate(total=Count('id'))
                .order_by('-total')
            )
        ]

        ctx.update({
            'departamento': departamento,
            # RE-01
            'total_expedientes': total_expedientes,
            # RE-02
            'total_concluidos': total_concluidos,
            'expedientes_activos': expedientes_activos,
            'expedientes_cancelados': expedientes_cancelados,
            'porcentaje_titulados': porcentaje_titulados,
            # RE-03 género
            'iniciados_hombres': iniciados_hombres,
            'iniciados_mujeres': iniciados_mujeres,
            'iniciados_sin_dato': iniciados_sin_dato,
            'titulados_hombres': titulados_hombres,
            'titulados_mujeres': titulados_mujeres,
            'titulados_sin_dato': titulados_sin_dato,
            # RE-04 generación
            'por_generacion': por_generacion,
            # RE-05 modalidad
            'por_modalidad': por_modalidad,
            # RE-06 carrera
            'por_carrera': por_carrera,
            # RE-07 distribución
            'expedientes_por_estado': expedientes_por_estado,
        })
        return ctx


class ToggleConfirmacionJefeView(JefeProyectoRequeridoMixin, View):
    """POST — Jefe de proyecto confirma/quita confirmación de un miembro del jurado."""

    def post(self, request, pk):
        from expediente.models import ConfirmacionActo
        from expediente.views_confirmacion import (
            _enviar_correo_confirmacion_recibida,
            _enviar_correo_acto_confirmado,
        )
        from django.contrib import messages
        from django.utils import timezone

        confirmacion = get_object_or_404(ConfirmacionActo, pk=pk)
        acto = confirmacion.acto
        expediente = acto.expediente

        if not confirmacion.confirmado:
            confirmacion.confirmado = True
            confirmacion.fecha_confirmacion = timezone.now()
            confirmacion.save()
            messages.success(request, f'Asistencia de {confirmacion.nombre_participante} confirmada.')

            _enviar_correo_confirmacion_recibida(confirmacion, acto)

            if acto.confirmaciones_completas():
                _enviar_correo_acto_confirmado(acto)
                messages.info(request, '¡Todas las confirmaciones completas! Se envió correo final a todos.')
        else:
            confirmacion.confirmado = False
            confirmacion.fecha_confirmacion = None
            confirmacion.save()
            messages.warning(request, f'Se quitó la confirmación de {confirmacion.nombre_participante}.')

        return redirect('administracion:jefe_detalle', pk=expediente.pk)
