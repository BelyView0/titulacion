from rest_framework import serializers

from administracion.models import Usuario
from alumnos.models import PerfilAlumno, Notificacion
from expediente.models import Expediente


class PerfilAlumnoSerializer(serializers.ModelSerializer):
    """
    Serializer para consultar y actualizar el perfil del alumno.

    Combina información del modelo Usuario y PerfilAlumno.
    """

    # Información académica proveniente de PerfilAlumno
    plan_estudios = serializers.SerializerMethodField()
    semestre_egreso = serializers.SerializerMethodField()
    promedio = serializers.SerializerMethodField()

    # Información calculada
    nombre = serializers.CharField(
        source='get_full_name',
        read_only=True
    )

    # Datos que no puede modificar el alumno
    numero_control = serializers.CharField(
        read_only=True
    )

    carrera = serializers.SerializerMethodField()

    class Meta:
        model = Usuario

        fields = [
            'id',
            'nombre',
            'first_name',
            'last_name',
            'apellido_materno',
            'numero_control',
            'carrera',
            'telefono',
            'genero',
            'generacion',
            'email',
            'email_verificado',
            'correo_institucional',
            'correo_institucional_verificado',
            'foto_perfil',
            'plan_estudios',
            'semestre_egreso',
            'promedio',
        ]

        read_only_fields = [
            'id',
            'nombre',
            'numero_control',
            'carrera',
            'generacion',
            'email_verificado',
            'correo_institucional',
            'correo_institucional_verificado',
            'plan_estudios',
            'semestre_egreso',
            'promedio',
        ]

    def get_carrera(self, obj):
        """
        Obtiene la carrera del usuario.
        """

        if obj.carrera:
            return obj.carrera.nombre

        return None

    def _get_perfil(self, obj):
        """
        Obtiene el PerfilAlumno relacionado con el usuario.
        """

        try:
            return obj.perfil_alumno
        except PerfilAlumno.DoesNotExist:
            return None

    def get_plan_estudios(self, obj):
        perfil = self._get_perfil(obj)

        if perfil and perfil.plan_estudios:
            return str(perfil.plan_estudios)

        return None

    def get_semestre_egreso(self, obj):
        perfil = self._get_perfil(obj)

        if perfil:
            return perfil.semestre_egreso

        return None

    def get_promedio(self, obj):
        perfil = self._get_perfil(obj)

        if perfil:
            return perfil.promedio

        return None

    def update(self, instance, validated_data):
        """
        Actualiza únicamente los datos que el alumno puede modificar.
        """

        old_email = instance.email

        # Correo personal
        if 'email' in validated_data:
            instance.email = validated_data['email']

        # Teléfono
        if 'telefono' in validated_data:
            instance.telefono = validated_data['telefono']


        # Foto de perfil
        if 'foto_perfil' in validated_data:
            instance.foto_perfil = validated_data['foto_perfil']

        # Si cambia el correo personal,
        # debe volver a verificarse.
        if instance.email != old_email:
            instance.email_verificado = False

        instance.save()

        return instance


class NotificacionDashboardSerializer(serializers.ModelSerializer):
    """
    Serializer de las notificaciones que aparecen en el dashboard.
    """

    class Meta:
        model = Notificacion
        fields = [
            'id',
            'tipo',
            'titulo',
            'mensaje',
            'leida',
            'fecha',
            'url_relacionada',
        ]


class DashboardAlumnoSerializer(serializers.Serializer):
    """
    Serializer del dashboard del alumno.
    """

    alumno = PerfilAlumnoSerializer(read_only=True)

    expediente = serializers.SerializerMethodField()

    notificaciones_no_leidas = serializers.IntegerField(
        read_only=True
    )

    notificaciones_recientes = NotificacionDashboardSerializer(
        many=True,
        read_only=True
    )

    def get_expediente(self, usuario):
        """
        Obtiene la información principal del expediente
        perteneciente al alumno autenticado.
        """

        try:
            expediente = usuario.expediente
        except Expediente.DoesNotExist:
            return None

        return {
            'id': expediente.id,
            'estado': expediente.estado,
            'estado_display': expediente.get_estado_display(),
            'modalidad': (
                expediente.modalidad.nombre
                if expediente.modalidad
                else None
            ),
            'titulo_trabajo': expediente.titulo_trabajo,
            'nombre_empresa': expediente.nombre_empresa,
        }