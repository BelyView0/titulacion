"""
Etapas de «Mi expediente» para la app móvil (SIGET).

Replica lo que la web muestra y permite hacer en
templates/alumnos/expediente/detalle.html y _cita_acciones.html:

  - construir_etapas()              -> datos extra del detalle (citas, pago,
                                       adeudos, certificados, acta, historial)
  - ConfirmarCitaAPIView            -> ConfirmarCitaView
  - SolicitarReprogramacionCitaAPIView -> SolicitarReprogramacionCitaView
  - SubirComprobantePagoAPIView     -> SubirComprobantePagoView
  - PrefichaPagoEnlaceAPIView       -> genera un enlace firmado (5 min) para
                                       descargar la preficha en PDF
  - PrefichaPagoDescargaView        -> sirve el PDF con ese enlace
  - SubirActaExencionAPIView        -> SubirActaExencionView
  - DocumentosProtocoloEnlaceAPIView / DocumentosProtocoloDescargaView
                                    -> DescargarDocumentosProtocoloAlumnoView
                                       (Guía y Documentos de Protocolo)
"""
import logging

from django.core import signing
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from administracion.models import ContactoArea, Rol
from expediente.models import (
    CitaDocumentoFisico,
    ConfirmacionAdeudo,
    EstadoExpediente,
    Expediente,
)
from expediente.notifications import (
    notificar_alumno,
    notificar_oficina_titulacion,
    notificar_usuarios_por_rol,
    registrar_cambio_estado,
)

from .permissions import IsAlumno, IsCorreoVerificado

logger = logging.getLogger(__name__)

# Estados en los que el alumno puede editar sus datos (igual que la web).
ESTADOS_EDITABLES_EXPEDIENTE = (
    EstadoExpediente.DATOS_EXPEDIENTE,
    EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
    EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA,
    EstadoExpediente.CARGA_DOCUMENTOS,
    EstadoExpediente.EN_CORRECCION,
)

SALT_PREFICHA = 'siget.preficha-pago'
SALT_PROTOCOLO = 'siget.documentos-protocolo'

# Estados en los que la web permite descargar la Guía de Protocolo.
ESTADOS_DESCARGA_PROTOCOLO = (
    EstadoExpediente.PROTOCOLO_PROGRAMADO,
    EstadoExpediente.ACTO_PROGRAMADO,
    EstadoExpediente.ACTO_REALIZADO,
    EstadoExpediente.CONCLUIDO,
)
VIGENCIA_ENLACE_SEGUNDOS = 300


# ─────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────

def _url_archivo(campo, request):
    """URL absoluta de un FileField, o None si está vacío."""
    if not campo:
        return None

    url = campo.url
    return request.build_absolute_uri(url) if request else url


def _expediente_o_404(usuario):
    try:
        return usuario.expediente
    except Expediente.DoesNotExist:
        return None


def _sin_expediente():
    return Response(
        {
            'detail': 'No tienes un expediente registrado.',
            'sin_expediente': True,
        },
        status=status.HTTP_404_NOT_FOUND,
    )


def _error(mensaje, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': mensaje}, status=codigo)


def _es_pdf(archivo):
    return archivo.name.lower().endswith('.pdf')


# ─────────────────────────────────────────────────────────────
# Serialización
# ─────────────────────────────────────────────────────────────

def serializar_cita(cita):
    """Misma información y reglas de botones que _cita_acciones.html."""
    if cita is None:
        return None

    estado = cita.estado
    programada = estado == CitaDocumentoFisico.EstadoCita.PROGRAMADA
    confirmada = estado == CitaDocumentoFisico.EstadoCita.CONFIRMADA_ALUMNO

    return {
        'id': cita.id,
        'tipo': cita.tipo,
        'tipo_display': cita.get_tipo_display(),
        'fecha_hora': cita.fecha_hora,
        'lugar': cita.lugar,
        'estado': estado,
        'estado_display': cita.get_estado_display(),
        'propuesta_fecha': cita.propuesta_alumno_fecha,
        'propuesta_notas': cita.propuesta_alumno_notas,
        'puede_confirmar': programada,
        'puede_reprogramar': programada or confirmada,
        'reprogramacion_solicitada': (
            estado == CitaDocumentoFisico.EstadoCita.REPROGRAMACION_SOLICITADA
        ),
    }


def _serializar_contacto(contacto):
    if not contacto:
        return None

    return {
        'area': contacto.get_area_display(),
        'responsable': contacto.nombre_responsable,
        'telefono': contacto.telefono_completo(),
        'correo': contacto.correo_departamento,
    }


def _serializar_adeudos(expediente):
    confirmaciones = {c.area: c for c in expediente.confirmaciones_adeudo.all()}
    contactos = {c.area: c for c in ContactoArea.areas_adeudo()}

    items = []
    for codigo, etiqueta in ConfirmacionAdeudo.Area.choices:
        conf = confirmaciones.get(codigo)

        if conf and conf.sin_adeudos:
            estado = 'sin'
        elif conf:
            estado = 'con'
        else:
            estado = 'pendiente'

        items.append({
            'area': etiqueta,
            'codigo': codigo,
            'estado': estado,
            'observaciones': conf.observaciones if conf else '',
            'contacto': (
                _serializar_contacto(contactos.get(codigo))
                if estado == 'con'
                else None
            ),
        })

    return items


def _panel_lateral(expediente):
    """
    Panel que la web muestra bajo «Estado actual». Es la misma cadena
    if/elif de detalle.html (el orden importa), para que app y web coincidan.
    """
    from alumnos.views import ESTADOS_ENVIO_DOCUMENTOS

    estado = expediente.estado

    if estado in ESTADOS_ENVIO_DOCUMENTOS:
        return 'ENVIAR_DOCUMENTOS'

    if estado == EstadoExpediente.EN_REVISION:
        return 'EN_REVISION'

    if estado in (
        EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
        EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA,
        EstadoExpediente.CERTIFICADO_FIRMADO,
    ):
        return 'PRECARGA'

    if estado == EstadoExpediente.PAGO_PENDIENTE:
        return 'PAGO'

    if estado == EstadoExpediente.ADEUDOS_EN_REVISION:
        return 'ADEUDOS'

    if expediente.comprobante_pago and expediente.pago_validado == 'APROBADO':
        return 'PAGO_APROBADO'

    if estado == EstadoExpediente.CONCLUIDO:
        return 'CONCLUIDO'

    return None


def construir_etapas(expediente, request):
    """Datos extra del detalle del expediente (todo lo que la web muestra)."""
    referencia = expediente.referencias_pago.filter(activa=True).first()

    cita_certificado = expediente.citas_fisicas.filter(
        tipo=CitaDocumentoFisico.TipoCita.CERTIFICADO
    ).order_by('-fecha_creacion').first()

    cita_oficio = expediente.citas_fisicas.filter(
        tipo=CitaDocumentoFisico.TipoCita.OFICIO_PUBLICACION
    ).order_by('-fecha_creacion').first()

    en_pago = expediente.estado == EstadoExpediente.PAGO_PENDIENTE
    pago_estado = expediente.pago_validado

    historial = [
        {
            'id': h.pk,
            'fecha': h.fecha,
            'descripcion': h.descripcion,
            'realizado_por': (
                h.realizado_por.get_full_name() if h.realizado_por else None
            ),
        }
        for h in expediente.historial.select_related('realizado_por').all()[:10]
    ]

    return {
        'panel': _panel_lateral(expediente),
        'puede_editar': expediente.estado in ESTADOS_EDITABLES_EXPEDIENTE,
        'fecha_apertura': expediente.fecha_apertura,
        'asesor_con_titulo': (
            expediente.asesor.get_nombre_con_titulo()
            if expediente.asesor
            else None
        ),
        'citas': {
            'certificado': serializar_cita(cita_certificado),
            'oficio': serializar_cita(cita_oficio),
        },
        'certificado_exencion': (
            {
                'firmado': _url_archivo(
                    expediente.certificacion_final_escaneada, request
                ),
                'generado': _url_archivo(
                    expediente.certificacion_final_pdf, request
                ),
            }
            if (
                expediente.certificacion_final_pdf
                or expediente.certificacion_final_escaneada
            )
            else None
        ),
        'pago': {
            'referencia': (
                {
                    'referencia_bancaria': referencia.referencia_bancaria,
                    'monto': str(referencia.monto),
                    'concepto': referencia.concepto,
                }
                if referencia
                else None
            ),
            'estado': pago_estado,
            'observaciones': expediente.pago_observaciones,
            'comprobante': _url_archivo(expediente.comprobante_pago, request),
            'puede_descargar_preficha': bool(referencia) and en_pago,
            # Igual que la web: se sube con estado PENDIENTE o tras un rechazo.
            'puede_subir_comprobante': (
                bool(referencia)
                and en_pago
                and pago_estado in ('PENDIENTE', 'RECHAZADO')
            ),
        },
        'adeudos': _serializar_adeudos(expediente),
        'constancia_no_adeudos': _url_archivo(
            expediente.constancia_no_adeudos, request
        ),
        'constancia_no_inconveniencia': _url_archivo(
            expediente.constancia_no_inconveniencia, request
        ),
        'certificacion_final_pdf': _url_archivo(
            expediente.certificacion_final_pdf, request
        ),
        'acta_exencion': {
            'visible': expediente.estado == EstadoExpediente.ACTO_REALIZADO,
            'subida': bool(expediente.acta_exencion_pdf),
        },
        'historial_reciente': historial,
    }


# ─────────────────────────────────────────────────────────────
# Citas
# ─────────────────────────────────────────────────────────────

class ConfirmarCitaAPIView(APIView):
    """El alumno confirma su asistencia a la cita (certificado u oficio)."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def post(self, request, pk):
        cita = get_object_or_404(
            CitaDocumentoFisico, pk=pk, expediente__alumno=request.user
        )

        if cita.estado != CitaDocumentoFisico.EstadoCita.PROGRAMADA:
            return _error('Esta cita no puede confirmarse en su estado actual.')

        cita.estado = CitaDocumentoFisico.EstadoCita.CONFIRMADA_ALUMNO
        cita.save(update_fields=['estado'])

        fecha_local = timezone.localtime(cita.fecha_hora)

        notificar_oficina_titulacion(
            cita.expediente,
            'Cita confirmada por el alumno',
            (
                f'{request.user.get_full_name()} confirmó asistencia a la cita '
                f'de {cita.get_tipo_display().lower()} el '
                f'{fecha_local:%d/%m/%Y a las %H:%M} en {cita.lugar}.'
            ),
            url=reverse('oficina_titulacion:citas_pendientes'),
            tipo='AVANCE',
        )

        return Response({
            'message': 'Cita confirmada. Le esperamos en la fecha indicada.',
            'cita': serializar_cita(cita),
        })


def _interpretar_fecha_propuesta(texto):
    """Acepta 'YYYY-MM-DDTHH:MM' (como la web) o ISO 8601 completo."""
    dt = parse_datetime(texto)

    if dt is None:
        raise ValueError('Formato de fecha inválido.')

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())

    return dt


class SolicitarReprogramacionCitaAPIView(APIView):
    """El alumno no puede asistir y solicita una nueva fecha."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def post(self, request, pk):
        cita = get_object_or_404(
            CitaDocumentoFisico, pk=pk, expediente__alumno=request.user
        )

        estados_ok = (
            CitaDocumentoFisico.EstadoCita.PROGRAMADA,
            CitaDocumentoFisico.EstadoCita.CONFIRMADA_ALUMNO,
        )

        if cita.estado not in estados_ok:
            return _error('No puedes solicitar reprogramación para esta cita.')

        notas = str(request.data.get('propuesta_notas') or '').strip()

        if not notas:
            return _error('Indica el motivo por el cual no puedes asistir.')

        nueva_fecha = str(request.data.get('propuesta_fecha') or '').strip()

        if nueva_fecha:
            try:
                cita.propuesta_alumno_fecha = _interpretar_fecha_propuesta(
                    nueva_fecha
                )
            except ValueError:
                return _error('Formato de fecha inválido.')
        else:
            cita.propuesta_alumno_fecha = None

        cita.propuesta_alumno_notas = notas
        cita.estado = CitaDocumentoFisico.EstadoCita.REPROGRAMACION_SOLICITADA
        cita.save()

        fecha_local = timezone.localtime(cita.fecha_hora)
        detalle = (
            f'{request.user.get_full_name()} no puede asistir el '
            f'{fecha_local:%d/%m/%Y a las %H:%M}.'
        )

        if cita.propuesta_alumno_fecha:
            propuesta = timezone.localtime(cita.propuesta_alumno_fecha)
            detalle += f' Propone: {propuesta:%d/%m/%Y a las %H:%M}.'

        detalle += f' Motivo: {notas}'

        notificar_oficina_titulacion(
            cita.expediente,
            'Solicitud de reprogramación de cita',
            detalle,
            url=reverse('oficina_titulacion:citas_pendientes'),
            tipo='URGENTE',
        )

        return Response({
            'message': (
                'Solicitud enviada. Oficina de Titulación te asignará '
                'una nueva fecha.'
            ),
            'cita': serializar_cita(cita),
        })


# ─────────────────────────────────────────────────────────────
# Pago de titulación
# ─────────────────────────────────────────────────────────────

class SubirComprobantePagoAPIView(APIView):
    """El alumno sube o reemplaza su comprobante de pago (PDF)."""

    permission_classes = [IsAlumno, IsCorreoVerificado]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        expediente = _expediente_o_404(request.user)

        if expediente is None:
            return _sin_expediente()

        if expediente.estado != EstadoExpediente.PAGO_PENDIENTE:
            return _error('No estás en la etapa de pago actualmente.')

        referencia = expediente.referencias_pago.filter(activa=True).first()

        if not referencia:
            return _error(
                'Aún no hay preficha de pago disponible. '
                'Espera a que Finanzas la genere.'
            )

        if expediente.pago_validado == 'CARGADO':
            return _error('Tu comprobante ya está en revisión por Finanzas.')

        comprobante = request.FILES.get('comprobante_pago')

        if not comprobante:
            return _error('Por favor, selecciona un archivo.')

        if not _es_pdf(comprobante):
            return _error('El comprobante debe ser un archivo en formato PDF.')

        expediente.comprobante_pago = comprobante
        expediente.pago_validado = 'CARGADO'
        expediente.fecha_subida_pago = timezone.now()
        expediente.save(update_fields=[
            'comprobante_pago',
            'pago_validado',
            'fecha_subida_pago',
            'fecha_ultima_actualizacion',
        ])

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=expediente.estado,
            realizado_por=request.user,
            descripcion='Alumno cargó su comprobante de pago.',
        )

        # Los avisos no deben tumbar el comprobante ya guardado.
        try:
            notificar_usuarios_por_rol(
                [Rol.FINANZAS],
                'Comprobante de pago por validar',
                f'{expediente.alumno.get_full_name()} cargó su comprobante '
                'de pago.',
                tipo='URGENTE',
                url=reverse(
                    'finanzas:expediente_pago_detalle',
                    kwargs={'pk': expediente.pk},
                ),
            )
            notificar_alumno(
                expediente=expediente,
                tipo='AVANCE',
                titulo='Comprobante de pago cargado',
                url=reverse('alumnos:expediente'),
                mensaje=(
                    'Has subido tu comprobante de pago. Finanzas lo '
                    'validará a la brevedad.'
                ),
            )
        except Exception:
            logger.exception('No se pudieron enviar los avisos del comprobante.')

        return Response(
            {
                'message': (
                    '¡Comprobante de pago subido correctamente! '
                    'En espera de validación por Finanzas.'
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class PrefichaPagoEnlaceAPIView(APIView):
    """
    Devuelve un enlace temporal (5 min) para abrir la preficha en PDF.

    El PDF se genera al vuelo, así que no existe una URL de /media/. El enlace
    va firmado para que la app pueda abrirlo en el visor del teléfono (que no
    envía el token JWT).
    """

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def get(self, request):
        expediente = _expediente_o_404(request.user)

        if expediente is None:
            return _sin_expediente()

        if expediente.estado != EstadoExpediente.PAGO_PENDIENTE:
            return _error('La preficha de pago no está disponible en esta etapa.')

        if not expediente.referencias_pago.filter(activa=True).exists():
            return _error('Aún no hay preficha de pago generada por Finanzas.')

        token = signing.dumps(
            {'expediente': expediente.pk, 'alumno': request.user.pk},
            salt=SALT_PREFICHA,
        )

        url = request.build_absolute_uri(
            reverse('api:alumnos:preficha-descarga', kwargs={'token': token})
        )

        return Response({
            'url': url,
            'expira_en_segundos': VIGENCIA_ENLACE_SEGUNDOS,
        })


class PrefichaPagoDescargaView(APIView):
    """Sirve el PDF de la preficha con el enlace firmado del paso anterior."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, token):
        try:
            datos = signing.loads(
                token,
                salt=SALT_PREFICHA,
                max_age=VIGENCIA_ENLACE_SEGUNDOS,
            )
        except signing.BadSignature:
            raise Http404

        expediente = get_object_or_404(
            Expediente,
            pk=datos.get('expediente'),
            alumno_id=datos.get('alumno'),
        )

        if expediente.estado != EstadoExpediente.PAGO_PENDIENTE:
            raise Http404

        referencia = expediente.referencias_pago.filter(activa=True).first()

        if not referencia:
            raise Http404

        from finanzas.preficha_pago import generar_preficha_pago_pdf

        try:
            pdf_bytes = generar_preficha_pago_pdf(referencia)
        except Exception:
            logger.exception('No se pudo generar la preficha de pago.')
            return HttpResponse(
                'No se pudo generar la preficha. Intenta de nuevo.',
                status=500,
            )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="preficha_{referencia.referencia_bancaria}.pdf"'
        )
        return response


# ─────────────────────────────────────────────────────────────
# Constancia / certificado escaneado tras el acto
# ─────────────────────────────────────────────────────────────

class SubirActaExencionAPIView(APIView):
    """El alumno sube su constancia de exención escaneada (PDF)."""

    permission_classes = [IsAlumno, IsCorreoVerificado]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        expediente = _expediente_o_404(request.user)

        if expediente is None:
            return _sin_expediente()

        if expediente.estado != EstadoExpediente.ACTO_REALIZADO:
            return _error(
                'No estás en la etapa para subir la constancia de exención '
                'escaneada.'
            )

        acta = request.FILES.get('acta_exencion_pdf')

        if not acta:
            return _error('Por favor, selecciona un archivo.')

        if not _es_pdf(acta):
            return _error('El documento debe ser un archivo en formato PDF.')

        expediente.acta_exencion_pdf = acta
        expediente.save(
            update_fields=['acta_exencion_pdf', 'fecha_ultima_actualizacion']
        )

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=expediente.estado,
            realizado_por=request.user,
            descripcion='Alumno cargó su constancia de exención escaneada.',
        )

        try:
            notificar_oficina_titulacion(
                expediente,
                'Constancia de exención escaneada subida',
                f'{expediente.alumno.get_full_name()} cargó su constancia de '
                'exención escaneada para revisión final.',
                tipo='AVANCE',
                url=reverse(
                    'oficina_titulacion:expediente_detalle',
                    kwargs={'pk': expediente.pk},
                ),
            )
        except Exception:
            logger.exception('No se pudo avisar a Oficina de la constancia.')

        return Response(
            {
                'message': (
                    '¡Constancia de exención subida correctamente! En espera '
                    'de validación final por Oficina de Titulación.'
                ),
            },
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────
# Guía y Documentos de Protocolo (PDF generado al vuelo)
# ─────────────────────────────────────────────────────────────

def _jurado_y_acto(expediente):
    jurado = getattr(expediente, 'jurado', None)
    acto = getattr(expediente, 'acto_protocolario', None)
    return jurado, acto


class DocumentosProtocoloEnlaceAPIView(APIView):
    """Enlace temporal (5 min) para abrir la Guía y Documentos de Protocolo."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def get(self, request):
        expediente = _expediente_o_404(request.user)

        if expediente is None:
            return _sin_expediente()

        if expediente.estado not in ESTADOS_DESCARGA_PROTOCOLO:
            return _error('Aún no puedes descargar los documentos de protocolo.')

        jurado, acto = _jurado_y_acto(expediente)

        if not jurado or not acto:
            return _error(
                'Ocurrió un error al generar la Guía de Protocolo. '
                'Por favor, contacta a la Oficina de Titulación.'
            )

        token = signing.dumps(
            {'expediente': expediente.pk, 'alumno': request.user.pk},
            salt=SALT_PROTOCOLO,
        )

        url = request.build_absolute_uri(
            reverse('api:alumnos:protocolo-descarga', kwargs={'token': token})
        )

        return Response({
            'url': url,
            'expira_en_segundos': VIGENCIA_ENLACE_SEGUNDOS,
        })


class DocumentosProtocoloDescargaView(APIView):
    """Sirve el PDF de protocolo con el enlace firmado del paso anterior."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, token):
        try:
            datos = signing.loads(
                token,
                salt=SALT_PROTOCOLO,
                max_age=VIGENCIA_ENLACE_SEGUNDOS,
            )
        except signing.BadSignature:
            raise Http404

        expediente = get_object_or_404(
            Expediente,
            pk=datos.get('expediente'),
            alumno_id=datos.get('alumno'),
        )

        if expediente.estado not in ESTADOS_DESCARGA_PROTOCOLO:
            raise Http404

        jurado, acto = _jurado_y_acto(expediente)

        if not jurado or not acto:
            raise Http404

        from administracion.pdf_oficio import generar_documentos_protocolo_pdf

        try:
            pdf_bytes = generar_documentos_protocolo_pdf(jurado, acto)
        except Exception:
            logger.exception('No se pudo generar la Guía de Protocolo.')
            return HttpResponse(
                'No se pudo generar la Guía de Protocolo. Contacta a la '
                'Oficina de Titulación.',
                status=500,
            )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="Guia_Protocolo_{expediente.alumno.username}.pdf"'
        )
        return response