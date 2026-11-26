from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from administracion.models import Usuario

class LoginSerializer(TokenObtainPairSerializer):
    """
    Serializer para el inicio de sesión de la aplicación móvil.

    Utiliza el mismo modelo Usuario que utiliza actualmente
    el sistema web.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Información adicional dentro del JWT
        token['user_id'] = user.id
        token['username'] = user.username
        token['rol'] = user.rol

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        user = self.user

        # Información que React Native necesita después del login
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'nombre': user.get_full_name(),
            'rol': user.rol,
            'numero_control': user.numero_control,
        }

        # Indica si es el primer acceso
        data['requires_password_change'] = user.debe_cambiar_password

        return data



class ChangePasswordSerializer(serializers.Serializer):
    """
    Cambio de contraseña voluntario (usuario autenticado).

    Igual que la web: código OTP enviado al correo + contraseña actual +
    contraseña nueva y su confirmación. Solo valida que los campos vengan;
    las reglas (y sus mensajes) se aplican en ChangePasswordView, en el mismo
    orden que OTPPasswordChangeVerifyView de la web.
    """

    otp = serializers.CharField(
        write_only=True,
        required=True,
        max_length=6
    )

    # trim_whitespace=False: una contraseña puede empezar o terminar con espacio.
    current_password = serializers.CharField(
        write_only=True,
        required=True,
        trim_whitespace=False
    )

    new_password = serializers.CharField(
        write_only=True,
        required=True,
        trim_whitespace=False
    )

    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        trim_whitespace=False
    )


class ForcePasswordChangeSerializer(serializers.Serializer):
    """
    Cambio de contraseña obligatorio (primer inicio de sesión).

    Igual que ForcePasswordChangeView de la web: no pide contraseña actual
    ni OTP, porque el usuario acaba de entrar con la contraseña temporal.
    El correo es opcional.
    """

    new_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False
    )

    confirm_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False
    )

    email = serializers.EmailField(
        required=False,
        allow_blank=True
    )


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class VerifyResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6
    )


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    otp = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6
    )

    new_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8
    )

    confirm_password = serializers.CharField(
        required=True,
        write_only=True
    )

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Las contraseñas nuevas no coinciden.'
            })

        from django.contrib.auth.password_validation import validate_password

        validate_password(attrs['new_password'])

        return attrs

class MeSerializer(serializers.ModelSerializer):
    """
    Serializer para devolver la información del usuario autenticado.
    """

    nombre = serializers.CharField(
        source='get_full_name',
        read_only=True
    )

    class Meta:
        model = Usuario
        fields = [
            'id',
            'username',
            'numero_control',
            'nombre',
            'first_name',
            'last_name',
            'apellido_materno',
            'rol',
            'carrera',
            'telefono',
            'genero',
            'generacion',
            'correo_institucional',
            'email',
            'debe_cambiar_password',
        ]
        read_only_fields = fields