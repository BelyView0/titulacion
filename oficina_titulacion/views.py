"""
Vistas del módulo Oficina de Titulación (SIGET).
Fusiona flujos legados de Escolares y Académico.
"""
import secrets
from datetime import datetime, timedelta

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView, View

from administracion.models import Carrera
from expediente.mixins import OficinaTitulacionRequeridoMixin
from expediente.models import (
    ActoProtocolario,
    AsignacionJurado,
    CitaDocumentoFisico,
    ConfirmacionActo,
    Documento,
    EstadoDocumento,
    EstadoExpediente,
    EstadoValidacion,
    Expediente,
    GrupoProtocolo,
    LoteCitacion,
    Modalidad,
    PlanEstudios,
    ValidacionDocumento,
    ESTADOS_ACTIVOS_SIGET,
)
from expediente.notifications import (
    notificar_alumno,
    registrar_cambio_documento,
    registrar_cambio_estado,
)
from expediente.siget_utils import expediente_completo, paso_expediente_display
from expediente.workflow import actualizar_estado_documento, verificar_avance_expediente

from oficina_titulacion.pdf_constancia import (
    generar_certificacion_final_pdf,
    generar_oficio_publicacion_pdf,
)
from oficina_titulacion.services import intentar_generar_constancia_no_adeudos


def _parse_datetime(value):
    """Parsea fecha/hora desde formulario (YYYY-MM-DD HH:MM o ISO)."""
    if not value:
        return None
    value = value.strip()
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            dt = datetime.strptime(value, fmt)
            if timezone.is_naive(dt):
                return timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except ValueError:
            continue
    return None


class DashboardOficinaView(OficinaTitulacionRequeridoMixin, TemplateView):
    template_name = 'oficina_titulacion/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base_qs = Expediente.objects.exclude(
            estado__in=[EstadoExpediente.BORRADOR, EstadoExpediente.CANCELADO]
        )
        ctx['total_activos'] = base_qs.exclude(
            estado=EstadoExpediente.CONCLUIDO
        ).count()
        ctx['total_concluidos'] = Expediente.objects.filter(
            estado=EstadoExpediente.CONCLUIDO
        ).count()

        conteos = base_qs.values('estado').annotate(total=Count('id'))
        mapa = {r['estado']: r['total'] for r in conteos}
        ctx['conteos_estado'] = [
            {
                'codigo': codigo,
                'label': label,
                'total': mapa.get(codigo, 0),
            }
            for codigo, label in EstadoExpediente.choices
            if codigo in ESTADOS_ACTIVOS_SIGET or codigo == EstadoExpediente.CONCLUIDO
        ]
        ctx['citas_pendientes'] = CitaDocumentoFisico.objects.filter(
            estado__in=[
                CitaDocumentoFisico.EstadoCita.PROGRAMADA,
                CitaDocumentoFisico.EstadoCita.CONFIRMADA_ALUMNO,
                CitaDocumentoFisico.EstadoCita.REPROGRAMACION_SOLICITADA,
            ]
        ).count()
        ctx['en_revision'] = mapa.get(EstadoExpediente.EN_REVISION, 0)
        ctx['adeudos_revision'] = mapa.get(EstadoExpediente.ADEUDOS_EN_REVISION, 0)
        return ctx


class ExpedienteListaView(OficinaTitulacionRequeridoMixin, ListView):
    model = Expediente
    template_name = 'oficina_titulacion/lista.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        qs = Expediente.objects.exclude(
            estado=EstadoExpediente.BORRADOR
        ).select_related(
            'alumno', 'modalidad', 'alumno__carrera', 'plan_estudios', 'asesor'
        ).order_by('-fecha_ultima_actualizacion')

        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)

        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__unaccent__icontains=busqueda)
                | Q(alumno__last_name__unaccent__icontains=busqueda)
                | Q(alumno__username__unaccent__icontains=busqueda)
                | Q(alumno__numero_control__unaccent__icontains=busqueda)
            )

        carrera_id = self.request.GET.get('carrera', '')
        if carrera_id:
            qs = qs.filter(alumno__carrera_id=carrera_id)

        modalidad_id = self.request.GET.get('modalidad', '')
        if modalidad_id:
            qs = qs.filter(modalidad_id=modalidad_id)

        plan_id = self.request.GET.get('plan', '')
        if plan_id:
            qs = qs.filter(plan_estudios_id=plan_id)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estado_filtro'] = self.request.GET.get('estado', '')
        ctx['busqueda'] = self.request.GET.get('q', '')
        ctx['carrera_id'] = self.request.GET.get('carrera', '')
        ctx['modalidad_id'] = self.request.GET.get('modalidad', '')
        ctx['plan_id'] = self.request.GET.get('plan', '')
        ctx['estados'] = EstadoExpediente.choices
        ctx['carreras_filter'] = Carrera.objects.filter(activa=True)
        ctx['modalidades_filter'] = Modalidad.objects.all()
        ctx['planes_filter'] = PlanEstudios.objects.filter(activo=True)
        return ctx


class ExpedienteDetalleView(OficinaTitulacionRequeridoMixin, DetailView):
    model = Expediente
    template_name = 'oficina_titulacion/detalle.html'
    context_object_name = 'expediente'

    def get_queryset(self):
        return Expediente.objects.select_related(
            'alumno', 'modalidad', 'plan_estudios', 'asesor', 'alumno__carrera'
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.object
        ctx['documentos'] = expediente.documentos.select_related(
            'tipo_documento'
        ).prefetch_related('validacion__validado_por').order_by('tipo_documento__orden')
        ctx['historial'] = expediente.historial.select_related('realizado_por')[:20]
        ctx['citas'] = expediente.citas_fisicas.order_by('-fecha_hora')[:10]
        ctx['confirmaciones_adeudo'] = expediente.confirmaciones_adeudo.all()
        ctx['jurado'] = AsignacionJurado.objects.filter(expediente=expediente).select_related(
            'presidente', 'secretario', 'vocal_propietario', 'vocal_suplente'
        ).first()
        try:
            ctx['acto'] = expediente.acto_protocolario
        except ActoProtocolario.DoesNotExist:
            ctx['acto'] = None
        return ctx


class ValidarDocumentoView(OficinaTitulacionRequeridoMixin, View):
    """Validación única de documento por Oficina de Titulación."""

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
            return redirect('oficina_titulacion:expediente_detalle', pk=documento.expediente.pk)

        if not documento.puede_revisar_oficina():
            messages.error(request, 'Este documento no está listo para revisión.')
            return redirect('oficina_titulacion:expediente_detalle', pk=documento.expediente.pk)

        validacion, _ = ValidacionDocumento.objects.get_or_create(
            documento=documento,
            defaults={'departamento': 'OFICINA'},
        )
        validacion.estado = estado_map[accion]
        validacion.validado_por = request.user
        validacion.observaciones = observaciones
        if not validacion.fecha_primera_revision:
            validacion.fecha_primera_revision = timezone.now()
        validacion.save()

        actualizar_estado_documento(documento, realizado_por=request.user)

        participio = {
            'APROBAR': 'aprobado',
            'RECHAZAR': 'rechazado',
            'CORRECCION': 'marcado para corrección',
        }[accion]

        if accion == 'APROBAR':
            tipo_notif = 'APROBADO' if documento.estado == EstadoDocumento.APROBADO else 'INFO'
            msg_alumno = (
                f'El documento "{documento.tipo_documento.nombre}" fue aprobado por Oficina de Titulación.'
                if documento.estado == EstadoDocumento.APROBADO
                else f'Oficina de Titulación registró revisión favorable del documento "{documento.tipo_documento.nombre}".'
            )
        elif accion == 'RECHAZAR':
            tipo_notif = 'RECHAZADO'
            msg_alumno = (
                f'El documento "{documento.tipo_documento.nombre}" fue rechazado. '
                f'Observaciones: {observaciones}'
            )
        else:
            tipo_notif = 'CORRECCION'
            msg_alumno = (
                f'El documento "{documento.tipo_documento.nombre}" requiere correcciones. '
                f'Observaciones: {observaciones}'
            )

        registrar_cambio_documento(
            documento=documento,
            accion=f'Oficina de Titulación: {accion}',
            realizado_por=request.user,
            observaciones=observaciones,
            departamento='OFICINA',
        )
        notificar_alumno(
            expediente=documento.expediente,
            tipo=tipo_notif,
            titulo=f'Documento {participio} — Oficina de Titulación',
            mensaje=msg_alumno,
        )
        verificar_avance_expediente(documento.expediente)

        messages.success(request, f'Documento {participio}.')
        return redirect('oficina_titulacion:expediente_detalle', pk=documento.expediente.pk)


class AprobarExpedienteView(OficinaTitulacionRequeridoMixin, View):
    """Aprueba el expediente cuando todos los documentos obligatorios están listos."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        if expediente.estado not in (
            EstadoExpediente.EN_REVISION,
            EstadoExpediente.CARGA_DOCUMENTOS,
            EstadoExpediente.EN_REVISION_DOCUMENTOS,
        ):
            messages.error(request, 'El expediente no está en etapa de revisión.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        if not expediente.todos_documentos_aprobados():
            messages.error(request, 'Faltan documentos obligatorios por aprobar.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        observaciones = request.POST.get('observaciones', '').strip()
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.EXPEDIENTE_APROBADO,
            realizado_por=request.user,
            descripcion=observaciones or 'Expediente aprobado por Oficina de Titulación.',
        )
        notificar_alumno(
            expediente=expediente,
            tipo='APROBADO',
            titulo='Expediente aprobado',
            mensaje='Tu expediente fue aprobado. Se generará el Oficio de Autorización de Publicación.',
        )
        messages.success(request, 'Expediente aprobado correctamente.')
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)


class CitacionMasivaView(OficinaTitulacionRequeridoMixin, TemplateView):
    template_name = 'oficina_titulacion/citas.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['modo'] = 'masiva'
        ctx['planes'] = PlanEstudios.objects.filter(activo=True)
        ctx['carreras'] = Carrera.objects.filter(activa=True)
        ctx['candidatos'] = Expediente.objects.filter(
            estado=EstadoExpediente.CERTIFICADO_PENDIENTE_CITA
        ).select_related('alumno', 'alumno__carrera', 'plan_estudios')
        plan_id = self.request.GET.get('plan', '')
        carrera_id = self.request.GET.get('carrera', '')
        if plan_id:
            ctx['candidatos'] = ctx['candidatos'].filter(plan_estudios_id=plan_id)
        if carrera_id:
            ctx['candidatos'] = ctx['candidatos'].filter(alumno__carrera_id=carrera_id)
        ctx['plan_id'] = plan_id
        ctx['carrera_id'] = carrera_id
        return ctx

    def post(self, request, *args, **kwargs):
        fecha_hora = _parse_datetime(request.POST.get('fecha_hora', ''))
        lugar = request.POST.get('lugar', '').strip()
        notas = request.POST.get('notas', '').strip()
        criterio = request.POST.get('criterio', '').strip() or 'Citación masiva certificado'
        expediente_ids = request.POST.getlist('expediente_ids')

        if not fecha_hora or not lugar:
            messages.error(request, 'Indica fecha/hora y lugar de la cita.')
            return redirect('oficina_titulacion:citacion_masiva')

        if not expediente_ids:
            messages.error(request, 'Selecciona al menos un expediente.')
            return redirect('oficina_titulacion:citacion_masiva')

        expedientes = Expediente.objects.filter(
            pk__in=expediente_ids,
            estado=EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
        )
        if not expedientes.exists():
            messages.error(request, 'No hay expedientes válidos para citar.')
            return redirect('oficina_titulacion:citacion_masiva')

        lote = LoteCitacion.objects.create(
            criterio=criterio,
            tipo='CERTIFICADO',
            creado_por=request.user,
            notas=notas,
        )

        creadas = 0
        for expediente in expedientes:
            CitaDocumentoFisico.objects.create(
                expediente=expediente,
                tipo=CitaDocumentoFisico.TipoCita.CERTIFICADO,
                fecha_hora=fecha_hora,
                lugar=lugar,
                notas=notas,
                lote=lote,
                creado_por=request.user,
            )
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA,
                realizado_por=request.user,
                descripcion=f'Cita para firma de certificado programada ({fecha_hora:%d/%m/%Y %H:%M}).',
            )
            notificar_alumno(
                expediente=expediente,
                tipo='AVANCE',
                titulo='Cita para certificado programada',
                mensaje=f'Se programó cita para firma de certificado el {fecha_hora:%d/%m/%Y a las %H:%M} en {lugar}.',
            )
            creadas += 1

        messages.success(request, f'Se crearon {creadas} citas en el lote #{lote.pk}.')
        return redirect('oficina_titulacion:citas_pendientes')


class CitasPendientesView(OficinaTitulacionRequeridoMixin, ListView):
    model = CitaDocumentoFisico
    template_name = 'oficina_titulacion/citas.html'
    context_object_name = 'citas'
    paginate_by = 30

    def get_queryset(self):
        qs = CitaDocumentoFisico.objects.exclude(
            estado=CitaDocumentoFisico.EstadoCita.COMPLETADA
        ).exclude(
            estado=CitaDocumentoFisico.EstadoCita.CANCELADA
        ).select_related(
            'expediente', 'expediente__alumno', 'expediente__alumno__carrera', 'lote'
        ).order_by('fecha_hora')

        tipo = self.request.GET.get('tipo', '')
        if tipo:
            qs = qs.filter(tipo=tipo)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['modo'] = 'pendientes'
        ctx['tipo_filtro'] = self.request.GET.get('tipo', '')
        return ctx


class CompletarCitaView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        cita = get_object_or_404(CitaDocumentoFisico, pk=pk)
        expediente = cita.expediente

        if cita.estado == CitaDocumentoFisico.EstadoCita.COMPLETADA:
            messages.warning(request, 'La cita ya estaba completada.')
            return redirect('oficina_titulacion:citas_pendientes')

        cita.estado = CitaDocumentoFisico.EstadoCita.COMPLETADA
        cita.save(update_fields=['estado'])

        if cita.tipo == CitaDocumentoFisico.TipoCita.CERTIFICADO:
            if expediente.estado == EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA:
                registrar_cambio_estado(
                    expediente=expediente,
                    estado_nuevo=EstadoExpediente.CERTIFICADO_FIRMADO,
                    realizado_por=request.user,
                    descripcion='Cita de certificado completada. Pendiente digitalización.',
                )
            notificar_alumno(
                expediente=expediente,
                tipo='AVANCE',
                titulo='Cita de certificado completada',
                mensaje='Se registró la firma de su certificado. Oficina de Titulación digitalizará el documento.',
            )
        elif cita.tipo == CitaDocumentoFisico.TipoCita.OFICIO_PUBLICACION:
            if expediente.estado == EstadoExpediente.OFICIO_CITA_PROGRAMADA:
                registrar_cambio_estado(
                    expediente=expediente,
                    estado_nuevo=EstadoExpediente.OFICIO_FIRMADO,
                    realizado_por=request.user,
                    descripcion='Cita de oficio de publicación completada.',
                )
            notificar_alumno(
                expediente=expediente,
                tipo='AVANCE',
                titulo='Cita de oficio completada',
                mensaje='Se registró la firma del Oficio de Autorización de Publicación.',
            )

        messages.success(request, 'Cita marcada como completada.')
        redirect_pk = request.POST.get('redirect_expediente')
        if redirect_pk:
            return redirect('oficina_titulacion:expediente_detalle', pk=redirect_pk)
        return redirect('oficina_titulacion:citas_pendientes')


class AprobarReprogramacionView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        cita = get_object_or_404(
            CitaDocumentoFisico,
            pk=pk,
            estado=CitaDocumentoFisico.EstadoCita.REPROGRAMACION_SOLICITADA,
        )
        nueva_fecha = _parse_datetime(request.POST.get('nueva_fecha', ''))
        if not nueva_fecha:
            nueva_fecha = cita.propuesta_alumno_fecha
        if not nueva_fecha:
            messages.error(request, 'Indica la nueva fecha y hora.')
            return redirect('oficina_titulacion:citas_pendientes')

        cita.fecha_hora = nueva_fecha
        cita.estado = CitaDocumentoFisico.EstadoCita.PROGRAMADA
        cita.notas = request.POST.get('notas', cita.notas)
        cita.save()

        notificar_alumno(
            expediente=cita.expediente,
            tipo='INFO',
            titulo='Reprogramación de cita aprobada',
            mensaje=f'Su cita fue reprogramada para el {nueva_fecha:%d/%m/%Y a las %H:%M} en {cita.lugar}.',
        )
        messages.success(request, 'Reprogramación aprobada.')
        return redirect('oficina_titulacion:citas_pendientes')


class GenerarOficioPublicacionView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        if expediente.estado not in (
            EstadoExpediente.EXPEDIENTE_APROBADO,
            EstadoExpediente.OFICIO_GENERADO,
        ):
            messages.error(request, 'El expediente debe estar aprobado para generar el oficio.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        pdf = generar_oficio_publicacion_pdf(expediente)
        if pdf:
            expediente.oficio_publicacion_pdf.save(
                f'oficio_publicacion_{expediente.pk}.pdf',
                pdf,
                save=False,
            )

        if expediente.estado == EstadoExpediente.EXPEDIENTE_APROBADO:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.OFICIO_GENERADO,
                realizado_por=request.user,
                descripcion='Oficio de Autorización de Publicación generado.',
            )
        else:
            expediente.save(update_fields=['oficio_publicacion_pdf', 'fecha_ultima_actualizacion'])

        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Oficio de publicación generado',
            mensaje='Se generó su Oficio de Autorización de Publicación. Oficina de Titulación programará cita para firma.',
        )
        messages.success(request, 'Oficio de publicación generado.')
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)


class ProgramarCitaOficioView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        if expediente.estado not in (
            EstadoExpediente.OFICIO_GENERADO,
            EstadoExpediente.OFICIO_CITA_PROGRAMADA,
        ):
            messages.error(request, 'El expediente no está listo para cita de oficio.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        fecha_hora = _parse_datetime(request.POST.get('fecha_hora', ''))
        lugar = request.POST.get('lugar', '').strip()
        notas = request.POST.get('notas', '').strip()

        if not fecha_hora or not lugar:
            messages.error(request, 'Indica fecha/hora y lugar.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        CitaDocumentoFisico.objects.create(
            expediente=expediente,
            tipo=CitaDocumentoFisico.TipoCita.OFICIO_PUBLICACION,
            fecha_hora=fecha_hora,
            lugar=lugar,
            notas=notas,
            creado_por=request.user,
        )

        if expediente.estado == EstadoExpediente.OFICIO_GENERADO:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.OFICIO_CITA_PROGRAMADA,
                realizado_por=request.user,
                descripcion=f'Cita para firma de oficio programada ({fecha_hora:%d/%m/%Y %H:%M}).',
            )

        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Cita para oficio de publicación',
            mensaje=f'Cita programada el {fecha_hora:%d/%m/%Y a las %H:%M} en {lugar}.',
        )
        messages.success(request, 'Cita de oficio programada.')
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)


class GenerarNoInconvenienciaView(OficinaTitulacionRequeridoMixin, View):
    """Genera o sube la Constancia de No Inconveniencia (adaptado de Escolares)."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        archivo = request.FILES.get('constancia_pdf')
        modo = request.POST.get('modo', 'generar')

        if modo == 'subir' and archivo:
            if not archivo.name.lower().endswith('.pdf'):
                messages.error(request, 'El archivo debe ser PDF.')
                return redirect('oficina_titulacion:expediente_detalle', pk=pk)
            expediente.constancia_no_inconveniencia = archivo
            expediente.fecha_constancia = timezone.now()
            expediente.save(update_fields=[
                'constancia_no_inconveniencia', 'fecha_constancia', 'fecha_ultima_actualizacion',
            ])
        else:
            from oficina_titulacion.pdf_constancia import generar_constancia_pdf

            try:
                pdf_bytes = generar_constancia_pdf(expediente)
            except Exception as exc:
                messages.error(request, f'Error al generar PDF: {exc}')
                return redirect('oficina_titulacion:expediente_detalle', pk=pk)

            expediente.constancia_no_inconveniencia.save(
                f'no_inconveniencia_{expediente.pk}.pdf',
                ContentFile(pdf_bytes),
                save=False,
            )
            expediente.fecha_constancia = timezone.now()
            expediente.save(update_fields=[
                'constancia_no_inconveniencia', 'fecha_constancia', 'fecha_ultima_actualizacion',
            ])

        if expediente.estado == EstadoExpediente.PAGO_VALIDADO:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.ADEUDOS_EN_REVISION,
                realizado_por=request.user,
                descripcion='Constancia de No Inconveniencia generada/cargada.',
            )

        intentar_generar_constancia_no_adeudos(expediente, request.user)

        notificar_alumno(
            expediente=expediente,
            tipo='INFO',
            titulo='Constancia de No Inconveniencia disponible',
            mensaje='Se registró su Constancia de No Inconveniencia en el expediente.',
        )
        messages.success(request, 'Constancia de No Inconveniencia registrada.')
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)


class GrupoProtocoloListCreateView(OficinaTitulacionRequeridoMixin, ListView):
    model = GrupoProtocolo
    template_name = 'oficina_titulacion/protocolo_lista.html'
    context_object_name = 'grupos'
    paginate_by = 20

    def get_queryset(self):
        return GrupoProtocolo.objects.annotate(
            num_actos=Count('actos')
        ).order_by('-fecha')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pendientes = Expediente.objects.filter(
            estado=EstadoExpediente.JURADO_ASIGNADO
        ).select_related('alumno', 'alumno__carrera')
        for grupo in ctx['grupos']:
            grupo.expedientes_pendientes = pendientes
        return ctx

    def post(self, request, *args, **kwargs):
        nombre = request.POST.get('nombre', '').strip()
        fecha = request.POST.get('fecha', '').strip()
        hora_inicio = request.POST.get('hora_inicio', '').strip()
        lugar = request.POST.get('lugar', '').strip()
        criterio = request.POST.get('criterio', '').strip()
        es_egel = request.POST.get('es_egel') == 'on'
        intervalo = request.POST.get('intervalo_minutos', '30')

        if not all([nombre, fecha, hora_inicio, lugar]):
            messages.error(request, 'Completa nombre, fecha, hora y lugar del grupo.')
            return redirect('oficina_titulacion:grupos_protocolo')

        try:
            intervalo_int = max(5, int(intervalo))
        except ValueError:
            intervalo_int = 30

        GrupoProtocolo.objects.create(
            nombre=nombre,
            criterio=criterio,
            fecha=fecha,
            hora_inicio=hora_inicio,
            lugar=lugar,
            es_egel=es_egel,
            intervalo_minutos=intervalo_int,
            creado_por=request.user,
        )
        messages.success(request, 'Grupo de protocolo creado.')
        return redirect('oficina_titulacion:grupos_protocolo')


class AsignarProtocoloView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        grupo = get_object_or_404(GrupoProtocolo, pk=pk)
        expediente_ids = request.POST.getlist('expediente_ids')

        if not expediente_ids:
            messages.error(request, 'Selecciona expedientes para asignar.')
            return redirect('oficina_titulacion:grupos_protocolo')

        expedientes = Expediente.objects.filter(
            pk__in=expediente_ids,
            estado=EstadoExpediente.JURADO_ASIGNADO,
        ).select_related('jurado')

        if not expedientes.exists():
            messages.error(request, 'Los expedientes deben tener jurado asignado (estado JURADO_ASIGNADO).')
            return redirect('oficina_titulacion:grupos_protocolo')

        base_dt = timezone.make_aware(
            datetime.combine(grupo.fecha, grupo.hora_inicio),
            timezone.get_current_timezone(),
        )
        intervalo = grupo.intervalo_minutos
        asignados = 0

        for idx, expediente in enumerate(expedientes):
            try:
                jurado = expediente.jurado
            except AsignacionJurado.DoesNotExist:
                continue

            hora_acto = base_dt + timedelta(minutes=intervalo * idx) if grupo.es_egel else base_dt

            acto, created = ActoProtocolario.objects.update_or_create(
                expediente=expediente,
                defaults={
                    'grupo': grupo,
                    'jurado': expediente.jurado,
                    'fecha_acto': hora_acto,
                    'hora_escalonada': hora_acto if grupo.es_egel else None,
                    'lugar': grupo.lugar,
                    'resultado': 'PENDIENTE',
                    'programado_por': request.user,
                },
            )

            if expediente.estado == EstadoExpediente.JURADO_ASIGNADO:
                registrar_cambio_estado(
                    expediente=expediente,
                    estado_nuevo=EstadoExpediente.PROTOCOLO_PROGRAMADO,
                    realizado_por=request.user,
                    descripcion=f'Protocolo programado en grupo "{grupo.nombre}" ({hora_acto:%d/%m/%Y %H:%M}).',
                )

            self._enviar_confirmaciones(request, acto, expediente)
            asignados += 1

        messages.success(request, f'{asignados} expediente(s) asignados al grupo "{grupo.nombre}".')
        return redirect('oficina_titulacion:grupos_protocolo')

    def _enviar_confirmaciones(self, request, acto, expediente):
        jurado = expediente.jurado
        if not jurado:
            return

        from django.conf import settings
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string

        participantes = [
            ('PRESIDENTE', jurado.presidente.get_nombre_corto(), jurado.presidente.email),
            ('SECRETARIO', jurado.secretario.get_nombre_corto(), jurado.secretario.email),
        ]
        if jurado.vocal_propietario:
            participantes.append(
                ('VOCAL_PROPIETARIO', jurado.vocal_propietario.get_nombre_corto(), jurado.vocal_propietario.email)
            )
        if jurado.vocal_suplente:
            participantes.append(
                ('VOCAL_SUPLENTE', jurado.vocal_suplente.get_nombre_corto(), jurado.vocal_suplente.email)
            )
        participantes.append(('ALUMNO', expediente.alumno.get_full_name(), expediente.alumno.email))

        fecha_fmt = acto.fecha_acto.strftime('%d de %B de %Y a las %H:%M')
        base_url = request.build_absolute_uri('/')[:-1]

        for rol, nombre, email in participantes:
            if not email:
                continue
            token = secrets.token_urlsafe(48)
            ConfirmacionActo.objects.update_or_create(
                acto=acto,
                rol=rol,
                defaults={
                    'nombre_participante': nombre,
                    'email': email,
                    'token': token,
                    'confirmado': False,
                },
            )
            confirm_url = f'{base_url}/confirmar/{token}/'
            rol_display = dict(ConfirmacionActo.ROL_CHOICES).get(rol, rol)

            if rol == 'ALUMNO':
                saludo = f'Estimado(a) {nombre},'
                mensaje = (
                    'Se programó su acto de recepción profesional. '
                    'Confirme su asistencia en la plataforma.'
                )
            else:
                saludo = f'Estimado(a) {nombre},'
                mensaje = (
                    f'Se le invita como {rol_display} al acto del alumno(a) '
                    f'{expediente.alumno.get_full_name()}.'
                )

            html_content = render_to_string('emails/notificacion_generica.html', {
                'titulo': 'Acto Protocolario',
                'saludo': saludo,
                'mensaje': mensaje,
                'datos_adicionales': {
                    'Alumno(a)': expediente.alumno.get_full_name(),
                    'Fecha y lugar': f'{fecha_fmt} en {acto.lugar}',
                },
                'url_accion': confirm_url if rol == 'ALUMNO' else None,
            })

            try:
                msg = EmailMultiAlternatives(
                    subject='[ITA Titulación] Confirme asistencia — Acto Protocolario',
                    body=f'{saludo}\n\n{mensaje}\n\n{confirm_url}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                msg.attach_alternative(html_content, 'text/html')
                msg.send(fail_silently=True)
            except Exception:
                pass

        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Acto protocolario programado',
            mensaje=f'Su acto está programado para el {fecha_fmt} en {acto.lugar}.',
        )


class ConfirmarActoView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        acto = get_object_or_404(ActoProtocolario, pk=pk)
        expediente = acto.expediente

        acto.resultado = 'APROBADO'
        acto.save(update_fields=['resultado'])

        if expediente.estado == EstadoExpediente.PROTOCOLO_PROGRAMADO:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.ACTO_REALIZADO,
                realizado_por=request.user,
                descripcion='Acto protocolario realizado y confirmado por Oficina de Titulación.',
            )

        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Acto protocolario realizado',
            mensaje='Se confirmó la realización de su acto protocolario.',
        )
        messages.success(request, 'Acto protocolario confirmado.')
        return redirect('oficina_titulacion:expediente_detalle', pk=expediente.pk)


class ReprogramarActoView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        acto = get_object_or_404(ActoProtocolario, pk=pk)
        expediente = acto.expediente
        nueva_fecha = _parse_datetime(request.POST.get('fecha_acto', ''))
        lugar = request.POST.get('lugar', '').strip() or acto.lugar

        if not nueva_fecha:
            messages.error(request, 'Indica la nueva fecha y hora del acto.')
            return redirect('oficina_titulacion:expediente_detalle', pk=expediente.pk)

        acto.fecha_acto = nueva_fecha
        acto.lugar = lugar
        acto.resultado = 'PENDIENTE'
        acto.observaciones = request.POST.get('observaciones', acto.observaciones)
        acto.save()

        acto.confirmaciones.update(confirmado=False)

        if expediente.estado != EstadoExpediente.PROTOCOLO_PROGRAMADO:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.PROTOCOLO_PROGRAMADO,
                realizado_por=request.user,
                descripcion=f'Acto reprogramado para {nueva_fecha:%d/%m/%Y %H:%M}.',
            )

        notificar_alumno(
            expediente=expediente,
            tipo='INFO',
            titulo='Acto protocolario reprogramado',
            mensaje=f'Su acto fue reprogramado para el {nueva_fecha:%d/%m/%Y a las %H:%M} en {lugar}.',
        )
        messages.success(request, 'Acto reprogramado.')
        return redirect('oficina_titulacion:expediente_detalle', pk=expediente.pk)


class GenerarCertificacionView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        if expediente.estado not in (
            EstadoExpediente.ACTO_REALIZADO,
            EstadoExpediente.CONCLUIDO,
        ):
            messages.error(request, 'El acto protocolario debe estar realizado.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        pdf = generar_certificacion_final_pdf(expediente)
        if pdf:
            expediente.certificacion_final_pdf.save(
                f'certificacion_{expediente.pk}.pdf',
                pdf,
                save=False,
            )
            expediente.save(update_fields=['certificacion_final_pdf', 'fecha_ultima_actualizacion'])

        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Certificación de exención generada',
            mensaje='Su Certificación de Exención de Examen Profesional está disponible en el sistema.',
        )
        messages.success(request, 'Certificación de exención generada.')
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)


class TablaGlobalAlumnosView(OficinaTitulacionRequeridoMixin, ListView):
    model = Expediente
    template_name = 'oficina_titulacion/tabla_global.html'
    context_object_name = 'expedientes'
    paginate_by = 50

    def get_queryset(self):
        return Expediente.objects.exclude(
            estado=EstadoExpediente.BORRADOR
        ).select_related(
            'alumno', 'alumno__carrera', 'modalidad', 'plan_estudios', 'asesor'
        ).order_by('alumno__carrera__nombre', 'alumno__first_name', 'alumno__last_name')

    def get(self, request, *args, **kwargs):
        if request.GET.get('export') == 'excel':
            return self._export_excel()
        return super().get(request, *args, **kwargs)

    def _export_excel(self):
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        qs = self.get_queryset()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Alumnos SIGET'

        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='1B396A', end_color='1B396A', fill_type='solid')
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'),
        )
        headers = [
            'Nombre', 'N° Control', 'Teléfono', 'Correo institucional', 'Correo alterno',
            'Carrera', 'Asesor', 'Plan', 'Modalidad', 'Expediente', 'Paso',
        ]

        for col, title in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=title)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')

        for row_num, exp in enumerate(qs, 2):
            alumno = exp.alumno
            asesor = ''
            if exp.asesor:
                asesor = exp.asesor.get_full_name()
            completo = 'Completo' if expediente_completo(exp) else 'Incompleto'
            row_data = [
                alumno.get_full_name(),
                alumno.numero_control or alumno.username,
                alumno.telefono or '',
                alumno.correo_institucional or '',
                alumno.email or '',
                alumno.carrera.nombre if alumno.carrera else '',
                asesor,
                exp.plan_estudios.nombre if exp.plan_estudios else '',
                exp.modalidad.nombre if exp.modalidad else '',
                completo,
                paso_expediente_display(exp.estado),
            ]
            for col, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col, value=value)
                cell.border = thin_border

        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 18
        ws.column_dimensions['A'].width = 35

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = (
            f'attachment; filename="Tabla_Global_Alumnos_{timezone.now():%Y%m%d_%H%M}.xlsx"'
        )
        wb.save(response)
        return response


class MarcarCertificadoListoView(OficinaTitulacionRequeridoMixin, View):
    """Digitaliza certificado firmado y avanza a carga de documentos."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        archivo = request.FILES.get('certificado_digital')

        if expediente.estado not in (
            EstadoExpediente.CERTIFICADO_FIRMADO,
            EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA,
        ):
            messages.error(request, 'El expediente no está en etapa de certificado firmado.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        if archivo:
            expediente.certificado_digital = archivo
            expediente.save(update_fields=['certificado_digital', 'fecha_ultima_actualizacion'])

        if expediente.estado == EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.CERTIFICADO_FIRMADO,
                realizado_por=request.user,
                descripcion='Certificado firmado registrado.',
            )

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.CARGA_DOCUMENTOS,
            realizado_por=request.user,
            descripcion='Certificado digitalizado. El alumno puede cargar documentos.',
        )

        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Certificado listo — Carga de documentos',
            mensaje='Su certificado fue registrado. Ya puede cargar los documentos de titulación en el sistema.',
        )
        messages.success(request, 'Certificado marcado como listo. Expediente en carga de documentos.')
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)
