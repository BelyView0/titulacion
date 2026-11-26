"""
Vistas del módulo Oficina de Titulación (SIGET).
Fusiona flujos legados de Escolares y Académico.
"""
import secrets
from datetime import datetime, timedelta

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView, View

import zipfile
from io import BytesIO
from pathlib import Path

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
    notificar_usuarios_por_rol,
    registrar_cambio_documento,
    registrar_cambio_estado,
)
from administracion.models import Rol
from expediente.siget_utils import expediente_completo, paso_expediente_display
from expediente.workflow import actualizar_estado_documento, verificar_avance_expediente

from oficina_titulacion.pdf_constancia import (
    generar_certificacion_final_pdf,
    generar_oficio_publicacion_pdf,
)
from oficina_titulacion.services import (
    intentar_generar_constancia_no_adeudos,
    forzar_regenerar_constancia_no_adeudos,
)


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


# Estados desde los que Oficina puede descargar el ZIP del expediente
ESTADOS_ZIP_EXPEDIENTE = frozenset({
    EstadoExpediente.EXPEDIENTE_APROBADO,
    EstadoExpediente.OFICIO_GENERADO,
    EstadoExpediente.OFICIO_CITA_PROGRAMADA,
    EstadoExpediente.OFICIO_FIRMADO,
    EstadoExpediente.PAGO_PENDIENTE,
    EstadoExpediente.PAGO_VALIDADO,
    EstadoExpediente.ADEUDOS_EN_REVISION,
    EstadoExpediente.DOCUMENTOS_OFICIALES_LISTOS,
    EstadoExpediente.JURADO_ASIGNADO,
    EstadoExpediente.PROTOCOLO_PROGRAMADO,
    EstadoExpediente.ACTO_REALIZADO,
    EstadoExpediente.CONCLUIDO,
    EstadoExpediente.EMPASTADO_PENDIENTE,
    EstadoExpediente.EMPASTADO_RECIBIDO,
})


def expediente_permite_zip(expediente):
    return expediente.estado in ESTADOS_ZIP_EXPEDIENTE


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

        from alumnos.models import Notificacion
        ctx['notificaciones_no_leidas'] = Notificacion.objects.filter(
            destinatario=self.request.user, leida=False
        ).count()
        ctx['notificaciones_recientes'] = Notificacion.objects.filter(
            destinatario=self.request.user
        ).order_by('-fecha')[:8]
        return ctx


class NotificacionesOficinaView(OficinaTitulacionRequeridoMixin, TemplateView):
    template_name = 'oficina_titulacion/notificaciones.html'

    def get_context_data(self, **kwargs):
        from alumnos.models import Notificacion
        from expediente.notifications import marcar_notificaciones_leidas

        ctx = super().get_context_data(**kwargs)
        marcar_notificaciones_leidas(self.request.user)
        ctx['notificaciones'] = Notificacion.objects.filter(
            destinatario=self.request.user,
        ).order_by('-fecha')[:50]
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
            from expediente.search_utils import q_busca
            qs = qs.filter(q_busca(
                busqueda,
                'alumno__first_name',
                'alumno__last_name',
                'alumno__username',
                'alumno__numero_control',
            ))

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
        ctx['puede_descargar_zip'] = expediente_permite_zip(expediente)
        return ctx


class ValidarDocumentoView(OficinaTitulacionRequeridoMixin, View):
    """Validación única de documento por Oficina de Titulación."""

    def _wants_json(self, request):
        return (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in (request.headers.get('Accept') or '')
        )

    def _respond(self, request, *, ok, message, documento=None, status=200):
        if self._wants_json(request):
            payload = {'ok': ok, 'message': message}
            if documento is not None:
                documento.refresh_from_db()
                val = documento.validacion_oficina
                payload.update({
                    'documento_id': documento.pk,
                    'estado': documento.estado,
                    'estado_display': documento.get_estado_display(),
                    'estado_color': documento.get_estado_color(),
                    'puede_revisar': documento.puede_revisar_oficina(),
                    'validacion_display': val.get_estado_display() if val else '',
                })
            return JsonResponse(payload, status=status if not ok else 200)
        if ok:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect(
            'oficina_titulacion:expediente_detalle',
            pk=documento.expediente.pk if documento else request.POST.get('expediente_id'),
        )

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
            return self._respond(request, ok=False, message='Acción no válida.', documento=documento, status=400)

        if not documento.puede_revisar_oficina():
            return self._respond(
                request, ok=False,
                message='Este documento no está listo para revisión.',
                documento=documento, status=400,
            )

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

        return self._respond(request, ok=True, message=f'Documento {participio}.', documento=documento)


class AprobarExpedienteView(OficinaTitulacionRequeridoMixin, View):
    """Aprueba el expediente cuando todos los documentos obligatorios están listos."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        if expediente.estado not in (
            EstadoExpediente.EN_REVISION,
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
            descripcion=observaciones or 'Expediente aprobado tras revisión documental.',
        )
        notificar_alumno(
            expediente=expediente,
            tipo='APROBADO',
            titulo='Expediente aprobado',
            mensaje='Tu expediente fue aprobado por Oficina de Titulación. Se generará el Oficio de Autorización de Publicación.',
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
        from expediente.workflow import habilitar_carga_documentos

        cita = get_object_or_404(CitaDocumentoFisico, pk=pk)
        expediente = cita.expediente

        if cita.estado == CitaDocumentoFisico.EstadoCita.COMPLETADA:
            messages.warning(request, 'La cita ya estaba completada.')
            return redirect('oficina_titulacion:citas_pendientes')

        if cita.tipo == CitaDocumentoFisico.TipoCita.CERTIFICADO:
            if cita.estado != CitaDocumentoFisico.EstadoCita.CONFIRMADA_ALUMNO:
                messages.error(
                    request,
                    'La cita de certificado debe estar confirmada por el alumno antes de marcarla como completada.',
                )
                redirect_pk = request.POST.get('redirect_expediente')
                if redirect_pk:
                    return redirect('oficina_titulacion:expediente_detalle', pk=redirect_pk)
                return redirect('oficina_titulacion:citas_pendientes')

        cita.estado = CitaDocumentoFisico.EstadoCita.COMPLETADA
        cita.save(update_fields=['estado'])

        if cita.tipo == CitaDocumentoFisico.TipoCita.CERTIFICADO:
            if expediente.estado == EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA:
                registrar_cambio_estado(
                    expediente=expediente,
                    estado_nuevo=EstadoExpediente.CERTIFICADO_FIRMADO,
                    realizado_por=request.user,
                    descripcion='Cita de certificado completada. Certificado firmado.',
                )
            habilitar_carga_documentos(expediente, realizado_por=request.user)
        elif cita.tipo == CitaDocumentoFisico.TipoCita.OFICIO_PUBLICACION:
            if expediente.estado == EstadoExpediente.OFICIO_CITA_PROGRAMADA:
                registrar_cambio_estado(
                    expediente=expediente,
                    estado_nuevo=EstadoExpediente.OFICIO_FIRMADO,
                    realizado_por=request.user,
                    descripcion='Cita de oficio de publicación completada.',
                )
                expediente.refresh_from_db()
            if expediente.estado == EstadoExpediente.OFICIO_FIRMADO:
                registrar_cambio_estado(
                    expediente=expediente,
                    estado_nuevo=EstadoExpediente.PAGO_PENDIENTE,
                    realizado_por=request.user,
                    descripcion='Oficio firmado. El expediente avanza a pago de titulación.',
                )
                expediente.pago_validado = 'PENDIENTE'
                expediente.save(update_fields=[
                    'pago_validado', 'fecha_ultima_actualizacion',
                ])
                notificar_usuarios_por_rol(
                    [Rol.FINANZAS],
                    'Preficha de pago pendiente',
                    f'{expediente.alumno.get_full_name()} requiere la generación de su preficha de pago de titulación.',
                    url=reverse('finanzas:expedientes_pago'),
                    tipo='URGENTE',
                )
            notificar_alumno(
                expediente=expediente,
                tipo='AVANCE',
                titulo='Oficio de publicación firmado',
                mensaje=(
                    'Se registró la firma del Oficio de Autorización de Publicación. '
                    'Finanzas generará tu preficha de depósito para que realices el pago de titulación.'
                ),
                url=reverse('alumnos:expediente'),
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
            return self._redirect(request, cita)

        lugar = request.POST.get('lugar', '').strip()
        if lugar:
            cita.lugar = lugar

        cita.fecha_hora = nueva_fecha
        cita.estado = CitaDocumentoFisico.EstadoCita.PROGRAMADA
        notas_oficina = request.POST.get('notas', '').strip()
        if notas_oficina:
            cita.notas = notas_oficina
        cita.propuesta_alumno_fecha = None
        cita.propuesta_alumno_notas = ''
        cita.save()

        notificar_alumno(
            expediente=cita.expediente,
            tipo='INFO',
            titulo='Nueva fecha de cita asignada',
            mensaje=(
                f'Su cita de {cita.get_tipo_display().lower()} fue reprogramada para el '
                f'{nueva_fecha:%d/%m/%Y a las %H:%M} en {cita.lugar}. '
                f'Confirme su asistencia en el sistema.'
            ),
            url=reverse('alumnos:expediente'),
        )
        messages.success(request, 'Cita reprogramada. El alumno fue notificado.')
        return self._redirect(request, cita)

    def _redirect(self, request, cita):
        if request.POST.get('redirect_expediente'):
            return redirect('oficina_titulacion:expediente_detalle', pk=cita.expediente_id)
        return redirect('oficina_titulacion:citas_pendientes')


class GenerarOficioPublicacionView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        if expediente.estado not in (
            EstadoExpediente.EXPEDIENTE_APROBADO,
            EstadoExpediente.OFICIO_GENERADO,
            EstadoExpediente.CERTIFICADO_FIRMADO,
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
        elif expediente.estado == EstadoExpediente.CERTIFICADO_FIRMADO:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.OFICIO_GENERADO,
                realizado_por=request.user,
                descripcion='Certificado registrado. Oficio de publicación generado.',
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


class DescargarExpedienteZipView(OficinaTitulacionRequeridoMixin, View):
    """ZIP con todos los documentos cargados: {control}_documentoN.ext"""

    def get(self, request, pk):
        expediente = get_object_or_404(
            Expediente.objects.select_related('alumno'),
            pk=pk,
        )
        if not expediente_permite_zip(expediente):
            messages.error(
                request,
                'El ZIP solo está disponible cuando el expediente ya fue aprobado.',
            )
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        documentos = (
            expediente.documentos
            .select_related('tipo_documento')
            .filter(archivo__isnull=False)
            .exclude(archivo='')
            .order_by('tipo_documento__orden', 'pk')
        )
        if not documentos.exists():
            messages.error(request, 'No hay documentos con archivo para empaquetar.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        alumno = expediente.alumno
        control = (alumno.numero_control or alumno.username or f'exp{expediente.pk}').strip()
        control_safe = ''.join(c for c in control if c.isalnum() or c in '-_') or f'exp{expediente.pk}'

        buffer = BytesIO()
        escritos = 0
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, doc in enumerate(documentos, start=1):
                try:
                    doc.archivo.open('rb')
                    data = doc.archivo.read()
                except Exception:
                    continue
                finally:
                    try:
                        doc.archivo.close()
                    except Exception:
                        pass
                if not data:
                    continue
                ext = Path(doc.archivo.name).suffix.lower() or '.pdf'
                zf.writestr(f'{control_safe}_documento{idx}{ext}', data)
                escritos += 1

        if escritos == 0:
            messages.error(request, 'No se pudieron leer los archivos del expediente.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = (
            f'attachment; filename="{control_safe}_expediente.zip"'
        )
        return response


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
                pdf = generar_constancia_pdf(expediente)
            except Exception as exc:
                messages.error(request, f'Error al generar PDF: {exc}')
                return redirect('oficina_titulacion:expediente_detalle', pk=pk)

            if not pdf:
                messages.error(request, 'No se pudo generar el PDF de no inconveniencia.')
                return redirect('oficina_titulacion:expediente_detalle', pk=pk)

            if not isinstance(pdf, ContentFile):
                pdf = ContentFile(pdf)

            # Regenerar: reemplaza archivo previo (nombre único evita caché del navegador)
            if expediente.constancia_no_inconveniencia:
                expediente.constancia_no_inconveniencia.delete(save=False)
            stamp = timezone.now().strftime('%Y%m%d%H%M%S')
            expediente.constancia_no_inconveniencia.save(
                f'no_inconveniencia_{expediente.pk}_{stamp}.pdf',
                pdf,
                save=False,
            )
            expediente.fecha_constancia = timezone.now()
            expediente.save(update_fields=[
                'constancia_no_inconveniencia', 'fecha_constancia', 'fecha_ultima_actualizacion',
            ])

        intentar_generar_constancia_no_adeudos(expediente, request.user)

        notificar_alumno(
            expediente=expediente,
            tipo='INFO',
            titulo='Constancia de No Inconveniencia disponible',
            mensaje=(
                'Se registró tu Constancia de no Inconveniencia para el Acto '
                'de Recepción Profesional en el expediente.'
            ),
        )
        messages.success(
            request,
            'Constancia de no Inconveniencia para el Acto de Recepción Profesional registrada.',
        )
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)


class RegenerarNoAdeudosView(OficinaTitulacionRequeridoMixin, View):
    """Regenera la Constancia de no adeudos con el formato actual."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        try:
            ok = forzar_regenerar_constancia_no_adeudos(expediente)
        except Exception as exc:
            messages.error(request, f'Error al regenerar PDF: {exc}')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        if not ok:
            messages.error(
                request,
                'No se pudo regenerar. Verifica que las tres áreas hayan confirmado sin adeudos.',
            )
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        messages.success(request, 'Constancia de no adeudos regenerada.')
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
                
            jurado.fecha_acto = hora_acto
            jurado.lugar_acto = grupo.lugar
            jurado.save()

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

        pdf_protocolo_bytes = None
        pdf_oficio_bytes = None
        try:
            from oficina_titulacion.pdf_generator import generar_documentos_protocolo
            from administracion.pdf_oficio import generar_oficio_jurado_pdf
            pdf_protocolo_bytes = generar_documentos_protocolo(expediente)
            pdf_oficio_bytes = generar_oficio_jurado_pdf(expediente.jurado)
        except Exception:
            pass

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
                    'Encuentre adjuntos los documentos de protocolo y su oficio de jurado. '
                    'Confirme su asistencia en la plataforma.'
                )
            else:
                saludo = f'Estimado(a) {nombre},'
                mensaje = (
                    f'Se le invita como {rol_display} al acto del alumno(a) '
                    f'{expediente.alumno.get_full_name()}. '
                    'Encuentre adjuntos los documentos de protocolo y el oficio de jurado.'
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
                if pdf_protocolo_bytes:
                    msg.attach('Documentos_Protocolo.pdf', pdf_protocolo_bytes, 'application/pdf')
                if pdf_oficio_bytes:
                    msg.attach('Oficio_Jurado.pdf', pdf_oficio_bytes, 'application/pdf')
                msg.send(fail_silently=True)
            except Exception:
                pass

        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Acto protocolario programado',
            mensaje=f'Su acto está programado para el {fecha_fmt} en {acto.lugar}.',
        )
        
        from expediente.notifications import notificar_oficina_titulacion, notificar_usuarios_por_rol
        notificar_oficina_titulacion(
            expediente=expediente,
            titulo='Acto Protocolario y Oficio de Jurado',
            mensaje=f'Se programó el acto protocolario del alumno(a) {expediente.alumno.get_full_name()} para el {fecha_fmt} y se generó exitosamente su Oficio de Jurado.'
        )
        notificar_usuarios_por_rol(
            roles=['JEFE_PROYECTO'],
            titulo='Acto Protocolario y Oficio de Jurado',
            mensaje=f'Se programó el acto protocolario del alumno(a) {expediente.alumno.get_full_name()} para el {fecha_fmt} y se generó exitosamente su Oficio de Jurado.'
        )
        from administracion.models import Usuario
        emails_extra = list(Usuario.objects.filter(rol__in=['OFICINA_TITULACION', 'JEFE_PROYECTO'], is_active=True).exclude(email='').values_list('email', flat=True))

        if emails_extra and (pdf_protocolo_bytes or pdf_oficio_bytes):
            saludo = 'Estimado(a) miembro del personal,'
            mensaje = (
                f'Se ha programado el acto protocolario del alumno(a) {expediente.alumno.get_full_name()} '
                f'para el {fecha_fmt} en {acto.lugar}. '
                'Encuentre adjuntos los documentos generados (Oficio de Jurado y/o Documentos de Protocolo).'
            )
            html_content = render_to_string('emails/notificacion_generica.html', {
                'titulo': 'Acto Protocolario Programado',
                'saludo': saludo,
                'mensaje': mensaje,
                'datos_adicionales': {
                    'Alumno(a)': expediente.alumno.get_full_name(),
                    'Fecha y lugar': f'{fecha_fmt} en {acto.lugar}',
                },
                'url_accion': None,
            })
            try:
                msg_extra = EmailMultiAlternatives(
                    subject=f'[ITA Titulación] Acto Protocolario Programado — {expediente.alumno.get_full_name()}',
                    body=f'{saludo}\n\n{mensaje}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=emails_extra,
                )
                msg_extra.attach_alternative(html_content, 'text/html')
                if pdf_protocolo_bytes:
                    msg_extra.attach('Documentos_Protocolo.pdf', pdf_protocolo_bytes, 'application/pdf')
                if pdf_oficio_bytes:
                    msg_extra.attach('Oficio_Jurado.pdf', pdf_oficio_bytes, 'application/pdf')
                msg_extra.send(fail_silently=True)
            except Exception:
                pass


class ConfirmarActoView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        acto = get_object_or_404(ActoProtocolario, pk=pk)
        expediente = acto.expediente

        acto.resultado = 'APROBADO'
        acto.save(update_fields=['resultado'])

        if expediente.estado == EstadoExpediente.PROTOCOLO_PROGRAMADO:
            # Generar certificado automático
            pdf = generar_certificacion_final_pdf(expediente)
            if pdf:
                expediente.certificacion_final_pdf.save(
                    f'certificacion_{expediente.pk}.pdf',
                    pdf,
                    save=False,
                )
                expediente.save(update_fields=['certificacion_final_pdf', 'fecha_ultima_actualizacion'])

            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.ACTO_REALIZADO,
                realizado_por=request.user,
                descripcion='Acto protocolario realizado. Certificación de exención generada.',
            )

        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Acto protocolario realizado',
            mensaje='Se confirmó la realización de su acto protocolario y se ha generado su Certificación de Exención para que la descargue. Próximamente se cargará el documento firmado para concluir su trámite.',
        )
        messages.success(request, 'Acto protocolario confirmado y Certificación generada exitosamente. En espera de subir archivo firmado para concluir.')
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
    def get(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        if expediente.estado not in (
            EstadoExpediente.ACTO_REALIZADO,
            EstadoExpediente.CONCLUIDO,
        ):
            messages.error(request, 'El acto protocolario debe estar realizado.')
            return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        if not expediente.certificacion_final_pdf:
            pdf = generar_certificacion_final_pdf(expediente)
            if pdf:
                expediente.certificacion_final_pdf.save(
                    f'certificacion_{expediente.pk}.pdf',
                    pdf,
                    save=False,
                )
                expediente.save(update_fields=['certificacion_final_pdf', 'fecha_ultima_actualizacion'])
                
                # Enviar notificación al alumno del certificado generado
                from expediente.notifications import notificar_alumno, url_expediente_alumno
                notificar_alumno(
                    expediente=expediente,
                    tipo='INFO',
                    titulo='Certificación Generada',
                    mensaje='Se ha generado tu certificado de exención en sistema para revisión.',
                    url=url_expediente_alumno()
                )
            else:
                messages.error(request, 'No se pudo generar la certificación.')
                return redirect('oficina_titulacion:expediente_detalle', pk=pk)

        from django.http import HttpResponse
        if expediente.certificacion_final_pdf:
            response = HttpResponse(expediente.certificacion_final_pdf.read(), content_type="application/pdf")
            response['Content-Disposition'] = f'attachment; filename="Certificacion_Exencion_{expediente.alumno.username}.pdf"'
            return response
        
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)


class SubirCertificacionFirmadaView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        
        if 'certificacion_final_escaneada' in request.FILES:
            archivo = request.FILES['certificacion_final_escaneada']
            
            # Delete old file if exists
            if expediente.certificacion_final_escaneada:
                expediente.certificacion_final_escaneada.delete(save=False)
                
            expediente.certificacion_final_escaneada = archivo
            expediente.save(update_fields=['certificacion_final_escaneada', 'fecha_ultima_actualizacion'])
            
            # Registrar en historial
            from expediente.models import HistorialExpediente
            from expediente.notifications import notificar_alumno, url_expediente_alumno
            HistorialExpediente.objects.create(
                expediente=expediente,
                estado_anterior=expediente.estado,
                estado_nuevo=expediente.estado,
                realizado_por=request.user,
                descripcion='Se cargó el certificado de exención firmado'
            )
            
            # Notificar al alumno
            notificar_alumno(
                expediente=expediente,
                tipo='INFO',
                titulo='Certificación Firmada Disponible',
                mensaje='Se ha subido tu certificado de exención firmado. Ya puedes descargarlo.',
                url=url_expediente_alumno()
            )
            
            messages.success(request, 'El certificado firmado se ha subido y notificado al alumno exitosamente.')
        else:
            messages.error(request, 'No se proporcionó ningún archivo.')
            
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
    """Registra la digitalización del certificado firmado."""

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

        from expediente.workflow import habilitar_carga_documentos
        habilitar_carga_documentos(expediente, realizado_por=request.user)

        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Certificado digital registrado',
            mensaje='Su certificado firmado fue registrado en el sistema.',
        )
        messages.success(request, 'Certificado digital registrado correctamente.')
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)


class ValidarConstanciaYConcluirView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        from expediente.models import Expediente, EstadoExpediente
        from expediente.notifications import registrar_cambio_estado, notificar_alumno
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        expediente = get_object_or_404(Expediente, pk=pk)
        
        if expediente.estado == EstadoExpediente.ACTO_REALIZADO:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.CONCLUIDO,
                realizado_por=request.user,
                descripcion='Oficina de Titulación concluyó el expediente exitosamente.'
            )
            notificar_alumno(
                expediente=expediente,
                tipo='AVANCE',
                titulo='Trámite de Titulación Concluido',
                mensaje='Tu trámite de titulación ha sido concluido exitosamente.',
            )
            messages.success(request, 'Expediente concluido exitosamente.')
        else:
            messages.error(request, 'El alumno no está en la etapa correcta para concluir el expediente.')
        return redirect('oficina_titulacion:expediente_detalle', pk=expediente.pk)


class DescargarOficioJuradoOficinaView(OficinaTitulacionRequeridoMixin, View):
    def get(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        try:
            asignacion = expediente.jurado
        except AsignacionJurado.DoesNotExist:
            raise Http404("El expediente no tiene jurado asignado.")

        if asignacion.oficio_pdf:
            response = HttpResponse(asignacion.oficio_pdf.read(), content_type="application/pdf")
            filename = f"Oficio_Jurado_{expediente.alumno.username}.pdf"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        else:
            raise Http404("El PDF del oficio aún no se ha generado.")


class DescargarDocumentosProtocoloOficinaView(OficinaTitulacionRequeridoMixin, View):
    def get(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        try:
            asignacion = expediente.jurado
        except AsignacionJurado.DoesNotExist:
            raise Http404("El expediente no tiene jurado asignado.")

        if not asignacion.documentos_protocolo_pdf:
            from administracion.pdf_oficio import generar_documentos_protocolo_pdf
            from django.core.files.base import ContentFile
            try:
                acto = expediente.acto_protocolario
            except Exception:
                acto = None
            try:
                pdf_bytes_docs = generar_documentos_protocolo_pdf(asignacion, acto)
                filename_docs = f"Documentos_Protocolo_{expediente.alumno.username}.pdf"
                asignacion.documentos_protocolo_pdf.save(filename_docs, ContentFile(pdf_bytes_docs), save=True)
            except Exception as e:
                pass

        if asignacion.documentos_protocolo_pdf:
            response = HttpResponse(asignacion.documentos_protocolo_pdf.read(), content_type="application/pdf")
            filename = f"Documentos_Protocolo_{expediente.alumno.username}.pdf"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        else:
            raise Http404("El PDF de los documentos de protocolo aún no se ha generado y falló la generación automática.")


class RegistrarRecepcionEmpastadoView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        from expediente.models import RecepcionEmpastado
        empastado, created = RecepcionEmpastado.objects.get_or_create(
            expediente=expediente,
            defaults={
                'fecha_recepcion': timezone.now().date(),
                'recibido_por': request.user,
                'estado': 'REVISADO',
            }
        )
        if not created:
            empastado.fecha_recepcion = timezone.now().date()
            empastado.recibido_por = request.user
            empastado.estado = 'REVISADO'
            empastado.save()

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=expediente.estado, 
            realizado_por=request.user,
            descripcion='Empastado físico recibido por Oficina de Titulación.',
        )

        from expediente.notifications import notificar_alumno
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Empastado recibido',
            mensaje='La Oficina de Titulación ha confirmado la recepción de tu empastado físico.',
        )

        messages.success(request, 'Se ha registrado la recepción del empastado físico y se ha notificado al alumno.')
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)

class RegenerarNoAdeudosView(OficinaTitulacionRequeridoMixin, View):
    def post(self, request, pk):
        from oficina_titulacion.services import forzar_regenerar_constancia_no_adeudos
        expediente = get_object_or_404(Expediente, pk=pk)
        resultado = forzar_regenerar_constancia_no_adeudos(expediente)
        if resultado:
            messages.success(request, 'Constancia de no adeudos regenerada exitosamente.')
        else:
            messages.error(request, 'No se pudo regenerar la constancia de no adeudos.')
        return redirect('oficina_titulacion:expediente_detalle', pk=pk)


class EstadisticasOficinaView(OficinaTitulacionRequeridoMixin, TemplateView):
    """
    Estadísticas de titulación para el Jefe de Proyecto (RE-01 a RE-07).
    Filtra por departamento del usuario.
    """
    template_name = 'oficina_titulacion/estadisticas.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs_base = Expediente.objects.all()

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

        # ─── RE-04: Estadísticas por año de ingreso (periodo inicio) ──
        por_generacion = (
            qs.filter(alumno__periodo_inicio_anio__isnull=False)
            .values('alumno__periodo_inicio_anio')
            .annotate(
                total=Count('id'),
                concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO))
            )
            .order_by('-alumno__periodo_inicio_anio')
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




import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import PieChart, BarChart, Reference
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION

def get_estadisticas_data_oficina():
    qs_base = Expediente.objects.all()

    qs = qs_base.select_related('alumno', 'modalidad')

    total_expedientes = qs.count()
    qs_concluidos = qs.filter(estado=EstadoExpediente.CONCLUIDO)
    total_concluidos = qs_concluidos.count()
    expedientes_activos = qs.exclude(
        estado__in=[EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO, EstadoExpediente.BORRADOR]
    ).count()
    expedientes_cancelados = qs.filter(estado=EstadoExpediente.CANCELADO).count()

    porcentaje_titulados = round(
        (total_concluidos / total_expedientes * 100) if total_expedientes > 0 else 0, 1
    )

    iniciados_hombres = qs.filter(alumno__genero='M').count()
    iniciados_mujeres = qs.filter(alumno__genero='F').count()
    iniciados_sin_dato = total_expedientes - iniciados_hombres - iniciados_mujeres

    titulados_hombres = qs_concluidos.filter(alumno__genero='M').count()
    titulados_mujeres = qs_concluidos.filter(alumno__genero='F').count()
    titulados_sin_dato = total_concluidos - titulados_hombres - titulados_mujeres

    por_generacion = list(
        qs.filter(alumno__periodo_inicio_anio__isnull=False)
        .values('alumno__periodo_inicio_anio')
        .annotate(
            total=Count('id'),
            concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO))
        )
        .order_by('-alumno__periodo_inicio_anio')
    )

    por_modalidad = list(
        qs.filter(modalidad__isnull=False)
        .values('modalidad__nombre')
        .annotate(
            total=Count('id'),
            concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO))
        )
        .order_by('-total')
    )

    por_carrera = list(
        qs.values('alumno__carrera__nombre')
        .annotate(
            total=Count('id'),
            concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO)),
            hombres=Count('id', filter=Q(alumno__genero='M')),
            mujeres=Count('id', filter=Q(alumno__genero='F')),
        )
        .order_by('-total')
    )

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

    return {
        'departamento': 'Global (Oficina de Titulación)',
        'total_expedientes': total_expedientes,
        'total_concluidos': total_concluidos,
        'expedientes_activos': expedientes_activos,
        'expedientes_cancelados': expedientes_cancelados,
        'porcentaje_titulados': porcentaje_titulados,
        'iniciados_hombres': iniciados_hombres,
        'iniciados_mujeres': iniciados_mujeres,
        'iniciados_sin_dato': iniciados_sin_dato,
        'titulados_hombres': titulados_hombres,
        'titulados_mujeres': titulados_mujeres,
        'titulados_sin_dato': titulados_sin_dato,
        'por_generacion': por_generacion,
        'por_modalidad': por_modalidad,
        'por_carrera': por_carrera,
        'expedientes_por_estado': expedientes_por_estado,
    }


class ExportarEstadisticasExcelOficinaView(OficinaTitulacionRequeridoMixin, View):
    def get(self, request, *args, **kwargs):
        stats = get_estadisticas_data_oficina()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Resumen General"

        # Estilos
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1B396A", end_color="1B396A", fill_type="solid")
        title_font = Font(size=14, bold=True)

        ws['A1'] = f"Estadísticas de Titulación - {stats['departamento']}"
        ws['A1'].font = title_font
        ws.merge_cells('A1:C1')
        ws.append([])
        
        # Resumen Global
        ws.append(["Métrica", "Cantidad"])
        for cell in ws[3]:
            cell.font = header_font; cell.fill = header_fill

        ws.append(["Total de Expedientes Iniciados", stats['total_expedientes']])
        ws.append(["Total Titulados (Concluidos)", stats['total_concluidos']])
        ws.append(["Expedientes en Proceso (Activos)", stats['expedientes_activos']])
        ws.append(["Expedientes Cancelados", stats['expedientes_cancelados']])
        ws.append(["Eficiencia de Titulación", f"{stats['porcentaje_titulados']}%"])
        ws.append([])

        # Estatus (Tabla para Gráfica de Pastel)
        row_start_estados = ws.max_row + 1
        ws.append(["Estado del Expediente", "Total"])
        for cell in ws[row_start_estados]:
            cell.font = header_font; cell.fill = header_fill
        
        for est in stats['expedientes_por_estado']:
            ws.append([est['estado'], est['total']])
        row_end_estados = ws.max_row
        ws.append([])

        # Gráfica de Pastel - Estados
        if len(stats['expedientes_por_estado']) > 0:
            pie = PieChart()
            labels = Reference(ws, min_col=1, min_row=row_start_estados+1, max_row=row_end_estados)
            data = Reference(ws, min_col=2, min_row=row_start_estados, max_row=row_end_estados)
            pie.add_data(data, titles_from_data=True)
            pie.set_categories(labels)
            pie.title = "Distribución por Estatus"
            ws.add_chart(pie, "D3")

        # Género
        ws.append(["Género", "Iniciaron Proceso", "Concluyeron Titulación"])
        for cell in ws[ws.max_row]:
            cell.font = header_font; cell.fill = header_fill
        ws.append(["Hombres", stats['iniciados_hombres'], stats['titulados_hombres']])
        ws.append(["Mujeres", stats['iniciados_mujeres'], stats['titulados_mujeres']])
        ws.append(["Sin especificar", stats['iniciados_sin_dato'], stats['titulados_sin_dato']])
        ws.append([])

        # Generación
        ws.append(["Generación", "Total Iniciaron", "Total Titulados"])
        for cell in ws[ws.max_row]:
            cell.font = header_font; cell.fill = header_fill
        for gen in stats['por_generacion']:
            ws.append([gen['alumno__periodo_inicio_anio'], gen['total'], gen['concluidos']])

        # Hoja 2: Modalidades y Carreras
        ws2 = wb.create_sheet(title="Modalidades y Carreras")
        
        row_start_mod = ws2.max_row
        ws2.append(["Modalidad", "Total Iniciaron", "Total Titulados"])
        for cell in ws2[1]:
            cell.font = header_font; cell.fill = header_fill
        for mod in stats['por_modalidad']:
            ws2.append([mod['modalidad__nombre'], mod['total'], mod['concluidos']])
        row_end_mod = ws2.max_row

        # Gráfica de Barras - Modalidades
        if len(stats['por_modalidad']) > 0:
            bar = BarChart()
            bar.type = "col"
            bar.style = 10
            bar.title = "Titulados por Modalidad"
            labels_mod = Reference(ws2, min_col=1, min_row=row_start_mod+1, max_row=row_end_mod)
            data_mod = Reference(ws2, min_col=3, min_row=row_start_mod, max_row=row_end_mod)
            bar.add_data(data_mod, titles_from_data=True)
            bar.set_categories(labels_mod)
            ws2.add_chart(bar, "E2")

        ws2.append([])
        ws2.append(["Carrera", "Total Iniciaron", "Total Titulados", "Hombres", "Mujeres"])
        for cell in ws2[ws2.max_row]:
            cell.font = header_font; cell.fill = header_fill
        for car in stats['por_carrera']:
            ws2.append([car['alumno__carrera__nombre'], car['total'], car['concluidos'], car['hombres'], car['mujeres']])

        # Ajustar ancho columnas
        from openpyxl.utils import get_column_letter
        for sheet in wb.worksheets:
            for col in sheet.columns:
                max_length = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                sheet.column_dimensions[col_letter].width = min(max_length + 2, 60)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="Estadisticas_Titulacion.xlsx"'
        wb.save(response)
        return response


class ExportarEstadisticasPPTXOficinaView(OficinaTitulacionRequeridoMixin, View):
    def get(self, request, *args, **kwargs):
        stats = get_estadisticas_data_oficina()

        prs = Presentation()
        
        # Helper colors
        BLUE_DARK = RGBColor(27, 57, 106)
        BLUE_LIGHT = RGBColor(0, 114, 198)
        GRAY = RGBColor(108, 117, 125)

        # Portada
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]

        title.text = "Reporte Ejecutivo de Titulación"
        title.text_frame.paragraphs[0].font.color.rgb = BLUE_DARK
        title.text_frame.paragraphs[0].font.bold = True
        
        subtitle.text = f"Departamento: {stats['departamento']}\nSistema HEDS"
        subtitle.text_frame.paragraphs[0].font.color.rgb = GRAY

        # Diapositiva 2: Resumen
        bullet_slide_layout = prs.slide_layouts[1]
        slide2 = prs.slides.add_slide(bullet_slide_layout)
        title_shape = slide2.shapes.title
        title_shape.text = "Resumen General"
        title_shape.text_frame.paragraphs[0].font.color.rgb = BLUE_DARK
        
        tf = slide2.shapes.placeholders[1].text_frame
        tf.text = f"Total de Expedientes: {stats['total_expedientes']}"
        tf.add_paragraph().text = f"Total de Titulados: {stats['total_concluidos']} ({stats['porcentaje_titulados']}%)"
        tf.add_paragraph().text = f"Expedientes en Proceso: {stats['expedientes_activos']}"
        tf.add_paragraph().text = f"Expedientes Cancelados: {stats['expedientes_cancelados']}"

        # Diapositiva 3: Gráfica de Estados (Pastel)
        blank_slide_layout = prs.slide_layouts[5] # Título solamente
        slide_estados = prs.slides.add_slide(blank_slide_layout)
        slide_estados.shapes.title.text = "Distribución por Estatus del Expediente"
        slide_estados.shapes.title.text_frame.paragraphs[0].font.color.rgb = BLUE_DARK

        if stats['expedientes_por_estado']:
            chart_data = CategoryChartData()
            chart_data.categories = [item['estado'] for item in stats['expedientes_por_estado']]
            chart_data.add_series('Total', (item['total'] for item in stats['expedientes_por_estado']))

            x, y, cx, cy = Inches(1.5), Inches(2), Inches(7), Inches(4.5)
            chart = slide_estados.shapes.add_chart(
                XL_CHART_TYPE.PIE, x, y, cx, cy, chart_data
            ).chart
            chart.has_legend = True
            chart.legend.position = XL_LEGEND_POSITION.RIGHT
            chart.plots[0].has_data_labels = True

        # Diapositiva 4: Demografía (Barras apiladas)
        slide_demo = prs.slides.add_slide(blank_slide_layout)
        slide_demo.shapes.title.text = "Demografía: Hombres vs Mujeres"
        slide_demo.shapes.title.text_frame.paragraphs[0].font.color.rgb = BLUE_DARK
        
        chart_data_demo = CategoryChartData()
        chart_data_demo.categories = ['Iniciaron Proceso', 'Titulados (Concluidos)']
        chart_data_demo.add_series('Hombres', (stats['iniciados_hombres'], stats['titulados_hombres']))
        chart_data_demo.add_series('Mujeres', (stats['iniciados_mujeres'], stats['titulados_mujeres']))
        if stats['iniciados_sin_dato'] > 0 or stats['titulados_sin_dato'] > 0:
            chart_data_demo.add_series('No especificado', (stats['iniciados_sin_dato'], stats['titulados_sin_dato']))

        x, y, cx, cy = Inches(1), Inches(2), Inches(8), Inches(4.5)
        chart_demo = slide_demo.shapes.add_chart(
            XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, cx, cy, chart_data_demo
        ).chart
        chart_demo.has_legend = True
        chart_demo.legend.position = XL_LEGEND_POSITION.BOTTOM

        # Diapositiva 5: Gráfica de Modalidades (Barras)
        slide_mod = prs.slides.add_slide(blank_slide_layout)
        slide_mod.shapes.title.text = "Top Modalidades de Titulación"
        slide_mod.shapes.title.text_frame.paragraphs[0].font.color.rgb = BLUE_DARK

        if stats['por_modalidad']:
            chart_data_mod = CategoryChartData()
            # Tomar top 5
            top_mod = stats['por_modalidad'][:5]
            chart_data_mod.categories = [item['modalidad__nombre'][:25] + '...' if len(item['modalidad__nombre']) > 25 else item['modalidad__nombre'] for item in top_mod]
            chart_data_mod.add_series('Concluidos', (item['concluidos'] for item in top_mod))
            chart_data_mod.add_series('Iniciados', (item['total'] for item in top_mod))

            x, y, cx, cy = Inches(0.5), Inches(2), Inches(9), Inches(4.5)
            chart_mod = slide_mod.shapes.add_chart(
                XL_CHART_TYPE.BAR_CLUSTERED, x, y, cx, cy, chart_data_mod
            ).chart
            chart_mod.has_legend = True
            chart_mod.legend.position = XL_LEGEND_POSITION.BOTTOM
            
        # Diapositiva 6: Gráfica por Carrera
        if stats['por_carrera']:
            slide_car = prs.slides.add_slide(blank_slide_layout)
            slide_car.shapes.title.text = "Expedientes por Carrera"
            slide_car.shapes.title.text_frame.paragraphs[0].font.color.rgb = BLUE_DARK
            
            chart_data_car = CategoryChartData()
            chart_data_car.categories = [item['alumno__carrera__nombre'][:25] + '...' if len(item['alumno__carrera__nombre']) > 25 else item['alumno__carrera__nombre'] for item in stats['por_carrera']]
            chart_data_car.add_series('Iniciados', (item['total'] for item in stats['por_carrera']))
            chart_data_car.add_series('Concluidos', (item['concluidos'] for item in stats['por_carrera']))
            
            x, y, cx, cy = Inches(0.5), Inches(2), Inches(9), Inches(4.5)
            chart_car = slide_car.shapes.add_chart(
                XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, cx, cy, chart_data_car
            ).chart
            chart_car.has_legend = True
            chart_car.legend.position = XL_LEGEND_POSITION.BOTTOM

        # Diapositiva 7: Gráfica por Generación
        if stats['por_generacion']:
            slide_gen = prs.slides.add_slide(blank_slide_layout)
            slide_gen.shapes.title.text = "Expedientes por Generación"
            slide_gen.shapes.title.text_frame.paragraphs[0].font.color.rgb = BLUE_DARK
            
            chart_data_gen = CategoryChartData()
            top_gen = stats['por_generacion'][:10] # Mostrar las últimas 10 generaciones
            top_gen.reverse() # Cronológico de izquierda a derecha
            chart_data_gen.categories = [str(item['alumno__periodo_inicio_anio']) for item in top_gen]
            chart_data_gen.add_series('Iniciados', (item['total'] for item in top_gen))
            chart_data_gen.add_series('Concluidos', (item['concluidos'] for item in top_gen))
            
            x, y, cx, cy = Inches(0.5), Inches(2), Inches(9), Inches(4.5)
            chart_gen = slide_gen.shapes.add_chart(
                XL_CHART_TYPE.LINE, x, y, cx, cy, chart_data_gen
            ).chart
            chart_gen.has_legend = True
            chart_gen.legend.position = XL_LEGEND_POSITION.BOTTOM

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
        response['Content-Disposition'] = f'attachment; filename="Presentacion_Estadisticas.pptx"'
        prs.save(response)
        return response
