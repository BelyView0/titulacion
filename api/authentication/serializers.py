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
    Serializer para cambiar la contraseña del usuario autenticado.
    """

    current_password = serializers.CharField(
        write_only=True,
        required=True
    )

    new_password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8
    )

    confirm_password = serializers.CharField(
        write_only=True,
        required=True
    )

    def validate(self, attrs):
        user = self.context['request'].user

        # Comprobar contraseña actual
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({
                'current_password': 'La contraseña actual es incorrecta.'
            })

        # Comprobar que las nuevas contraseñas coincidan
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Las contraseñas nuevas no coinciden.'
            })

        # Validar la nueva contraseña con las reglas de Django
        from django.contrib.auth.password_validation import validate_password

        validate_password(
            attrs['new_password'],
            user=user
        )

        return attrs

class ForgotPasswordSerializer(serializers.Serializer):
    """
    Solicita el envío de un código OTP para recuperar la contraseña.
    """

    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)

class VerifyResetOTPSerializer(serializers.Serializer):
    """
    Verifica el código OTP enviado al usuario.
    """

    username = serializers.CharField(required=True)
    otp = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6
    )

class ResetPasswordSerializer(serializers.Serializer):
    """
    Establece una nueva contraseña después de verificar el OTP.
    """

    username = serializers.CharField(required=True)

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

        validate_password(
            attrs['new_password']
        )

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