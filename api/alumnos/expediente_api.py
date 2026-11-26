"""
API del expediente para la app móvil (SIGET).

Replica la lógica de alumnos/views.py para que web y app se comporten igual:
  - serializar_expediente()        -> resumen del expediente (panel de inicio)
  - CatalogoExpedienteAPIView      -> planes, modalidades y asesores del formulario
  - ExpedienteCrearAPIView         -> ExpedienteCreateView de la web
  - ConfirmarAsistenciaAPIView     -> ConfirmarAsistenciaAlumnoView de la web
"""
import logging

from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from administracion.models import ContactoArea, Profesor
from expediente.documentos_semestres import sincronizar_documentos_expediente
from expediente.models import (
    ConfirmacionActo,
    EstadoExpediente,
    Expediente,
    Modalidad,
    PlanEstudios,
    RecepcionEmpastado,
    HistorialExpediente,
    HistorialDocumento,
)
from expediente.notifications import registrar_cambio_estado

from alumnos.views import (
    ESTADOS_ENVIO_DOCUMENTOS,
    ESTADOS_PRECARGA_DOCUMENTOS,
    _obligatorios_sin_cargar,
    etapas_y_completados,
)
from expediente.models import EstadoDocumento
from expediente.notifications import (
    notificar_alumno,
    notificar_oficina_titulacion,
)

from .permissions import IsAlumno, IsCorreoVerificado

logger = logging.getLogger(__name__)

# Estados de documento en los que el alumno puede subir o reemplazar el
# archivo (igual que DocumentoCargarView de la web).
ESTADOS_DOCUMENTO_EDITABLES = (
    EstadoDocumento.PENDIENTE,
    EstadoDocumento.CARGADO,
    EstadoDocumento.RECHAZADO,
    EstadoDocumento.REQUIERE_CORRECCION,
)


# ─────────────────────────────────────────────────────────────
# Resumen del expediente (lo usa el dashboard)
# ─────────────────────────────────────────────────────────────

def _serializar_acto(expediente):
    # El reverse OneToOne lanza RelatedObjectDoesNotExist (subclase de
    # AttributeError) cuando no existe, por eso getattr con valor por defecto.
    acto = getattr(expediente, 'acto_protocolario', None)

    if not acto:
        return None

    confirmaciones = list(acto.confirmaciones.all())
    mia = next((c for c in confirmaciones if c.rol == 'ALUMNO'), None)

    return {
        'fecha_acto': acto.fecha_acto,
        'lugar': acto.lugar,
        'confirmaciones_completas': acto.confirmaciones_completas(),
        'mi_confirmacion': (
            None
            if mia is None
            else {
                'confirmado': mia.confirmado,
                'fecha_confirmacion': mia.fecha_confirmacion,
            }
        ),
        'confirmaciones': [
            {
                'rol': c.rol,
                'rol_display': c.get_rol_display(),
                'confirmado': c.confirmado,
                'fecha_confirmacion': c.fecha_confirmacion,
            }
            for c in confirmaciones
        ],
    }


def serializar_expediente(expediente):
    """Datos que muestra el panel de inicio del alumno en la web."""
    modalidad = expediente.modalidad
    plan = modalidad.plan_estudios if modalidad else expediente.plan_estudios

    return {
        'id': expediente.id,
        'estado': expediente.estado,
        'estado_display': expediente.get_estado_display(),
        'estado_color': expediente.get_estado_display_color(),
        'porcentaje_progreso': expediente.porcentaje_progreso(),
        'modalidad': modalidad.nombre if modalidad else None,
        'plan_estudios': plan.nombre if plan else None,
        'asesor': expediente.asesor.get_full_name() if expediente.asesor else None,
        'titulo_trabajo': expediente.titulo_trabajo,
        'nombre_empresa': expediente.nombre_empresa,
        'documentos': {
            'total': expediente.documentos_total(),
            'aprobados': expediente.documentos_aprobados(),
            'pendientes': expediente.documentos_pendientes(),
        },
        'fecha_conclusion': expediente.fecha_conclusion,
        'empastado_recibido': RecepcionEmpastado.objects.filter(
            expediente=expediente
        ).exists(),
        'acto': _serializar_acto(expediente),
    }


# ─────────────────────────────────────────────────────────────
# Catálogos del formulario de creación
# ─────────────────────────────────────────────────────────────

class CatalogoExpedienteAPIView(APIView):
    """Equivale al formulario + ModalidadesPorPlanView (AJAX) de la web."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def get(self, request):
        planes = PlanEstudios.objects.filter(activo=True).prefetch_related(
            Prefetch(
                'modalidades',
                queryset=Modalidad.objects.filter(activa=True).order_by('nombre'),
            )
        )

        asesores = Profesor.objects.filter(activo=True)
        contacto = ContactoArea.servicios_escolares()

        return Response({
            'planes': [
                {
                    'id': plan.id,
                    'nombre': plan.nombre,
                    'etiqueta': str(plan),
                    'modalidades': [
                        {'id': m.id, 'nombre': m.nombre}
                        for m in plan.modalidades.all()
                    ],
                }
                for plan in planes
            ],
            'asesores': [
                {'id': p.id, 'nombre': p.get_full_name()}
                for p in asesores
            ],
            'contacto_escolares': (
                {
                    'area': contacto.get_area_display(),
                    'responsable': contacto.nombre_responsable,
                    'telefono': contacto.telefono_completo(),
                    'correo': contacto.correo_departamento,
                }
                if contacto
                else None
            ),
        })

# ─────────────────────────────────────────────────────────────
# Creación del expediente
# ─────────────────────────────────────────────────────────────

_MENSAJES_CAMPO = {
    'required': 'Este campo es obligatorio.',
    'null': 'Este campo es obligatorio.',
    'blank': 'Este campo es obligatorio.',
    'does_not_exist': 'Selecciona una opción válida.',
    'incorrect_type': 'Selecciona una opción válida.',
}


class ExpedienteCrearSerializer(serializers.Serializer):
    """Mismos campos y validaciones que ExpedienteForm de la web."""

    plan_estudios = serializers.PrimaryKeyRelatedField(
        queryset=PlanEstudios.objects.filter(activo=True),
        error_messages=_MENSAJES_CAMPO,
    )
    modalidad = serializers.PrimaryKeyRelatedField(
        queryset=Modalidad.objects.filter(activa=True),
        error_messages=_MENSAJES_CAMPO,
    )
    asesor = serializers.PrimaryKeyRelatedField(
        queryset=Profesor.objects.filter(activo=True),
        error_messages=_MENSAJES_CAMPO,
    )
    titulo_trabajo = serializers.CharField(
        max_length=500,
        error_messages={
            **_MENSAJES_CAMPO,
            'max_length': 'Máximo 500 caracteres.',
        },
    )
    nombre_empresa = serializers.CharField(
        max_length=300,
        error_messages={
            **_MENSAJES_CAMPO,
            'max_length': 'Máximo 300 caracteres.',
        },
    )

    def validate(self, attrs):
        if attrs['modalidad'].plan_estudios_id != attrs['plan_estudios'].id:
            raise serializers.ValidationError(
                {'modalidad': 'La modalidad no corresponde al plan seleccionado.'}
            )

        return attrs


MENSAJE_EXPEDIENTE_CREADO = (
    'Expediente creado correctamente. Ya puedes precargar tus documentos; '
    'el envío a revisión se habilitará después de la cita de firma de certificado.'
)


class ExpedienteCrearAPIView(APIView):
    """El alumno crea su expediente inicial seleccionando modalidad."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def post(self, request):
        usuario = request.user

        if Expediente.objects.filter(alumno=usuario).exists():
            return Response(
                {'detail': 'Ya tienes un expediente registrado.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ExpedienteCrearSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        try:
            with transaction.atomic():
                expediente = Expediente(
                    alumno=usuario,
                    plan_estudios=datos['plan_estudios'],
                    modalidad=datos['modalidad'],
                    asesor=datos['asesor'],
                    titulo_trabajo=datos['titulo_trabajo'],
                    nombre_empresa=datos['nombre_empresa'],
                    estado=EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
                )
                expediente.save()

                sincronizar_documentos_expediente(expediente)

                registrar_cambio_estado(
                    expediente=expediente,
                    estado_nuevo=EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
                    realizado_por=usuario,
                    descripcion=(
                        'Expediente registrado. Pendiente cita para firma '
                        'de certificado.'
                    ),
                )
        except IntegrityError:
            # Doble toque / dos peticiones simultáneas (OneToOne con alumno)
            return Response(
                {'detail': 'Ya tienes un expediente registrado.'},
                status=status.HTTP_409_CONFLICT,
            )

        expediente.refresh_from_db()

        return Response(
            {
                'message': MENSAJE_EXPEDIENTE_CREADO,
                'expediente': serializar_expediente(expediente),
            },
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────
# Confirmación de asistencia al acto protocolario
# ─────────────────────────────────────────────────────────────

class ConfirmarAsistenciaAPIView(APIView):
    """El alumno confirma su propia asistencia al acto protocolario."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def post(self, request):
        try:
            expediente = request.user.expediente
        except Expediente.DoesNotExist:
            return Response(
                {'detail': 'No tienes un expediente registrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        acto = getattr(expediente, 'acto_protocolario', None)

        if not acto:
            return Response(
                {'detail': 'No hay un acto protocolario programado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        confirmacion = ConfirmacionActo.objects.filter(
            acto=acto, rol='ALUMNO'
        ).first()

        if not confirmacion:
            return Response(
                {'detail': 'No se encontró tu confirmación.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if confirmacion.confirmado:
            return Response(
                {
                    'detail': 'Ya confirmaste tu asistencia anteriormente.',
                    'expediente': serializar_expediente(expediente),
                },
                status=status.HTTP_200_OK,
            )

        confirmacion.confirmado = True
        confirmacion.fecha_confirmacion = timezone.now()
        confirmacion.save()

        # Los correos no deben tumbar la confirmación ya guardada.
        try:
            from expediente.views_confirmacion import (
                _enviar_correo_acto_confirmado,
                _enviar_correo_confirmacion_recibida,
            )

            _enviar_correo_confirmacion_recibida(confirmacion, acto)

            if acto.confirmaciones_completas():
                _enviar_correo_acto_confirmado(acto)
        except Exception:
            logger.exception('No se pudo enviar el correo de confirmación de asistencia.')

        return Response(
            {
                'message': (
                    '¡Tu asistencia ha sido confirmada exitosamente! '
                    'Se te envió un correo de confirmación.'
                ),
                'expediente': serializar_expediente(expediente),
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────
# Mi Expediente: detalle con documentos y envío a revisión
# ─────────────────────────────────────────────────────────────

def _expediente_del_alumno(usuario):
    try:
        return usuario.expediente
    except Expediente.DoesNotExist:
        return None


def _respuesta_sin_expediente():
    return Response(
        {
            'detail': 'No tienes un expediente registrado.',
            'sin_expediente': True,
        },
        status=status.HTTP_404_NOT_FOUND,
    )


def _nombres_documentos_faltantes(expediente):
    return [
        d.tipo_documento.nombre
        for d in _obligatorios_sin_cargar(expediente).select_related('tipo_documento')
    ]



class ExpedienteDetalleAPIView(APIView):
    """Equivale a ExpedienteDetalleView de la web (sección «Mi Expediente»)."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def get(self, request):
        expediente = _expediente_del_alumno(request.user)

        if expediente is None:
            return _respuesta_sin_expediente()

        # Crea los espacios de documentos que falten según semestres cursados.
        sincronizar_documentos_expediente(expediente)

        # Import local: serializers.py importa este módulo.
        from .serializers import DocumentoAlumnoSerializer

        puede_cargar = expediente.estado in ESTADOS_PRECARGA_DOCUMENTOS
        puede_enviar = expediente.estado in ESTADOS_ENVIO_DOCUMENTOS

        documentos = DocumentoAlumnoSerializer(
            expediente.documentos.select_related(
                'tipo_documento', 'validacion'
            ).order_by('tipo_documento__orden'),
            many=True,
            context={'request': request},
        ).data

        for documento in documentos:
            documento['puede_cargar'] = (
                puede_cargar
                and documento['estado'] in ESTADOS_DOCUMENTO_EDITABLES
            )

        faltantes = _nombres_documentos_faltantes(expediente)

        tiene_obligatorios = expediente.documentos.filter(
            tipo_documento__es_obligatorio=True
        ).exists()

        return Response({
            'expediente': serializar_expediente(expediente),
            'puede_cargar_documentos': puede_cargar,
            'puede_enviar_documentos': puede_enviar,
            'documentos_faltantes': faltantes,
            'todos_obligatorios_cargados': tiene_obligatorios and not faltantes,
            'documentos': documentos,
        })

    def patch(self, request):
        expediente = _expediente_del_alumno(request.user)

        if expediente is None:
            return _respuesta_sin_expediente()

        # Estados en los que el alumno puede modificar sus datos.
        estados_editables = [
            EstadoExpediente.DATOS_EXPEDIENTE,
            EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
            EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA,
            EstadoExpediente.CARGA_DOCUMENTOS,
            EstadoExpediente.EN_CORRECCION,
        ]

        if expediente.estado not in estados_editables:
            return Response(
                {
                    'detail': (
                        'No puedes modificar los datos de tu expediente '
                        'en su estado actual.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Import local para evitar importaciones circulares.
        from .serializers import ExpedienteActualizarSerializer

        serializer = ExpedienteActualizarSerializer(
            data=request.data,
            context={'expediente': expediente},
        )

        serializer.is_valid(raise_exception=True)

        datos = serializer.validated_data

        nombres_campos = {
            'plan_estudios': 'plan de estudios',
            'modalidad': 'modalidad de titulación',
            'asesor': 'asesor',
            'titulo_trabajo': 'título del trabajo',
            'nombre_empresa': 'nombre de la empresa',
        }

        campos_modificados = []

        # Identificar y aplicar únicamente los campos que cambiaron.
        for campo, valor in datos.items():
            valor_actual = getattr(expediente, campo)

            if valor_actual != valor:
                setattr(expediente, campo, valor)
                campos_modificados.append(nombres_campos[campo])

        # Evitar registrar cambios cuando los datos son iguales.
        if not campos_modificados:
            return Response(
                {
                    'message': 'No se realizaron modificaciones.',
                    'expediente': serializar_expediente(expediente),
                },
                status=status.HTTP_200_OK,
            )

        # Guardar los cambios y registrar el movimiento en el historial.
        with transaction.atomic():
            estado_actual = expediente.estado

            expediente.save()

            HistorialExpediente.objects.create(
                expediente=expediente,
                estado_anterior=estado_actual,
                estado_nuevo=estado_actual,
                realizado_por=request.user,
                descripcion=(
                    'Actualizó los datos del expediente: '
                    + ', '.join(campos_modificados)
                    + '.'
                ),
            )

        expediente.refresh_from_db()

        return Response(
            {
                'message': (
                    'Los datos del expediente se actualizaron correctamente.'
                ),
                'expediente': serializar_expediente(expediente),
            },
            status=status.HTTP_200_OK,
        )

class EnviarDocumentosAPIView(APIView):
    """El alumno envía su expediente a revisión de Oficina de Titulación."""

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def post(self, request):
        expediente = _expediente_del_alumno(request.user)

        if expediente is None:
            return _respuesta_sin_expediente()

        if expediente.estado not in ESTADOS_ENVIO_DOCUMENTOS:
            return Response(
                {
                    'detail': (
                        'El envío a revisión solo está disponible después de '
                        'la cita de certificado y cuando el expediente esté en '
                        'etapa de carga o corrección.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        faltantes = _nombres_documentos_faltantes(expediente)

        if faltantes:
            resumen = ', '.join(faltantes[:3])
            if len(faltantes) > 3:
                resumen += '...'

            return Response(
                {
                    'detail': f'Faltan documentos obligatorios: {resumen}',
                    'documentos_faltantes': faltantes,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.EN_REVISION,
                realizado_por=request.user,
                descripcion='Alumno envió expediente completo a revisión.',
            )
            notificar_oficina_titulacion(
                expediente,
                'Expediente en revisión',
                f'{expediente.alumno.get_full_name()} envió su expediente a revisión.',
                url=reverse(
                    'oficina_titulacion:expediente_detalle',
                    kwargs={'pk': expediente.pk},
                ),
            )

        # El correo al alumno no debe tumbar el envío ya registrado.
        try:
            notificar_alumno(
                expediente=expediente,
                tipo='AVANCE',
                titulo='Documentos enviados a revisión',
                mensaje='Tu expediente fue enviado a Oficina de Titulación para revisión.',
                url=reverse('alumnos:expediente'),
            )
        except Exception:
            logger.exception('No se pudo notificar al alumno el envío a revisión.')

        expediente.refresh_from_db()

        return Response(
            {
                'message': '¡Expediente enviado a revisión!',
                'expediente': serializar_expediente(expediente),
            },
            status=status.HTTP_200_OK,
        )
        
class HistorialExpedienteAPIView(APIView):
    permission_classes = [IsAlumno, IsCorreoVerificado]

    def get(self, request):
        expediente = _expediente_del_alumno(request.user)

        if not expediente:
            return _respuesta_sin_expediente()

        cambios_expediente = HistorialExpediente.objects.filter(
            expediente=expediente
        ).select_related('realizado_por')

        cambios_documentos = HistorialDocumento.objects.filter(
            documento__expediente=expediente
        ).select_related(
            'realizado_por',
            'documento__tipo_documento'
        )

        historial = []

        for cambio in cambios_expediente:
            historial.append({
                'id': f'expediente-{cambio.pk}',
                'tipo': 'EXPEDIENTE',
                'fecha': cambio.fecha,
                'titulo': 'Cambio en el expediente',
                'descripcion': cambio.descripcion,
                'estado_anterior': cambio.get_estado_anterior_display(),
                'estado_nuevo': cambio.get_estado_nuevo_display(),
                'documento': None,
                'realizado_por': (
                    cambio.realizado_por.get_full_name()
                    if cambio.realizado_por
                    else 'Sistema'
                ),
            })

        for cambio in cambios_documentos:
            historial.append({
                'id': f'documento-{cambio.pk}',
                'tipo': 'DOCUMENTO',
                'fecha': cambio.fecha,
                'titulo': cambio.accion,
                'descripcion': cambio.observaciones,
                'estado_anterior': None,
                'estado_nuevo': None,
                'documento': cambio.documento.tipo_documento.nombre,
                'departamento': cambio.departamento,
                'realizado_por': (
                    cambio.realizado_por.get_full_name()
                    if cambio.realizado_por
                    else 'Sistema'
                ),
            })

        historial.sort(
            key=lambda elemento: elemento['fecha'],
            reverse=True
        )

        return Response({
            'historial': historial
        }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────
# Seguimiento (equivale a TimelineView / alumnos/expediente/timeline.html)
# ─────────────────────────────────────────────────────────────

class SeguimientoAPIView(APIView):
    """GET /api/v1/alumnos/seguimiento/

    Entrega lo mismo que la vista web recibe en su contexto: expediente,
    estados_proceso, estados_completados e historial (más reciente primero).
    Sin expediente responde 200 con `expediente: null` (la web muestra el
    aviso "No tienes un expediente de titulación activo").
    """

    permission_classes = [IsAlumno, IsCorreoVerificado]

    def get(self, request):
        expediente = _expediente_del_alumno(request.user)

        if not expediente:
            return Response({
                'expediente': None,
                'estados_proceso': [],
                'estados_completados': [],
                'historial': [],
            })

        modalidad = expediente.modalidad
        plan = modalidad.plan_estudios if modalidad else expediente.plan_estudios

        estados_proceso, estados_completados = etapas_y_completados(expediente)

        historial = [
            {
                'id': h.pk,
                'descripcion': h.descripcion,
                'estado_nuevo': h.estado_nuevo,
                'estado_nuevo_display': h.get_estado_nuevo_display(),
                'estado_nuevo_color': h.get_estado_nuevo_color(),
                'estado_anterior': h.estado_anterior or None,
                'estado_anterior_display': (
                    h.get_estado_anterior_display() if h.estado_anterior else None
                ),
                'fecha': h.fecha,
                'realizado_por': (
                    h.realizado_por.get_full_name() if h.realizado_por else None
                ),
            }
            for h in expediente.historial.select_related('realizado_por').all()
        ]

        return Response({
            'expediente': {
                'modalidad': modalidad.nombre if modalidad else None,
                'plan_estudios': plan.nombre if plan else None,
                'estado': expediente.estado,
                'estado_display': expediente.get_estado_display(),
                'estado_color': expediente.get_estado_display_color(),
                'porcentaje_progreso': expediente.porcentaje_progreso(),
            },
            'estados_proceso': [
                {'valor': str(valor), 'etiqueta': str(etiqueta)}
                for valor, etiqueta in estados_proceso
            ],
            'estados_completados': [str(v) for v in estados_completados],
            'historial': historial,
        })