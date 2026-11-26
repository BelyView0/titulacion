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
)
from expediente.notifications import registrar_cambio_estado

from .permissions import IsAlumno, IsCorreoVerificado

logger = logging.getLogger(__name__)


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
        if Expediente.objects.filter(alumno=request.user).exists():
            return Response(
                {'detail': 'Ya tienes un expediente registrado.'},
                status=status.HTTP_409_CONFLICT,
            )

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