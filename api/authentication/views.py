import random
from datetime import timedelta

from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    LoginSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    VerifyResetOTPSerializer,
    ResetPasswordSerializer,
    MeSerializer,
)

from administracion.models import Usuario, PasswordResetOTP


class LoginView(TokenObtainPairView):
    """
    Endpoint de inicio de sesión para la aplicación móvil.
    """

    serializer_class = LoginSerializer


class MeView(APIView):
    """
    Devuelve la información del usuario autenticado.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MeSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """
    Endpoint para cambiar la contraseña del usuario autenticado.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        user = request.user

        user.set_password(serializer.validated_data['new_password'])
        user.debe_cambiar_password = False

        user.save(
            update_fields=[
                'password',
                'debe_cambiar_password'
            ]
        )

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