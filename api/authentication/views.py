import random

from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import LoginSerializer, ChangePasswordSerializer
from administracion.models import Usuario, PasswordResetOTP 

from .serializers import (
    LoginSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    VerifyResetOTPSerializer,
    ResetPasswordSerializer,
    MeSerializer,
)

class LoginView(TokenObtainPairView):
    """
    Endpoint de inicio de sesión para la aplicación móvil.

    Utiliza el mismo usuario y contraseña del sistema actual,
    pero devuelve tokens JWT para React Native.
    """

    serializer_class = LoginSerializer

class MeView(APIView):
    """
    Devuelve la información del usuario autenticado.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MeSerializer(request.user)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )



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

        # Cambiar contraseña
        user.set_password(serializer.validated_data['new_password'])

        # El usuario ya cumplió el cambio obligatorio
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

class ForgotPasswordView(APIView):
    """
    Genera y envía un código OTP para recuperar la contraseña.
    """

    permission_classes = []

    def post(self, request):

        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        email = serializer.validated_data['email']

        try:user = Usuario.objects.get(
        Q(username=username) &
        (
            Q(email__iexact=email) |
            Q(correo_institucional__iexact=email)
        )
    )
            
        except Usuario.DoesNotExist:
            return Response(
                {
                    'message': (
                        'No fue posible procesar la solicitud '
                        'con los datos proporcionados.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Invalidar OTP anteriores
        PasswordResetOTP.objects.filter(
            usuario=user,
            usado=False
        ).update(usado=True)

        # Generar OTP de 6 dígitos
        codigo = f'{random.randint(0, 999999):06d}'

        PasswordResetOTP.objects.create(
            usuario=user,
            codigo=codigo
        )

        # Enviar correo
        send_mail(
            subject='Código de recuperación de contraseña - ITA',
            message=(
                f'Estimado(a) {user.get_full_name()},\n\n'
                f'Su código de recuperación es: {codigo}\n\n'
                'Este código tiene una vigencia limitada.\n\n'
                'Si usted no solicitó este cambio, ignore este mensaje.'
            ),
            from_email=None,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response(
            {
                'message': (
                    'Si los datos proporcionados son correctos, '
                    'se ha enviado un código de recuperación al correo.'
                )
            },
            status=status.HTTP_200_OK
        )

class VerifyResetOTPView(APIView):
    """
    Verifica un código OTP de recuperación.
    """

    permission_classes = []

    def post(self, request):

        serializer = VerifyResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        codigo = serializer.validated_data['otp']

        try:
            user = Usuario.objects.get(username=username)
        except Usuario.DoesNotExist:
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

        # Vigencia del OTP
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
    Establece una nueva contraseña utilizando un OTP válido.
    """

    permission_classes = []

    def post(self, request):

        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        new_password = serializer.validated_data['new_password']

        try:
            user = Usuario.objects.get(username=username)
        except Usuario.DoesNotExist:
            return Response(
                {'message': 'Solicitud inválida.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        codigo = serializer.validated_data['otp']

        if not codigo:
            return Response(
                {'message': 'El código OTP es requerido.'},
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

        if timezone.now() - otp.creado_en > timedelta(minutes=5):
            otp.usado = True
            otp.save(update_fields=['usado'])

            return Response(
                {'message': 'El código OTP ha expirado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cambiar contraseña
        user.set_password(new_password)

        # Ya no necesita cambio obligatorio
        user.debe_cambiar_password = False

        user.save(
            update_fields=[
                'password',
                'debe_cambiar_password'
            ]
        )

        # Marcar OTP como utilizado
        otp.usado = True
        otp.save(update_fields=['usado'])

        return Response(
            {
                'message': 'Contraseña restablecida correctamente.',
                'requires_password_change': False
            },
            status=status.HTTP_200_OK
        )