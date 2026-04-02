"""
Vistas del módulo Académico (División de Estudios Profesionales).
Revisión inicial de expediente, validación de documentos, empastado, jurado, acto.
"""
from django.views.generic import TemplateView, ListView, View, CreateView, UpdateView, DetailView
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone

from expediente.mixins import AcademicoRequeridoMixin
from expediente.models import (
    Expediente, Documento, ValidacionDocumento,
    RecepcionEmpastado, AsignacionJurado, ActoProtocolario,
    EstadoExpediente, EstadoDocumento, EstadoValidacion
)
from expediente.notifications import notificar_alumno, registrar_cambio_estado, registrar_cambio_documento
from expediente.workflow import actualizar_estado_documento, verificar_avance_expediente
from administracion.models import Usuario


class DashboardAcademicoView(AcademicoRequeridoMixin, TemplateView):
    template_name = 'academico/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['expedientes_para_revision_inicial'] = Expediente.objects.filter(
            estado=EstadoExpediente.EN_REVISION_ACADEMICO
        ).count()
        ctx['documentos_para_revisar'] = Documento.objects.filter(
            expediente__estado=EstadoExpediente.EN_REVISION_DOCUMENTOS,
            estado=EstadoDocumento.CARGADO
        ).count()
        ctx['expedientes_empastado_pendiente'] = Expediente.objects.filter(
            estado=EstadoExpediente.EMPASTADO_PENDIENTE
        ).count()
        ctx['expedientes_jurado_pendiente'] = Expediente.objects.filter(
            estado=EstadoExpediente.EMPASTADO_RECIBIDO
        ).count()
        ctx['expedientes_recientes'] = Expediente.objects.filter(
            estado__in=[
                EstadoExpediente.EN_REVISION_ACADEMICO,
                EstadoExpediente.DOCUMENTOS_PENDIENTES,
                EstadoExpediente.EN_REVISION_DOCUMENTOS,
                EstadoExpediente.EMPASTADO_PENDIENTE,
                EstadoExpediente.EMPASTADO_RECIBIDO,
                EstadoExpediente.JURADO_ASIGNADO,
                EstadoExpediente.ACTO_PROGRAMADO,
            ]
        ).select_related('alumno', 'modalidad').order_by('-fecha_ultima_actualizacion')[:10]
        return ctx


class ExpedienteListaAcademicoView(AcademicoRequeridoMixin, ListView):
    model = Expediente
    template_name = 'academico/expedientes/lista.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        qs = Expediente.objects.select_related(
            'alumno', 'modalidad', 'alumno__carrera'
        ).order_by('-fecha_ultima_actualizacion')
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estado_filtro'] = self.request.GET.get('estado', '')
        ctx['estados'] = EstadoExpediente.choices
        return ctx


class ExpedienteDetalleAcademicoView(AcademicoRequeridoMixin, DetailView):
    model = Expediente
    template_name = 'academico/expedientes/detalle.html'
    context_object_name = 'expediente'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.object
        ctx['documentos'] = expediente.documentos.select_related(
            'tipo_documento'
        ).prefetch_related('validaciones').order_by('tipo_documento__orden')
        ctx['historial'] = expediente.historial.select_related('realizado_por')[:15]
        return ctx


class ValidarExpedienteInicialView(AcademicoRequeridoMixin, View):
    """División aprueba o rechaza el expediente inicial del alumno."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk,
                                        estado=EstadoExpediente.EN_REVISION_ACADEMICO)
        accion = request.POST.get('accion')
        observaciones = request.POST.get('observaciones', '').strip()

        if accion == 'APROBAR':
            expediente.observaciones_division = observaciones
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.DOCUMENTOS_PENDIENTES,
                realizado_por=request.user,
                descripcion='División de Estudios aprobó la revisión inicial. Alumno debe cargar documentos.'
            )
            notificar_alumno(
                expediente=expediente,
                tipo='APROBADO',
                titulo='División de Estudios aprobó tu expediente inicial',
                mensaje='Tu expediente inicial fue revisado y aprobado. Ahora debes cargar todos los documentos requeridos en el sistema.',
            )
            messages.success(request, 'Expediente aprobado. El alumno puede cargar sus documentos.')

        elif accion == 'RECHAZAR':
            expediente.observaciones_division = observaciones
            expediente.save(update_fields=['observaciones_division'])
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.EN_CORRECCION,
                realizado_por=request.user,
                descripcion=f'División rechazó el expediente inicial. Observaciones: {observaciones}'
            )
            # Luego volver a BORRADOR para que el alumno pueda reenviar
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.BORRADOR,
                realizado_por=request.user,
                descripcion='Expediente devuelto al alumno para corrección.'
            )
            notificar_alumno(
                expediente=expediente,
                tipo='RECHAZADO',
                titulo='Tu expediente requiere correcciones',
                mensaje=f'División de Estudios ha regresado tu expediente con las siguientes observaciones: {observaciones}',
            )
            messages.warning(request, 'Expediente devuelto al alumno con observaciones.')

        return redirect('academico:expediente_detalle', pk=pk)


class ValidarDocumentoAcademicoView(AcademicoRequeridoMixin, View):
    """División revisa y valida un documento individual."""

    def post(self, request, pk):
        documento = get_object_or_404(Documento, pk=pk)
        accion = request.POST.get('accion')
        observaciones = request.POST.get('observaciones', '').strip()

        estado_map = {
            'APROBAR': EstadoValidacion.APROBADO,
            'RECHAZAR': EstadoValidacion.RECHAZADO,
            'CORRECCION': EstadoValidacion.REQUIERE_CORRECCION,
        }
        if accion not in estado_map:
            messages.error(request, 'Acción no válida.')
            return redirect('academico:expediente_detalle', pk=documento.expediente.pk)

        validacion, _ = ValidacionDocumento.objects.get_or_create(
            documento=documento,
            departamento='DIVISION',
        )
        validacion.estado = estado_map[accion]
        validacion.validado_por = request.user
        validacion.observaciones = observaciones
        if not validacion.fecha_primera_revision:
            validacion.fecha_primera_revision = timezone.now()
        validacion.save()

        # Actualizar estado del documento usando lógica compartida (requiere AMBOS departamentos)
        actualizar_estado_documento(documento)

        if accion == 'APROBAR':
            if documento.estado == EstadoDocumento.APROBADO:
                tipo_notif = 'APROBADO'
                msg_alumno = f'El documento "{documento.tipo_documento.nombre}" ha sido aprobado por todos los departamentos.'
            else:
                tipo_notif = 'INFO'
                msg_alumno = f'División de Estudios aprobó el documento "{documento.tipo_documento.nombre}". Pendiente revisión de Servicios Escolares.'
        elif accion == 'RECHAZAR':
            tipo_notif = 'RECHAZADO'
            msg_alumno = f'División de Estudios rechazó el documento "{documento.tipo_documento.nombre}". {observaciones}'
        else:
            tipo_notif = 'CORRECCION'
            msg_alumno = f'El documento "{documento.tipo_documento.nombre}" requiere correcciones. {observaciones}'

        registrar_cambio_documento(
            documento=documento,
            accion=f'División de Estudios: {accion}',
            realizado_por=request.user,
            observaciones=observaciones,
            departamento='DIVISION'
        )
        notificar_alumno(
            expediente=documento.expediente,
            tipo=tipo_notif,
            titulo=f'Revisión de documento — División',
            mensaje=msg_alumno,
        )

        # Verificar si el expediente puede avanzar (todos los docs aprobados por ambos)
        verificar_avance_expediente(documento.expediente)

        messages.success(request, f'Documento {accion.lower()}do.')
        return redirect('academico:expediente_detalle', pk=documento.expediente.pk)


class RecepcionEmpastadoView(AcademicoRequeridoMixin, CreateView):
    model = RecepcionEmpastado
    template_name = 'academico/empastado/recibir.html'
    fields = ['fecha_recepcion', 'estado', 'observaciones']

    def get_expediente(self):
        return get_object_or_404(Expediente, pk=self.kwargs['pk'],
                                  estado=EstadoExpediente.EMPASTADO_PENDIENTE)

    def form_valid(self, form):
        expediente = self.get_expediente()
        recepcion = form.save(commit=False)
        recepcion.expediente = expediente
        recepcion.recibido_por = self.request.user
        recepcion.save()

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.EMPASTADO_RECIBIDO,
            realizado_por=self.request.user,
            descripcion=f'División recibió el empastado. Estado: {recepcion.get_estado_display()}'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Empastado recibido por División de Estudios',
            mensaje='División de Estudios ha recibido y revisado tu trabajo empastado. El siguiente paso es la asignación de jurado.',
        )
        messages.success(self.request, 'Recepción de empastado registrada.')
        return redirect('academico:expediente_detalle', pk=expediente.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['expediente'] = self.get_expediente()
        return ctx


class AsignacionJuradoView(AcademicoRequeridoMixin, CreateView):
    model = AsignacionJurado
    template_name = 'academico/jurado/asignar.html'
    fields = ['presidente', 'secretario', 'vocal', 'fecha_carta', 'notas']

    def get_expediente(self):
        return get_object_or_404(Expediente, pk=self.kwargs['pk'],
                                  estado=EstadoExpediente.EMPASTADO_RECIBIDO)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        personal = Usuario.objects.filter(
            rol__in=['ACADEMICO', 'ADMIN']
        ).order_by('last_name')
        form.fields['presidente'].queryset = personal
        form.fields['secretario'].queryset = personal
        form.fields['vocal'].queryset = personal
        return form

    def form_valid(self, form):
        expediente = self.get_expediente()
        jurado = form.save(commit=False)
        jurado.expediente = expediente
        jurado.asignado_por = self.request.user
        jurado.save()

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.JURADO_ASIGNADO,
            realizado_por=self.request.user,
            descripcion=f'Jurado asignado: Presidente {jurado.presidente}, Secretario {jurado.secretario}, Vocal {jurado.vocal}'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Jurado asignado para tu examen profesional',
            mensaje=f'Se ha asignado el jurado para tu acto protocolario. Presidente: {jurado.presidente.get_full_name()}.',
        )
        messages.success(self.request, 'Jurado asignado exitosamente.')
        return redirect('academico:expediente_detalle', pk=expediente.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['expediente'] = self.get_expediente()
        return ctx


class ActoProtocolarioView(AcademicoRequeridoMixin, CreateView):
    model = ActoProtocolario
    template_name = 'academico/acto/programar.html'
    fields = ['fecha_acto', 'lugar', 'observaciones']

    def get_expediente(self):
        return get_object_or_404(Expediente, pk=self.kwargs['pk'],
                                  estado=EstadoExpediente.JURADO_ASIGNADO)

    def form_valid(self, form):
        expediente = self.get_expediente()
        acto = form.save(commit=False)
        acto.expediente = expediente
        acto.jurado = expediente.jurado
        acto.resultado = 'PENDIENTE'
        acto.programado_por = self.request.user
        acto.save()

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.ACTO_PROGRAMADO,
            realizado_por=self.request.user,
            descripcion=f'Acto protocolario programado para el {acto.fecha_acto} en {acto.lugar}'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='¡Tu examen profesional está programado!',
            mensaje=f'Tu acto protocolario ha sido programado para el {acto.fecha_acto.strftime("%d/%m/%Y a las %H:%M")} en {acto.lugar}.',
        )
        messages.success(self.request, 'Acto protocolario programado exitosamente.')
        return redirect('academico:expediente_detalle', pk=expediente.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['expediente'] = self.get_expediente()
        return ctx


class RegistrarResultadoActoView(AcademicoRequeridoMixin, UpdateView):
    model = ActoProtocolario
    template_name = 'academico/acto/resultado.html'
    fields = ['resultado', 'calificacion', 'observaciones']

    def form_valid(self, form):
        acto = form.save()
        expediente = acto.expediente
        if acto.resultado in ['APROBADO', 'APROBADO_MENCION']:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.CONCLUIDO,
                realizado_por=self.request.user,
                descripcion=f'Proceso concluido. Resultado del acto protocolario: {acto.get_resultado_display()}'
            )
            expediente.fecha_conclusion = timezone.now()
            expediente.save(update_fields=['fecha_conclusion'])
            notificar_alumno(
                expediente=expediente,
                tipo='APROBADO',
                titulo='¡Felicidades! Proceso de titulación concluido',
                mensaje=f'Has concluido exitosamente tu proceso de titulación. Resultado: {acto.get_resultado_display()}. ¡Enhorabuena!',
            )
        messages.success(self.request, f'Resultado registrado: {acto.get_resultado_display()}')
        return redirect('academico:expediente_detalle', pk=expediente.pk)