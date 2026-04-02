"""
Vistas del módulo de Escolares (Servicios Escolares).
Validación final de documentos, integración de expediente, envío a CDMX.
"""
import io
import os
import zipfile

from django.views.generic import TemplateView, ListView, View, CreateView, UpdateView, DetailView
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.text import slugify

from expediente.mixins import EscolaresRequeridoMixin
from expediente.models import (
    Expediente, Documento, ValidacionDocumento,
    EnvioCDMX, EstadoExpediente, EstadoDocumento, EstadoValidacion
)
from expediente.notifications import notificar_alumno, registrar_cambio_estado, registrar_cambio_documento
from expediente.workflow import actualizar_estado_documento, verificar_avance_expediente


class DashboardEscolaresView(EscolaresRequeridoMixin, TemplateView):
    template_name = 'escolares/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['expedientes_para_revision'] = Expediente.objects.filter(
            estado=EstadoExpediente.EN_REVISION_DOCUMENTOS
        ).select_related('alumno', 'modalidad').count()
        ctx['expedientes_para_integrar'] = Expediente.objects.filter(
            estado=EstadoExpediente.LISTO_INTEGRACION
        ).count()
        ctx['expedientes_enviados_cdmx'] = Expediente.objects.filter(
            estado=EstadoExpediente.ENVIADO_CDMX
        ).count()
        ctx['expedientes_recientes'] = Expediente.objects.exclude(
            estado__in=[EstadoExpediente.BORRADOR, EstadoExpediente.CANCELADO]
        ).select_related('alumno', 'modalidad').order_by('-fecha_ultima_actualizacion')[:10]
        return ctx


class ExpedienteListaEscolaresView(EscolaresRequeridoMixin, ListView):
    model = Expediente
    template_name = 'escolares/expedientes/lista.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        qs = Expediente.objects.select_related(
            'alumno', 'modalidad', 'alumno__carrera'
        ).order_by('-fecha_ultima_actualizacion')
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        busqueda = self.request.GET.get('q')
        if busqueda:
            qs = qs.filter(
                alumno__first_name__icontains=busqueda
            ) | qs.filter(
                alumno__last_name__icontains=busqueda
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estado_filtro'] = self.request.GET.get('estado', '')
        ctx['estados'] = EstadoExpediente.choices
        return ctx


class ExpedienteDetalleEscolaresView(EscolaresRequeridoMixin, DetailView):
    model = Expediente
    template_name = 'escolares/expedientes/detalle.html'
    context_object_name = 'expediente'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.object
        ctx['documentos'] = expediente.documentos.select_related(
            'tipo_documento'
        ).prefetch_related('validaciones__validado_por').order_by('tipo_documento__orden')
        ctx['historial'] = expediente.historial.select_related('realizado_por')[:15]
        try:
            ctx['envio_cdmx'] = expediente.envios_cdmx.order_by('-fecha_creacion').first()
        except Exception:
            ctx['envio_cdmx'] = None
        return ctx


class ValidarDocumentoEscolaresView(EscolaresRequeridoMixin, View):
    """Escolares aprueba, rechaza o solicita corrección en un documento."""

    def post(self, request, pk):
        documento = get_object_or_404(Documento, pk=pk)
        accion = request.POST.get('accion')  # APROBAR, RECHAZAR, CORRECCION
        observaciones = request.POST.get('observaciones', '').strip()

        estado_map = {
            'APROBAR': EstadoValidacion.APROBADO,
            'RECHAZAR': EstadoValidacion.RECHAZADO,
            'CORRECCION': EstadoValidacion.REQUIERE_CORRECCION,
        }
        if accion not in estado_map:
            messages.error(request, 'Acción no válida.')
            return redirect('escolares:expediente_detalle', pk=documento.expediente.pk)

        validacion, _ = ValidacionDocumento.objects.get_or_create(
            documento=documento,
            departamento='ESCOLARES',
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
                msg_alumno = f'Servicios Escolares aprobó el documento "{documento.tipo_documento.nombre}". Pendiente revisión de División de Estudios.'
        elif accion == 'RECHAZAR':
            tipo_notif = 'RECHAZADO'
            msg_alumno = f'El documento "{documento.tipo_documento.nombre}" fue rechazado por Servicios Escolares. Observaciones: {observaciones}'
        else:
            tipo_notif = 'CORRECCION'
            msg_alumno = f'El documento "{documento.tipo_documento.nombre}" requiere correcciones. Observaciones: {observaciones}'

        registrar_cambio_documento(
            documento=documento,
            accion=f'Servicios Escolares: {accion}',
            realizado_por=request.user,
            observaciones=observaciones,
            departamento='ESCOLARES'
        )

        notificar_alumno(
            expediente=documento.expediente,
            tipo=tipo_notif,
            titulo=f'Documento {accion.lower()}do por Servicios Escolares',
            mensaje=msg_alumno,
        )

        # Verificar si el expediente puede avanzar (todos los docs aprobados por ambos)
        verificar_avance_expediente(documento.expediente)

        messages.success(request, f'Documento actualizado: {accion}')
        return redirect('escolares:expediente_detalle', pk=documento.expediente.pk)


class IntegrarExpedienteView(EscolaresRequeridoMixin, View):
    """Escolares marca el expediente como integrado (todos los docs aprobados)."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        if not expediente.todos_documentos_aprobados():
            messages.error(request, 'No todos los documentos están aprobados.')
            return redirect('escolares:expediente_detalle', pk=pk)

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.INTEGRADO,
            realizado_por=request.user,
            descripcion='Servicios Escolares integró el expediente completo.'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Expediente Integrado',
            mensaje='Servicios Escolares ha integrado tu expediente completo. En proceso de envío a CDMX.',
        )
        messages.success(request, 'Expediente integrado exitosamente.')
        return redirect('escolares:expediente_detalle', pk=pk)


class DescargarExpedienteView(EscolaresRequeridoMixin, View):
    """Descarga un ZIP con todos los documentos del expediente para envío físico."""

    def get(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        # Crear ZIP en memoria
        buffer = io.BytesIO()
        alumno_name = expediente.alumno.get_full_name().replace(' ', '_')
        ncontrol = expediente.alumno.username

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Agregar cada documento del expediente
            for doc in expediente.documentos.select_related('tipo_documento').all():
                if doc.archivo:
                    try:
                        archivo_path = doc.archivo.path
                        if os.path.exists(archivo_path):
                            # Nombre limpio para el archivo dentro del ZIP
                            ext = os.path.splitext(doc.archivo.name)[1]
                            nombre_limpio = doc.tipo_documento.nombre.replace(' ', '_').replace('/', '-')
                            nombre_archivo = f"{doc.tipo_documento.orden:02d}_{nombre_limpio}_v{doc.version}{ext}"
                            zf.write(archivo_path, nombre_archivo)
                    except Exception:
                        continue

            # Agregar fotografía digital si existe
            if expediente.fotografia_digital:
                try:
                    foto_path = expediente.fotografia_digital.path
                    if os.path.exists(foto_path):
                        ext = os.path.splitext(expediente.fotografia_digital.name)[1]
                        zf.write(foto_path, f"Fotografia_Digital{ext}")
                except Exception:
                    pass

            # Agregar un resumen en texto
            resumen = f"""EXPEDIENTE DE TITULACIÓN - INSTITUTO TECNOLÓGICO DE APIZACO
{'=' * 60}

Alumno: {expediente.alumno.get_full_name()}
N° Control: {ncontrol}
Carrera: {getattr(expediente.alumno, 'carrera', 'N/A')}
Modalidad: {expediente.modalidad.nombre if expediente.modalidad else 'N/A'}
Plan de Estudios: {expediente.modalidad.plan_estudios.nombre if expediente.modalidad else 'N/A'}
Título del trabajo: {expediente.titulo_trabajo or 'N/A'}
Empresa: {expediente.nombre_empresa or 'N/A'}
Fecha de apertura: {expediente.fecha_apertura.strftime('%d/%m/%Y %H:%M')}
Estado: {expediente.get_estado_display()}

DOCUMENTOS INCLUIDOS
{'-' * 40}
"""
            for doc in expediente.documentos.select_related('tipo_documento').all():
                estado_txt = doc.get_estado_display()
                tiene_archivo = "Sí" if doc.archivo else "No"
                resumen += f"  - {doc.tipo_documento.nombre} (v{doc.version}) — {estado_txt} — Archivo: {tiene_archivo}\n"

            resumen += f"\n\nGenerado el: {timezone.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            zf.writestr("_RESUMEN_EXPEDIENTE.txt", resumen)

        # Preparar respuesta
        alumno_slug = slugify(expediente.alumno.get_full_name())
        filename = f"Expediente_{ncontrol}_{alumno_slug}.zip"

        response = HttpResponse(buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(response.content)
        return response


class EnviarCDMXView(EscolaresRequeridoMixin, View):
    """Escolares registra el envío del expediente a CDMX."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)

        numero_oficio = request.POST.get('numero_oficio', '').strip()
        fecha_envio = request.POST.get('fecha_envio', '').strip()
        observaciones = request.POST.get('observaciones_envio', '').strip()

        if not numero_oficio or not fecha_envio:
            messages.error(request, 'Debes indicar el número de oficio y la fecha de envío.')
            return redirect('escolares:expediente_detalle', pk=pk)

        envio = EnvioCDMX.objects.create(
            expediente=expediente,
            numero_oficio=numero_oficio,
            fecha_envio=fecha_envio,
            observaciones_envio=observaciones,
            estado='ENVIADO',
            registrado_por=request.user,
        )

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.ENVIADO_CDMX,
            realizado_por=request.user,
            descripcion=f'Expediente enviado a CDMX. Oficio: {envio.numero_oficio}'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Expediente enviado a CDMX',
            mensaje=f'Tu expediente fue enviado a CDMX/TecNM para registro de título. Oficio: {envio.numero_oficio}',
        )
        messages.success(request, 'Envío a CDMX registrado exitosamente.')
        return redirect('escolares:expediente_detalle', pk=pk)


class RespuestaCDMXView(EscolaresRequeridoMixin, UpdateView):
    model = EnvioCDMX
    template_name = 'escolares/cdmx/respuesta.html'
    fields = ['estado', 'fecha_respuesta', 'observaciones_cdmx', 'numero_registro_titulo']

    def form_valid(self, form):
        envio = form.save()
        expediente = envio.expediente

        if envio.estado == 'APROBADO':
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.APROBADO_CDMX,
                realizado_por=self.request.user,
                descripcion=f'CDMX aprobó el expediente. Registro: {envio.numero_registro_titulo}'
            )
            # Actualizar a empastado pendiente
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.EMPASTADO_PENDIENTE,
                realizado_por=self.request.user,
                descripcion='Expediente aprobado por CDMX. Pendiente recepción de empastado en División de Estudios.'
            )
            notificar_alumno(
                expediente=expediente,
                tipo='APROBADO',
                titulo='¡Tu expediente fue aprobado por CDMX!',
                mensaje='CDMX aprobó tu expediente. El siguiente paso es entregar el empastado en División de Estudios.',
            )
        else:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.RECHAZADO_CDMX,
                realizado_por=self.request.user,
                descripcion=f'CDMX rechazó el expediente. Observaciones: {envio.observaciones_cdmx}'
            )
            notificar_alumno(
                expediente=expediente,
                tipo='RECHAZADO',
                titulo='Expediente rechazado por CDMX',
                mensaje=f'CDMX rechazó tu expediente. Observaciones: {envio.observaciones_cdmx}. Contacta a Servicios Escolares.',
            )

        messages.success(self.request, 'Respuesta de CDMX registrada.')
        return redirect('escolares:expediente_detalle', pk=expediente.pk)
