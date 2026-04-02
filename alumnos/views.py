"""
Vistas del módulo Alumnos.
Panel principal, expediente, documentos, timeline, notificaciones.
"""
from django.views.generic import (
    TemplateView, CreateView, UpdateView, ListView, View, DetailView
)
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone

from expediente.mixins import AlumnoRequeridoMixin, ExpedientePropioMixin
from expediente.models import (
    Expediente, Documento, EstadoDocumento, EstadoExpediente,
    Modalidad, TipoDocumento, HistorialExpediente
)
from expediente.notifications import registrar_cambio_estado
from alumnos.models import PerfilAlumno, Notificacion


class DashboardAlumnoView(AlumnoRequeridoMixin, TemplateView):
    template_name = 'alumnos/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['expediente'] = self.request.user.expediente
        except Expediente.DoesNotExist:
            ctx['expediente'] = None
        ctx['notificaciones_no_leidas'] = Notificacion.objects.filter(
            destinatario=self.request.user, leida=False
        ).count()
        ctx['notificaciones_recientes'] = Notificacion.objects.filter(
            destinatario=self.request.user
        ).order_by('-fecha')[:5]
        return ctx


class ExpedienteCreateView(AlumnoRequeridoMixin, CreateView):
    """El alumno crea su expediente inicial seleccionando modalidad."""
    model = Expediente
    template_name = 'alumnos/expediente/crear.html'
    fields = ['modalidad', 'titulo_trabajo', 'nombre_empresa', 'fotografia_digital']

    def dispatch(self, request, *args, **kwargs):
        # Si ya tiene expediente, redirigir al detalle
        if hasattr(request.user, 'expediente'):
            return redirect('alumnos:expediente')
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['modalidad'].queryset = Modalidad.objects.filter(activa=True).select_related('plan_estudios')
        return form

    def form_valid(self, form):
        expediente = form.save(commit=False)
        expediente.alumno = self.request.user
        expediente.estado = EstadoExpediente.BORRADOR
        expediente.save()

        # Crear documentos pendientes basados en la modalidad seleccionada
        tipos = TipoDocumento.objects.filter(
            modalidad=expediente.modalidad
        ).order_by('orden')
        for tipo in tipos:
            Documento.objects.create(
                expediente=expediente,
                tipo_documento=tipo,
                estado=EstadoDocumento.PENDIENTE,
            )

        # Registrar en historial
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.BORRADOR,
            realizado_por=self.request.user,
            descripcion='Expediente creado por el alumno.'
        )

        # Marcar la foto física si subió digital
        if expediente.fotografia_digital:
            expediente.fotografia_fisica_entregada = False  # pendiente físico
            expediente.save(update_fields=['fotografia_fisica_entregada'])

        messages.success(self.request,
            '¡Expediente creado! Ahora puedes cargar tus documentos requeridos.')
        return redirect('alumnos:expediente')


class ExpedienteDetalleView(ExpedientePropioMixin, TemplateView):
    template_name = 'alumnos/expediente/detalle.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.get_expediente()
        if not expediente:
            return ctx
        ctx['expediente'] = expediente
        ctx['documentos'] = expediente.documentos.select_related(
            'tipo_documento'
        ).prefetch_related('validaciones').order_by('tipo_documento__orden')
        ctx['historial'] = expediente.historial.select_related('realizado_por').all()[:10]
        return ctx


class SolicitarRevisionView(ExpedientePropioMixin, View):
    """El alumno envía su expediente a revisión de División de Estudios."""

    def post(self, request, *args, **kwargs):
        expediente = self.get_expediente()
        if not expediente:
            messages.error(request, 'No tienes expediente activo.')
            return redirect('alumnos:dashboard')

        if expediente.estado != EstadoExpediente.BORRADOR:
            messages.error(request, 'Tu expediente no está en estado Borrador.')
            return redirect('alumnos:expediente')

        from expediente.notifications import notificar_alumno
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.EN_REVISION_ACADEMICO,
            realizado_por=request.user,
            descripcion='Alumno envió expediente a revisión de División de Estudios.'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Expediente enviado a revisión',
            mensaje='Tu expediente ha sido enviado a División de Estudios para revisión inicial.',
            url=reverse('alumnos:expediente')
        )
        messages.success(request, 'Expediente enviado a revisión de División de Estudios.')
        return redirect('alumnos:expediente')


class EnviarDocumentosRevisionView(ExpedientePropioMixin, View):
    """El alumno envía sus documentos cargados a revisión de Escolares y Académico."""

    def post(self, request, *args, **kwargs):
        expediente = self.get_expediente()
        if not expediente:
            messages.error(request, 'No tienes expediente activo.')
            return redirect('alumnos:dashboard')

        if expediente.estado not in [EstadoExpediente.DOCUMENTOS_PENDIENTES, EstadoExpediente.RECHAZADO_CDMX]:
            messages.error(request, 'Tu expediente no está en un estado que permita el envío de documentos.')
            return redirect('alumnos:expediente')

        # Verificar que todos los documentos obligatorios fueron cargados
        docs_obligatorios = expediente.documentos.filter(
            tipo_documento__es_obligatorio=True
        )
        docs_sin_cargar = docs_obligatorios.filter(estado=EstadoDocumento.PENDIENTE)

        if docs_sin_cargar.exists():
            nombres = ', '.join([d.tipo_documento.nombre for d in docs_sin_cargar[:3]])
            messages.error(
                request,
                f'Faltan documentos obligatorios por cargar: {nombres}...'
            )
            return redirect('alumnos:expediente')

        from expediente.notifications import notificar_alumno
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.EN_REVISION_DOCUMENTOS,
            realizado_por=request.user,
            descripcion='Alumno re-envió documentos a revisión tras correcciones (CDMX o Escolares).'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Documentos enviados a revisión',
            mensaje='Tus documentos han sido enviados a Servicios Escolares y División de Estudios para validación.',
            url=reverse('alumnos:expediente')
        )
        messages.success(request, '¡Documentos enviados a revisión! Escolares y División validarán tus documentos.')
        return redirect('alumnos:expediente')


class DocumentoCargarView(ExpedientePropioMixin, UpdateView):
    """El alumno carga o reemplaza un documento."""
    model = Documento
    template_name = 'alumnos/documentos/cargar.html'
    fields = ['archivo', 'notas_alumno']

    def get_object(self):
        return get_object_or_404(
            Documento,
            pk=self.kwargs['pk'],
            expediente__alumno=self.request.user
        )

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        # Solo permite cargar si está en estado que lo permita
        estados_permitidos = [
            EstadoDocumento.PENDIENTE,
            EstadoDocumento.RECHAZADO,
            EstadoDocumento.REQUIERE_CORRECCION,
        ]
        if obj.estado not in estados_permitidos:
            messages.warning(request, 'Este documento no requiere acción en este momento.')
            return redirect('alumnos:expediente')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        documento = form.save(commit=False)
        documento.estado = EstadoDocumento.CARGADO
        documento.version += 1
        documento.fecha_carga = timezone.now()
        documento.save()

        # Resetear validaciones anteriores
        documento.validaciones.all().delete()

        from expediente.notifications import registrar_cambio_documento
        registrar_cambio_documento(
            documento=documento,
            accion=f'Alumno cargó versión {documento.version} del documento.',
            realizado_por=self.request.user,
        )
        messages.success(self.request, f'Documento "{documento.tipo_documento.nombre}" cargado exitosamente.')
        return redirect('alumnos:expediente')


class NotificacionListView(AlumnoRequeridoMixin, ListView):
    model = Notificacion
    template_name = 'alumnos/notificaciones/lista.html'
    context_object_name = 'notificaciones'
    paginate_by = 20

    def get_queryset(self):
        # Marcar todas como leídas al entrar
        qs = Notificacion.objects.filter(destinatario=self.request.user).order_by('-fecha')
        qs.filter(leida=False).update(leida=True)
        return qs


class TimelineView(ExpedientePropioMixin, TemplateView):
    template_name = 'alumnos/expediente/timeline.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.get_expediente()
        ctx['expediente'] = expediente
        if expediente:
            ctx['historial'] = expediente.historial.select_related('realizado_por').all()

            # Etapas lineales del proceso para el mapa visual
            etapas_lineales = [
                (EstadoExpediente.BORRADOR, 'Borrador'),
                (EstadoExpediente.EN_REVISION_ACADEMICO, 'Revisión División'),
                (EstadoExpediente.DOCUMENTOS_PENDIENTES, 'Carga de Documentos'),
                (EstadoExpediente.EN_REVISION_DOCUMENTOS, 'Revisión Documentos'),
                (EstadoExpediente.LISTO_INTEGRACION, 'Listo Integración'),
                (EstadoExpediente.INTEGRADO, 'Integrado'),
                (EstadoExpediente.ENVIADO_CDMX, 'Enviado CDMX'),
                (EstadoExpediente.APROBADO_CDMX, 'Aprobado CDMX'),
                (EstadoExpediente.EMPASTADO_PENDIENTE, 'Empastado Pendiente'),
                (EstadoExpediente.EMPASTADO_RECIBIDO, 'Empastado Recibido'),
                (EstadoExpediente.JURADO_ASIGNADO, 'Jurado Asignado'),
                (EstadoExpediente.ACTO_PROGRAMADO, 'Acto Programado'),
                (EstadoExpediente.CONCLUIDO, 'Concluido'),
            ]
            ctx['estados_proceso'] = etapas_lineales

            # Determinar qué estados ya se pasaron
            valores_lineales = [e[0] for e in etapas_lineales]
            estado_actual = expediente.estado
            if estado_actual in valores_lineales:
                idx_actual = valores_lineales.index(estado_actual)
                ctx['estados_completados'] = valores_lineales[:idx_actual]
            else:
                ctx['estados_completados'] = []
        return ctx

