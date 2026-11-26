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
)

from .permissions import IsAlumno, IsCorreoVerificado


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
            request.user
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
        
class CargarDocumentoAlumnoView(APIView):
    """
    Permite al alumno cargar o reemplazar un documento de su expediente.
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

        # Verificar que el expediente permita cargar documentos.
        estados_permitidos = [
            EstadoExpediente.CARGA_DOCUMENTOS,
            EstadoExpediente.EN_CORRECCION,
        ]

        if expediente.estado not in estados_permitidos:
            return Response(
                {
                    'detail': 'El expediente no se encuentra en una etapa que permita cargar documentos.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # No permitir reemplazar documentos aprobados.
        if documento.estado == EstadoDocumento.APROBADO:
            return Response(
                {
                    'detail': 'Este documento ya fue aprobado y no puede reemplazarse.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener el archivo enviado.
        archivo = request.FILES.get('archivo')

        if not archivo:
            return Response(
                {
                    'archivo': 'Debes seleccionar un archivo.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar extensión.
        if not tipo_documento.admite_extension(archivo.name):
            return Response(
                {
                    'archivo': (
                        'El formato del archivo no está permitido. '
                        f'Formatos admitidos: {tipo_documento.formatos_admitidos}'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar tamaño máximo.
        tamano_maximo = int(
            tipo_documento.tamano_max_mb * 1024 * 1024
        )

        if archivo.size > tamano_maximo:
            return Response(
                {
                    'archivo': (
                        f'El archivo supera el tamaño máximo permitido '
                        f'de {tipo_documento.tamano_max_mb} MB.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener notas opcionales.
        notas = request.data.get('notas_alumno', '')

        # Identificar si se está reemplazando un archivo existente.
        reemplazando = bool(documento.archivo)

        if reemplazando:
            documento.version += 1

        # Actualizar el documento.
        documento.archivo = archivo
        documento.estado = EstadoDocumento.CARGADO
        documento.fecha_carga = timezone.now()
        documento.notas_alumno = notas

        documento.save()

        # Registrar el movimiento en el historial.
        HistorialDocumento.objects.create(
            documento=documento,
            accion='Documento cargado por el alumno',
            departamento='ALUMNO',
            realizado_por=request.user,
            observaciones=notas
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
