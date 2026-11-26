from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from alumnos.models import Notificacion
from expediente.models import Documento
from .serializers import DocumentoAlumnoSerializer
from .permissions import IsAlumno
from .serializers import (
    PerfilAlumnoSerializer,
    DashboardAlumnoSerializer,
    NotificacionDashboardSerializer,
)

from django.shortcuts import get_object_or_404
from django.utils import timezone

from expediente.models import (
    Documento,
    EstadoDocumento,
    EstadoExpediente,
    HistorialDocumento,
)

from django.utils.crypto import get_random_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string

from administracion.models import (
    EmailVerificationOTP,
    ConfiguracionInstitucional,
    Rol,
    Usuario,
)

from .permissions import IsAlumno, IsCorreoVerificado
from django.urls import reverse
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from expediente.models import EstadoValidacion, ValidacionDocumento
from expediente.notifications import registrar_cambio_documento
from titulacion.validators import validar_archivo_tipo_documento

from .expediente_api import (
    ESTADOS_DOCUMENTO_EDITABLES,
    ESTADOS_PRECARGA_DOCUMENTOS,
)

class PerfilAlumnoView(APIView):
    """
    Consulta y actualiza el perfil del alumno autenticado.
    """

    permission_classes = [IsAlumno]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        """
        Obtiene el perfil del alumno autenticado.
        """

        serializer = PerfilAlumnoSerializer(
            request.user,
            context={'request': request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        """
        Actualiza los datos permitidos del perfil.
        """

        serializer = PerfilAlumnoSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


class DashboardAlumnoView(APIView):
    permission_classes = [IsAlumno, IsCorreoVerificado]

    def get(self, request):
        notificaciones_no_leidas = Notificacion.objects.filter(
            destinatario=request.user,
            leida=False
        ).count()

        notificaciones_recientes = Notificacion.objects.filter(
            destinatario=request.user
        ).order_by('-fecha')[:5]

        serializer = DashboardAlumnoSerializer(
            request.user,
            context={'request': request}
        )

        data = serializer.data

        data['notificaciones_no_leidas'] = notificaciones_no_leidas

        data['notificaciones_recientes'] = NotificacionDashboardSerializer(
            notificaciones_recientes,
            many=True
        ).data

        return Response(
            data,
            status=status.HTTP_200_OK
        )
        
        
class DocumentosAlumnoView(APIView):
    """
    Consulta los documentos del expediente
    perteneciente al alumno autenticado.
    """

    permission_classes = [IsAlumno]

    def get(self, request):
        documentos = Documento.objects.filter(
            expediente__alumno=request.user
        ).select_related(
            'tipo_documento',
            'expediente'
        ).order_by(
            'tipo_documento__orden'
        )

        serializer = DocumentoAlumnoSerializer(
            documentos,
            many=True,
            context={'request': request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )
        
class SolicitarCorreccionControlAPIView(APIView):
    """
    Recibe una solicitud de corrección del número de control
    y notifica a los administradores.
    """

    permission_classes = [IsAlumno]

    def post(self, request):
        nuevo_control = str(
            request.data.get('nuevo_control') or ''
        ).strip()

        comentario = str(
            request.data.get('comentario') or ''
        ).strip()

        if not nuevo_control:
            return Response(
                {
                    'detail': 'Debes proporcionar el número de control correcto.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        admins = Usuario.objects.filter(
            rol=Rol.ADMINISTRADOR
        )

        url_admin = request.build_absolute_uri(
            reverse(
                'administracion:usuario_editar',
                args=[user.pk]
            )
        )

        mensaje = (
            f'El usuario {user.get_full_name()} ({user.username}) '
            f'ha solicitado un cambio de su número de control/empleado a: '
            f'{nuevo_control}.'
        )

        if comentario:
            mensaje += f'\nComentario: {comentario}'

        for admin in admins:

            # Crear notificación interna
            Notificacion.objects.create(
                destinatario=admin,
                tipo='URGENTE',
                titulo='Solicitud de cambio de Número de Control',
                mensaje=mensaje,
                url_relacionada=reverse(
                    'administracion:usuario_editar',
                    args=[user.pk]
                )
            )

            # Enviar correo electrónico
            if admin.email:
                try:
                    html_content = render_to_string(
                        'emails/notificacion_generica.html',
                        {
                            'titulo': 'Solicitud de cambio de Número de Control',
                            'saludo': f'Hola {admin.get_full_name()},',
                            'mensaje': mensaje,
                            'url_accion': url_admin
                        }
                    )

                    msg = EmailMultiAlternatives(
                        'Solicitud de cambio de Número de Control',
                        (
                            f'{mensaje}\n\n'
                            f'Puedes revisar y editar el usuario aquí: {url_admin}'
                        ),
                        settings.DEFAULT_FROM_EMAIL,
                        [admin.email]
                    )

                    msg.attach_alternative(
                        html_content,
                        'text/html'
                    )

                    msg.send(fail_silently=True)

                except Exception:
                    pass

        return Response(
            {
                'detail': (
                    'Tu solicitud de corrección ha sido enviada '
                    'a los administradores.'
                )
            },
            status=status.HTTP_200_OK
        )
        
class CargarDocumentoAlumnoView(APIView):
    """
    Permite al alumno cargar o reemplazar un documento de su expediente.

    Aplica las mismas reglas que DocumentoCargarView de la web:
      - se permite precargar desde que existe el expediente
        (ESTADOS_PRECARGA_DOCUMENTOS), no solo en CARGA_DOCUMENTOS;
      - solo se puede subir si el documento está pendiente, cargado,
        rechazado o requiere corrección;
      - valida formato y tamaño con validar_archivo_tipo_documento;
      - deja la validación de Oficina de Titulación en «pendiente» y
        registra el movimiento en el historial.
    """

    permission_classes = [IsAlumno]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        # Buscar únicamente documentos pertenecientes al alumno autenticado.
        documento = get_object_or_404(
            Documento.objects.select_related(
                'expediente',
                'tipo_documento'
            ),
            pk=pk,
            expediente__alumno=request.user
        )

        expediente = documento.expediente
        tipo_documento = documento.tipo_documento

        if expediente.estado not in ESTADOS_PRECARGA_DOCUMENTOS:
            return Response(
                {
                    'detail': (
                        'La carga de documentos no está disponible '
                        'en la etapa actual del expediente.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if documento.estado not in ESTADOS_DOCUMENTO_EDITABLES:
            return Response(
                {
                    'detail': 'Este documento no requiere acción en este momento.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        archivo = request.FILES.get('archivo')

        if not archivo:
            return Response(
                {'archivo': 'Debes seleccionar un archivo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Formato y tamaño según el tipo de documento (igual que la web).
        try:
            validar_archivo_tipo_documento(archivo, tipo_documento)
        except DjangoValidationError as error:
            return Response(
                {'archivo': ' '.join(error.messages)},
                status=status.HTTP_400_BAD_REQUEST
            )

        notas = request.data.get('notas_alumno', '')

        # Identificar si se está reemplazando un archivo existente.
        reemplazando = bool(documento.archivo)

        with transaction.atomic():
            if reemplazando:
                documento.version += 1

            documento.archivo = archivo
            documento.estado = EstadoDocumento.CARGADO
            documento.fecha_carga = timezone.now()
            documento.notas_alumno = notas

            documento.save()

            # Una nueva versión vuelve a quedar pendiente de validación.
            ValidacionDocumento.objects.filter(documento=documento).delete()
            ValidacionDocumento.objects.create(
                documento=documento,
                estado=EstadoValidacion.PENDIENTE
            )

            registrar_cambio_documento(
                documento=documento,
                accion=(
                    f'Alumno cargó versión {documento.version} del documento.'
                ),
                realizado_por=request.user,
                observaciones=notas,
            )

        serializer = DocumentoAlumnoSerializer(
            documento,
            context={'request': request}
        )

        return Response(
            {
                'detail': (
                    'Documento reemplazado correctamente.'
                    if reemplazando
                    else 'Documento cargado correctamente.'
                ),
                'documento': serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class EnviarVerificacionCorreoAPIView(APIView):
    """
    Envía un código OTP al correo personal o institucional del alumno.
    """

    permission_classes = [IsAlumno]

    def post(self, request, tipo):
        user = request.user

        if tipo not in ['personal', 'institucional']:
            return Response(
                {'detail': 'Tipo de correo inválido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        correo_destino = (
            user.email
            if tipo == 'personal'
            else user.correo_institucional
        )

        if not correo_destino:
            return Response(
                {'detail': 'No tienes registrado este tipo de correo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # No enviar otro código si el correo ya está verificado.
        correo_verificado = (
            user.email_verificado
            if tipo == 'personal'
            else user.correo_institucional_verificado
        )

        if correo_verificado:
            return Response(
                {'detail': 'Este correo ya se encuentra verificado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not ConfiguracionInstitucional.smtp_configurado():
            return Response(
                {'detail': 'El servicio de correo no está configurado.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Invalidar códigos anteriores no utilizados.
        EmailVerificationOTP.objects.filter(
            usuario=user,
            tipo_correo=tipo.upper(),
            usado=False
        ).update(usado=True)

        # Generar un nuevo código.
        codigo = get_random_string(
            length=6,
            allowed_chars='0123456789'
        )

        otp = EmailVerificationOTP.objects.create(
            usuario=user,
            tipo_correo=tipo.upper(),
            email_a_verificar=correo_destino,
            codigo=codigo
        )

        subject = (
            f'Código de Verificación para Correo {tipo.capitalize()}'
        )

        message = (
            f'Tu código de verificación es: {codigo}\n'
            'Este código expirará en 15 minutos.'
        )

        try:
            html_content = render_to_string(
                'emails/otp_codigo.html',
                {
                    'codigo': codigo,
                    'user_name': user.get_full_name() or user.username,
                    'full_name': user.get_full_name() or user.username,
                    'mensaje_corto': (
                        f'Has solicitado verificar tu correo {tipo}'
                    ),
                    'minutos_validez': 15,
                }
            )

            email = EmailMultiAlternatives(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [correo_destino]
            )

            email.attach_alternative(html_content, 'text/html')
            email.send(fail_silently=False)

        except Exception:
            otp.delete()

            return Response(
                {
                    'detail': (
                        'No se pudo enviar el código. '
                        'Contacta al administrador.'
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return Response(
            {
                'detail': 'Código de verificación enviado correctamente.',
                'tipo': tipo,
                'correo': correo_destino,
            },
            status=status.HTTP_200_OK
        )

class ValidarVerificacionCorreoAPIView(APIView):
    """
    Valida el código OTP y marca el correo correspondiente como verificado.
    """

    permission_classes = [IsAlumno]

    def post(self, request, tipo):
        user = request.user

        if tipo not in ['personal', 'institucional']:
            return Response(
                {'detail': 'Tipo de correo inválido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        correo_destino = (
            user.email
            if tipo == 'personal'
            else user.correo_institucional
        )

        if not correo_destino:
            return Response(
                {'detail': 'No tienes registrado este tipo de correo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        correo_verificado = (
            user.email_verificado
            if tipo == 'personal'
            else user.correo_institucional_verificado
        )

        if correo_verificado:
            return Response(
                {'detail': 'Este correo ya está verificado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        codigo = str(request.data.get('codigo', '')).strip()

        if len(codigo) != 6 or not codigo.isdigit():
            return Response(
                {'detail': 'Debes ingresar un código válido de 6 dígitos.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp = EmailVerificationOTP.objects.filter(
            usuario=user,
            tipo_correo=tipo.upper(),
            codigo=codigo,
            email_a_verificar=correo_destino,
            usado=False
        ).order_by('-id').first()

        if not otp:
            return Response(
                {
                    'detail': (
                        'El código es incorrecto o ya fue utilizado.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not otp.is_valid():
            return Response(
                {
                    'detail': (
                        'El código ha expirado. '
                        'Solicita uno nuevo.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Marcar el código como utilizado.
        otp.usado = True
        otp.save(update_fields=['usado'])

        # Marcar el correo correspondiente como verificado.
        if tipo == 'personal':
            user.email_verificado = True
            user.save(update_fields=['email_verificado'])
        else:
            user.correo_institucional_verificado = True
            user.save(
                update_fields=['correo_institucional_verificado']
            )

        return Response(
            {
                'detail': (
                    f'Tu correo {tipo} ha sido verificado exitosamente.'
                ),
                'tipo': tipo,
                'verificado': True,
                'requiere_verificacion_correo': (
                    user.requiere_verificacion_correo()
                ),
            },
            status=status.HTTP_200_OK
        )