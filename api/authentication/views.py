import random
from datetime import timedelta

from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    LoginSerializer,
    ChangePasswordSerializer,
    ForcePasswordChangeSerializer,
    ForgotPasswordSerializer,
    VerifyResetOTPSerializer,
    ResetPasswordSerializer,
    MeSerializer,
)

from administracion.emails import (
    correos_registrados,
    enviar_alerta_cambio_password,
    enviar_codigo_otp,
)
from administracion.models import Usuario, PasswordResetOTP
from administracion.views_auth import generate_otp_for_user, is_otp_valid


class LoginView(TokenObtainPairView):
    """
    Endpoint de inicio de sesión para la aplicación móvil.
    """

    serializer_class = LoginSerializer


class LogoutView(APIView):
    """
    Cierra la sesión de la app: invalida (lista negra) el refresh token.

    No exige access token: el propio refresh token es la credencial, así que
    funciona aunque el access ya haya vencido. Siempre responde 200 para que
    la app pueda limpiar su sesión local sin importar el resultado.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh = request.data.get('refresh')

        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except (TokenError, AttributeError):
                # Token inválido/vencido, o app token_blacklist sin instalar.
                pass

        return Response(
            {'message': 'Sesión cerrada.'},
            status=status.HTTP_200_OK
        )


class MeView(APIView):
    """
    Devuelve la información del usuario autenticado.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MeSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


def _error(mensaje, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': mensaje}, status=codigo)


def _exige_cambio_obligatorio(user):
    """
    Mientras debe_cambiar_password sea True la web solo deja entrar a la
    pantalla de cambio obligatorio (middleware); la API hace lo mismo.
    """
    if user.debe_cambiar_password:
        return _error(
            'Primero debes establecer tu nueva contraseña.',
            status.HTTP_403_FORBIDDEN
        )

    return None


class ForcePasswordChangeView(APIView):
    """
    Cambio de contraseña OBLIGATORIO del primer inicio de sesión.

    Equivale a ForcePasswordChangeView de la web: no pide contraseña actual
    ni OTP, rechaza la contraseña temporal, acepta un correo opcional y
    marca el correo institucional como verificado.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if not user.debe_cambiar_password:
            return Response(
                {
                    'detail': 'Tu contraseña ya fue actualizada.',
                    'requires_password_change': False
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ForcePasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        datos = serializer.validated_data
        new_password = datos.get('new_password', '')
        confirm_password = datos.get('confirm_password', '')
        email = datos.get('email', '').strip()

        if not new_password or not confirm_password:
            return _error('Debes llenar todos los campos.')

        if new_password != confirm_password:
            return _error('Las contraseñas no coinciden.')

        if len(new_password) < 8:
            return _error('La contraseña debe tener al menos 8 caracteres.')

        # No permitir que use la misma contraseña temporal.
        if user.check_password(new_password):
            return _error('No puedes usar la misma contraseña. Elige una nueva.')

        campos = [
            'password',
            'debe_cambiar_password',
            'correo_institucional_verificado',
        ]

        if email:
            user.email = email
            campos.append('email')

        user.set_password(new_password)
        user.debe_cambiar_password = False
        user.correo_institucional_verificado = True
        user.save(update_fields=campos)

        return Response(
            {
                'message': 'Contraseña actualizada exitosamente. Bienvenido al sistema.',
                'requires_password_change': False
            },
            status=status.HTTP_200_OK
        )


class RequestPasswordChangeOTPView(APIView):
    """
    Paso 1 del cambio VOLUNTARIO: envía el código OTP de 6 dígitos al
    correo del usuario (equivale a OTPPasswordChangeRequestView de la web).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        bloqueo = _exige_cambio_obligatorio(user)
        if bloqueo:
            return bloqueo

        if not correos_registrados(user):
            return _error('No tienes un correo registrado para recibir el código.')

        otp = generate_otp_for_user(user)
        enviar_codigo_otp(user, otp.codigo, context='change')

        return Response(
            {
                'message': (
                    'Hemos enviado un código de verificación de 6 dígitos '
                    'a tu correo electrónico. Expira en 5 minutos.'
                ),
                'expira_en_minutos': 5
            },
            status=status.HTTP_200_OK
        )


class ChangePasswordView(APIView):
    """
    Paso 2 del cambio VOLUNTARIO: valida OTP + contraseña actual + nueva.

    Equivale a OTPPasswordChangeVerifyView de la web (mismas validaciones,
    en el mismo orden y con los mismos mensajes) y envía la alerta de
    seguridad por correo al terminar.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        bloqueo = _exige_cambio_obligatorio(user)
        if bloqueo:
            return bloqueo

        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        datos = serializer.validated_data

        if not user.check_password(datos['current_password']):
            return _error('Tu contraseña actual es incorrecta.')

        if datos['new_password'] != datos['confirm_password']:
            return _error('Las nuevas contraseñas no coinciden.')

        if len(datos['new_password']) < 8:
            return _error('La nueva contraseña debe tener al menos 8 caracteres.')

        otp_instance = is_otp_valid(user, datos['otp'].strip())

        if not otp_instance:
            return _error(
                'El código es incorrecto o ha expirado (límite de 5 minutos). '
                'Solicita uno nuevo.'
            )

        user.set_password(datos['new_password'])
        user.save(update_fields=['password'])

        otp_instance.usado = True
        otp_instance.save()

        enviar_alerta_cambio_password(user)

        return Response(
            {
                'message': 'Contraseña actualizada correctamente.',
                'requires_password_change': False
            },
            status=status.HTTP_200_OK
        )


def obtener_usuario_por_correo(email):
    """
    Busca un usuario activo mediante su correo personal
    o institucional.
    """

    return Usuario.objects.filter(
        is_active=True
    ).filter(
        Q(email__iexact=email) |
        Q(correo_institucional__iexact=email)
    ).first()


class ForgotPasswordView(APIView):
    """
    Genera y envía un código OTP utilizando solamente el correo.
    """

    permission_classes = []

    def post(self, request):

        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        user = obtener_usuario_por_correo(email)

        # Respuesta genérica para no revelar si existe una cuenta.
        mensaje = (
            'Si el correo está registrado, '
            'se ha enviado un código de recuperación.'
        )

        if not user:
            return Response(
                {'message': mensaje},
                status=status.HTTP_200_OK
            )

        # Determinar cuál de los correos registrados coincide.
        if user.email and user.email.lower() == email.lower():
            destino = user.email
        else:
            destino = user.correo_institucional

        # Invalidar códigos OTP anteriores.
        PasswordResetOTP.objects.filter(
            usuario=user,
            usado=False
        ).update(usado=True)

        # Generar código OTP de seis dígitos.
        codigo = f'{random.randint(0, 999999):06d}'

        PasswordResetOTP.objects.create(
            usuario=user,
            codigo=codigo
        )

        # Enviar código al correo proporcionado.
        send_mail(
            subject='Código de recuperación de contraseña - ITA',
            message=(
                f'Estimado(a) {user.get_full_name()},\n\n'
                f'Su código de recuperación es: {codigo}\n\n'
                'Este código tiene una vigencia de 5 minutos.\n\n'
                'Si usted no solicitó este cambio, ignore este mensaje.'
            ),
            from_email=None,
            recipient_list=[destino],
            fail_silently=False,
        )

        return Response(
            {'message': mensaje},
            status=status.HTTP_200_OK
        )


class VerifyResetOTPView(APIView):
    """
    Verifica el código OTP utilizando el correo electrónico.
    """

    permission_classes = []

    def post(self, request):

        serializer = VerifyResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        codigo = serializer.validated_data['otp']

        user = obtener_usuario_por_correo(email)

        if not user:
            return Response(
                {'message': 'Código inválido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp = (
            PasswordResetOTP.objects
            .filter(
                usuario=user,
                codigo=codigo,
                usado=False
            )
            .order_by('-creado_en')
            .first()
        )

        if not otp:
            return Response(
                {'message': 'Código OTP inválido o ya utilizado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Comprobar vigencia de cinco minutos.
        if timezone.now() - otp.creado_en > timedelta(minutes=5):

            otp.usado = True
            otp.save(update_fields=['usado'])

            return Response(
                {'message': 'El código OTP ha expirado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                'message': 'Código OTP verificado correctamente.',
                'verified': True
            },
            status=status.HTTP_200_OK
        )


class ResetPasswordView(APIView):
    """
    Restablece la contraseña utilizando el correo y el código OTP.
    """

    permission_classes = []

    def post(self, request):

        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        codigo = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        user = obtener_usuario_por_correo(email)

        if not user:
            return Response(
                {'message': 'Solicitud inválida.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp = (
            PasswordResetOTP.objects
            .filter(
                usuario=user,
                codigo=codigo,
                usado=False
            )
            .order_by('-creado_en')
            .first()
        )

        if not otp:
            return Response(
                {'message': 'Código OTP inválido o ya utilizado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Comprobar vigencia del código.
        if timezone.now() - otp.creado_en > timedelta(minutes=5):

            otp.usado = True
            otp.save(update_fields=['usado'])

            return Response(
                {'message': 'El código OTP ha expirado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Establecer la nueva contraseña.
        user.set_password(new_password)
        user.debe_cambiar_password = False

        user.save(
            update_fields=[
                'password',
                'debe_cambiar_password'
            ]
        )

        # Marcar el código como utilizado.
        otp.usado = True
        otp.save(update_fields=['usado'])

        return Response(
            {
                'message': 'Contraseña restablecida correctamente.',
                'requires_password_change': False
            },
            status=status.HTTP_200_OK
        )